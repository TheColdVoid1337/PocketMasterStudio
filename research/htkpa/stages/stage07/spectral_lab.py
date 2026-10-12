#!/usr/bin/env python3
"""Stage 7: minimal, read-only-by-default NAM-output-to-Post-FIR research CLI.

This is not a Sonicake HTKPA clone. This uses *only* a baseline CLO's upstream
parameters and an independently rendered NAM WaveNet output. No vendor CLO/WAV
or commercial DLL is required to FIT the 512-tap Post-FIR. The result has not
passed a generalization or on-device acceptance gate and MUST stay experimental.

Dependencies: numpy, scipy. Stereo WAV input: 16-bit 44.1/48kHz identical L/R.
Sparse NPZ: 'audio' float32/64 70s@44100, 'valid' boolean mask, holding 2s
windows at TRAIN and HOLDOUT positions (NAM WaveNet predicted). Optional:
--write-experimental-clo explicitly creates a separate candidate with CRC16.
"""
from __future__ import annotations
import argparse, json, hashlib, struct
from pathlib import Path
import numpy as np
from scipy import signal, fft

FS=44100; NFFT=4800; N_TAPS=512
TRAIN=[(5,7),(18,20),(30,32),(43,45),(58,60)]
HOLDOUT=[(13,15),(26,28),(39,41),(53,55),(65,67)]

def crc16(buf):
    crc=0xffff
    for t in buf:
        crc ^= t
        for _ in range(8):crc=(crc>>1)^(0xa001 if crc&1 else 0)
    return crc & 0xffff

def read_clo(path):
    raw=bytearray(path.read_bytes())
    if len(raw)!=8840 or raw[:4]!=b'VTSI' or struct.unpack_from('<I',raw,4)[0]!=8840:
        raise ValueError('Bad CLO header/size')
    if struct.unpack_from('>H',raw,8)[0]!=crc16(raw[12:]): raise ValueError('Bad CLO CRC')
    if struct.unpack_from('<I',raw,132)[0]!=2048:raise ValueError('Unexpected Post-FIR length')
    g=np.frombuffer(raw,dtype='<f4',offset=104,count=4).astype('f8')
    a=np.frombuffer(raw,dtype='<f4',offset=136,count=128).astype('f8')
    b=np.frombuffer(raw,dtype='<f4',offset=648,count=N_TAPS).astype('f8')
    dc=np.frombuffer(raw,dtype='<f8',offset=64,count=5).astype('f8')
    return raw,g,a,b,dc

def read_wav(path):
    from scipy.io import wavfile
    sr,s=wavfile.read(path)
    if sr not in (FS,48000) or s.dtype!=np.int16 or s.ndim!=2 or s.shape[1]!=2:
        raise ValueError('Require PCM16 stereo WAV 44100/48000 Hz')
    if not np.array_equal(s[:,0],s[:,1]):raise ValueError('Stereo reference must duplicate one mono channel')
    x=s[:,0].astype('f8')/32768
    return signal.resample_poly(x,147,160) if sr==48000 else x

def pre_nonlinear_and_dc(x,g,a,dc):
    v=signal.lfilter(a,[1.],x)
    z=np.empty_like(v); k=v>=0
    z[k]=-g[0]*np.expm1(-np.minimum(v[k]*g[2],60.))
    z[~k]=g[1]*np.expm1(-np.minimum(-v[~k]*g[3],60.))
    return signal.lfilter(dc[:3],[1.,dc[3],dc[4]],z)

def spectral_cross(q,y,nperseg=NFFT):
    if q.shape!=y.shape:raise ValueError('Input and predicted NAM WAV shapes differ')
    cross=[];auto=[]
    for lo,hi in TRAIN:
        u,v=int(lo*FS),int(hi*FS)
        freqs,pp=signal.welch(q[u:v],FS,nperseg=nperseg,noverlap=nperseg//2,window='hann',scaling='spectrum')
        _,cc=signal.csd(q[u:v],y[u:v],FS,nperseg=nperseg,noverlap=nperseg//2,window='hann',scaling='spectrum')
        auto.append(pp);cross.append(cc)
    pqq=np.mean(auto,axis=0); pqy=np.mean(cross,axis=0)
    mag=np.maximum(np.abs(pqy)/(pqq+np.max(pqq)*1e-6),1e-10)
    return freqs,mag

def minimum_phase_from_spectrum(freqs,mag,count=N_TAPS,nfft=32768):
    if nfft <= count*2 or nfft%2:raise ValueError('invalid FFT size')
    freq_new=np.linspace(0,FS/2,nfft//2+1)
    log_m=np.interp(freq_new,freqs,np.log(np.maximum(mag,1e-10)))
    cepstrum=fft.irfft(log_m,nfft)
    causal=np.zeros(nfft)
    causal[0]=cepstrum[0];causal[1:nfft//2]=2*cepstrum[1:nfft//2];causal[nfft//2]=cepstrum[nfft//2]
    return fft.irfft(np.exp(fft.rfft(causal)),nfft)[:count]

def fit(q,y):
    f,mag=spectral_cross(q,y)
    return minimum_phase_from_spectrum(f,mag)

def lag_train(a,b):
    s,e=int(30*FS),int(32*FS)
    corr=signal.correlate(a[s:e],b[s:e],'full',method='fft')
    lags=signal.correlation_lags(e-s,e-s,'full')
    mask=abs(lags)<=256
    return int(lags[mask][np.argmax(abs(corr[mask]))])

def metrics(pred,target,windows,lag):
    a=[];b=[]
    for lo,hi in windows:
        s,e=int(lo*FS),int(hi*FS)
        a.append(pred[s+max(lag,0):e+min(lag,0)])
        b.append(target[s+max(-lag,0):e+min(-lag,0)])
    aa=np.concatenate(a);bb=np.concatenate(b)
    k=float(np.dot(aa,bb)/max(np.dot(aa,aa),1e-30))
    cor=float(np.corrcoef(aa,bb)[0,1]);err=float(np.linalg.norm(k*aa-bb)/max(np.linalg.norm(bb),1e-30))
    return {'abs_correlation':abs(cor),'signed_correlation':cor,'nrmse_after_signed_gain':err}

def save_candidate(baseline,h,out):
    raw=bytearray(baseline);raw[648:648+N_TAPS*4]=np.asarray(h,dtype='<f4').tobytes()
    struct.pack_into('>H',raw,8,crc16(raw[12:]))
    out.write_bytes(raw)
    assert read_clo(out)[0] == raw

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--reference-wav',type=Path,required=True)
    ap.add_argument('--independent-nam-output-npz',type=Path,required=True)
    ap.add_argument('--baseline-clo',type=Path,required=True)
    ap.add_argument('--out-dir',type=Path,required=True)
    ap.add_argument('--write-experimental-clo',action='store_true')
    opts=ap.parse_args()
    x=read_wav(opts.reference_wav)
    s=np.load(opts.independent_nam_output_npz)
    target=np.asarray(s['audio'],dtype=np.float64)
    valid=np.asarray(s['valid'],dtype=bool)
    if x.shape!=target.shape or target.shape!=valid.shape:
        raise ValueError('DI and NAM WaveNet target must have same 70s timeline')
    for lo,hi in TRAIN+HOLDOUT:
        if not valid[int(lo*FS):int(hi*FS)].all():raise ValueError('Missing valid WaveNet region '+str((lo,hi)))
    raw,g,pre,baseline,dc=read_clo(opts.baseline_clo)
    q=pre_nonlinear_and_dc(x,g,pre,dc)
    fitted=fit(q,target)
    pred0=signal.lfilter(baseline,[1.],q)
    pred1=signal.lfilter(fitted,[1.],q)
    # Spectral magnitude has a sign ambiguity. Fix global polarity using TRAIN
    # only (a constant sign is *not* a vendor-derived amplitude/phase profile).
    initial_lag=lag_train(pred1,target)
    initial_sign=metrics(pred1,target,TRAIN,initial_lag)['signed_correlation']
    sign_flipped = bool(initial_sign < 0)
    if sign_flipped:
        fitted=-fitted;pred1=-pred1
    # RMS match for A/B if explicitly writing a file; not part of spectral fitting.
    rms=lambda w:np.sqrt(np.mean(np.concatenate([w[int(lo*FS):int(hi*FS)] for lo,hi in TRAIN])**2))
    scale=float(rms(pred0)/max(rms(pred1),1e-30))
    fitted *= scale;pred1*=scale
    l0=lag_train(pred0,target);l1=lag_train(pred1,target)
    report={'stage':7,'model':'NAM-only independent WaveNet windows, baseline Pre-FIR + saturator',
            'not_vendor_algorithm':True,'nperseg':NFFT,'spectral_method':'cross spectral magnitude; minimum-phase; no Gaussian',
            'train_windows':TRAIN,'heldout_windows':HOLDOUT,
            'baseline_sha256':hashlib.sha256(opts.baseline_clo.read_bytes()).hexdigest(),
            'target_sha256':hashlib.sha256(opts.independent_nam_output_npz.read_bytes()).hexdigest(),
            'rms_gain_match_to_baseline':scale,'train_only_polarity_flip':sign_flipped,
            'before':{'training_lag':l0,'train':metrics(pred0,target,TRAIN,l0),'holdout':metrics(pred0,target,HOLDOUT,l0)},
            'after':{'training_lag':l1,'train':metrics(pred1,target,TRAIN,l1),'holdout':metrics(pred1,target,HOLDOUT,l1)},
            'experimental_file_written':False,'not_accepted_for_production':True}
    opts.out_dir.mkdir(parents=True,exist_ok=True)
    if opts.write_experimental_clo:
        out=opts.out_dir/'UNVALIDATED_Stage7_Spectral_MinPhase.clo';save_candidate(raw,fitted,out)
        report['experimental_file_written']=str(out)
    (opts.out_dir/'fitting_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'before':report['before']['holdout'],'after':report['after']['holdout'],'experimental_file_written':report['experimental_file_written']},indent=2))
if __name__=='__main__':main()

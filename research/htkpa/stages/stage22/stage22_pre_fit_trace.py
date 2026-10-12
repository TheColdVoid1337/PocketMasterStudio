#!/usr/bin/env python3
"""Read-only DLL-first pre-saturator caller analysis, NOT a NAM-to-CLO fitter.

This tests precise pointer roles and calls for native 0x1800BE830. The optional
WAV audit is an approximate diagnostics-only implementation (not native SSE
parity and not suitable for extracting vendor gains). The commercial DLL is
only read by objdump and PE parsing, never executed.
"""
from __future__ import annotations
import argparse, hashlib, io, json, math, re, struct, subprocess, zipfile
from pathlib import Path
import numpy as np

DLL_HASH='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
PINS={
# context-owned 70s-plus-600 (padded) source/reference buffers
0x1800B5676:'0x18024cda4',0x1800B567E:'0x18024ccb0',
0x1800B56B5:'[rbx+0x243e0]',0x1800B56F2:'[rbx+0x243e8]',
# reference-only mean removal and affine trend removal before saturator fitting
0x1800BE8E7:'[r14+0x243e8]',0x1800BE8F0:'addss',
0x1800BE90F:'divss  xmm2,xmm1',
0x1800BE927:'[rcx+rax*1]',0x1800BE930:'[rcx+rax*1]',
0x1800BE980:'[r14+0x243e8]',
0x1800BE9CF:'mulss  xmm5,xmm9',0x1800BE9DB:'subss  xmm5,xmm0',
0x1800BE9F2:'divss  xmm5,xmm1',0x1800BEA01:'divss  xmm3,xmm2',
0x1800BEA23:'mulss  xmm1,xmm5',0x1800BEA27:'addss  xmm1,xmm3',
0x1800BEA30:'subss  xmm0,xmm1',0x1800BEA34:'movss',
# alignment is searched in output around six seconds, 600-sample max
0x1800BEA59:'cvttss2si edi,xmm6',0x1800BEA5D:'lea    r10d,[rdi+rdi*2]',
0x1800BEA61:'add    r10d,r10d',0x1800BEA64:'0x258',
0x1800BEA79:'[r14+0x243e8]',0x1800BEAA0:'movss',
0x1800BEAB2:'comisd xmm1,xmm3',0x1800BEAD3:'sub    ecx,r10d',
# input pointer and target pointer are distinct; target includes offset
0x1800BEADA:'0x18024ccd0',0x1800BEAE7:'0x18024cd34',
0x1800BEAF0:'0x18024cd40',0x1800BEAF8:'[r14+0x243e0]',
0x1800BEAFF:'[r14+0x243e8]',0x1800BEB14:'[rsp+0x80]',
0x1800BEB1F:'lea    r13,[r8+rax*4]',
0x1800BEB2B:'0x17',0x1800BEB4D:'0x1e',0x1800BEB6F:'0x32',
# only 23..28 seconds sent to fitter, initial 5s count from xmm8
0x1800BEDBF:'cvttss2si esi,xmm8',0x1800BEDD8:'mov    r9d,esi',
0x1800BEDDB:'mov    r8,rbp',0x1800BEDDE:'mov    rdx,r15',
0x1800BEDE4:'call   0x1800bdbe0',
# IIR helper is called AFTER saturation fitting
0x1800BEE19:'mov    r9d,edi',0x1800BEE25:'call   0x1800bd490',
}
CONST={0x18024cd6c:('f',70.),0x18024cda4:('f',600.),
       0x18024ccb0:('f',4.),0x18024ccd0:('f',5.),
       0x18024cd34:('f',15.),0x18024cd40:('f',20.),
       0x18024c6c8:('d',.01)}

def pe_read(data,addr,n):
    pos=struct.unpack_from('<I',data,0x3c)[0]
    assert data[:2]==b'MZ' and data[pos:pos+4]==b'PE\x00\x00'
    sections=struct.unpack_from('<H',data,pos+6)[0];optsize=struct.unpack_from('<H',data,pos+20)[0]
    for i in range(sections):
        header=pos+24+optsize+i*40
        vs,rva,raw,ro=struct.unpack_from('<IIII',data,header+8)
        off=addr-0x180000000-rva
        if 0<=off and off+n<=raw:return data[ro+off:ro+off+n]
    raise ValueError('unknown PE VA '+hex(addr))

def verify(dll):
    dll=Path(dll);data=dll.read_bytes()
    assert hashlib.sha256(data).hexdigest()==DLL_HASH,'DLL mismatch'
    ranges=[(0x1800B5640,0x1800B570C),(0x1800BE830,0x1800BEF00)]
    asm={}
    for start,stop in ranges:
        out=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',f'--start-address={start:#x}',f'--stop-address={stop:#x}',str(dll)],text=True)
        asm.update({int(m.group(1),16):m.group(2).strip() for line in out.splitlines() if (m:=re.match(r'\s*([0-9a-f]+):\s*(.*)',line))})
    for addr,needle in PINS.items():
        ins=asm.get(addr,'')
        assert needle in ins,f'{addr:#x} expected {needle!r} got {ins!r}'
    constants={}
    for a,(typ,expected) in CONST.items():
        value=struct.unpack('<'+typ,pe_read(data,a,4 if typ=='f' else 8))[0]
        assert abs(value-expected)<1e-7,(a,value)
        constants[hex(a)]=value
    return constants

def native_window_pointers(fs,shift):
    # Native branches use sample offsets constructed from integer sample_rate.
    # This models address arithmetic, not sample-rate conversion.
    fs=int(fs);s=int(shift)
    assert fs>0 and 0<=s<=600
    return dict(input_data_start=0, reference_data_start=s,
      fit_input_start=23*fs,fit_reference_start=23*fs+s,
      fit_samples=int(np.float32(np.float32(fs)*np.float32(5))),
      output_alignment_search_start=6*fs,
      output_alignment_search_end_exclusive=6*fs+600,
      trailing_buffer_padding=600,required_float_capacity=int(fs*70+600))

def detrend_reference_diagnostic(reference):
    """Double-precision vectorized diagnostic of native two passes.

    Does not claim bitwise native parity; native float32 sums may be sequential.
    Input must already represent the context's Fs-domain reference buffer.
    """
    reference=np.asarray(reference,dtype=np.float32)
    assert reference.ndim==1 and np.isfinite(reference).all()
    n=reference.size
    x=reference.astype(np.float64)
    # DLL accumulates mean in float32 then uses float32 updates; double OLS
    # here is deliberately labeled DIAGNOSTIC.
    mean=x.mean();y=x-mean
    q=np.arange(1,n+1,dtype=np.float64)
    cov=(q-q.mean()) @ y
    slope=cov/np.sum((q-q.mean())**2)
    intercept=(y.sum()-slope*q.sum())/n
    return (y-slope*q-intercept).astype(np.float32),dict(mean=float(mean),slope=float(slope),intercept=float(intercept))

def detect_alignment(signal,fs,threshold=.01):
    assert fs>0 and len(signal)>=6*fs+600
    probe=np.asarray(signal,dtype=np.float32)[6*fs:6*fs+600]
    candidates=np.flatnonzero(np.abs(probe)>threshold)
    return int(candidates[0]) if len(candidates) else 600

def tests():
    out=[]
    def chk(label,condition):
        assert condition,label;out.append(label)
    for fs in (44100,48000,96000):
        for shift in (0,19,599,600):
            p=native_window_pointers(fs,shift)
            chk(f'window fs={fs} shift={shift}',p['fit_reference_start']-p['fit_input_start']==shift)
            chk(f'5s fs={fs} shift={shift}',p['fit_samples']==5*fs)
            chk(f'70s and padding fs={fs} shift={shift}',p['required_float_capacity']==70*fs+600)
            chk(f'nonoverlapping other 30s fs={fs} shift={shift}',p['fit_input_start']+p['fit_samples']<=30*fs)
    # Known exact output-array construction for onset search; first above-threshold hit
    fake=np.zeros(6*100+610,dtype=np.float32)
    fake[6*100+31]=-.011
    chk('onset negative first hit',detect_alignment(fake,100)==31)
    fake[6*100+13]=.02
    chk('onset picks earlier hit',detect_alignment(fake,100)==13)
    fake[:]=0
    chk('no-hit sentinel',detect_alignment(fake,100)==600)
    q=np.arange(2000,dtype=np.float32)
    trend=np.float32(.2)+np.float32(.00001)*q
    centered,m=detrend_reference_diagnostic(trend)
    chk('detrending affine synthetic max residual',np.max(np.abs(centered))<5e-6)
    chk('detrending returned finite regression',all(np.isfinite(v) for v in m.values()))
    return out

def actual_wav_audit(root):
    # Uses Sonicake captures strictly as *independent read-only references*.
    import soundfile as sf
    ret={}
    for model,fn in (('JCM800_2203','Sonicake Manager Files.zip'),('SC20','Sonicake Manager(1).zip')):
        with zipfile.ZipFile(Path(root)/fn) as z:
            inp=z.read('wavs/nam_input_wav.wav');out=z.read('wavs/outputFile.wav')
            x,xi=sf.read(io.BytesIO(inp),dtype='float32');y,yi=sf.read(io.BytesIO(out),dtype='float32')
            assert xi==44100 and yi==48000 and len(x)==70*xi and len(y)==70*yi
            assert np.array_equal(x[:,0],x[:,1]) and np.array_equal(y[:,0],y[:,1])
            # Native audio loader's Fs-domain f32 PCM decode may differ, so
            # only the output-WAV diagnostic is computed; no cross-WAV fit.
            aligned,stat=detrend_reference_diagnostic(np.pad(y[:,0],(0,600)))
            shift=detect_alignment(aligned,yi)
            ret[model]={'sha256_di':hashlib.sha256(inp).hexdigest(),
                        'native_fs_and_resampling':'NOT_PROVEN_FROM_WAV',
                        'reference_wav_rate':yi,'di_wav_rate':xi,
                        'diagnostic_output_48k_alignment_samples':shift,
                        'diagnostic_ols':stat,
                        'fitter_input_waveform':'NOT_COMPUTED',
                        'native_4_gains':'NOT_COMPUTED'}
    assert ret['JCM800_2203']['sha256_di']==ret['SC20']['sha256_di']
    return ret

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--dll',required=True);ap.add_argument('--root');ap.add_argument('--out');args=ap.parse_args()
    constant=verify(args.dll);test=tests()
    result={'stage':22,'status':'STATIC_PRE_FIT_MAPPING','dll_sha256':DLL_HASH,
      'pinned_instructions':len(PINS),'pinned_constants':constant,
      'synthetic_assertions':len(test),'assertions':test,
      'real_wav_gain_parity':'NOT_TESTED_NO_VERIFIED_INPUT_SAMPLE_RATE_CONVERSION',
      'stage21_fitter_scope':'FULL_SYNTHETIC_ORDINARY_DOMAIN'}
    if args.root:result['read_only_wav_diagnostics']=actual_wav_audit(args.root)
    s=json.dumps(result,sort_keys=True,indent=2)+'\n'
    if args.out:Path(args.out).write_text(s)
    print(f'Stage22: verified {len(PINS)} static address pins, {len(CONST)} PE constants and {len(test)} assertions; vendor gains NOT_COMPUTED')
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Correct-direction 44.1->48k diagnostic, deliberately NOT native parity.

Requires numpy, scipy, soundfile and archived Stage21 source beside stage23d.
Official CLO is read only AFTER calculating each independent candidate; never
used to initialize/adjust/rescale any input to the fit.
"""
from __future__ import annotations
import argparse,json,sys,os
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
sys.path.insert(0,os.environ.get('HTKPA_STAGE21_DIR',str(Path(__file__).resolve().parents[1]/'stage21')))
from stage21_saturator_source import fit_preprocessed_waveforms,read_vendor_gains

def detrend_DIAGNOSTIC(y):
    # This is NOT the native SSE f32 sequential sum nor the on-disk WAV decoder.
    y=np.asarray(y,dtype=np.float64)
    n=y.size;i=np.arange(n,dtype=np.float64)
    d=y-y.mean()
    slope=np.dot(i-(n-1)/2,d)/(n*(n*n-1)/12)
    return (d-slope*(i-(n-1)/2)).astype(np.float32)

def process(directory,model):
    directory=Path(directory)
    x,xf=sf.read(directory/'nam_input_wav.wav',dtype='float32',always_2d=True)
    y,yf=sf.read(directory/'outputFile.wav',dtype='float32',always_2d=True)
    assert xf==44100 and yf==48000
    assert x.shape==(xf*70,2) and y.shape==(yf*70,2)
    assert np.array_equal(x[:,0],x[:,1]) and np.array_equal(y[:,0],y[:,1])
    source=resample_poly(x[:,0],160,147).astype(np.float32)
    target=detrend_DIAGNOSTIC(y[:,0]);fs=48000
    onset=np.flatnonzero(np.abs(target[6*fs:6*fs+600])>0.01)
    shift=int(onset[0]) if len(onset) else 600
    lo,hi=23*fs,28*fs
    fitted=fit_preprocessed_waveforms(source[lo:hi],target[lo+shift:hi+shift],fs)
    independently_derived=fitted['native_four_parameters']
    # Only now read official oracle. No inference or tuning with oracle.
    official=read_vendor_gains(directory/'cloFile.clo')
    names=('pmax','nmax','prate','nrate')
    return {'model':model,'status':'NON_NATIVE_PARITY_NEGATIVE_CONTROL',
            'source_wav_fs':xf,'target_wav_fs':yf,'assumed_native_fs_FROM_NAM':fs,
            'source_resampling':'GENERIC scipy.signal.resample_poly 160/147, NOT original 0x18000CE00',
            'target_detrend':'GENERIC float64 OLS, NOT original f32 accumulation',
            'target_onset_samples':shift,'fit_window_seconds':[23,28],
            'independent_diagnostic_gains_NOT_VENDOR':dict(zip(names,independently_derived)),
            'official_CLO_gains_READ_ONLY':official,
            'note':'Official gains are held out until AFTER candidate calculation. Large mismatch does not validate a converter.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--2203',type=Path,required=True);p.add_argument('--sc20',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    rows=[process(a.__dict__['2203'],'2203'),process(a.sc20,'SC20')]
    a.out.write_text(json.dumps(rows,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf8')
    for d in rows:print(d['model'],d['target_onset_samples'],d['independent_diagnostic_gains_NOT_VENDOR'])
    print('STRICT GATE: NATIVE FOUR GAINS = NOT_COMPUTED')
if __name__=='__main__':main()

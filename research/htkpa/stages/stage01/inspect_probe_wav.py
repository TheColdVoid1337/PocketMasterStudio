#!/usr/bin/env python3
"""Read-only probe WAV segmentation; never opens a DLL or connects to pedal."""
import argparse
import json
import wave
import numpy as np
from pathlib import Path
from scipy.signal import resample_poly

REGIONS = [(0, 5, 'warm-up'), (6, 21, 'quiet'), (23, 28, 'loud'), (30, 50, 'sweep'), (50, 70, 'dynamic')]

def wav(path):
    with wave.open(str(path), 'rb') as w:
        if w.getsampwidth() != 2 or w.getnchannels() != 2:
            raise ValueError(f'Expected 16-bit stereo PCM: {path}')
        fs = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').reshape(-1,2)
        if not np.array_equal(x[:,0],x[:,1]):
            raise ValueError(f'Expected identical L/R channels: {path}')
        return x[:,0].astype(np.float64)/32768., fs

def db(arr):
    return float(20*np.log10(max(np.sqrt(np.mean(arr*arr)),1e-15)))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('input',type=Path)
    ap.add_argument('output',type=Path)
    ap.add_argument('--directory',type=Path,default=Path('.'))
    args=ap.parse_args()
    xi,fi=wav(args.input);xo,fo=wav(args.output)
    if len(xi)/fi!=70 or len(xo)/fo!=70:raise ValueError('This fixture is not 70s')
    if fi!=44100 or fo!=48000:raise ValueError('This fixture expects 44100→48000')
    data=[]
    for a,b,name in REGIONS:
        yin=xi[int(a*fi):int(b*fi)];yout=xo[int(a*fo):int(b*fo)]
        data.append({'region':name,'start_s':a,'end_s':b,'input_rms_dbfs':round(db(yin),3),'output_rms_dbfs':round(db(yout),3)})
    # Approximate the official 44.1-kHz resampled output; not guaranteed the same resampler kernel.
    y44=resample_poly(xo,147,160)
    window=y44[6*44100:6*44100+600]
    indices=np.flatnonzero(abs(window)>0.01)
    result={'regions':data,'output_onset_after_6s_samples_at_44100':int(indices[0]) if len(indices) else None,
            'input_fs':fi,'output_fs':fo,'all_channels_identical':True,
            'note':'600-sample threshold and time offsets from static DLL code; resampling approximation from scipy'}
    args.directory.mkdir(parents=True,exist_ok=True)
    (args.directory/'probe_wav_regions.json').write_text(json.dumps(result,indent=2)+'\n')
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    def secs(x,fs):return np.array([db(x[i*fs:(i+1)*fs]) for i in range(70)])
    fig,ax=plt.subplots(figsize=(12.8,4.6))
    ax.plot(np.arange(70)+0.5,secs(xi,fi),label='Reference DI (44.1 kHz)')
    ax.plot(np.arange(70)+0.5,secs(xo,fo),label='Vendor output (48 kHz)')
    for boundary in [5,6,21,23,28,30,50]:ax.axvline(boundary,alpha=0.24,ls='--')
    for a,b,name in REGIONS:
        ax.text((a+b)/2,-9,name,ha='center',fontsize=9,rotation=0)
    ax.set_xlim(0,70);ax.set_ylim(-110,5)
    ax.set_xlabel('Time (s)');ax.set_ylabel('RMS per 1-second block (dBFS)')
    ax.set_title('Sonicake 70-second probe: fixed regions in HTKPA call path')
    ax.grid(alpha=.15);ax.legend(loc='lower right')
    fig.tight_layout();fig.savefig(args.directory/'probe_regions.png',dpi=155)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()

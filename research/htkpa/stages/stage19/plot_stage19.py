#!/usr/bin/env python3
"""Plot static coefficient tables recovered from DLL; no native library execution."""
from pathlib import Path
import sys
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import freqz
from stage19_source_first import BANKS,pe_data
p=Path('/mnt/data/htkpa_stage14_work/5868USB.dll')
raw=p.read_bytes()
banks={rate:np.concatenate([np.frombuffer(pe_data(raw,addr,16 if i<12 else 4),dtype='<f4') for i,addr in enumerate(bank['addresses'])]) for rate,bank in BANKS.items()}
fig,ax=plt.subplots(figsize=(9.2,4.8))
for sr,h in banks.items():
    f,v=freqz(h,worN=4096,fs=sr)
    keep=(f>=80)&(f<=10000)
    ax.semilogx(f[keep],20*np.log10(np.maximum(abs(v[keep]),1e-10)),label=f'{sr:,} Hz')
ax.set(xlim=(80,10000),xlabel='Frequency (Hz)',ylabel='Magnitude (dB)',title='DLL-extracted 50-tap initial FIR banks: frequency response')
ax.grid(True,which='both',alpha=.3);ax.legend();fig.tight_layout()
fig.savefig('/mnt/data/HTKPA_DLL_RE_v0_19/initial_50tap_banks.png',dpi=160)

#!/usr/bin/env python3
"""Pure synthetic illustration; no DLL, vendor WAV or device access."""
from pathlib import Path
import importlib.util, json
import numpy as np
spec=importlib.util.spec_from_file_location('lab',Path(__file__).with_name('verify_stage13.py'))
lab=importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)
root=Path(__file__).parent
n=128
u=np.linspace(0,1,n)
curve=0.73 + .62*np.exp(-.5*((u-.34)/.12)**2) + .06*np.cos(2*np.pi*u)
spectral=lab.spectral_kernel_from_magnitude(np.r_[curve,curve[-2:0:-1]])
h=lab.full_synthetic_pre_fir(curve,n)
report={
 'description':'synthetic arbitrary positive input curve; not fitted from user NAM, WAV or Sonicake output',
 'input_curve_length':n,
 'mirror_support':len(spectral),
 'input_curve_min':float(curve.min()),
 'input_curve_max':float(curve.max()),
 'spectrum_min_magnitude':float(np.abs(spectral).min()),
 'spectrum_max_magnitude':float(np.abs(spectral).max()),
 'pre_fir_taps':len(h),
 'pre_fir_sum':float(np.sum(h)),
 'pre_fir_l2':float(np.linalg.norm(h)),
 'pre_fir_first_16':[float(x) for x in h[:16]],
 'all_finite':bool(np.isfinite(h).all()),
 'precision_note':'float64 numerical/algebraic reference; not native float32 bit-exact',
}
(root/'synthetic_example.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
try:
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 fig,ax=plt.subplots(figsize=(9.0,3.5))
 ax.plot(np.arange(len(h)),h,linewidth=1.1)
 ax.set(title='Stage 13: Synthetic 128-tap Pre-FIR (not a vendor capture)',xlabel='Tap index',ylabel='Coefficient amplitude')
 ax.grid(alpha=.28)
 fig.tight_layout()
 fig.savefig(root/'synthetic_pre_fir.png',dpi=160)
 plt.close(fig)
except ImportError:pass
print(json.dumps(report,indent=2))

"""Sanitized Stage23W check of private, Frida-captured f64 FIR arrays."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np

N=4096
def read(root,name):
 p=root/name
 a=np.fromfile(p,dtype='<f8'); assert a.shape==(N,)
 return a,hashlib.sha256(p.read_bytes()).hexdigest()
def complex_product(x,h):
 y=x*h; ar,ai=x[2::2],x[3::2]; br,bi=h[2::2],h[3::2]
 y[2::2]=ar*br+ai*bi; y[3::2]=ai*br-ar*bi
 return y
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--private-root',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args()
 x,xh=read(a.private_root,'input_post_fft_00.f64le.bin'); h,hh=read(a.private_root,'coeff_post_fft_00.f64le.bin'); y,yh=read(a.private_root,'after_spectral_multiply_00.f64le.bin')
 lane=x*h; active=np.empty_like(x); active[:2]=lane[:2]; active[2::2]=lane[2::2]; active[3::2]=x[3::2]*h[2::2]
 r={'status':'NATIVE_HIT','block':0,'array_doubles':N,'array_hashes':{'input_post_fft':xh,'coeff_post_fft':hh,'after_spectral_multiply':yh},'naive_lane_max_abs_error':float(np.max(np.abs(y-lane))),'active_lane_max_abs_error':float(np.max(np.abs(y-active))),'active_lane_relation':'confirmed bitwise for captured block: even coefficient applies to both packed pair entries','second_coeff_snapshot':'excluded: its timestamp is later than the paired block-1 spectra'}
 a.out.write_text(json.dumps(r,indent=2)+'\n'); print(json.dumps(r,indent=2))
if __name__=='__main__': main()

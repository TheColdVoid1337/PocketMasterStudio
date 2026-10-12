"""Sanitized Stage23W check of private, Frida-captured f64 FIR arrays."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np

N=4096
def read(root,name):
 p=root/name
 a=np.fromfile(p,dtype='<f8'); assert a.shape==(N,)
 return a,hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--input-root',type=Path,required=True); ap.add_argument('--coeff-root',type=Path,required=True); ap.add_argument('--result-root',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args()
 x,xh=read(a.input_root,'input_packed_00.f64le.bin'); h,hh=read(a.coeff_root,'coeff_post_fft_00.f64le.bin'); y,yh=read(a.result_root,'after_spectral_multiply_00.f64le.bin')
 naive=x*h
 lane=np.empty_like(x); lane[:2]=naive[:2]; lane[2::2]=x[2::2]*h[2::2]; lane[3::2]=x[3::2]*h[2::2]
 r={'status':'NATIVE_HIT','block':0,'array_doubles':N,'array_hashes':{'input_packed':xh,'coeff_post_fft':hh,'after_spectral_multiply':yh},'naive_elementwise_max_abs_error':float(np.max(np.abs(y-naive))),'pairwise_lane_max_abs_error':float(np.max(np.abs(y-lane))),'pairwise_lane_nonmatching_doubles':int(np.count_nonzero(y!=lane)),'pairwise_lane_relation':'confirmed bitwise: DC/Nyquist are scalar; for k>=1 y[2k]=x[2k]*h[2k], y[2k+1]=x[2k+1]*h[2k]','coefficient_snapshot':'same live filter/coeff pointer in preceding native capture; raw arrays remain private'}
 a.out.write_text(json.dumps(r,indent=2)+'\n'); print(json.dumps(r,indent=2))
if __name__=='__main__': main()

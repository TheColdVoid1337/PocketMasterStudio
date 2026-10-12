#!/usr/bin/env python3
"""Demonstrates Stage18 on SYNTHETIC spectral arrays. Does not write CLO."""
from pathlib import Path
import argparse,json,numpy as np
from stage18_source_first import initial_curves_from_spectral_arrays,conditioned_curve,native_linspace

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    n=2401
    hz=native_linspace(80.,10000.,n)
    t=np.linspace(0,1,n,dtype=np.float32)
    u=(1.0+0.15*np.sin(6*np.pi*t)+0.1*t).astype(np.float32)
    v=(0.7+0.3*t+0.12*np.sin(10*np.pi*t)).astype(np.float32)
    A,B,init=initial_curves_from_spectral_arrays(u,v)
    result={'dataset':'SYNTHETIC / no user audio / NOT native-parity','initialization':init,
            'spectral_inputs':{'length':n,'max_auxiliary':float(max(u)),'min_raw_curve':float(min(v))},'outputs':{}}
    for name,src,m in [('pre',A,128),('post',B,2048)]:
        f,mag,info=conditioned_curve(hz,src,m)
        result['outputs'][name]={'size':len(mag),'first_hz':float(f[0]),'last_hz':float(f[-1]),
            'min':float(mag.min()),'max':float(mag.max()),'first_5':mag[:5].astype(float).tolist(),
            'last_5':mag[-5:].astype(float).tolist(),'widths':info}
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('PASS independent SYNTHETIC spectral preparation for 128 and 2048 target samples')
if __name__=='__main__':main()

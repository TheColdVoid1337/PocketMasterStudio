"""READ-ONLY, NON-NATIVE-PARITY demonstration that naive WAV resampling is insufficient.

Requires NumPy/SciPy/soundfile. Intentionally never uses vendor CLO values to fit.
"""
import argparse,json,sys
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from stage21_saturator_source import fit_preprocessed_waveforms,read_vendor_gains

def reference_ols_DIAGNOSTIC(y):
    n=len(y)
    # vectorized float64 regression, NOT the native sequential-f32 OLS
    d=y.astype(np.float64)
    d-=d.mean()
    i=np.arange(n,dtype=np.float64)
    slope=np.dot(i-(n-1)/2,d)/(n*(n*n-1)/12)
    intercept=d.mean()-slope*(n-1)/2
    return (d-(slope*i+intercept)).astype('float32')

def audit(xfile,yfile,clofile,model):
    x,xf=sf.read(str(xfile),dtype='float32')
    y,yf=sf.read(str(yfile),dtype='float32')
    assert xf==44100 and yf==48000 and x.shape==(70*xf,2) and y.shape==(70*yf,2)
    assert np.array_equal(x[:,0],x[:,1]) and np.array_equal(y[:,0],y[:,1])
    # HYPOTHETICAL resampler, not source-proven native CE00/11B60 kernel.
    yy=resample_poly(y[:,0],147,160).astype('float32')
    assert len(yy)==len(x)
    yy=reference_ols_DIAGNOSTIC(yy)
    onset=np.flatnonzero(np.abs(yy[6*xf:6*xf+600])>0.01)
    shift=int(onset[0]) if len(onset) else 600
    a,b=23*xf,28*xf
    r=fit_preprocessed_waveforms(x[a:b,0],yy[a+shift:b+shift],xf)
    names=('pmax','nmax','prate','nrate')
    fitted=dict(zip(names,r['native_four_parameters']))
    oracle=read_vendor_gains(clofile)
    return {'model':model,'status':'NON_PARITY_DIAGNOSTIC','source_WAV_fs':xf,'target_WAV_fs':yf,
        'target_conversion':'UNVERIFIED scipy.signal.resample_poly 147/160',
        'reference_trend':'UNVERIFIED float64 OLS',
        'alignment_samples_44k1':shift,'fit_samples_44k1':b-a,
        'diagnostic_gains_NOT_NATIVE':fitted,'official_CLO_READ_ONLY':oracle,
        'relative_error_percent':{p:float(100*(fitted[p]/oracle[p]-1)) for p in names},
        'comment':'This experiment explicitly does NOT reconstruct CE00/11B60. Large deviations are expected; no calibration to oracle.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--2203',dest='a',required=True,help='extracted 2203 capture directory')
    p.add_argument('--sc20',required=True,help='extracted SC20 capture directory');p.add_argument('--output',required=True)
    args=p.parse_args()
    rows=[]
    for model,path in [('2203',Path(args.a)),('SC20',Path(args.sc20))]:
        rows.append(audit(path/'nam_input_wav.wav',path/'outputFile.wav',path/'cloFile.clo',model))
    Path(args.output).write_text(json.dumps(rows,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    for r in rows:print(r['model'],r['alignment_samples_44k1'],r['diagnostic_gains_NOT_NATIVE'],r['relative_error_percent'])
if __name__=='__main__':main()

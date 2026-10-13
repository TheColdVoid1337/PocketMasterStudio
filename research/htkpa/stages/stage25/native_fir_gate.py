"""Stage25 independent same-capture native FIR spectral comparison (no private dumps committed)."""
import argparse, hashlib, json, zipfile
from pathlib import Path
import numpy as np
SHA="fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"
PRE="20261013_overlap_capture/"
def gate(dll,archive):
 if hashlib.sha256(Path(dll).read_bytes()).hexdigest()!=SHA:raise ValueError("wrong original DLL")
 blocks=[]
 with zipfile.ZipFile(archive) as z:
  if z.testzip() is not None:raise ValueError("CRC failure")
  def rd(name):
   v=z.read(PRE+name)
   if len(v)!=32768:raise ValueError("wrong f64 buffer length")
   return np.frombuffer(v,dtype="<f8").copy()
  # One filter object, two consecutive temporal blocks: DO NOT use coeff_post_fft_01 for block 1.
  h=rd("coeff_post_fft_00.f64le.bin")
  for i in range(2):
   t=f"{i:02}"
   x=rd(f"input_packed_{t}.f64le.bin")
   y=rd(f"after_spectral_multiply_{t}.f64le.bin")
   actual_inverse=rd(f"after_inverse_{t}.f64le.bin")
   result=x.copy()
   result[:2]*=h[:2];result[2::2]*=h[2::2];result[3::2]*=h[2::2]
   bad=int(np.count_nonzero(result.view("<u8")!=y.view("<u8")))
   spec=np.empty(2049,dtype=np.complex128)
   spec[0]=y[0];spec[-1]=y[1];spec[1:-1]=y[2::2]+1j*y[3::2]
   target=2048*np.fft.irfft(np.conj(spec),n=4096)
   max_err=float(np.max(np.abs(target-actual_inverse)))
   if bad or max_err>1e-15:raise AssertionError((i,bad,max_err))
   blocks.append({"block":i,"multiplication_unequal_f64":bad,"inverse_max_abs_error":max_err})
 return {"stage":"Stage25","scope":"native same-filter 2-block spectral internals, not end-to-end resampler","dll_sha256":SHA,
 "status":"PASS_NATIVE_INTERNAL_ONLY","blocks":blocks,
 "remaining":"no same-call confirmed FIR time outputs, fractional interpolator or PCM24 reload samples"}
if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("--dll",required=True,type=Path);p.add_argument("--native-archive",required=True,type=Path)
 p.add_argument("--out",type=Path);a=p.parse_args()
 r=gate(a.dll,a.native_archive)
 if a.out:a.out.write_text(json.dumps(r,indent=2)+"\n")
 print(json.dumps(r,indent=2))

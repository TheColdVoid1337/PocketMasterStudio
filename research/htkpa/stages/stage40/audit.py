#!/usr/bin/env python3
"""Stage40: compare public r8brain native packed FIR FFTs vs original DLL.
Only metadata/digests leave private environment, never packed arrays.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile
import zipfile
import numpy as np

PIN="cb2abb9977efe2471979b380ed95daa56ab4fdb9"
ROOT="20261013_overlap_capture/"
NATIVE_SHA=[
 ("649adeb70df4bb17f73ca09c0e4bc8bd3511271fa388d989bb2094ead22b0770",
  "2fbd0bb69f5fa2436ef922c073b97abbdecb4a95487ad4978303e3d7aef2f2a9"),
 ("ccb1dcb24dc73dfa5b273a22f96d6093713f52518cadf26e595e94ff9ee6b9cc",
  "ee75eb6eef4e99a47be30c32e8ee76b4f9b549f62f4eb8d0df5eda02baebff41")]
def read_native(z, prefix, i, expected):
    raw=z.read(ROOT+prefix+f"_{i:02d}.f64le.bin")
    if len(raw)!=4096*8 or hashlib.sha256(raw).hexdigest()!=expected:
        raise ValueError(f"wrong original private {prefix}_{i} fixture")
    return np.frombuffer(raw,dtype="<f8").copy()
def compare(public, original):
    delta=public-original
    idx=int(np.argmax(np.abs(delta)))
    exact=(public.view("<u8")==original.view("<u8"))
    ma=float(np.max(np.abs(delta)))
    scale=float(np.max(np.abs(original)))
    return {"samples":len(original),"bit_exact":int(exact.sum()),
      "max_abs":ma,"rms":float(np.sqrt(np.mean(delta*delta))),
      "max_abs_over_native_peak":(ma/scale if scale else None),
      "largest_error_index":idx,
      "max_original_abs":scale,
      "public_dc":float(public[0]),"native_dc":float(original[0]),
      "public_nyquist":float(public[1]),"native_nyquist":float(original[1])}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--native-zip",type=Path,required=True,
      help="Private Stage23W archive; no contents committed")
    p.add_argument("--upstream",type=Path,required=True)
    p.add_argument("--cpp",type=Path,default=Path(__file__).with_name("r8b_kernel_gate.cpp"))
    p.add_argument("--out",type=Path,help="JSON result summary, NOT private buffers")
    a=p.parse_args()
    rev=subprocess.check_output(
        ["git","-C",str(a.upstream),"rev-parse","HEAD"],text=True).strip()
    if rev!=PIN:raise ValueError("r8brain revision mismatch: "+rev)
    with tempfile.TemporaryDirectory(prefix="stage40_private_") as work:
        d=Path(work)
        binary=d/"kernel";outputs=[d/"public1417.bin",d/"public1543.bin"]
        subprocess.run(["c++","-std=c++17","-O2","-fno-fast-math",
          "-I"+str(a.upstream),str(a.cpp),"-o",str(binary)],check=True)
        run=subprocess.run([str(binary),*(str(x) for x in outputs)],
           text=True,capture_output=True,check=True)
        public_meta=[json.loads(line) for line in run.stdout.splitlines()]
        rows=[]
        with zipfile.ZipFile(a.native_zip) as native:
            for i,(pre_sha,post_sha) in enumerate(NATIVE_SHA):
                pre=read_native(native,"coeff_pre_fft",i,pre_sha)
                ref=read_native(native,"coeff_post_fft",i,post_sha)
                raw=outputs[i].read_bytes()
                if len(raw)!=4096*8:raise ValueError("public spectrum wrong length")
                public=np.frombuffer(raw,dtype="<f8").copy()
                if not np.isfinite(public).all():raise ValueError("nonfinite public kernel")
                row={"kernel":i,"native_time_sha256":pre_sha,
                     "native_spectrum_sha256":post_sha,
                     "public_spectrum_sha256":hashlib.sha256(raw).hexdigest(),
                     "native_max_abs_time":float(np.max(np.abs(pre))),
                     "compiled_source":public_meta[i],
                     "public_vs_native_spectrum":compare(public,ref)}
                rows.append(row)
    result={"stage":40,"status":"SPECTRAL_DIFFERENTIAL_MEASURED",
            "source_revision":PIN,"filter_count":2,"filters":rows,
            "limits":"This differentiates public generated FIR spectra from vendor. The raw spectral mismatch alone does not identify the vintage source revision or establish bit-parity."}
    text=json.dumps(result,indent=2)+"\n"
    if a.out:a.out.write_text(text)
    print(text)
if __name__=="__main__":main()

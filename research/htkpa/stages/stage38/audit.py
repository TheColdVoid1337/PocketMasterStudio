#!/usr/bin/env python3
"""Stage38 offline FFT gate. Local private archives only; prints metadata/digests."""
import argparse,hashlib,json,shutil,subprocess,tarfile,tempfile,zipfile
from pathlib import Path
import numpy as np
PIN="cb2abb9977efe2471979b380ed95daa56ab4fdb9"
PREFIX="20261013_output_route/"
FIELDS=("input_pre_fft","input_post_fft","after_spectral_multiply","after_inverse")
def data(z,field,frame):
    path=f"{PREFIX}{field}_{frame:02d}.f64le.bin"
    raw=z.read(path)
    if len(raw)!=32768:raise ValueError("Native array is not 4096 f64: "+path)
    arr=np.frombuffer(raw,dtype="<f8").copy()
    if not np.isfinite(arr).all():raise ValueError("Nonfinite native data")
    return arr,raw
def native_packed_forward(x):
    spec=np.fft.rfft(x).conj()
    out=np.empty(len(x),dtype="<f8")
    out[0],out[1]=spec[0].real,spec[-1].real
    out[2::2],out[3::2]=spec[1:-1].real,spec[1:-1].imag
    return out
def native_packed_inverse(x):
    n=len(x);spec=np.empty(n//2+1,dtype=np.complex128)
    spec[0],spec[-1]=x[0],x[1]
    spec[1:-1]=x[2::2]+1j*x[3::2]
    return np.fft.irfft(spec.conj(),n=n)*(n/2)
def compare(x,y):
    d=x-y
    return {"count":len(x),"max_abs":float(np.max(np.abs(d))),
            "rms":float(np.sqrt(np.mean(d*d))),
            "exact_f64":int(np.count_nonzero(x.view("<u8")==y.view("<u8")))}
def cpp_gate(src_zip,upstream,cpp):
    actual=subprocess.check_output(["git","-C",str(upstream),"rev-parse","HEAD"],text=True).strip()
    if actual!=PIN:raise ValueError("Unexpected r8brain source SHA: "+actual)
    if not (upstream/"CDSPRealFFT.h").is_file():raise ValueError("Missing CDSPRealFFT.h")
    if not cpp.is_file():raise ValueError("Missing Stage38 C++ source")
    with tempfile.TemporaryDirectory(prefix="stage38_private_") as td:
        tmp=Path(td);exe=tmp/"fft_gate"
        subprocess.run(["c++","-std=c++17","-O2","-fno-fast-math","-I"+str(upstream),str(cpp),"-o",str(exe)],check=True)
        with zipfile.ZipFile(src_zip) as z:
            for frame in (0,1):
                for field in FIELDS:
                    name=f"{field}_{frame:02d}.f64le.bin"
                    b=z.read(PREFIX+name)
                    if len(b)!=32768:raise ValueError("Bad private buffer")
                    (tmp/name).write_bytes(b)
        result=subprocess.run([str(exe),str(tmp)],capture_output=True,text=True,check=True)
        lines=[json.loads(line) for line in result.stdout.splitlines()]
        if lines[-1].get("status")!="PASS_NUMERICAL_FFT_ONLY":
            raise ValueError("Source-compiled native FFT gate failed")
        return lines
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--native-zip",type=Path,required=True)
    p.add_argument("--stage35-archive",type=Path)
    p.add_argument("--upstream",type=Path,help="Local r8brain checkout pinned to HEAD SHA")
    p.add_argument("--cpp",type=Path,default=Path(__file__).with_name("r8b_fft_gate.cpp"))
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    rows=[]
    with zipfile.ZipFile(a.native_zip) as z:
        for f in (0,1):
            inp,_=data(z,"input_pre_fft",f)
            ref,_=data(z,"input_post_fft",f)
            spec,_=data(z,"after_spectral_multiply",f)
            inv,raw_inv=data(z,"after_inverse",f)
            forward=compare(native_packed_forward(inp[:2048]),ref[:2048])
            inverse=compare(native_packed_inverse(spec),inv)
            if forward["max_abs"]>2e-15 or inverse["max_abs"]>2e-17:
                raise AssertionError("Native FFT/Numpy numeric mismatch")
            rows.append(dict(frame=f,forward_2048=forward,inverse_4096=inverse,
                             inverse_sha256=hashlib.sha256(raw_inv).hexdigest()))
        stage35="not_checked"
        if a.stage35_archive:
            with tarfile.open(a.stage35_archive,"r:gz") as t:
                blocks=[m for m in t.getmembers() if m.name.startswith("frida_capture/block_") and m.name.endswith(".bin")]
                if len(blocks)!=1:raise ValueError("Expected one Stage35 binary block")
                b=t.extractfile(blocks[0]).read()
            _,inv0=data(z,"after_inverse",0)
            if len(b)!=15776 or b!=inv0[:15776]:
                raise AssertionError("Stage35 memcpy != FFT inverse prefix")
            stage35="1972_F64_BIT_EXACT"
    result={"stage":38,"status":"PASS_NUMPY_NUMERIC_ONLY","upstream_commit":PIN,
            "frames":rows,"stage35_fft_to_copy":stage35,
            "geometry":{"fft_input":2048,"fft_output":4096,"kernel_taps":1417,"prev_input":708,
                        "input_len":2680,"native_copy_f64":1972},
            "scope":"Native/NumPy FFT convention: not compiled public code or final 48k parity"}
    if a.upstream:
        result["public_cpp_fft"]=cpp_gate(a.native_zip,a.upstream,a.cpp)
        result["status"]="PASS_NUMPY_AND_COMPILED_R8BRAIN_FFT"
    output=json.dumps(result,indent=2)+"\n"
    if a.out:a.out.write_text(output)
    print(output)
if __name__=="__main__":main()

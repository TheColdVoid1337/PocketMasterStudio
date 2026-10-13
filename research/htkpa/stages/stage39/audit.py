#!/usr/bin/env python3
"""Stage39 offline source reconstruction + real r8brain CDSPBlockConvolver comparison.

All sample arrays are private; only numeric summary is printed and optionally saved.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tarfile
import tempfile
import zipfile
import numpy as np

PIN="cb2abb9977efe2471979b380ed95daa56ab4fdb9"
PREFIX="20261013_output_route/"
def one(z,field,index):
    raw=z.read(f"{PREFIX}{field}_{index:02d}.f64le.bin")
    if len(raw)!=4096*8:raise ValueError(f"invalid native {field}/{index} size")
    return np.frombuffer(raw,dtype="<f8").copy()
def stage33_input(archive):
    with tarfile.open(archive,"r:gz") as t:
        es=[json.loads(s) for s in t.extractfile("frida_capture/events.jsonl")]
    hits=[e for e in es if e.get("kind")=="hit" and e.get("site")=="input_entry"]
    if len(hits)!=1:raise ValueError("Stage33 must contain exactly one input_entry")
    f=hits[0]["fields"]["input_2048"]
    if f.get("encoding")!="hex_f64le" or f.get("count")!=2048:
        raise ValueError("Stage33 wrong data encoding")
    b=bytes.fromhex(f["hex"])
    if len(b)!=16384:raise ValueError("Stage33 input size mismatch")
    return np.frombuffer(b,dtype="<f8").copy()
def stage35_output(archive):
    with tarfile.open(archive,"r:gz") as t:
        es=[json.loads(s) for s in t.extractfile("frida_capture/events.jsonl")]
        blocks=[e for e in es if e.get("kind")=="binary_block" and e.get("site")=="one_binary_copy"]
        if len(blocks)!=1:raise ValueError("Stage35 expected exactly one block")
        e=blocks[0]
        data=t.extractfile("frida_capture/"+e["file"]).read()
    if len(data)!=1972*8 or hashlib.sha256(data).hexdigest()!=e["sha256"]:
        raise ValueError("Stage35 integrity mismatch")
    return data
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--native-zip",type=Path,required=True)
    p.add_argument("--stage33-archive",type=Path,required=True)
    p.add_argument("--stage35-archive",type=Path,required=True)
    p.add_argument("--upstream",type=Path,required=True)
    p.add_argument("--cpp",type=Path,default=Path(__file__).with_name("r8b_convolver_gate.cpp"))
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    with zipfile.ZipFile(a.native_zip) as z:
        a0=one(z,"input_pre_fft",0)
        a1=one(z,"input_pre_fft",1)
        inv0=one(z,"after_inverse",0)
    src=np.concatenate([a0[:1340],a1[:1340]])
    x=stage33_input(a.stage33_archive)
    if not np.array_equal(x,src[:2048]):raise ValueError("Stage33 first 2048 differs from FFT reconstructed input")
    if not np.all(a0[1340:]==0):raise ValueError("FFT frame0 history is not initially zero")
    if not np.array_equal(a1[1340:2048],a0[632:1340]):
        raise ValueError("FFT frame1 previous input history 708 mismatch")
    if not np.all(a1[2048:]==0):raise ValueError("FFT input FFT padding not zero")
    b=stage35_output(a.stage35_archive)
    if b!=inv0[:1972].astype("<f8").tobytes():
        raise ValueError("Stage35 memcpy block differs from inverse FFT prefix")
    actual=subprocess.check_output(["git","-C",str(a.upstream),"rev-parse","HEAD"],text=True).strip()
    if actual!=PIN:raise ValueError("wrong public r8brain source pin")
    result={"stage":39,"status":"INPUT_HISTORY_NATIVE_BIT_PARITY_PASS",
            "source_pin":PIN,"native_fft_frames":2,"reconstructed_input_f64":2680,
            "stage33_prefix_matched_f64":2048,"second_frame_history_matched_f64":708,
            "stage35_after_inverse_prefix_matched_f64":1972,
            "private_input_sha256":hashlib.sha256(src.astype("<f8").tobytes()).hexdigest(),
            "private_reference_sha256":hashlib.sha256(b).hexdigest(),
            "compiled_convolver":None}
    with tempfile.TemporaryDirectory(prefix="htkpa_stage39_private_") as td:
        d=Path(td);exe=d/"r8b_convolver";input_path=d/"input.f64le";ref_path=d/"native.f64le"
        input_path.write_bytes(src.astype("<f8").tobytes())
        ref_path.write_bytes(b)
        subprocess.run(["c++","-std=c++17","-O2","-fno-fast-math","-I"+str(a.upstream),str(a.cpp),"-o",str(exe)],check=True)
        process=subprocess.run([str(exe),str(input_path),str(ref_path)],capture_output=True,text=True)
        if not process.stdout.strip():
            raise ValueError("C++ output unavailable: "+process.stderr[:1200])
        lines=process.stdout.splitlines()
        item=json.loads(lines[-1])
        item["return_code"]=process.returncode
        result["compiled_convolver"]=item
        result["status"]=item["status"] if process.returncode==0 else "PUBLIC_CONVOLVER_NOT_YET_MATCHED"
        result["scope"]="First FIR-stage public r8brain vs native numerical comparison, not fractional/final 48k"
    printed=json.dumps(result,indent=2)+"\n"
    print(printed)
    if a.out:a.out.write_text(printed)
    # A convolver mismatch is an informative differential outcome, not an invalid fixture.
    if result["compiled_convolver"]["status"]=="NOT_MATCHED":
        print("[NOTE] Differential mismatch is legitimate. Inspect latency/source version, do not claim parity.")
if __name__=="__main__":
    main()

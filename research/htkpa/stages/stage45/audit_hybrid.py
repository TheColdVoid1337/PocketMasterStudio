#!/usr/bin/env python3
"""HTKPA Stage45: vendor first FIR -> public fractional resampler (offline).

Compare HYBRID output against public complete r8brain chain. The real vendor
48000-Hz output has NOT been captured, so vendor final parity is NOT tested.
All sound waveforms remain inside a deleted private temporary workspace.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np

PINS=[
    ("v6.5","3c930bf6825c0cfea4a813210c83b1a650c820b5","2023-12-07"),
    ("v7.2","8fff6f3db26f14a8f5e8fb871000613673db5753","2026-07-27"),
    ("v7.6","cb2abb9977efe2471979b380ed95daa56ab4fdb9","2026-09-30"),
]
CHUNKS=(64,512,1972)

def imp(path:Path, name:str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:raise RuntimeError("missing local dependency "+str(path))
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module

def compare(a,b):
    if len(a)!=len(b):
        return {"equal_sample_counts":False,"left_f64":len(a),"right_f64":len(b),
                "interpretation":"Cannot compare elementwise without matching lengths"}
    if not len(a):
        return {"equal_sample_counts":True,"count":0,"bit_exact":0,
                "max_abs":0.0,"rms":0.0}
    delta=a-b
    return {"equal_sample_counts":True,"count":len(a),
            "bit_exact":int(np.count_nonzero(a.view("<u8")==b.view("<u8"))),
            "max_abs":float(np.max(np.abs(delta))),
            "rms":float(np.sqrt(np.mean(delta*delta)))}

def build(cxx,cpp,source,output):
    args=[cxx,"-std=c++17","-O2","-fno-fast-math","-pthread",
          "-I"+str(source),str(cpp)]
    old=source/"r8bbase.cpp"
    if old.is_file():args.append(str(old))
    args+=["-o",str(output)]
    result=subprocess.run(args,capture_output=True,text=True)
    if result.returncode:
        raise RuntimeError("compile of public r8brain source failed: "+result.stderr[-2000:])

def run(executable,input_path,output_path,chunk):
    process=subprocess.run([str(executable),str(input_path),str(output_path),str(chunk)],
                           capture_output=True,text=True)
    if process.returncode:
        raise RuntimeError("public executable error: "+process.stderr[-2000:])
    info=json.loads(process.stdout.splitlines()[-1])
    binary=output_path.read_bytes()
    if len(binary)%8 or len(binary)!=info["output_f64"]*8:
        raise ValueError("bad public output length or alignment")
    samples=np.frombuffer(binary,dtype="<f8").copy()
    if not np.isfinite(samples).all():
        raise ValueError("nonfinite public output")
    info["sha256"]=hashlib.sha256(binary).hexdigest()
    return info,samples

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--native-zip",type=Path,required=True)
    p.add_argument("--stage33-archive",type=Path,required=True)
    p.add_argument("--stage35-archive",type=Path,required=True)
    p.add_argument("--source-cache",type=Path,required=True)
    p.add_argument("--cxx",default="c++")
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    for path in (a.native_zip,a.stage33_archive,a.stage35_archive):
        if not path.is_file():raise FileNotFoundError("private archived sample not found: "+str(path))
    root=Path(__file__).resolve().parents[1]
    stage43=imp(root/"stage43"/"audit_convolver_versions.py","_htkpa45_stage43")
    input_bytes,fir_bytes=stage43.native_input_and_reference(
        a.native_zip,a.stage33_archive,a.stage35_archive)
    if len(input_bytes)!=2680*8 or len(fir_bytes)!=1972*8:
        raise ValueError("original native input / FIR data not expected dimensions")
    common=imp(root/"stage41"/"audit_versions.py","_htkpa45_stage41")
    common.COMMITS=[(v,p,d,v!="v7.6") for v,p,d in PINS]
    cache=common.prepare_git_cache(a.source_cache)

    full_cpp=root/"stage44"/"public_resampler.cpp"
    frac_cpp=Path(__file__).with_name("hybrid_fractional.cpp")
    rows=[]
    public_full={}
    hybrid={}
    with tempfile.TemporaryDirectory(prefix="htkpa_stage45_private_") as td:
        temp=Path(td)
        original_input=temp/"vendor_input_2680.f64le"
        original_fir=temp/"vendor_first_fir_1972.f64le"
        original_input.write_bytes(input_bytes)
        original_fir.write_bytes(fir_bytes)
        for version,commit,date in PINS:
            print("[BUILD] "+version+" "+commit[:12],flush=True)
            work=temp/version.replace(".","_")
            work.mkdir()
            public_source=work/"source"
            common.unpack_revision(cache,commit,public_source)
            exe_full=work/"full_chain"
            exe_frac=work/"hybrid_frac"
            build(a.cxx,full_cpp,public_source,exe_full)
            build(a.cxx,frac_cpp,public_source,exe_frac)

            full_info,full_data=run(exe_full,original_input,work/"full.bin",2680)
            public_full[version]=full_data
            hybrid_runs=[]
            hybrid_data={}
            for chunk in CHUNKS:
                meta,out=run(exe_frac,original_fir,
                             work/("hybrid_"+str(chunk)+".bin"),chunk)
                hybrid_runs.append(meta)
                hybrid_data[chunk]=out
            baseline=hybrid_data[1972]
            hybrid[version]=baseline
            invariant={str(chunk):compare(hybrid_data[chunk],baseline)
                       for chunk in CHUNKS[:-1]}
            compared=compare(baseline,full_data)
            print("[MEASURE] "+version+" full="+str(len(full_data))+
                  " hybrid="+str(len(baseline))+
                  " hybrid-vs-public-maxabs="+str(compared.get("max_abs")),
                  flush=True)
            rows.append({
                "version":version,"commit":commit,"date":date,
                "public_full":full_info,
                "vendor_FIR_to_public_frac":hybrid_runs,
                "hybrid_chunk_invariance":invariant,
                "hybrid_vs_full_public":compared
            })

    result={
        "stage":45,
        "status":"PUBLIC_HYBRID_DIFFERENTIAL_MEASURED",
        "input_sha256":hashlib.sha256(input_bytes).hexdigest(),
        "vendor_first_FIR_sha256":hashlib.sha256(fir_bytes).hexdigest(),
        "versions":rows,
        "hybrid_v72_vs_v65":compare(hybrid["v7.2"],hybrid["v6.5"]),
        "hybrid_v76_vs_v65":compare(hybrid["v7.6"],hybrid["v6.5"]),
        "vendor_fractional_or_final_48k_parity":"NOT_TESTED_NO_VENDOR_FINAL_REFERENCE",
        "purpose":"Quantify how much vendor-observed first FIR low-bit deviations propagate through source-compiled PUBLIC fractional interpolation. Not the embedded vendor fractional code.",
        "privacy":"Only hashes and numeric error metrics; original WAV/FFT/DLL and generated public audio are never committed.",
    }
    serialized=json.dumps(result,indent=2)+"\n"
    print(serialized)
    if a.out:
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(serialized,encoding="utf-8")

if __name__=="__main__":
    main()

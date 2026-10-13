#!/usr/bin/env python3
"""Stage44 offline historical r8brain 44.1 kHz -> 48 kHz PUBLIC pipeline.

No vendor final 48k signal is present: DO NOT call results Sonicake output
parity. Original vendor input is cryptographically cross-checked using
Stage43/Stage39 before executing any public resampler.
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
    ("v6.5","3c930bf6825c0cfea4a813210c83b1a650c820b5","2023-12-07",True),
    ("v7.2","8fff6f3db26f14a8f5e8fb871000613673db5753","2026-07-27",True),
    ("v7.6","cb2abb9977efe2471979b380ed95daa56ab4fdb9","2026-09-30",False)
]
CHUNKS=(64,512,2680)

def load_local(path:Path, name:str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:raise RuntimeError("Cannot load local test module")
    m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m
    spec.loader.exec_module(m)
    return m

def diff(a,b):
    if len(a)!=len(b):
        return {"equal_sample_counts":False,"a_count":len(a),"b_count":len(b)}
    if len(a)==0:
        return {"equal_sample_counts":True,"compared":0,"bit_exact":0,
                "max_abs":0.0,"rms":0.0}
    delta=a-b
    return {
        "equal_sample_counts":True,
        "compared":len(a),
        "bit_exact":int(np.count_nonzero(a.view("<u8")==b.view("<u8"))),
        "max_abs":float(np.max(np.abs(delta))),
        "rms":float(np.sqrt(np.mean(delta*delta))),
    }

def run_release(common,cxx,cpp,cache,version,revision,legacy,root,input_path):
    src=root/"public_source"
    common.unpack_revision(cache,revision,src)
    exe=root/"resampler"
    build=[cxx,"-std=c++17","-O2","-fno-fast-math","-pthread",
           "-I"+str(src),str(cpp)]
    old_base=src/"r8bbase.cpp"
    if old_base.is_file():
        build.append(str(old_base))
    build+=["-o",str(exe)]
    compile=subprocess.run(build,text=True,capture_output=True)
    if compile.returncode:
        return {"status":"COMPILE_FAILED","return_code":compile.returncode,
                "stderr_tail":compile.stderr[-1400:]},None
    runs=[]
    outputs={}
    for chunk in CHUNKS:
        output=root/("output_"+str(chunk)+".f64le")
        result=subprocess.run([str(exe),str(input_path),str(output),str(chunk)],
                              capture_output=True,text=True)
        if result.returncode:
            return {"status":"RUNTIME_FAILED","chunk":chunk,
                    "return_code":result.returncode,
                    "stderr_tail":result.stderr[-1400:]},None
        meta=json.loads(result.stdout.splitlines()[-1])
        raw=output.read_bytes()
        if len(raw)%8 or len(raw)//8!=meta["output_f64"]:
            return {"status":"OUTPUT_LENGTH_INVALID","chunk":chunk},None
        values=np.frombuffer(raw,dtype="<f8").copy()
        if not np.isfinite(values).all():
            return {"status":"NONFINITE_OUTPUT","chunk":chunk},None
        meta["public_output_sha256"]=hashlib.sha256(raw).hexdigest()
        runs.append(meta)
        outputs[chunk]=values
    baseline=outputs[CHUNKS[-1]]
    return {
        "status":"COMPLETED_PUBLIC_ONLY",
        "runs":runs,
        "chunk_invariance":{str(k):diff(outputs[k],baseline) for k in CHUNKS[:-1]},
    },baseline

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--native-zip",type=Path,required=True)
    p.add_argument("--stage33-archive",type=Path,required=True)
    p.add_argument("--stage35-archive",type=Path,required=True)
    p.add_argument("--source-cache",type=Path,required=True)
    p.add_argument("--cpp",type=Path,default=Path(__file__).with_name("public_resampler.cpp"))
    p.add_argument("--cxx",default="c++")
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    for private in (a.native_zip,a.stage33_archive,a.stage35_archive):
        if not private.is_file():raise FileNotFoundError("Missing ignored private fixture "+str(private))
    stage43=load_local(Path(__file__).resolve().parents[1]/"stage43"/"audit_convolver_versions.py",
                       "_htkpa_44_stage43")
    raw, reference=stage43.native_input_and_reference(
        a.native_zip,a.stage33_archive,a.stage35_archive)
    if len(raw)!=2680*8 or len(reference)!=1972*8:
        raise AssertionError("Genuine vendor input or FIR reference differs from Stage43")
    common=load_local(Path(__file__).resolve().parents[1]/"stage41"/"audit_versions.py",
                      "_htkpa_44_stage41")
    common.COMMITS=PINS
    cache=common.prepare_git_cache(a.source_cache)
    rows=[]
    outputs={}
    with tempfile.TemporaryDirectory(prefix="htkpa_stage44_private_") as td:
        root=Path(td)
        inp=root/"original_vendor_input_2680.f64le"
        inp.write_bytes(raw)
        for version,revision,release_date,legacy in PINS:
            print("[BUILD] "+version+" @ "+revision[:12],flush=True)
            scratch=root/("build_"+version.replace(".","_"))
            scratch.mkdir()
            report,out=run_release(common,a.cxx,a.cpp,cache,version,revision,legacy,scratch,inp)
            rows.append({"version":version,"pin":revision,"release_date":release_date,**report})
            if out is not None:
                outputs[version]=out
                print("[PUBLIC] "+version+" full-resampler-output="+str(len(out))+
                      " f64 / chunk-invariance="+
                      str(all(v.get("bit_exact")==v.get("compared")
                              for v in report["chunk_invariance"].values())),
                      flush=True)
            else:
                print("[WARN] "+version+" "+report["status"],flush=True)
        historical_comparisons={}
        if "v6.5" in outputs:
            for version,out in outputs.items():
                if version!="v6.5":
                    historical_comparisons[version+"_vs_v6.5"]=diff(out,outputs["v6.5"])
    result={
        "stage":44,
        "status":"PUBLIC_PIPELINE_READY" if len(outputs)==len(PINS) else "INCOMPLETE_PUBLIC_BUILDS",
        "origin":"Stage43 original vendor input (2680 f64) verified vs Stage33/Stage23W, but no captured vendor 48k final output",
        "native_input_sha256":hashlib.sha256(raw).hexdigest(),
        "native_first_fir_output_sha256":hashlib.sha256(reference).hexdigest(),
        "parameters_assumed":{"source_hz":44100,"destination_hz":48000,
                              "transition_percent":2.0,"attenuation_db":180.15,
                              "phase":"linear"},
        "source_chain_expected":"CDSPBlockConvolver(2x 44100->88200) then CDSPFracInterpolator(88200->48000)",
        "versions":rows,
        "public_vs_public":historical_comparisons,
        "vendor_final_output_parity":"NOT_TESTED_NO_VENDOR_48K_REFERENCE",
        "notes":"Compared full PUBLIC r8brain pipeline under pinned C++ source. "
                "Chunk-size invariance and public version comparisons do not demonstrate "
                "the vendor's fractional interpolation or final resampled output.",
        "privacy":"No original or generated waveform arrays committed or serialized in report."
    }
    text=json.dumps(result,indent=2)+"\n"
    print(text)
    if a.out:
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(text,encoding="utf-8")
    if len(outputs)!=len(PINS):
        raise SystemExit(2)

if __name__=="__main__":
    main()

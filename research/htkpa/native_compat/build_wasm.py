#!/usr/bin/env python3
"""Stage67 opt-in WebAssembly build of Stage66's recovered fractional C ABI.

Builds against an *exact*, locally cached MIT r8brain v6.5 commit. Applies
the numerically validated Sonicake window+polynomial change only to ephemeral
source. Output lives in the ignored PRIVATE research/_LOCAL_FILES tree, NOT
inside PocketMasterStudio.html and not in Git. Existing SonicMaster DSP
browser NAM->CLO implementation is untouched.

Requires em++ from the locally installed Emscripten SDK. No auto-install,
no GitHub Actions, no network downloads. Output: .mjs, .wasm, SHA manifest.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
STAGE63=ROOT/"research"/"htkpa"/"stages"/"stage63"/"audit_audio_parity.py"
BRIDGE=HERE/"htkpa_native_frac_bridge.cpp"
VERSION="v6.5"
EXPORTS=[
    "_malloc","_free",
    "_htkpa_v1_id","_htkpa_v1_open","_htkpa_v1_min_output_capacity",
    "_htkpa_v1_process","_htkpa_v1_reset","_htkpa_v1_close",
]
REQUIRED_PATCH=("HTKPA_Stage62_Params","IsWhole = false;","FilterFracs = 673;")


def load_stage63():
    spec=importlib.util.spec_from_file_location("_htkpa_stage67_stage63",STAGE63)
    if spec is None or spec.loader is None:
        raise RuntimeError("Stage63 pinned source-patch module is missing")
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module


def sha(file:Path)->str:
    return hashlib.sha256(file.read_bytes()).hexdigest()


def command(emxx:str,source:Path,dest:Path)->list[str]:
    return [
        emxx,"-std=c++17","-O2","-fno-fast-math","-fexceptions",
        "-I"+str(source),str(BRIDGE),
        "-sMODULARIZE=1","-sEXPORT_ES6=1","-sENVIRONMENT=web,worker,node",
        "-sWASM=1","-sALLOW_MEMORY_GROWTH=1","-sFILESYSTEM=0",
        "-sDISABLE_EXCEPTION_CATCHING=0",
        "-sEXPORTED_FUNCTIONS="+json.dumps(EXPORTS,separators=(",",":")),
        "-o",str(dest),
    ]


def build(source_cache:Path,out_dir:Path,emxx:str)->dict:
    if not BRIDGE.is_file():
        raise ValueError("Stage66 C ABI source unavailable")
    if not shutil.which(emxx):
        raise RuntimeError("Emscripten em++ not installed/in PATH; activate emsdk first")
    stage63=load_stage63()
    public_commit=stage63.stage55.PINS[VERSION]
    with tempfile.TemporaryDirectory(prefix="htkpa_stage67_public_mit_") as td:
        temp=Path(td)
        public=temp/"r8brain";public.mkdir()
        stage63.stage55.ensure_checkout(source_cache,public_commit,public)
        header=public/"CDSPFracInterpolator.h"
        original=header.read_text(encoding="utf-8")
        updated,details=stage63.patch_header(original,"native_window_poly_673")
        for anchor in REQUIRED_PATCH:
            if anchor not in updated:
                raise ValueError("Stage67 cannot confirm exact native spline source patch")
        if details["beta_hex"]!="0x1.91af20df9e8bap+3" or (
                details["power_hex"]!="0x1.83fa5ca7f6a99p+0"):
            raise ValueError("Stage67 DLL Kaiser coefficient constants changed")
        header.write_text(updated,encoding="utf-8")
        target=temp/"htkpa_native_frac.mjs"
        argv=command(emxx,public,target)
        proc=subprocess.run(argv,capture_output=True,text=True)
        if proc.returncode:
            raise RuntimeError("Emscripten build failed (exit "+
                               str(proc.returncode)+"):\n"+
                               proc.stderr[-4200:])
        wasm=target.with_suffix(".wasm")
        if not target.is_file() or not wasm.is_file() or (
                target.stat().st_size<1000 or wasm.stat().st_size<1000):
            raise ValueError("Emscripten did not create both expected JS and WASM assets")
        # A build is only published after BOTH files are present and hashed.
        manifest={
            "stage":67,"schema_version":1,
            "created_utc":datetime.now(timezone.utc).isoformat(),
            "build_type":"opt-in isolated browser/worker reference; not production NAM conversion",
            "public_source_commit":public_commit,
            "original_vendor_dll_sha256":"fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa",
            "bridge_cpp_sha256":sha(BRIDGE),
            "consumer_adapter_sha256":sha(ROOT/"src"/"htkpa_wasm_adapter.js"),
            "patch":details,
            "emxx":emxx,"exports":EXPORTS,
            "output":{
                "htkpa_native_frac.mjs":{"sha256":sha(target),"bytes":target.stat().st_size},
                "htkpa_native_frac.wasm":{"sha256":sha(wasm),"bytes":wasm.stat().st_size}},
            "source_in_private_temporary_directory":True,
            "vendor_binary_included":False
        }
        out_dir.mkdir(parents=True,exist_ok=True)
        for original_file in (target,wasm):
            dest=out_dir/original_file.name
            part=out_dir/(original_file.name+".staging")
            shutil.copyfile(original_file,part)
            os.replace(part,dest)
        final=out_dir/"htkpa_wasm_build.json"
        tmpmeta=out_dir/"htkpa_wasm_build.json.staging"
        tmpmeta.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
        os.replace(tmpmeta,final)
        return {"manifest":str(final),
                "public_source_commit":public_commit,
                "bytes_wasm":manifest["output"]["htkpa_native_frac.wasm"]["bytes"],
                "sha256_wasm":manifest["output"]["htkpa_native_frac.wasm"]["sha256"],
                "runtime":"browser WebAssembly ES module; explicitly opt in"}


def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--source-cache",type=Path,required=True)
    ap.add_argument("--out-dir",type=Path,
                    default=ROOT/"research"/"_LOCAL_FILES"/"htkpa_wasm")
    ap.add_argument("--emxx",default="em++")
    args=ap.parse_args()
    print(json.dumps(build(args.source_cache,args.out_dir,args.emxx),
                     ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("[ERROR] Stage67:",type(exc).__name__+":",exc,file=sys.stderr)
        raise SystemExit(2)

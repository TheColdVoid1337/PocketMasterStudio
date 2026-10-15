#!/usr/bin/env python3
"""Stage68: real Emscripten/WebAssembly 1181-sample native numerical gate.

No new Frida, vendor DLL or web access. Inputs are the pinned Stage54+64
private samples and original WAV. The real WASM binary must come from the
isolated Stage67 Emscripten build and pass SHA/source/ABI manifest guards.
Node runs its actual browser-compatible adapter against real Emscripten
exports. Checks forward 1067 + reverse 114 native outputs, streaming splits,
reset equality, RMS and max errors, without shifting sample coordinates.
All native/wasm f64 streams are kept in a private temporary directory; ONLY
scalar metrics and hashes may enter the sealed research_run .tar.gz.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
STAGE66=HERE/"audit_bridge.py"
STAGE67=HERE/"build_wasm.py"
RUNNER=HERE/"audit_wasm_runner.cjs"
import importlib.util


def load(label:str,file:Path):
    spec=importlib.util.spec_from_file_location(label,file)
    if spec is None or spec.loader is None:
        raise ImportError("prior native-compat source unavailable")
    result=importlib.util.module_from_spec(spec)
    sys.modules[label]=result
    spec.loader.exec_module(result)
    return result

earlier=load("_htkpa68_stage66",STAGE66)
builder=load("_htkpa68_stage67",STAGE67)
stage65=earlier.stage65
stage55=earlier.stage55
stage63=earlier.stage63

NATIVE_BOUNDS={"reverse":1e-14,"forward":1e-16}


def verify_build(folder:Path)->dict:
    manifest_path=folder/"htkpa_wasm_build.json"
    data=json.loads(manifest_path.read_text(encoding="utf-8"))
    if (data.get("stage")!=67 or data.get("schema_version")!=1
            or data.get("public_source_commit")!=stage55.PINS["v6.5"]
            or data.get("original_vendor_dll_sha256")!=
               "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"
            or data.get("bridge_cpp_sha256")!=builder.sha(builder.BRIDGE)
            or data.get("consumer_adapter_sha256")!=
               builder.sha(ROOT/"src"/"htkpa_wasm_adapter.js")
            or data.get("exports")!=builder.EXPORTS
            or data.get("runtime_exports")!=builder.RUNTIME_EXPORTS
            or data.get("vendor_binary_included") is not False):
        raise ValueError("unverified Stage67 WASM build source/bridge/ABI provenance")
    patch=data.get("patch",{})
    if (patch.get("beta_hex")!="0x1.91af20df9e8bap+3" or
            patch.get("power_hex")!="0x1.83fa5ca7f6a99p+0" or
            patch.get("interpolation_mode")!="forced_poly_673" or
            patch.get("phase_positions")!=673):
        raise ValueError("Stage67 WASM patch is not the known native fractional mode")
    for name in ("htkpa_native_frac.mjs","htkpa_native_frac.wasm"):
        meta=data.get("output",{}).get(name,{})
        file=folder/name
        if (not file.is_file() or meta.get("bytes")!=file.stat().st_size or
                meta.get("sha256")!=builder.sha(file) or
                file.stat().st_size<1000):
            raise ValueError("Stage67 WASM build artifact SHA mismatch: "+name)
    return {"wasm_sha256":data["output"]["htkpa_native_frac.wasm"]["sha256"],
            "esm_sha256":data["output"]["htkpa_native_frac.mjs"]["sha256"],
            "public_commit":data["public_source_commit"],
            "adapter_sha256":data["consumer_adapter_sha256"]}


def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--wasm-dir",type=Path,required=True)
    ap.add_argument("--stage64",type=Path,required=True)
    ap.add_argument("--stage63",type=Path,required=True)
    ap.add_argument("--stage62",type=Path,required=True)
    ap.add_argument("--stage54",type=Path,required=True)
    ap.add_argument("--wav",type=Path,required=True)
    ap.add_argument("--node",default="node")
    args=ap.parse_args()
    wasm=verify_build(args.wasm_dir)
    if not shutil.which(args.node):
        raise RuntimeError("Node.js not found (required only for real WASM validation)")
    native,provenance=stage65.read_extended(args.stage64)
    stage65.read_stage63(args.stage63)
    stage63.check_stage62(args.stage62)
    prior54=stage55.archive_bytes(args.stage54,stage55.EXPECTED["stage54_tar"],{
        "input_0001.bin":(24,stage55.EXPECTED["native_96k_first3"]),
        "input_0002.bin":(2048,stage55.EXPECTED["native_96k_next256"]),
        "output_0001.bin":(256,stage55.EXPECTED["native_48k_first32"])})
    sample=stage55.wav_input_2680(args.wav)
    report={"stage":68,"schema_version":1,
            "created_utc":datetime.now(timezone.utc).isoformat(),
            "status":"REAL_WASM_NATIVE_PARITY_MEASURED",
            "wasm":wasm,"native_capture":provenance,
            "scope":"isolated real Emscripten C ABI + browser adapter, real pinned native 114+1067; not integrated into production NAM/CLO",
            "comparisons":{}}
    with tempfile.TemporaryDirectory(prefix="htkpa_stage68_private_") as folder:
        root=Path(folder)
        in3=root/"input_3.f64le";in3.write_bytes(prior54["input_0001.bin"])
        in256=root/"input_256.f64le";in256.write_bytes(prior54["input_0002.bin"])
        in2680=root/"input_2680.f64le";in2680.write_bytes(sample)
        outfile=root/"private_outputs"
        args_node=[
            args.node,str(RUNNER),
            str((args.wasm_dir/"htkpa_native_frac.mjs").resolve()),
            str(in3),str(in256),str(in2680),str(outfile),
            "3,256","2680"]
        called=subprocess.run(args_node,capture_output=True,text=True)
        if called.returncode:
            raise RuntimeError("real WebAssembly playback failed:\n"+called.stderr[-4000:])
        summary=json.loads(called.stdout.splitlines()[-1])
        if (summary.get("status")!="WASM_NATIVE_COMPAT_GENERATED" or
                summary.get("reverse_f64")!=114 or
                summary.get("forward_f64")!=1067 or
                summary.get("wasm_abi")!=earlier.API_ID or
                summary.get("split_bit_equal") is not True or
                summary.get("reset_bit_equal") is not True):
            raise ValueError("real Emscripten stream/reset metadata inconsistent")
        for side,count in (("reverse",114),("forward",1067)):
            output=(outfile/(side+".f64le")).read_bytes()
            if (len(output)!=count*8 or
                    stage55.sha(output)!=summary[side+"_sha256"]):
                raise ValueError("actual WASM audio bytes/SHA mismatch")
            metrics=stage65.detailed_metrics(native[side],output,count)
            metrics["exact_linux_stage66_public_sha256"]=(
                earlier.EXPECTED_PATCHED_FULL_SHA[side])
            metrics["bit_identical_to_linux_stage66"]=(
                metrics["public_sha256"]==earlier.EXPECTED_PATCHED_FULL_SHA[side])
            if metrics["rms_error"]>NATIVE_BOUNDS[side]:
                report["status"]="REAL_WASM_NUMERIC_DIFFERENCE"
            report["comparisons"][side]=metrics
            print(f"[WASM] {side}: f64={count}, RMS={metrics['rms_error']:.17g}, "
                  f"max={metrics['max_abs_error']:.17g}, "
                  f"bit_native={metrics['bit_equal']}/{count}, "
                  f"bit_linux={metrics['bit_identical_to_linux_stage66']}",flush=True)
    folder=os.environ.get("RESEARCH_ARTIFACT_DIR")
    if folder:
        output=Path(folder);output.mkdir(parents=True,exist_ok=True)
        (output/"stage68_wasm_native_parity.json").write_text(
            json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] Stage68: {type(exc).__name__}: {exc}",file=sys.stderr)
        raise SystemExit(2)

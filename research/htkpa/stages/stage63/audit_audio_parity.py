#!/usr/bin/env python3
"""Stage63: DIRECT native/public AUDIO prefix replay with recovered Kaiser bank.

Stage62 established coefficient parity at ~7.14e-17 RMS from exactly
DLL-derived beta=12.55262798/power=1.51553897. Stage63 tests whether
*those same window parameters* plus native observed 673-phase quadratic
interpolation reproduce the first 32 f64 output samples for two independent
conversions:
 - native 96k->44.1k from Stage49, fed exact Stage54 native [3,256] f64;
 - native 44.1k->48k path from Stage54, fed exact Stage44 2680 WAV samples.
Test modes: original upstream; native window only; native window + forced
polynomial 673; native window + default polynomial position count.

Source patches affect ONLY temporary checked-out, commit-SHA-pinned MIT
r8brain headers. No arbitrary time alignment or cross correlation. Output
sample buffers remain temporary; reports hold scalar errors and SHA only.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import tarfile
import tempfile

HERE=Path(__file__).resolve().parent


def load_py(label:str,path:Path):
    spec=importlib.util.spec_from_file_location(label,path)
    if spec is None or spec.loader is None:
        raise ImportError(f"missing prior-stage module: {path}")
    module=importlib.util.module_from_spec(spec)
    sys.modules[label]=module
    spec.loader.exec_module(module)
    return module


stage55=load_py("_htkpa_stage63_stage55",HERE.parent/"stage55"/"audit_numeric.py")
stage57=load_py("_htkpa_stage63_stage57",HERE.parent/"stage57"/"audit_poly.py")
stage62=load_py("_htkpa_stage63_stage62",HERE.parent/"stage62"/"audit_native_window.py")

VERSION="v6.5"
STAGE62_TAR_SHA="77702bc9500c3e429fb5627df2d33c3bbaa6b8210dbc21b8223546d3cdce828f"
STAGE62_NUMERIC_RMS=7.1378242035994835e-17
STAGE62_COEFF_PUBLIC_SHA="7e6df2bcdadec2e3b8db4c58c11a732b52da606d57e190136b905c1389275617"
REVERSE_NATIVE_LENGTHS=[0,114]
FORWARD_NATIVE_LENGTH=1067
TRIALS=("native_window_whole","native_window_poly_default","native_window_poly_673")


def check_stage62(path:Path)->dict:
    original=path.read_bytes()
    if stage55.sha(original)!=STAGE62_TAR_SHA:
        raise ValueError("Stage62 exact archive SHA does not match validated run")
    with tarfile.open(path,"r:gz") as t:
        data=json.loads(t.extractfile("output/stage62_native_window.json").read())
        run=json.loads(t.extractfile("run.json").read())
    best=data["results"]["native_both"]
    m=best["metrics"]
    if (run.get("status")!="SUCCEEDED" or data.get("status")!="NATIVE_WINDOW_PARAMS_HYPOTHESES_MEASURED"
            or data.get("source_commit")!=stage55.PINS[VERSION]
            or data.get("native",{}).get("coefficient_sha256")!=stage62.NATIVE_SHA
            or best["window"]["beta_f64_hex"]!=stage62.NATIVE_BETA.hex()
            or best["window"]["power_f64_hex"]!=stage62.NATIVE_POWER.hex()
            or m.get("bank_sha256")!=STAGE62_COEFF_PUBLIC_SHA
            or not math.isclose(m.get("rms_error",float("inf")),
                                STAGE62_NUMERIC_RMS,rel_tol=1e-13,abs_tol=1e-19)):
        raise ValueError("Stage62 coefficient parity gate does not match")
    return {"archive_sha256":stage55.sha(original),
            "native_coefficient_sha256":stage62.NATIVE_SHA,
            "public_matched_bank_sha256":STAGE62_COEFF_PUBLIC_SHA,
            "bank_rms_error":m["rms_error"],
            "bank_bit_equal":m["bit_equal"]}


def patch_header(upstream:str,trial:str)->tuple[str,dict]:
    if trial not in TRIALS:
        raise ValueError("unexpected resampler trial")
    if trial=="native_window_whole":
        text=upstream
        poly="upstream_whole_or_auto"
    else:
        submode="poly_673" if trial=="native_window_poly_673" else "poly_default_fracs"
        text,_=stage57.patch_frac_header(upstream,submode)
        poly="forced_poly_673" if submode=="poly_673" else "forced_poly_default_positions"
    text,params=stage62.patch_public_header(text,"native_both")
    return text,{"interpolation_mode":poly,"beta":params["beta"],
                 "power":params["power"],"beta_hex":params["beta_f64_hex"],
                 "power_hex":params["power_f64_hex"],
                 "phase_positions":673 if poly=="forced_poly_673" else None,
                 "only_private_public_source_patched":True}


def sample_error(native:bytes,generated:bytes,expected_samples:int=32)->dict:
    if expected_samples!=32:
        raise ValueError("this gate validates exactly 32 native samples")
    result=stage55.metric(native,generated)
    if result["status"]!="COMPARED_SAME_INDEX_FIRST_32":
        return result
    n=__import__("struct").unpack("<32d",native)
    p=__import__("struct").unpack("<32d",generated[:256])
    error=[abs(x-y) for x,y in zip(n,p)]
    result["mean_abs_error"]=math.fsum(error)/32
    result["sample_indices_max_abs"]=[
        i for i,e in enumerate(error) if e==max(error)]
    result["native_rms"]=math.sqrt(math.fsum(x*x for x in n)/32)
    result["rms_to_native_rms"]=(
        result["rms_error"]/result["native_rms"] if result["native_rms"] else None)
    result["strict_comparison"]="same native/public output indices 0..31; NO shift"
    return result


def compare(trial:str,reverse_info:dict,reverse:bytes,forward_info:dict,
            forward:bytes,native49:dict,native54:dict)->dict:
    rgeom=reverse_info["output_f64"]==REVERSE_NATIVE_LENGTHS
    fgeom=forward_info["output_f64"]==FORWARD_NATIVE_LENGTH
    r=(sample_error(native49["block_0001.bin"],reverse)
       if rgeom else {"status":"REVERSE_COUNT_GEOMETRY_MISMATCH",
                      "actual":reverse_info["output_f64"],
                      "expected":REVERSE_NATIVE_LENGTHS})
    f=(sample_error(native54["output_0001.bin"],forward)
       if fgeom else {"status":"FORWARD_COUNT_GEOMETRY_MISMATCH",
                      "actual":forward_info["output_f64"],
                      "expected":FORWARD_NATIVE_LENGTH})
    return {"trial":trial,"reverse_counts":reverse_info["output_f64"],
            "forward_output_f64":forward_info["output_f64"],
            "reverse":r,"forward":f,
            "reverse_output_sha256":stage55.sha(reverse),
            "forward_output_sha256":stage55.sha(forward),
            "reverse_first32_sha256":stage55.sha(reverse[:256]),
            "forward_first32_sha256":stage55.sha(forward[:256])}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--stage62",type=Path,required=True)
    ap.add_argument("--stage54",type=Path,required=True)
    ap.add_argument("--stage49",type=Path,required=True)
    ap.add_argument("--wav",type=Path,required=True)
    ap.add_argument("--source-cache",type=Path,required=True)
    ap.add_argument("--cxx",default="c++")
    args=ap.parse_args()
    coefficient_gate=check_stage62(args.stage62)
    native54=stage55.archive_bytes(args.stage54,stage55.EXPECTED["stage54_tar"],{
        "input_0001.bin":(24,stage55.EXPECTED["native_96k_first3"]),
        "input_0002.bin":(2048,stage55.EXPECTED["native_96k_next256"]),
        "output_0001.bin":(256,stage55.EXPECTED["native_48k_first32"])})
    native49=stage55.archive_bytes(args.stage49,stage55.EXPECTED["stage49_tar"],{
        "block_0001.bin":(256,stage55.EXPECTED["native_44k_first32"])})
    stage55.validate_provenance(native49,native54)
    wav=stage55.wav_input_2680(args.wav)

    report={"stage":63,"schema_version":1,
            "created_utc":datetime.now(timezone.utc).isoformat(),
            "status":"NATIVE_WINDOW_AUDIO_PREFIXES_COMPARED",
            "public_commit":stage55.PINS[VERSION],
            "native_dll_sha256":stage55.EXPECTED.get("dll","fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"),
            "stage62_coeff_parity_gate":coefficient_gate,
            "scope":"Stage49 96k->44.1 first32 and Stage54 44.1->48 first32; pinned equal inputs and zero-index alignment",
            "trials":{}}
    with tempfile.TemporaryDirectory(prefix="htkpa_stage63_private_") as d:
        root=Path(d)
        src=root/"public";src.mkdir()
        stage55.ensure_checkout(args.source_cache,stage55.PINS[VERSION],src)
        header=src/"CDSPFracInterpolator.h"
        original=header.read_text(encoding="utf-8")
        in3=root/"in3.bin";in3.write_bytes(native54["input_0001.bin"])
        in256=root/"in256.bin";in256.write_bytes(native54["input_0002.bin"])
        inwav=root/"in2680.bin";inwav.write_bytes(wav)

        def trial_run(label:str)->tuple[dict,dict]:
            revexe=root/(label+"_reverse")
            fwdexe=root/(label+"_forward")
            stage55.compile_public(src,HERE.parent/"stage55"/"public_reverse.cpp",
                                   revexe,args.cxx)
            stage55.compile_public(src,HERE.parent/"stage44"/"public_resampler.cpp",
                                   fwdexe,args.cxx)
            rdest=root/(label+"_reverse.f64le")
            fdest=root/(label+"_forward.f64le")
            ri,rb=stage55.execute(revexe,[
                str(in3),str(in256),str(rdest),"180.15","0","0"],rdest)
            fi,fb=stage55.execute(fwdexe,[str(inwav),str(fdest),"2680"],fdest)
            if len(rb)!=ri["total_f64"]*8 or len(fb)!=fi["output_f64"]*8:
                raise ValueError("compiled public output byte counts mismatch")
            return compare(label,ri,rb,fi,fb,native49,native54),{"reverse_info":ri,
                                                                 "forward_info":fi}

        baseline,_=trial_run("original_public")
        if (baseline["reverse_counts"]!=REVERSE_NATIVE_LENGTHS or
                baseline["forward_output_f64"]!=FORWARD_NATIVE_LENGTH or
                baseline["reverse_first32_sha256"]!=stage57.BASELINE_REVERSE_SHA or
                baseline["forward_output_sha256"]!=stage57.BASELINE_FORWARD_SHA):
            raise ValueError("Stage55 original numerical baseline cannot be reproduced")
        report["original_public"]=baseline
        for trial in TRIALS:
            patch,details=patch_header(original,trial)
            header.write_text(patch,encoding="utf-8")
            results,_=trial_run(trial)
            results["patch"]=details
            for dname in ("reverse","forward"):
                current=results[dname].get("rms_error")
                past=baseline[dname].get("rms_error")
                results[dname]["rms_improvement_factor"]=(
                    past/current if current and past is not None else None)
            report["trials"][trial]=results
            print(f"[AUDIO] {trial}: reverse {results['reverse_counts']} "
                  f"RMS={results['reverse'].get('rms_error')} "
                  f"max={results['reverse'].get('max_abs_error')} "
                  f"bit={results['reverse'].get('bit_equal')}/32; "
                  f"forward {results['forward_output_f64']} "
                  f"RMS={results['forward'].get('rms_error')} "
                  f"max={results['forward'].get('max_abs_error')} "
                  f"bit={results['forward'].get('bit_equal')}/32",flush=True)
    # Distinguish true numerical progress from merely matching rate/count geometry.
    target=report["trials"]["native_window_poly_673"]
    if any(target[path]["status"]!="COMPARED_SAME_INDEX_FIRST_32"
           for path in ("reverse","forward")):
        report["status"]="NATIVE_POLY_AUDIO_GEOMETRY_MISMATCH"
    elif target["reverse"]["rms_error"]>=baseline["reverse"]["rms_error"]*(1-1e-8) and (
         target["forward"]["rms_error"]>=baseline["forward"]["rms_error"]*(1-1e-8)):
        report["status"]="NATIVE_WINDOW_AUDIO_NO_IMPROVEMENT"
    artifacts=os.environ.get("RESEARCH_ARTIFACT_DIR")
    if artifacts:
        path=Path(artifacts);path.mkdir(parents=True,exist_ok=True)
        (path/"stage63_audio_parity.json").write_text(
            json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] Stage63: {type(exc).__name__}: {exc}",file=sys.stderr)
        raise SystemExit(2)

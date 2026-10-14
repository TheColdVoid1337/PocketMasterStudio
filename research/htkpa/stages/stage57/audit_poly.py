#!/usr/bin/env python3
"""Stage57: numerical test of the native POLYNOMIAL fractional interpolation path.

Source evidence: original 5868USB.dll V1.5.2 RVA 0x13763 uses hardcoded 673.0
phase scale; RVA 0x1376f-0x13775 computes filter block stride 72 f64;
24 source taps at r10 offsets 8..0xc0 are multiplied by quadratic polynomial
coefficients from runtime .data RVA 0x2c7560. Public v6.5/v7.2 whole-ratio
stepping chooses a different coefficient bank by default.

NO native binary modification. Always export pinned public MIT source to a
private temporary directory, patch exactly one public C++ header there, and
compile source-controlled hypotheses. All audio stays under an ephemeral
directory; only numerical metrics go to RESEARCH_ARTIFACT_DIR and tar.gz.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile

HERE=Path(__file__).resolve().parent
STAGE55=HERE.parent/"stage55"/"audit_numeric.py"
spec=importlib.util.spec_from_file_location("_htkpa57_stage55", STAGE55)
if spec is None or spec.loader is None:
    raise RuntimeError("Stage55 required")
old=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=old
spec.loader.exec_module(old)

WHOLE_STEPPING = ("IsWhole = getWholeStepping( SrcSampleRate, DstSampleRate, InStep,\n"
                  "\t\t\tOutStep );")
FRAC_COUNT = "FilterFracs = (int) ceil( pow( 6.4, ReqAtten / 50.0 ));"
BASELINE_REVERSE_SHA="1741985a4fc6c5cb1d937b9f11a262642ec3fc24a9ac615088448ecf9619ff96"
BASELINE_FORWARD_SHA=old.EXPECTED["public_full_v65"]
BASELINE_REVERSE_RMS=8.408374042995589e-05
BASELINE_FORWARD_RMS=1.2240292948462753e-09
TRIALS=("poly_default_fracs","poly_673")


def patch_frac_header(text: str, trial: str) -> tuple[str, dict]:
    """Exact-match, fail-closed patch of extracted and unmodified PUBLIC source."""
    if trial not in TRIALS:
        raise ValueError("unexpected public resampler trial")
    normalized=text.replace("\r\n","\n")
    if normalized.count(WHOLE_STEPPING)!=1 or normalized.count(FRAC_COUNT)!=1:
        raise ValueError("unrecognized upstream fractional constructor; refusing source patch")
    changed=normalized.replace(WHOLE_STEPPING,
        "IsWhole = false; // HTKPA offline controlled polynomial-mode hypothesis")
    fracs=None
    if trial=="poly_673":
        changed=changed.replace(FRAC_COUNT,
            "FilterFracs = 673; // HTKPA stage57 observed native phase index count")
        fracs=673
    if changed==normalized or "IsWhole = getWholeStepping(" in changed:
        raise ValueError("failed to force non-whole fractional stepping")
    return changed, {"is_whole":False,"forced_filter_fracs":fracs,
                     "native_assembly_fracs":673,"native_assembly_taps":24,
                     "native_interp_element_size":3,
                     "public_source_patched_only_in_temp":True}


def row_metric(native: bytes, actual: bytes, geometry: bool) -> dict:
    if not geometry:
        return {"status":"GEOMETRY_MISMATCH_NOT_COMPARABLE"}
    return old.metric(native,actual)


def factor(before: float, after: dict) -> float|None:
    rms=after.get("rms_error")
    return (before/rms if isinstance(rms,(int,float)) and rms>0 else None)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--stage54",type=Path,required=True)
    ap.add_argument("--stage49",type=Path,required=True)
    ap.add_argument("--wav",type=Path,required=True)
    ap.add_argument("--source-cache",type=Path,required=True)
    ap.add_argument("--version",choices=("v6.5","v7.2"),default="v6.5")
    ap.add_argument("--cxx",default="c++")
    args=ap.parse_args()

    native54=old.archive_bytes(args.stage54,old.EXPECTED["stage54_tar"],{
        "input_0001.bin":(24,old.EXPECTED["native_96k_first3"]),
        "input_0002.bin":(2048,old.EXPECTED["native_96k_next256"]),
        "output_0001.bin":(256,old.EXPECTED["native_48k_first32"])})
    native49=old.archive_bytes(args.stage49,old.EXPECTED["stage49_tar"],{
        "block_0001.bin":(256,old.EXPECTED["native_44k_first32"])})
    old.validate_provenance(native49,native54)
    wav=old.wav_input_2680(args.wav)
    report={"stage":57,"schema_version":1,
            "status":"POLYNOMIAL_SOURCE_HYPOTHESES_MEASURED",
            "created_utc":datetime.now(timezone.utc).isoformat(),
            "pinned_public":args.version,"pinned_commit":old.PINS[args.version],
            "native_dll_sha256":"fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa",
            "native_static_assembly":{
                "process_rva":"0x135c0","phase_scale_rva":"0x13763",
                "phase_scale_f64":673.0,
                "filter_table_rva":"0x2c7560",
                "filter_stride_f64":72,"tap_count":24,
                "hypothesis":"native uses a quadratic spline fractional filter bank even at rational rates"},
            "comparisons":{},
            "privacy":"Native/public f64 buffers only in ephemeral temp; scalar metrics in private tar capsule"}
    with tempfile.TemporaryDirectory(prefix="htkpa_stage57_private_") as temp_raw:
        work=Path(temp_raw)
        src=work/"public_source"
        src.mkdir()
        old.ensure_checkout(args.source_cache,old.PINS[args.version],src)
        orig=(src/"CDSPFracInterpolator.h").read_text(encoding="utf-8")
        in3=work/"in3.f64";in3.write_bytes(native54["input_0001.bin"])
        in256=work/"in256.f64";in256.write_bytes(native54["input_0002.bin"])
        in2680=work/"in2680.f64";in2680.write_bytes(wav)
        # Build original public code for self-consistency; a patched result
        # is not allowed to be evaluated if earlier baseline cannot replay.
        baseline_src=src
        baseline_forward=work/"base_forward"
        baseline_reverse=work/"base_reverse"
        old.compile_public(baseline_src,HERE.parent/"stage55"/"public_reverse.cpp",
                           baseline_reverse,args.cxx)
        old.compile_public(baseline_src,HERE.parent/"stage44"/"public_resampler.cpp",
                           baseline_forward,args.cxx)
        base_rinfo,base_rev=old.execute(baseline_reverse,
            [str(in3),str(in256),str(work/"base_r.bin"),"180.15","0","0"],
            work/"base_r.bin")
        base_finfo,base_fwd=old.execute(baseline_forward,
            [str(in2680),str(work/"base_f.bin"),"2680"],
            work/"base_f.bin")
        if (base_rinfo["output_f64"]!=[0,114] or old.sha(base_rev[:256])!=BASELINE_REVERSE_SHA or
                base_finfo["output_f64"]!=1067 or old.sha(base_fwd)!=BASELINE_FORWARD_SHA):
            raise RuntimeError("public v6.5/v7.2 baseline disagrees with Stage55 SHA; refusing patch comparison")
        for trial in TRIALS:
            header,provenance=patch_frac_header(orig,trial)
            (src/"CDSPFracInterpolator.h").write_text(header,encoding="utf-8")
            reverse_exe=work/("reverse_"+trial)
            forward_exe=work/("forward_"+trial)
            old.compile_public(src,HERE.parent/"stage55"/"public_reverse.cpp",
                               reverse_exe,args.cxx)
            old.compile_public(src,HERE.parent/"stage44"/"public_resampler.cpp",
                               forward_exe,args.cxx)
            reverse_info,reverse_data=old.execute(reverse_exe,
                [str(in3),str(in256),str(work/(trial+"_reverse.bin")),"180.15","0","0"],
                work/(trial+"_reverse.bin"))
            forward_info,forward_data=old.execute(forward_exe,
                [str(in2680),str(work/(trial+"_forward.bin")),"2680"],
                work/(trial+"_forward.bin"))
            reverse_metrics=row_metric(native49["block_0001.bin"],reverse_data,
                                       reverse_info["output_f64"]==[0,114])
            forward_metrics=row_metric(native54["output_0001.bin"],forward_data,
                                       forward_info["output_f64"]==1067)
            info={"public_patch":provenance,
                  "reverse_output_calls":reverse_info["output_f64"],
                  "forward_output_f64":forward_info["output_f64"],
                  "reverse":reverse_metrics,"forward":forward_metrics,
                  "reverse_rms_improvement_factor":factor(BASELINE_REVERSE_RMS,reverse_metrics),
                  "forward_rms_improvement_factor":factor(BASELINE_FORWARD_RMS,forward_metrics),
                  "public_reverse_first32_sha256":old.sha(reverse_data[:256]),
                  "public_forward_first32_sha256":old.sha(forward_data[:256])}
            report["comparisons"][trial]=info
            print(f"[TRIAL] {trial}: reverse={reverse_info['output_f64']} "
                  f"RMS={reverse_metrics.get('rms_error')} "
                  f"improve={info['reverse_rms_improvement_factor']}x; "
                  f"forward={forward_info['output_f64']} "
                  f"RMS={forward_metrics.get('rms_error')} "
                  f"improve={info['forward_rms_improvement_factor']}x",
                  flush=True)
    outfile=os.environ.get("RESEARCH_ARTIFACT_DIR")
    if outfile:
        out=Path(outfile);out.mkdir(parents=True,exist_ok=True)
        (out/"stage57_numeric.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] Stage57 {type(exc).__name__}: {exc}",file=sys.stderr)
        raise SystemExit(2)

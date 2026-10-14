#!/usr/bin/env python3
"""Stage56 OFFLINE parameter hypothesis sweep on exactly Stage55-verified native prefixes.

Purpose: test whether a constructor-parameter mismatch explains Stage55's
3.37e-4 reverse and 5.20e-9 forward native/public differences.
Uses pinned PUBLIC r8brain v6.5, private Stage49/54 archives and Sonicake WAV.
Generated wave buffers are temporary. Only aggregate numeric metrics get sealed
by tools/research_run.py into research/_LOCAL_FILES/research_runs/*.tar.gz.
No cross-correlation, arbitrary shifts, proprietary binaries in Git, or runtime hooks.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
STAGE55 = HERE.parent / "stage55" / "audit_numeric.py"
_spec = importlib.util.spec_from_file_location("_htkpa_stage55_util", STAGE55)
if _spec is None or _spec.loader is None:
    raise ImportError("Stage55 code missing")
old = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = old
_spec.loader.exec_module(old)

# Small, explicit diagnostic sweep. Tested native ratio scalar fields are fixed.
R_ATTENUATIONS=(125.46,139.73,154.05,168.21,180.15,182.1076,195.56,206.91,209.061,222.501)
R_LATENCIES=(0.0,0.5)
F_TRANSBANDS=(1.5,2.0,2.5,3.0)
F_ATTENUATIONS=(139.73,168.21,180.15,195.56,206.91)
EXPECTED_REVERSE_COUNTS=[0,114]
EXPECTED_FORWARD_COUNT=1067


def rank_key(row:dict):
    """Geometry-qualified best possible exact-index fit; no arbitrary shifting."""
    compare=row.get("metric",{})
    if compare.get("status")!="COMPARED_SAME_INDEX_FIRST_32":
        return (1, float("inf"),float("inf"),0)
    return (0,compare["rms_error"],compare["max_abs_error"],-compare["bit_equal"])


def summary(rows:list[dict], keep:int=8)->dict:
    sorted_rows=sorted(rows,key=rank_key)
    valid=sum(rank_key(row)[0]==0 for row in rows)
    return {"hypotheses_tested":len(rows),"matching_output_geometry":valid,
            "top":sorted_rows[:keep]}


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--stage54",required=True,type=Path)
    p.add_argument("--stage49",required=True,type=Path)
    p.add_argument("--wav",required=True,type=Path)
    p.add_argument("--source-cache",required=True,type=Path)
    p.add_argument("--cxx",default="c++")
    args=p.parse_args()
    native54=old.archive_bytes(args.stage54,old.EXPECTED["stage54_tar"],{
        "input_0001.bin":(24,old.EXPECTED["native_96k_first3"]),
        "input_0002.bin":(2048,old.EXPECTED["native_96k_next256"]),
        "output_0001.bin":(256,old.EXPECTED["native_48k_first32"])})
    native49=old.archive_bytes(args.stage49,old.EXPECTED["stage49_tar"],{
        "block_0001.bin":(256,old.EXPECTED["native_44k_first32"])})
    old.validate_provenance(native49,native54)
    original=old.wav_input_2680(args.wav)
    report={"stage":56,"schema_version":1,"status":"PUBLIC_CONSTRUCTOR_HYPOTHESES_TESTED",
            "created_utc":datetime.now(timezone.utc).isoformat(),
            "public_pin":"v6.5","public_commit":old.PINS["v6.5"],
            "inputs_sha_verified":True,
            "scope":"same-index 32 f64 only; parameter hypotheses not native configuration proof",
            "reverse":None,"forward":None}

    with tempfile.TemporaryDirectory(prefix="htkpa_stage56_private_") as d:
        temp=Path(d)
        src=temp/"public_source";src.mkdir()
        old.ensure_checkout(args.source_cache,old.PINS["v6.5"],src)
        reverse_exe=temp/"reverse_public"
        forward_exe=temp/"forward_public"
        old.compile_public(src,HERE.parent/"stage55"/"public_reverse.cpp",
                           reverse_exe,args.cxx)
        old.compile_public(src,HERE/"public_forward_variant.cpp",
                           forward_exe,args.cxx)
        in3=temp/"input3.bin";in3.write_bytes(native54["input_0001.bin"])
        in256=temp/"input256.bin";in256.write_bytes(native54["input_0002.bin"])
        in2680=temp/"input2680.bin";in2680.write_bytes(original)
        # Independently repeat Stage55 baseline. Abort rather than analyzing
        # mismatched build/fixture/latency conditions as a parameter effect.
        old_reverse,ob=old.execute(
            reverse_exe,[str(in3),str(in256),str(temp/"rev_base.bin"),"180.15","0","0"],
            temp/"rev_base.bin")
        old_forward,fb=old.execute(
            forward_exe,[str(in2680),str(temp/"fwd_base.bin"),"2.0","180.15","0"],
            temp/"fwd_base.bin")
        if (old_reverse["output_f64"]!=EXPECTED_REVERSE_COUNTS or
            old.sha(ob[:256]) != "1741985a4fc6c5cb1d937b9f11a262642ec3fc24a9ac615088448ecf9619ff96" or
            old_forward["output_f64"]!=EXPECTED_FORWARD_COUNT or
            old.sha(fb) != old.EXPECTED["public_full_v65"]):
            raise ValueError("Stage55 exact public baseline mismatch; refuse sweep")
        forward_rows=[]
        for t in F_TRANSBANDS:
            for a in F_ATTENUATIONS:
                output=temp/"fwd.bin"
                args2=[str(in2680),str(output),str(t),str(a),"0"]
                meta,samples=old.execute(forward_exe,args2,output)
                valid=(meta["output_f64"]==EXPECTED_FORWARD_COUNT)
                diff=(old.metric(native54["output_0001.bin"],samples)
                      if valid else {"status":"GEOMETRY_MISMATCH","f64":meta["output_f64"]})
                forward_rows.append({"transband_percent":t,"attenuation_db":a,
                                     "output_f64":meta["output_f64"],"metric":diff})
        reverse_rows=[]
        for a in R_ATTENUATIONS:
            for third in (0,1):
                for latency in R_LATENCIES:
                    output=temp/"rev.bin"
                    call=[str(in3),str(in256),str(output),str(a),
                          str(third),str(latency)]
                    meta,samples=old.execute(reverse_exe,call,output)
                    valid=(meta["output_f64"]==EXPECTED_REVERSE_COUNTS)
                    diff=(old.metric(native49["block_0001.bin"],samples)
                          if valid else {"status":"GEOMETRY_MISMATCH",
                                         "counts":meta["output_f64"]})
                    reverse_rows.append({"attenuation_db":a,"is_third":third,
                                         "previous_latency":latency,
                                         "counts":meta["output_f64"],"metric":diff})
        report["reverse"]=summary(reverse_rows)
        report["forward"]=summary(forward_rows)
        report["reference_baseline"]={
            "reverse":old.metric(native49["block_0001.bin"],ob),
            "forward":old.metric(native54["output_0001.bin"],fb)}
        report["reverse"]["top"][0]["rank_reasons"] = (
            "best among controlled public candidates; native constructor settings unknown")
        report["forward"]["top"][0]["rank_reasons"] = (
            "best among controlled public candidates; whole-stream equality untested")
        if (rank_key(report["reverse"]["top"][0])>=rank_key(
                {"metric":report["reference_baseline"]["reverse"]}) and
            rank_key(report["forward"]["top"][0])>=rank_key(
                {"metric":report["reference_baseline"]["forward"]})):
            report["status"]="NO_PARAMETER_IMPROVEMENT_OVER_STAGE55"
        print("[SWEEP] reverse:",len(reverse_rows),"candidates, matching geometry:",
              report["reverse"]["matching_output_geometry"])
        print("[SWEEP] forward:",len(forward_rows),"candidates, matching geometry:",
              report["forward"]["matching_output_geometry"])
        for direction in ("reverse","forward"):
            for row in report[direction]["top"][:3]:
                print("[TOP]",direction,
                      {k:v for k,v in row.items() if k!="metric"},
                      "RMS=",row["metric"].get("rms_error"),
                      "max=",row["metric"].get("max_abs_error"))
    destination=os.environ.get("RESEARCH_ARTIFACT_DIR")
    if destination:
        folder=Path(destination);folder.mkdir(parents=True,exist_ok=True)
        (folder/"stage56_sweep.json").write_text(
            json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as err:
        print(f"[ERROR] Stage56: {type(err).__name__}: {err}",file=sys.stderr)
        raise SystemExit(2)

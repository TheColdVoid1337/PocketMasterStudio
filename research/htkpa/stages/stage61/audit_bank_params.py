#!/usr/bin/env python3
"""Stage61: exact-index native/public coefficient-bank window parameter gate.

Only uses SHA-pinned Stage58 generated f64 bank and pinned public r8brain v6.5.
Compiles public source once, tries a finite fixed attenuation/IsThird grid,
normalizes documented upstream shuffle2_3() layout, and scores all 48,456
coefficients. Native/private audio and generated banks stay local/temp.
No production code tuning or undocumented phase alignment.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import numpy as np

HERE=Path(__file__).resolve().parent
STAGE59=HERE.parent/"stage59"/"audit_coeff.py"
spec=importlib.util.spec_from_file_location("_htkpa61_stage59",STAGE59)
if spec is None or spec.loader is None:
    raise ImportError("stage59 pinned native/public coefficient utilities required")
base=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=base
spec.loader.exec_module(base)
PIN="v6.5"
NATIVE_EXPECTED="14acac11db2295b56e7bc2693b8e9b34368e5b455be2911425bc6825fe81a601"
PUBLIC_EXPECTED="dbe44bde762d9d7b7259671e52b335f5def2d8d247996b4c43c8a2fb3319e24b"
BASELINE_RMS=0.00014383206675982235

def candidates()->list[tuple[float,int]]:
    # 41 grid values for each filter family, plus two exact prior hypotheses.
    levels=sorted(set([170.0+0.5*i for i in range(41)]+[180.15,182.1076]))
    return [(attenuation,third) for third in (0,1) for attenuation in levels]


def candidate_score(native:bytes,public:bytes)->dict:
    m=base.metrics(native,public)
    error=(np.frombuffer(native,dtype="<f8")-
           np.frombuffer(public,dtype="<f8")).reshape(673,24,3)
    by_comp=[float(np.sqrt(np.mean(error[:,:,i]**2))) for i in range(3)]
    m["component_rms"]=by_comp
    m["rms_vs_stage59_factor"]=BASELINE_RMS/m["rms_error"] if m["rms_error"] else None
    return m


def row_rank(row:dict):
    m=row["metrics"]
    return (m["rms_error"],m["max_abs_error"],-m["bit_equal"])


def run_one(executable:Path,dest:Path,atten:float,third:int)->tuple[dict,bytes|None]:
    result=subprocess.run([str(executable),str(dest),str(atten),str(third)],
                          capture_output=True,text=True)
    if result.returncode:
        raise RuntimeError("public coefficient generation failed: "+
                           result.stderr[-1800:])
    meta=json.loads(result.stdout.splitlines()[-1])
    if meta.get("geometry_ok") is not True:
        if dest.exists():
            raise ValueError("public skipped geometry but unexpectedly wrote data")
        return meta,None
    if (meta.get("bytes")!=base.BYTES or meta.get("phases")!=673 or
            meta.get("taps")!=24 or meta.get("is_third")!=third):
        raise ValueError("public bank geometry metadata contradicts expected")
    data=dest.read_bytes()
    dest.unlink()
    scalar=base.convert_public_layout(data,meta.get("layout"))
    if len(scalar)!=base.BYTES:
        raise ValueError("unexpected normalized coefficient bank size")
    return meta,scalar


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--stage58",required=True,type=Path)
    p.add_argument("--source-cache",required=True,type=Path)
    p.add_argument("--cxx",default="c++")
    args=p.parse_args()
    native,provenance=base.read_native(args.stage58)
    if base.sha(native)!=NATIVE_EXPECTED:
        raise ValueError("wrong native coefficient bank SHA for Stage61")
    report={"stage":61,"schema_version":1,
            "created_utc":datetime.now(timezone.utc).isoformat(),
            "status":"PUBLIC_BANK_PARAMETER_GRID_MEASURED",
            "native":provenance,
            "public_version":PIN,"public_commit":base.PINS[PIN],
            "scope":"84 fixed independent public attenuation/IsThird hypotheses, exact 673x24x3 geometry and SIMD normalization",
            "baseline_rms":BASELINE_RMS,
            "no_arbitrary_shifts":True,"distinct_valid_banks":[],
            "invalid_geometry_hypotheses":[],
            "total_hypotheses":len(candidates())}
    with tempfile.TemporaryDirectory(prefix="htkpa_stage61_private_") as td:
        root=Path(td)
        src=root/"public";src.mkdir()
        base.checkout(args.source_cache,base.PINS[PIN],src)
        binary=root/"public_bank_variant"
        command=[args.cxx,"-std=c++17","-O2","-fno-fast-math","-pthread",
                 "-I"+str(src),str(HERE/"public_bank_variant.cpp")]
        if (src/"r8bbase.cpp").is_file():
            command.append(str(src/"r8bbase.cpp"))
        command+=["-o",str(binary)]
        built=subprocess.run(command,capture_output=True,text=True)
        if built.returncode:
            raise RuntimeError("public bank variant compile failed: "+built.stderr[-2600:])
        # Refuse to score candidates unless unmodified Stage59 baseline can be
        # reproduced exactly from the new exporter and matching SIMD conversion.
        meta,baseline=run_one(binary,root/"bank.f64le",180.15,0)
        if baseline is None or base.sha(baseline)!=PUBLIC_EXPECTED:
            raise ValueError("public 180.15/0 baseline differs from corrected Stage59")
        old_score=candidate_score(native,baseline)
        if not math.isclose(old_score["rms_error"],BASELINE_RMS,
                            rel_tol=1e-10,abs_tol=1e-14):
            raise ValueError("baseline coefficient RMS failed to reproduce")
        rows=[]
        unique_by_sha={}
        same_reused=defaultdict(list)
        for attenuation,third in candidates():
            meta,scalar=run_one(binary,root/"bank.f64le",attenuation,third)
            record={"requested_attenuation":attenuation,"is_third":third,
                    "effective_attenuation":meta.get("effective_attenuation"),
                    "taps":meta.get("taps")}
            if scalar is None:
                report["invalid_geometry_hypotheses"].append(record)
                continue
            digest=base.sha(scalar)
            record["sha256"]=digest
            if digest not in unique_by_sha:
                score=candidate_score(native,scalar)
                unique_by_sha[digest]=score
            record["metrics"]=unique_by_sha[digest]
            same_reused[digest].append(record)
            rows.append(record)
        report["matching_geometry_count"]=len(rows)
        report["unique_coefficient_banks"]=len(unique_by_sha)
        ranked=sorted(rows,key=row_rank)
        report["top"]=ranked[:15]
        report["all_valid_hypotheses"]=[{"attenuation":v["requested_attenuation"],
                                         "is_third":v["is_third"],
                                         "effective_attenuation":v["effective_attenuation"],
                                         "sha256":v["sha256"]} for v in rows]
        report["distinct_valid_banks"]=[{
            "sha256":sha,"count_hypotheses":len(members),
            "example":{k:members[0][k] for k in
                       ("requested_attenuation","is_third","effective_attenuation")},
            "metrics":metric}
            for sha,metric in sorted(unique_by_sha.items(),
                key=lambda pair:pair[1]["rms_error"])
            for members in [same_reused[sha]]]
        best=ranked[0] if ranked else None
        if best is None:
            raise ValueError("no geometry-preserving public parameter hypothesis")
        report["best_rms_improvement_factor"]=(
            BASELINE_RMS/best["metrics"]["rms_error"]
            if best["metrics"]["rms_error"] else None)
        if best["metrics"]["rms_error"]>=BASELINE_RMS*(1-1e-8):
            report["status"]="NO_BANK_PARAMETER_IMPROVEMENT"
        print("[BANK-SCAN]",len(candidates()),"trials;",
              len(rows),"geometry-valid;",
              len(unique_by_sha),"distinct banks",flush=True)
        for record in report["top"][:5]:
            print("[TOP]",record["requested_attenuation"],
                  "third",record["is_third"],
                  "effective",record["effective_attenuation"],
                  "RMS",record["metrics"]["rms_error"],
                  "component RMS",record["metrics"]["component_rms"],
                  flush=True)
    artifacts=os.environ.get("RESEARCH_ARTIFACT_DIR")
    if artifacts:
        out=Path(artifacts);out.mkdir(parents=True,exist_ok=True)
        (out/"stage61_bank_parameter_scan.json").write_text(
            json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] Stage61 {type(exc).__name__}: {exc}",file=sys.stderr)
        raise SystemExit(2)

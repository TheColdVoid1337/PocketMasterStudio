#!/usr/bin/env python3
"""Stage60: isolate residual shape in native/public 673x72 fractional banks.

The prior Stage59 SIMD pair layout was corrected. This diagnostic compares
*unchanged* native/public scalar-layout coefficients from SHA-pinned sources.
It tests three explicit first-order explanations: global gain, uniform phase
offset, and a zero-at-endpoints phase-bulge basis. Diagnostic projections are
NOT replacements for the original filter and do NOT prove native parity.

No native DLL execution; no Frida; all coefficient arrays temporary/private.
Output includes only aggregate numerical metrics via RESEARCH_ARTIFACT_DIR.
"""
from __future__ import annotations
import argparse
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
spec=importlib.util.spec_from_file_location("_stage60_stage59",STAGE59)
if spec is None or spec.loader is None:
    raise RuntimeError("Stage59 dependencies missing")
old=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=old
spec.loader.exec_module(old)
PIN="v6.5"
EXPECTED_NATIVE_SHA="14acac11db2295b56e7bc2693b8e9b34368e5b455be2911425bc6825fe81a601"
EXPECTED_PUBLIC_SHA="dbe44bde762d9d7b7259671e52b335f5def2d8d247996b4c43c8a2fb3319e24b"
EXPECTED_BASELINE_RMS=0.00014383206675982235
NPHASES, NTAPS, NCOEFFS=673,24,3


def rms(a:np.ndarray)->float:
    return float(np.sqrt(np.mean(np.square(a,dtype=np.float64),dtype=np.float64)))


def summarize(delta:np.ndarray)->dict:
    return {"rms":rms(delta),"max_abs":float(np.max(np.abs(delta)))}


def phase_profile(native:np.ndarray, public:np.ndarray)->dict:
    n=np.asarray(native,dtype="<f8").reshape(NPHASES,NTAPS,NCOEFFS)
    p=np.asarray(public,dtype="<f8").reshape(NPHASES,NTAPS,NCOEFFS)
    if not (np.isfinite(n).all() and np.isfinite(p).all()):
        raise ValueError("non-finite coefficient")
    e=n-p
    bins=[(0,31),(32,167),(168,335),(336,504),(505,640),(641,672)]
    bins_out=[]
    for lo,hi in bins:
        bins_out.append({"phases":[lo,hi],
                         "rms":rms(e[lo:hi+1]),
                         "max_abs":float(np.max(np.abs(e[lo:hi+1])))})
    phase_ids=(0,1,2,16,100,168,336,337,504,600,671,672)
    return {
        "by_coeff":[{"component":j,**summarize(e[:,:,j])} for j in range(3)],
        "by_phase_bins":bins_out,
        "selected_phases":[{"phase":i,**summarize(e[i])} for i in phase_ids],
        "by_tap":[{"tap":i,**summarize(e[:,i,:])} for i in range(NTAPS)],
        "largest_error":{
            "phase":int(np.unravel_index(np.argmax(np.abs(e)),e.shape)[0]),
            "tap":int(np.unravel_index(np.argmax(np.abs(e)),e.shape)[1]),
            "component":int(np.unravel_index(np.argmax(np.abs(e)),e.shape)[2]),
            "absolute_error":float(np.max(np.abs(e)))},
        "native_per_phase_sum":[{"component":j,
            "sum_min":float(np.min(np.sum(n[:,:,j],axis=1))),
            "sum_max":float(np.max(np.sum(n[:,:,j],axis=1)))} for j in range(3)],
    }


def project_phase_model(native:np.ndarray,public:np.ndarray)->dict:
    """Bounded first-order projections, not numerical parity/phase alignment."""
    n=np.asarray(native,dtype="<f8").reshape(NPHASES,NTAPS,NCOEFFS)
    p=np.asarray(public,dtype="<f8").reshape(NPHASES,NTAPS,NCOEFFS)
    if not np.isfinite(n).all() or not np.isfinite(p).all():
        raise ValueError("non-finite input")
    e=n-p
    initial=summarize(e)

    norm2=float(np.sum(p*p,dtype=np.float64))
    if norm2<=0:
        raise ValueError("public bank all zeros")
    gain=float(np.sum(n*p,dtype=np.float64)/norm2)
    gain_error=summarize(n-gain*p)

    # A table position is 1/673 sample phase. For each row, centered
    # finite difference estimates how coefficients respond to a phase move.
    # Evaluate only interior rows where no endpoint extrapolation is needed.
    derivative=(p[2:]-p[:-2])*0.5
    error_interior=e[1:-1]
    def fit(basis:np.ndarray):
        v=derivative*basis[:,None,None]
        denominator=float(np.sum(v*v,dtype=np.float64))
        if denominator<=0:
            raise ValueError("zero derivative energy")
        estimate=float(np.sum(error_interior*v,dtype=np.float64)/denominator)
        # +/- one half table phase is small enough for local linearization;
        # explicitly report whether unconstrained fit exceeded the budget.
        bounded=float(np.clip(estimate,-0.5,0.5))
        residual=error_interior-bounded*v
        return {"unconstrained_delta_positions":estimate,
                "bounded_delta_positions":bounded,
                "within_half_phase":abs(estimate)<=0.5,
                "baseline_interior_rms":rms(error_interior),
                "projected_interior_rms":rms(residual),
                "improvement_factor":(rms(error_interior)/rms(residual)
                                      if rms(residual)>0 else None)}

    idx=np.arange(1,NPHASES-1,dtype=np.float64)
    x=idx/(NPHASES-1)
    uniform=fit(np.ones_like(x))
    bulge=fit(4*x*(1-x))
    # Independent fits, not combined parameter optimization or arbitrary
    # alignment. An improvement is evidence of a pattern, NOT a calibration.
    return {"original":initial,
            "gain_fit":{"gain":gain,**gain_error,
                        "rms_improvement_factor":initial["rms"]/gain_error["rms"]
                           if gain_error["rms"]>0 else None},
            "phase_offset_uniform":uniform,
            "phase_offset_zero_at_edges_bulge":bulge,
            "phase_fit_method":"linearized derivative on phases 1..671; +/-0.5 phase-position bound",
            "interpretation_limit":"diagnostic residual projection only, does not establish native phase offset"}


def compile_public(source:Path,exe:Path,cxx:str):
    cmd=[cxx,"-std=c++17","-O2","-fno-fast-math","-pthread",
         "-I"+str(source),str(HERE.parent/"stage59"/"public_frac_bank.cpp")]
    if (source/"r8bbase.cpp").is_file():
        cmd.append(str(source/"r8bbase.cpp"))
    cmd+=["-o",str(exe)]
    p=subprocess.run(cmd,capture_output=True,text=True)
    if p.returncode:
        raise RuntimeError("public bank compile failed: "+p.stderr[-1600:])


def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--stage58",type=Path,required=True)
    ap.add_argument("--source-cache",type=Path,required=True)
    ap.add_argument("--cxx",default="c++")
    args=ap.parse_args()
    native,provenance=old.read_native(args.stage58)
    if old.sha(native)!=EXPECTED_NATIVE_SHA:
        raise ValueError("native Stage58 SHA does not match corrected Stage59")
    report={"stage":60,"schema_version":1,"created_utc":datetime.now(timezone.utc).isoformat(),
            "status":"RESIDUAL_STRUCTURE_MEASURED_NOT_PARITY",
            "native":provenance,"public_commit":old.PINS[PIN],
            "baseline_from_stage59":{"normalized_rms":EXPECTED_BASELINE_RMS,
                                     "normalized_public_sha256":EXPECTED_PUBLIC_SHA},
            "scope":"coefficient matrix only; fixed phase/tap order; diagnostic projections not applied to audio"}
    with tempfile.TemporaryDirectory(prefix="htkpa_stage60_private_") as d:
        tmp=Path(d)
        src=tmp/"public";src.mkdir()
        old.checkout(args.source_cache,old.PINS[PIN],src)
        exe=tmp/"coeff_export"
        compile_public(src,exe,args.cxx)
        outfile=tmp/"public_raw.f64le"
        run=subprocess.run([str(exe),str(outfile),"180.15"],
                           capture_output=True,text=True)
        if run.returncode:
            raise RuntimeError("public coefficient run failed: "+run.stderr[-1500:])
        metadata=json.loads(run.stdout.splitlines()[-1])
        public=old.convert_public_layout(outfile.read_bytes(),metadata.get("layout"))
        if old.sha(public)!=EXPECTED_PUBLIC_SHA:
            raise ValueError("normalized public table differs from corrected Stage59")
        a=np.frombuffer(native,dtype="<f8")
        b=np.frombuffer(public,dtype="<f8")
        baseline=old.metrics(native,public)
        if not math.isclose(baseline["rms_error"],EXPECTED_BASELINE_RMS,
                            rel_tol=1e-10,abs_tol=1e-14):
            raise ValueError("Stage59 RMS baseline is not reproducible")
        report["public_memory_layout"]=metadata["layout"]
        report["baseline_reverified"]=baseline
        report["residual_profile"]=phase_profile(a,b)
        report["explicit_models"]=project_phase_model(a,b)
        print("[PROFILE] baseline RMS",baseline["rms_error"],
              "max",baseline["max_abs_error"],flush=True)
        print("[PROFILE] component RMS:",
              [x["rms"] for x in report["residual_profile"]["by_coeff"]],flush=True)
        for mode in ("phase_offset_uniform","phase_offset_zero_at_edges_bulge"):
            info=report["explicit_models"][mode]
            print("[MODEL]",mode,"delta positions",info["bounded_delta_positions"],
                  "interior RMS",info["projected_interior_rms"],flush=True)
    location=os.environ.get("RESEARCH_ARTIFACT_DIR")
    if location:
        out=Path(location);out.mkdir(parents=True,exist_ok=True)
        (out/"stage60_residual.json").write_text(
            json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0

if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] Stage60: {type(exc).__name__}: {exc}",file=sys.stderr)
        raise SystemExit(2)

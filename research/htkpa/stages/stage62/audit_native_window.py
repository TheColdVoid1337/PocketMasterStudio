#!/usr/bin/env python3
"""Stage62: test EXACT native-vs-public Kaiser beta/power on one pinned 673x72 bank.

Static native proof for ORIGINAL SHA-pinned 5868USB.dll V1.5.2:
  coefficient init RVA 0x16080:
   0x160A6 lea rbp,[RIP+...] -> DLL RVA 0x2451B0, pair table base
   0x160AD movsd xmm7,[... RVA 0x24CB38] -> 12.0 (half taps)
   0x16126 call ceil imported via IAT RVA 0x18BA30 -> ceil(12)=12
   0x16133..0x1614C table pair index = 2*(12-3) = 18
   0x1614C beta  <- [RVA 0x245240] -> 12.55262798
   0x16152 power <- [RVA 0x245248] -> 1.51553897
Public 24-tap getWinParams instead chooses beta 9.5945017884101773,
power 1.9718456992078597, effective attenuation 182.1076.

No native binary or production public source is modified. Pinned MIT r8brain
is extracted into a disposable directory, and ONLY the constructor's one
getWinParams call is overridden with two exact DLL-derived f64 constants.
Independent beta-only and power-only controls expose each contribution.
Output: scalar metrics only, sealed to private .tar.gz by research_run.py.
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
import subprocess
import sys
import tempfile
import numpy as np

HERE=Path(__file__).resolve().parent
STAGE59=HERE.parent/"stage59"/"audit_coeff.py"
spec=importlib.util.spec_from_file_location("_htkpa62_stage59",STAGE59)
if spec is None or spec.loader is None:
    raise ImportError("Stage59 source required")
base=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=base
spec.loader.exec_module(base)

PIN="v6.5"
NATIVE_SHA="14acac11db2295b56e7bc2693b8e9b34368e5b455be2911425bc6825fe81a601"
PUBLIC_BASELINE_SHA="dbe44bde762d9d7b7259671e52b335f5def2d8d247996b4c43c8a2fb3319e24b"
BASELINE_RMS=0.00014383206675982235

# These two hex float strings encode exactly the original V1.5.2 binary
# IEEE754 doubles at RVAs 0x245240 and 0x245248, respectively.
NATIVE_BETA=float.fromhex("0x1.91af20df9e8bap+3")
NATIVE_POWER=float.fromhex("0x1.83fa5ca7f6a99p+0")
PUBLIC_BETA=9.5945017884101773
PUBLIC_POWER=1.9718456992078597

GET_WINDOW_CALL=re.compile(
    r"const\s+double\s*\*\s*const\s+Params\s*=\s*getWinParams\s*\(\s*"
    r"ReqAtten\s*,\s*IsThird\s*,\s*FilterLen\s*\)\s*;")
PUBLIC_ROW_GUARD="9.5945017884101773, 1.9718456992078597, 182.1076"
TRIALS=("native_beta_only","native_power_only","native_both")


def patch_public_header(source:str,trial:str)->tuple[str,dict]:
    if trial not in TRIALS:
        raise ValueError("unrecognized coefficient patch trial")
    text=source.replace("\r\n","\n")
    if text.count(PUBLIC_ROW_GUARD)!=1:
        raise ValueError("public source parameter table pin mismatch")
    if len(GET_WINDOW_CALL.findall(text))!=1:
        raise ValueError("public getWinParams call not uniquely recognized")
    beta=NATIVE_BETA if trial in ("native_beta_only","native_both") else PUBLIC_BETA
    power=NATIVE_POWER if trial in ("native_power_only","native_both") else PUBLIC_POWER
    if not math.isfinite(beta) or not math.isfinite(power):
        raise ValueError("nonfinite controlled window parameters")
    replacement=(
        "static const double HTKPA_Stage62_Params[3] = {"
        +beta.hex()+", "+power.hex()+", 182.1076};\n"
        "        FilterLen = 24;\n"
        "        const double* const Params = HTKPA_Stage62_Params;"
    )
    patched,n=GET_WINDOW_CALL.subn(lambda m:replacement,text)
    if n!=1 or "HTKPA_Stage62_Params" not in patched:
        raise ValueError("source override failed")
    return patched,{"trial":trial,"beta":beta,"power":power,
                    "beta_f64_hex":beta.hex(),"power_f64_hex":power.hex(),
                    "native_beta_rva":"0x245240","native_power_rva":"0x245248",
                    "pin_effective_attenuation":182.1076,
                    "forced_filter_taps":24}


def analytic_c0(beta:float,power:float)->np.ndarray:
    """24-tap normalized sinc * Kaiser^power, phases 0..672 (scalar).

    Directly follows the public/natively reconstructed wftKaiser
    generateFrac pattern for the base polynomial coefficient c0.
    This independent NumPy model is NOT a bit-exact native arithmetic
    replay; compare RMS/max, never equality of IEEE754 bits.
    """
    if not math.isfinite(beta) or not math.isfinite(power) or beta<=0 or power<=0:
        raise ValueError("invalid Kaiser analytical parameters")
    phase=1.0-np.arange(673,dtype=np.float64)[:,None]/673.0
    x=np.arange(-12,12,dtype=np.float64)[None,:]+phase
    radius=np.maximum(0.0,1.0-(x/12.0)**2)
    win=np.power(np.i0(beta*np.sqrt(radius))/np.i0(beta),power)
    kernel=np.sinc(x)*win
    kernel/=kernel.sum(axis=1,keepdims=True)
    if kernel.shape!=(673,24) or not np.isfinite(kernel).all():
        raise ValueError("invalid analytical kernel")
    return kernel


def analytic_c0_comparison(native:bytes)->dict:
    n=np.frombuffer(native,dtype="<f8").reshape(673,24,3)[:,:,0]
    out={}
    for label,beta,power in (
            ("public_nominal",PUBLIC_BETA,PUBLIC_POWER),
            ("native_exact_dll",NATIVE_BETA,NATIVE_POWER)):
        delta=n-analytic_c0(beta,power)
        out[label]={"rms_error":float(np.sqrt(np.mean(delta**2))),
                    "max_abs_error":float(np.max(np.abs(delta))),
                    "normalization_max_error":float(np.max(
                        np.abs(analytic_c0(beta,power).sum(axis=1)-1.0)))}
    best=out["native_exact_dll"]["rms_error"]
    if best>1e-8:
        raise ValueError("native DLL params do not reproduce Stage58 c0 to stated bound")
    out["rms_improvement_factor"]=out["public_nominal"]["rms_error"]/best if best else None
    out["comparable_scope"]="16152 c0 coefficients only; other spline coefficients require compiled public source"
    return out


def summarize_metric(native:bytes,actual:bytes)->dict:
    m=base.metrics(native,actual)
    return {"bank_sha256":m["public_sha256"],
            "bit_equal":m["bit_equal"],"max_abs_error":m["max_abs_error"],
            "rms_error":m["rms_error"],
            "rms_improvement_vs_public":BASELINE_RMS/m["rms_error"] if m["rms_error"] else None,
            "phase_0_rms":m["row_rms_p0"],
            "phase_336_rms":m["row_rms_p336"],
            "phase_672_rms":m["row_rms_p672"]}


def compile_public(src:Path,output:Path,cxx:str):
    command=[cxx,"-std=c++17","-O2","-fno-fast-math","-pthread",
             "-I"+str(src),
             str(HERE.parent/"stage59"/"public_frac_bank.cpp")]
    if (src/"r8bbase.cpp").is_file():
        command.append(str(src/"r8bbase.cpp"))
    command.extend(["-o",str(output)])
    result=subprocess.run(command,text=True,capture_output=True)
    if result.returncode:
        raise RuntimeError("public bank compile failure: "+result.stderr[-3000:])


def generate(exe:Path,filename:Path)->tuple[dict,bytes]:
    r=subprocess.run([str(exe),str(filename),"180.15"],
                     capture_output=True,text=True)
    if r.returncode:
        raise RuntimeError("public coefficient-bank execution failed: "+r.stderr[-1500:])
    meta=json.loads(r.stdout.splitlines()[-1])
    if (meta.get("phases")!=673 or meta.get("taps")!=24
            or meta.get("element_size")!=3 or meta.get("bytes")!=base.BYTES):
        raise ValueError("public bank geometry mismatch")
    buf=base.convert_public_layout(filename.read_bytes(),meta.get("layout"))
    filename.unlink()
    if len(buf)!=base.BYTES:
        raise ValueError("normalized generated bank length mismatch")
    return meta,buf


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--stage58",type=Path,required=True)
    ap.add_argument("--source-cache",type=Path,required=True)
    ap.add_argument("--cxx",default="c++")
    args=ap.parse_args()
    native,provenance=base.read_native(args.stage58)
    if base.sha(native)!=NATIVE_SHA:
        raise ValueError("Stage58 native table SHA pin mismatch")
    report={"stage":62,"schema_version":1,
            "created_utc":datetime.now(timezone.utc).isoformat(),
            "status":"NATIVE_WINDOW_PARAMS_HYPOTHESES_MEASURED",
            "native":provenance,
            "source_commit":base.PINS[PIN],
            "hypothesis":"native/public 24-tap Kaiser beta/power lookup-table mismatch",
            "mode":"same 673x24x3; same interpolation; only constructor window pair changes",
            "source_altered_only_in_private_temp":True,
            "results":{},
            "analytic_c0":analytic_c0_comparison(native)}
    print("[ANALYTIC-C0] native-param RMS",
          report["analytic_c0"]["native_exact_dll"]["rms_error"],
          "vs public nominal RMS",
          report["analytic_c0"]["public_nominal"]["rms_error"],flush=True)
    with tempfile.TemporaryDirectory(prefix="htkpa_stage62_private_") as dir:
        root=Path(dir)
        src=root/"r8brain";src.mkdir()
        base.checkout(args.source_cache,base.PINS[PIN],src)
        header=src/"CDSPFracInterpolator.h"
        original=header.read_text(encoding="utf-8")
        # Protect against accidentally comparing unrelated source versions.
        if len(GET_WINDOW_CALL.findall(original))!=1 or original.count(PUBLIC_ROW_GUARD)!=1:
            raise ValueError("upstream window initialization changed unexpectedly")
        exe=root/"public"
        compile_public(src,exe,args.cxx)
        original_meta,original_bytes=generate(exe,root/"baseline.f64le")
        if base.sha(original_bytes)!=PUBLIC_BASELINE_SHA:
            raise ValueError("Stage59 normalized baseline SHA not reproduced")
        baseline=summarize_metric(native,original_bytes)
        if not math.isclose(baseline["rms_error"],BASELINE_RMS,
                            rel_tol=1e-12,abs_tol=1e-15):
            raise ValueError("Stage59 baseline RMS changed")
        report["public_baseline"]={"beta":PUBLIC_BETA,"power":PUBLIC_POWER,
                                   "metadata":original_meta,"metrics":baseline}
        for trial in TRIALS:
            modified,params=patch_public_header(original,trial)
            header.write_text(modified,encoding="utf-8")
            compile_public(src,exe,args.cxx)
            metadata,bytes_public=generate(exe,root/(trial+".f64le"))
            result={"window":params,"compiled_public_layout":metadata.get("layout"),
                    "metrics":summarize_metric(native,bytes_public)}
            report["results"][trial]=result
            m=result["metrics"]
            print(f"[WINDOW] {trial}: exact={m['bit_equal']}/{base.N} "
                  f"RMS={m['rms_error']:.17g}, "
                  f"max={m['max_abs_error']:.17g}, "
                  f"RMS improvement={m['rms_improvement_vs_public']}",flush=True)
        best=min(report["results"],key=lambda x:report["results"][x]["metrics"]["rms_error"])
        report["best_trial"]=best
        if report["results"][best]["metrics"]["rms_error"]>=BASELINE_RMS*(1-1e-9):
            report["status"]="NATIVE_WINDOW_PARAMS_DID_NOT_IMPROVE"
    output=os.environ.get("RESEARCH_ARTIFACT_DIR")
    if output:
        path=Path(output);path.mkdir(parents=True,exist_ok=True)
        (path/"stage62_native_window.json").write_text(
            json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"[ERROR] Stage62: {type(error).__name__}: {error}",file=sys.stderr)
        raise SystemExit(2)

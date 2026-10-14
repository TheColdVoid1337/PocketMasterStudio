#!/usr/bin/env python3
"""Stage65 offline full bounded native/public fractional AUDIO parity gate.

Stage64 captures 1067 f64 forward and 114 f64 reverse outputs from one
Sonicake NAM->CLO conversion under SHA/vtable/observed-call guards.
Replay exactly the Stage54 [3,256] native 96k input and first 2680 WAV f64
against public r8brain v6.5 compiled with proven original DLL:
  Kaiser beta=12.55262798, power=1.51553897,
  IsWhole=false, FilterFracs=673, 24 taps, quadratic interpolation.
Compare ALL 1181 samples by their natural zero-based output index. No alignment
search, time offsets, model training, or proprietary runtime execution.
Reports scalar metrics only; original/private audio stays in temporary files.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import sys
import tarfile
import tempfile

HERE=Path(__file__).resolve().parent


def load_module(label:str,path:Path):
    spec=importlib.util.spec_from_file_location(label,path)
    if spec is None or spec.loader is None:
        raise ImportError("prior-stage module missing: "+str(path))
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module


prior=load_module("_htkpa65_stage63",HERE.parent/"stage63"/"audit_audio_parity.py")
stage55=prior.stage55
stage57=prior.stage57
FILE_NAMES={"forward":"forward_1067.f64le.bin",
            "reverse":"reverse_114.f64le.bin"}
FIRST_32={
    "forward":"6221729cf455706ac4b5ab9bedbada953836089ae2399d10fc6c87de3f4a1782",
    "reverse":"65b48ee4d3a6b0f86f8ab539761f45d52fc5799a7ce8a4e88b86c215eb0b6dae",
}
LONG_EXPECTED={
    "forward":{"observed":1,"input_f64":6170612,
               "output_f64":3358150,"copied_f64":1067,
               "numerator":88200,"denominator":48000},
    "reverse":{"observed":18,"input_f64":256,
               "output_f64":114,"copied_f64":114,
               "numerator":96000,"denominator":44100},
    "total_max_bytes":9448,
}
STAGE63_SHA="4b4f1452551b11019b57ff76267f81770061bb02707b26ca6d3dbc119b1dc04e"
PATCH_FIRST32={
    "forward":"d0adb870014d5d9e89245cf2aaf7b068de0b99e2923a51b080eafe3361b60555",
    "reverse":"c0c4cc48b1142e7bfa6868449691776538e2e75f2ef4d1ead54477218690fc6a",
}


def read_extended(archive:Path)->tuple[dict[str,bytes],dict]:
    with tarfile.open(archive,"r:gz") as t:
        names=t.getnames()
        if len(names)!=len(set(names)):
            raise ValueError("duplicate native Frida tar member")
        root="frida_capture/"
        cfg=json.load(t.extractfile(root+"config.json"))
        manifest=json.load(t.extractfile(root+"manifest.json"))
        events=[json.loads(row) for row in
                t.extractfile(root+"events.jsonl").read().splitlines() if row]
        if (cfg.get("mode")!="guarded_fractional_io" or
                cfg.get("sha256")!="fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa" or
                cfg.get("sites",[{}])[0].get("rva")!=0x135c0 or
                cfg.get("long_probe")!=LONG_EXPECTED or
                manifest.get("status")!="FRACTIONAL_EXTENDED_OUTPUTS_CLO_STABLE" or
                manifest.get("completion_verified") is not True or
                manifest.get("hook_count")!=1 or
                manifest.get("process_cleanup_status")!="CLOSED_GRACEFULLY"):
            raise ValueError("Stage64 runtime config/guard/completion provenance mismatch")
        relevant=[e for e in events if e.get("kind")=="fractional_extended_output"]
        if len(relevant)!=2:
            raise ValueError("Stage64 expected exactly two native extended output events")
        data={}
        owners=set()
        for e in relevant:
            side=e.get("side")
            if side not in FILE_NAMES or side in data or e.get("valid") is not True:
                raise ValueError("unknown or duplicate Stage64 output side")
            spec=LONG_EXPECTED[side]
            if (e.get("site")!=cfg["sites"][0]["name"] or
                    e.get("observed")!=spec["observed"] or
                    e.get("input_f64")!=spec["input_f64"] or
                    e.get("output_f64")!=spec["output_f64"] or
                    e.get("copied_f64")!=spec["copied_f64"] or
                    e.get("copied_bytes")!=spec["copied_f64"]*8 or
                    e.get("rate_numerator")!=spec["numerator"] or
                    e.get("rate_denominator")!=spec["denominator"] or
                    e.get("first32_sha256")!=FIRST_32[side] or
                    e.get("provenance")!="fractional_r9_ref_onleave_extended" or
                    e.get("file")!=FILE_NAMES[side]):
                raise ValueError("Stage64 output call geometry or native prefix mismatch")
            owner=e.get("processor_pointer")
            if (not isinstance(owner,str) or not owner.startswith("0x")
                    or owner in owners):
                raise ValueError("Stage64 native processor pointers should be distinct")
            owners.add(owner)
            member=t.getmember(root+FILE_NAMES[side])
            if not member.isfile() or member.size!=spec["copied_f64"]*8:
                raise ValueError("Stage64 output member size mismatch")
            buf=t.extractfile(member).read()
            if (len(buf)!=spec["copied_f64"]*8 or
                    stage55.sha(buf)!=e.get("sha256") or
                    stage55.sha(buf[:256])!=FIRST_32[side]):
                raise ValueError("Stage64 output SHA/prefix mismatch")
            values=struct.unpack("<"+str(spec["copied_f64"])+"d",buf)
            if not all(math.isfinite(val) for val in values):
                raise ValueError("nonfinite Stage64 original f64")
            data[side]=buf
        if len(data)!=2 or sum(map(len,data.values()))!=9448:
            raise ValueError("Stage64 9448-byte total is not exact")
        return data,{"archive_sha256":stage55.sha(archive.read_bytes()),
                     "native_forward_sha256":stage55.sha(data["forward"]),
                     "native_reverse_sha256":stage55.sha(data["reverse"]),
                     "native_f64_total":1181}


def read_stage63(path:Path)->dict:
    if stage55.sha(path.read_bytes())!=STAGE63_SHA:
        raise ValueError("Stage63 input artifact SHA mismatch")
    with tarfile.open(path,"r:gz") as t:
        obj=json.load(t.extractfile("output/stage63_audio_parity.json"))
        run=json.load(t.extractfile("run.json"))
    if run.get("status")!="SUCCEEDED" or obj.get("status")!="NATIVE_WINDOW_AUDIO_PREFIXES_COMPARED":
        raise ValueError("Stage63 result is not verified")
    entry=obj["trials"]["native_window_poly_673"]
    for side in ("forward","reverse"):
        if (entry["reverse_first32_sha256"] if side=="reverse"
                else entry["forward_first32_sha256"])!=PATCH_FIRST32[side]:
            raise ValueError("Stage63 public first32 pin mismatch")
        if entry[side].get("status")!="COMPARED_SAME_INDEX_FIRST_32":
            raise ValueError("Stage63 did not validate native sample indices")
    return {"archive_sha256":STAGE63_SHA,
            "forward_rms_first32":entry["forward"]["rms_error"],
            "reverse_rms_first32":entry["reverse"]["rms_error"]}


def detailed_metrics(native:bytes,public:bytes,count:int)->dict:
    if len(native)!=count*8 or len(public)!=count*8:
        raise ValueError("extended coefficient/audio block length mismatch")
    n=struct.unpack("<"+str(count)+"d",native)
    p=struct.unpack("<"+str(count)+"d",public)
    if not all(math.isfinite(x) for x in (*n,*p)):
        raise ValueError("non-finite input/output for extended comparison")
    def segment(start:int,end:int):
        left=n[start:end]
        right=p[start:end]
        d=[a-b for a,b in zip(left,right)]
        err=math.sqrt(math.fsum(x*x for x in d)/len(d))
        return {"range":[start,end-1],"f64":len(d),
                "rms_error":err,"max_abs_error":max(abs(x) for x in d),
                "bit_equal":sum(native[i*8:(i+1)*8]==public[i*8:(i+1)*8]
                                for i in range(start,end))}
    ranges=([(0,32),(32,256),(256,512),(512,count)] if count==1067
            else [(0,32),(32,64),(64,count)])
    result=segment(0,count)
    native_rms=math.sqrt(math.fsum(x*x for x in n)/count)
    result.update({"public_sha256":stage55.sha(public),
                   "native_sha256":stage55.sha(native),
                   "native_rms":native_rms,
                   "relative_rms_error":result["rms_error"]/native_rms if native_rms else None,
                   "segments":[segment(a,b) for a,b in ranges],
                   "alignment":"same-index original native/public no shift"})
    return result


def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--stage64",required=True,type=Path)
    ap.add_argument("--stage63",required=True,type=Path)
    ap.add_argument("--stage62",required=True,type=Path)
    ap.add_argument("--stage54",required=True,type=Path)
    ap.add_argument("--stage49",required=True,type=Path)
    ap.add_argument("--wav",required=True,type=Path)
    ap.add_argument("--source-cache",required=True,type=Path)
    ap.add_argument("--cxx",default="c++")
    args=ap.parse_args()
    long,provenance=read_extended(args.stage64)
    earlier=read_stage63(args.stage63)
    coeff=prior.check_stage62(args.stage62)
    native54=stage55.archive_bytes(args.stage54,stage55.EXPECTED["stage54_tar"],{
        "input_0001.bin":(24,stage55.EXPECTED["native_96k_first3"]),
        "input_0002.bin":(2048,stage55.EXPECTED["native_96k_next256"]),
        "output_0001.bin":(256,stage55.EXPECTED["native_48k_first32"])})
    native49=stage55.archive_bytes(args.stage49,stage55.EXPECTED["stage49_tar"],{
        "block_0001.bin":(256,stage55.EXPECTED["native_44k_first32"])})
    stage55.validate_provenance(native49,native54)
    wav=stage55.wav_input_2680(args.wav)
    report={"stage":65,"schema_version":1,"created_utc":datetime.now(timezone.utc).isoformat(),
            "status":"EXTENDED_AUDIO_PARITY_MEASURED",
            "native_capture":provenance,
            "stage62_bank_gate":coeff,
            "stage63_first32_gate":earlier,
            "public_commit":stage55.PINS["v6.5"],
            "scope":"original native/public 114 reverse +1067 forward f64, no shifts",
            "comparisons":{}}
    with tempfile.TemporaryDirectory(prefix="htkpa_stage65_private_") as directory:
        root=Path(directory)
        source=root/"public";source.mkdir()
        stage55.ensure_checkout(args.source_cache,stage55.PINS["v6.5"],source)
        header=source/"CDSPFracInterpolator.h"
        original=header.read_text(encoding="utf-8")
        in3=root/"in3.f64";in3.write_bytes(native54["input_0001.bin"])
        in256=root/"in256.f64";in256.write_bytes(native54["input_0002.bin"])
        inwav=root/"in2680.f64";inwav.write_bytes(wav)
        def run(label:str)->tuple[dict,dict]:
            rev_exe=root/(label+"_reverse")
            fwd_exe=root/(label+"_forward")
            stage55.compile_public(source,HERE.parent/"stage55"/"public_reverse.cpp",rev_exe,args.cxx)
            stage55.compile_public(source,HERE.parent/"stage44"/"public_resampler.cpp",fwd_exe,args.cxx)
            rdest=root/(label+"_rev.f64")
            fdest=root/(label+"_fwd.f64")
            ri,rb=stage55.execute(rev_exe,[
                str(in3),str(in256),str(rdest),"180.15","0","0"],rdest)
            fi,fb=stage55.execute(fwd_exe,[str(inwav),str(fdest),"2680"],fdest)
            if (ri["output_f64"]!=[0,114] or fi["output_f64"]!=1067):
                raise ValueError("native/public output geometry mismatch")
            if len(rb)!=114*8 or len(fb)!=1067*8:
                raise ValueError("unexpected public f64 byte length")
            return {"reverse":detailed_metrics(long["reverse"],rb,114),
                    "forward":detailed_metrics(long["forward"],fb,1067)},{
                    "reverse_full_sha256":stage55.sha(rb),
                    "forward_full_sha256":stage55.sha(fb)}
        baseline,base_digests=run("original")
        if (stage55.sha(bytes.fromhex("")) is None or
                baseline["reverse"]["public_sha256"]!=
                    "601a107e28c552085cef213e911de3373189128c5f91e5c430825805066915e7" or
                baseline["forward"]["public_sha256"]!=
                    "d1e7fde902ba117da0536ecbe1d4a4fde0a4a8918e3d02883187a8a63f27e6e1"):
            raise ValueError("Stage55 full original public output baseline is no longer reproducible")
        patched,details=prior.patch_header(original,"native_window_poly_673")
        header.write_text(patched,encoding="utf-8")
        matched,digests=run("native_673")
        for side in ("forward","reverse"):
            if stage55.sha(bytes.fromhex("")) is None:
                raise RuntimeError("unreachable hash safety assertion")
            # Confirm Stage63 first32 public sample identity before scoring
            # the additional 82/1035 samples.
            spec=matched[side]["segments"][0]
            if (spec["rms_error"]!=earlier[side+"_rms_first32"] or
                    matched[side]["public_sha256"]!=digests[side+"_full_sha256"]):
                raise ValueError("Stage63 first32 public output differs from Stage65 replay")
            if side=="forward":
                if matched[side]["segments"][0]["f64"]!=32:
                    raise ValueError("forward segment geometry mismatch")
        report["comparisons"]={"original_public":baseline,
                                "native_window_poly_673":matched}
        report["patch"]=details
        for side in ("reverse","forward"):
            past=baseline[side]["rms_error"]
            now=matched[side]["rms_error"]
            report["comparisons"]["native_window_poly_673"][side]["rms_improvement_factor"]=(
                past/now if now else None)
            print(f"[EXTENDED] {side}: f64={matched[side]['f64']} "
                  f"bit_equal={matched[side]['bit_equal']} "
                  f"RMS={now:.17g} max={matched[side]['max_abs_error']:.17g} "
                  f"relative_RMS={matched[side]['relative_rms_error']:.4g} "
                  f"improvement={past/now if now else None}",flush=True)
        if matched["reverse"]["rms_error"]<=1e-14 and matched["forward"]["rms_error"]<=1e-16:
            report["status"]="EXTENDED_OUTPUTS_NEAR_F64_PRECISION"
        else:
            report["status"]="EXTENDED_OUTPUTS_NUMERIC_MISMATCH"
    destination=os.environ.get("RESEARCH_ARTIFACT_DIR")
    if destination:
        folder=Path(destination);folder.mkdir(parents=True,exist_ok=True)
        (folder/"stage65_extended_parity.json").write_text(
            json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] Stage65: {type(exc).__name__}: {exc}",file=sys.stderr)
        raise SystemExit(2)

#!/usr/bin/env python3
"""HTKPA Stage55: OFFLINE native/public r8brain numerical comparisons.

Read only user-private tar captures and Sonicake's SHA-pinned built-in WAV.
Public C++ code is extracted from user's existing pinned bare git cache.
All generated audio and build products are temporary; only scalar metrics
may be written under RESEARCH_ARTIFACT_DIR (sealed by research_run.py).
Never claims native/public parity from a rate or count match alone.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
import wave

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PINS = {
    "v6.5": "3c930bf6825c0cfea4a813210c83b1a650c820b5",
    "v7.2": "8fff6f3db26f14a8f5e8fb871000613673db5753",
}
EXPECTED = {
    "stage54_tar": "d2275640d357bca7b03ed413c464037eb07f8abb1a4a6d75a2b54ced8b8181a8",
    "stage49_tar": "7c375c3ee25abf6f57632c966a11c21514fe38605384bab2aab264831a6ba837",
    "wav": "9bb6c1b136dfbeb7538a6060499d98c89342b76ec568b76836e36ab98b29aa1a",
    "wav_input_2680": "9519d98a65e88f0858819a2579202768c945f9b9604ae4cd9fc656162d173acf",
    "native_96k_first3": "df36dcda32dbed569581efe826190733e83d41cff2f48850ace5f033c98470d6",
    "native_96k_next256": "9136f8dd141fac2efa13e1addcac2e7fc004a52140fa57498fe3c88ff325471c",
    "native_48k_first32": "6221729cf455706ac4b5ab9bedbada953836089ae2399d10fc6c87de3f4a1782",
    "native_44k_first32": "65b48ee4d3a6b0f86f8ab539761f45d52fc5799a7ce8a4e88b86c215eb0b6dae",
    "public_full_v65": "d1e7fde902ba117da0536ecbe1d4a4fde0a4a8918e3d02883187a8a63f27e6e1",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_sha(data: bytes, expected: str, label: str) -> None:
    actual = sha(data)
    if actual != expected:
        raise ValueError(f"{label} SHA mismatch: expected {expected}, got {actual}")


def archive_bytes(path: Path, expected_sha: str, parts: dict[str, tuple[int, str]]):
    assert_sha(path.read_bytes(), expected_sha, path.name)
    result = {}
    with tarfile.open(path, "r:gz") as t:
        inventory = t.getnames()
        if len(inventory) != len(set(inventory)):
            raise ValueError("duplicate tar archive member")
        for name, (length, digest) in parts.items():
            member = t.getmember("frida_capture/" + name)
            if not member.isfile() or member.size != length:
                raise ValueError("missing or wrong native data: " + name)
            data = t.extractfile(member).read()
            assert_sha(data, digest, name)
            result[name] = data
        config = json.loads(t.extractfile("frida_capture/config.json").read())
        manifest = json.loads(t.extractfile("frida_capture/manifest.json").read())
        events = [json.loads(line) for line in
                  t.extractfile("frida_capture/events.jsonl").read().splitlines() if line]
        if not (manifest.get("completion_verified") and
                manifest.get("process_cleanup_status")=="CLOSED_GRACEFULLY" and
                manifest.get("hook_count")==1):
            raise ValueError("unverified native runtime capture")
        result["config"], result["manifest"], result["events"] = config, manifest, events
    return result


def validate_provenance(old: dict, new: dict) -> None:
    if new["manifest"].get("status") != "FRACTIONAL_PAIRED_PREFIXES_CLO_STABLE":
        raise ValueError("Stage54 incomplete")
    if (new["config"].get("sites", [{}])[0].get("rva") != 0x135c0 or
        new["config"].get("input_probe", {}).get("total_max_bytes") != 2072 or
        new["config"].get("output_probe", {}).get("total_max_bytes") != 256):
        raise ValueError("Stage54 descriptor is not expected")
    observations = {e.get("kind"):[] for e in new["events"]}
    for e in new["events"]:
        observations.setdefault(e.get("kind"),[]).append(e)
    ins=observations.get("fractional_input_prefix",[])
    outs=observations.get("fractional_output_prefix",[])
    if (len(ins)!=2 or len(outs)!=1 or [e.get("step") for e in ins]!=[1,2] or
            [e.get("observed") for e in ins]!=[17,18] or
            outs[0].get("observed")!=1 or
            ins[0].get("processor_pointer")!=ins[1].get("processor_pointer") or
            ins[0].get("processor_pointer")==outs[0].get("processor_pointer")):
        raise ValueError("native I/O events do not establish intended distinct processor provenance")
    if old["manifest"].get("status") not in (
        "NATIVE_48K_SAMPLES_CAPTURED_CLO_STABLE", "BLOCKED_AFTER_METADATA"):
        raise ValueError("Stage49 native prefix was not a verified event")
    binary=[e for e in old["events"] if e.get("kind")=="binary_hit"]
    if len(binary)!=1 or binary[0].get("observed")!=18:
        raise ValueError("Stage49 output is not the expected first observed positive 96k->44.1 call")


def wav_input_2680(path: Path) -> bytes:
    assert_sha(path.read_bytes(), EXPECTED["wav"], "Manager built-in WAV")
    with wave.open(str(path), "rb") as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate(),
            w.getnframes()) != (2, 2, 44100, 3087000):
            raise ValueError("built-in WAV geometry mismatch")
        interleaved = struct.unpack("<" + "h"*5360, w.readframes(2680))
    if any(interleaved[i]!=interleaved[i+1] for i in range(0,5360,2)):
        raise ValueError("stereo input channels differ")
    binary = struct.pack("<2680d", *(interleaved[i]/32768.0 for i in range(0,5360,2)))
    assert_sha(binary, EXPECTED["wav_input_2680"], "Stage44 input prefix")
    return binary


def ensure_checkout(cache: Path, commit: str, dest: Path) -> None:
    if not (cache/"HEAD").is_file() or not (cache/"objects").is_dir():
        raise FileNotFoundError("Pinned public source cache absent; re-run Stage41 source bootstrap")
    rev = subprocess.run(["git","-C",str(cache),"rev-parse",commit+"^{commit}"],
                         text=True,capture_output=True,check=True).stdout.strip()
    if rev!=commit:
        raise ValueError("public source commit mismatch")
    tar = subprocess.run(["git","-C",str(cache),"archive","--format=tar",commit],
                         capture_output=True,check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar),mode="r:") as src:
        src.extractall(dest,filter="data")


def compile_public(src: Path, file: Path, exe: Path, cxx: str) -> None:
    command = [cxx,"-std=c++17","-O2","-fno-fast-math","-pthread",
               "-I"+str(src),str(file)]
    if (src/"r8bbase.cpp").is_file():
        command.append(str(src/"r8bbase.cpp"))
    command.extend(["-o",str(exe)])
    run = subprocess.run(command,text=True,capture_output=True)
    if run.returncode:
        raise RuntimeError("public r8brain compile failure: "+run.stderr[-2800:])


def execute(exe: Path, args: list[str], dest: Path):
    result = subprocess.run([str(exe),*args],capture_output=True,text=True)
    if result.returncode:
        raise RuntimeError(f"public {exe.name} failure: {result.stderr[-2800:]}")
    info=json.loads(result.stdout.splitlines()[-1])
    return info, dest.read_bytes()


def metric(native: bytes, public: bytes):
    """Same-index first 32 f64 comparison; NEVER search an arbitrary offset."""
    if len(native)!=256 or len(public)<256 or len(public)%8:
        return {"status":"UNALIGNED_OR_TOO_SHORT","native_bytes":len(native),
                "public_bytes":len(public)}
    x=struct.unpack("<32d",native)
    y=struct.unpack("<32d",public[:256])
    delta=[a-b for a,b in zip(x,y)]
    if not all(math.isfinite(v) for v in (*x,*y,*delta)):
        raise ValueError("non-finite comparison data")
    sq=math.fsum(d*d for d in delta)/32
    return {"status":"COMPARED_SAME_INDEX_FIRST_32","f64":32,
            "bit_equal":sum(native[i:i+8]==public[i:i+8] for i in range(0,256,8)),
            "max_abs_error":max(abs(d) for d in delta),
            "rms_error":math.sqrt(sq),
            "native_peak":max(abs(v) for v in x),
            "public_first32_sha256":sha(public[:256]),
            "native_first32_sha256":sha(native)}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--stage54",type=Path,required=True)
    ap.add_argument("--stage49",type=Path,required=True)
    ap.add_argument("--wav",type=Path,required=True)
    ap.add_argument("--source-cache",type=Path,required=True)
    ap.add_argument("--cxx",default="c++")
    args=ap.parse_args()
    work_out=os.environ.get("RESEARCH_ARTIFACT_DIR")
    new=archive_bytes(args.stage54,EXPECTED["stage54_tar"],{
        "input_0001.bin":(24,EXPECTED["native_96k_first3"]),
        "input_0002.bin":(2048,EXPECTED["native_96k_next256"]),
        "output_0001.bin":(256,EXPECTED["native_48k_first32"])})
    old=archive_bytes(args.stage49,EXPECTED["stage49_tar"],{
        "block_0001.bin":(256,EXPECTED["native_44k_first32"])})
    validate_provenance(old,new)
    original=wav_input_2680(args.wav)
    report={"stage":55,"schema_version":1,"status":"OFFLINE_NUMERIC_MEASURED",
            "date_utc":datetime.now(timezone.utc).isoformat(),
            "native_archives_verified":True,
            "wav_input_sha256":sha(original),"native_44k_sha256":EXPECTED["native_44k_first32"],
            "native_48k_sha256":EXPECTED["native_48k_first32"],
            "comparisons":{},"assumptions":{
                "public_reverse":"CDSPFracInterpolator(96000,44100,180.15,false,0) on 3 then 256 native input f64",
                "public_forward":"CDSPResampler(44100,48000,2680,2.0,180.15,linear) on first 2680 normalized WAV f64",
                "alignment":"same initial output sample index, no cross-correlation shift search",
                "scope":"Fractional/rate numerical parity only, not NAM fitting or CLO export"}}
    with tempfile.TemporaryDirectory(prefix="htkpa_stage55_offline_") as rawtemp:
        temp=Path(rawtemp)
        in3=temp/"native3.f64le";in3.write_bytes(new["input_0001.bin"])
        in256=temp/"native256.f64le";in256.write_bytes(new["input_0002.bin"])
        wav2680=temp/"wav2680.f64le";wav2680.write_bytes(original)
        for version, commit in PINS.items():
            build=temp/version;build.mkdir()
            src=build/"source";src.mkdir()
            ensure_checkout(args.source_cache,commit,src)
            reversed_exe=build/"public_reverse"
            forward_exe=build/"public_forward"
            compile_public(src,HERE/"public_reverse.cpp",reversed_exe,args.cxx)
            compile_public(src,HERE.parent/"stage44"/"public_resampler.cpp",forward_exe,args.cxx)
            backward_out=build/"reverse_out.f64le"
            forward_out=build/"forward_out.f64le"
            reverse_info,backward=execute(reversed_exe,
                [str(in3),str(in256),str(backward_out),"180.15","0","0"],backward_out)
            forward_info,forward=execute(forward_exe,
                [str(wav2680),str(forward_out),"2680"],forward_out)
            if len(backward)!=reverse_info["total_f64"]*8 or len(forward)!=forward_info["output_f64"]*8:
                raise ValueError("public output length contradicts C++ metadata")
            reverse_ok=(reverse_info["output_f64"]==[0,114])
            forward_ok=(forward_info["output_f64"]==1067)
            row={"pinned_commit":commit,"reverse_counts":reverse_info["output_f64"],
                 "forward_f64":forward_info["output_f64"],
                 "reverse_count_geometry_match":reverse_ok,
                 "forward_count_geometry_match":forward_ok,
                 "reverse_prefix":(metric(old["block_0001.bin"],backward) if reverse_ok
                                   else {"status":"GEOMETRY_MISMATCH_NO_SAMPLE_PARITY",
                                         "expected":[0,114],"actual":reverse_info["output_f64"]}),
                 "forward_prefix":(metric(new["output_0001.bin"],forward) if forward_ok
                                   else {"status":"GEOMETRY_MISMATCH_NO_SAMPLE_PARITY",
                                         "expected":1067,"actual":forward_info["output_f64"]}),
                 "forward_whole_sha256":sha(forward)}
            if version=="v6.5":
                row["stage44_original_public_sha_match"]=(sha(forward)==EXPECTED["public_full_v65"])
            print(f"[MEASURE] {version} reverse {row['reverse_counts']} "
                  f"maxerr={row['reverse_prefix'].get('max_abs_error')} "
                  f"forward {row['forward_f64']} "
                  f"maxerr={row['forward_prefix'].get('max_abs_error')}",flush=True)
            report["comparisons"][version]=row
    if report["comparisons"]["v6.5"]["stage44_original_public_sha_match"] is False:
        report["status"]="PUBLIC_BASELINE_MISMATCH_REVIEW_REQUIRED"
    elif any(not row["reverse_count_geometry_match"] or not row["forward_count_geometry_match"]
             for row in report["comparisons"].values()):
        report["status"]="COUNT_GEOMETRY_MISMATCH_NO_NUMERIC_PARITY"
    if work_out:
        output=Path(work_out)
        output.mkdir(parents=True,exist_ok=True)
        (output/"stage55_metrics.json").write_text(
            json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"[ERROR] Stage55: {type(e).__name__}: {e}",file=sys.stderr)
        raise SystemExit(2)

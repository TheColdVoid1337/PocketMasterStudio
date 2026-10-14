#!/usr/bin/env python3
"""Stage66: build & VERIFY a reusable original-compatible fractional C ABI.

Target application is browser-only: this is an isolated native reference
module for future WASM/JS port and independently confirms stream state.
The proprietary DLL, waveform payload and generated .so NEVER enter Git.
Pinned MIT r8brain v6.5 is checked out only under a private temp directory.
An exact-match checked source edit supplies proven V1.5.2 Kaiser beta/power,
forced 673-phase polynomial fractional interpolation (Stage62/63).

Mode 1: CDSPFracInterpolator 96000->44100.
Mode 2: CDSPResampler 44100->48000 (2% / 180.15 dB / linear).
Against Stage64 real native 114+1067 f64, confirm count, position, max/RMS
error; check true streaming chunk invariance and reset. No time-shift fitting.
"""
from __future__ import annotations
import argparse
import ctypes
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
STAGES=HERE.parent/"stages"
sys.path.insert(0,str(STAGES/"stage65"))
import audit_extended as stage65  # noqa: E402
stage55=stage65.stage55
stage63=stage65.prior
PIN="v6.5"
API_ID="r8brain-v6.5__sonicake-1.5.2__kaiser12.55262798_1.51553897__poly673"
MODE_REVERSE=1
MODE_FORWARD=2
EXPECTED_PATCHED_FULL_SHA={
    "reverse":"bd2d5357a1bf2b92f11e8e5cad4852099aa0ae61cce350881d7f6b5eecea47cf",
    "forward":"6e11c948aee2f15ac0a613d8f0c1a3f8865d789d6f5bde93d3d09495014da5a7"}
# Count and relative-error bounds were established independently in Stage65.
EXPECTED_NATIVE_COUNTS={"reverse":114,"forward":1067}
MAX_ACCEPT_RMS={"reverse":1e-14,"forward":1e-16}


def compile_bridge(source:Path,output:Path,cxx:str)->dict:
    header=source/"CDSPFracInterpolator.h"
    original=header.read_text(encoding="utf-8")
    patched,details=stage63.patch_header(original,"native_window_poly_673")
    # Fail closed if any upstream version diverges from the pinned constructor.
    if (patched==original or patched.count("HTKPA_Stage62_Params")!=2 or
            "FilterFracs = 673;" not in patched or "IsWhole = false;" not in patched):
        raise ValueError("original-compatible pinned public source patch failed")
    header.write_text(patched,encoding="utf-8")
    cmd=[cxx,"-std=c++17","-O2","-fno-fast-math","-pthread",
         "-fPIC","-shared","-I"+str(source),
         str(HERE/"htkpa_native_frac_bridge.cpp")]
    if (source/"r8bbase.cpp").is_file():
        cmd.append(str(source/"r8bbase.cpp"))
    cmd+=["-o",str(output)]
    p=subprocess.run(cmd,text=True,capture_output=True)
    if p.returncode:
        raise RuntimeError("failed to compile original-compatible C ABI: "+p.stderr[-3500:])
    return {"source_commit":stage55.PINS[PIN],
            "bridge_source_sha256":hashlib.sha256(
                (HERE/"htkpa_native_frac_bridge.cpp").read_bytes()).hexdigest(),
            "patch":details,
            "compiler_command_has_fast_math":False,
            "compiled_library_sha256":hashlib.sha256(output.read_bytes()).hexdigest()}


def bind_abi(library:Path):
    dl=ctypes.CDLL(str(library))
    dl.htkpa_v1_id.restype=ctypes.c_char_p
    dl.htkpa_v1_open.argtypes=[ctypes.c_int]
    dl.htkpa_v1_open.restype=ctypes.c_void_p
    dl.htkpa_v1_min_output_capacity.argtypes=[ctypes.c_void_p,ctypes.c_int]
    dl.htkpa_v1_min_output_capacity.restype=ctypes.c_int
    dl.htkpa_v1_process.argtypes=[
        ctypes.c_void_p,ctypes.POINTER(ctypes.c_double),ctypes.c_int,
        ctypes.POINTER(ctypes.c_double),ctypes.c_int]
    dl.htkpa_v1_process.restype=ctypes.c_int
    dl.htkpa_v1_reset.argtypes=[ctypes.c_void_p]
    dl.htkpa_v1_reset.restype=ctypes.c_int
    dl.htkpa_v1_close.argtypes=[ctypes.c_void_p]
    dl.htkpa_v1_close.restype=None
    if dl.htkpa_v1_id().decode("ascii")!=API_ID:
        raise ValueError("compiled shared library ABI identifier mismatch")
    return dl


class Stream:
    def __init__(self,dl,mode:int):
        self.dl=dl
        self.handle=dl.htkpa_v1_open(mode)
        if not self.handle:
            raise RuntimeError("native-compatible stream could not be opened")
    def close(self):
        if self.handle:
            self.dl.htkpa_v1_close(self.handle)
            self.handle=None
    def reset(self):
        if self.dl.htkpa_v1_reset(self.handle)!=0:
            raise RuntimeError("native-compatible stream reset failed")
    def process(self,values:list[float])->bytes:
        if not self.handle or len(values)>2680:
            raise ValueError("closed stream or unsupported block size")
        cap=self.dl.htkpa_v1_min_output_capacity(self.handle,len(values))
        if cap<0 or cap>20000:
            raise RuntimeError("unexpected C ABI required output capacity")
        b=(ctypes.c_double*len(values))(*values)
        # Public r8brain's capacity may exceed actual output length.
        out=(ctypes.c_double*max(1,cap))()
        emitted=self.dl.htkpa_v1_process(self.handle,b,len(values),out,cap)
        if emitted<0 or emitted>cap:
            raise RuntimeError("C ABI processing error "+str(emitted))
        for k in range(emitted):
            if not math.isfinite(out[k]):
                raise ValueError("nonfinite C ABI output")
        return ctypes.string_at(ctypes.addressof(out),emitted*8)


def decode_f64(data:bytes)->list[float]:
    if len(data)%8:
        raise ValueError("not f64le")
    import struct
    return list(struct.unpack("<"+str(len(data)//8)+"d",data))


def run_blocks(dl,mode:int,blocks:list[list[float]])->bytes:
    state=Stream(dl,mode)
    try:
        output=b"".join(state.process(b) for b in blocks)
        state.reset()
        replay=b"".join(state.process(b) for b in blocks)
        if output!=replay:
            raise ValueError("C ABI state reset did not reproduce original output bits")
        return output
    finally:
        state.close()


def metric(native:bytes,public:bytes,expected:int)->dict:
    return stage65.detailed_metrics(native,public,expected)


def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--stage64",type=Path,required=True)
    ap.add_argument("--stage63",type=Path,required=True)
    ap.add_argument("--stage62",type=Path,required=True)
    ap.add_argument("--stage54",type=Path,required=True)
    ap.add_argument("--stage49",type=Path,required=True)
    ap.add_argument("--source-cache",type=Path,required=True)
    ap.add_argument("--wav",type=Path,required=True)
    ap.add_argument("--cxx",default="c++")
    args=ap.parse_args()
    data,provenance=stage65.read_extended(args.stage64)
    stage65.read_stage63(args.stage63)
    stage63.check_stage62(args.stage62)
    old54=stage55.archive_bytes(args.stage54,stage55.EXPECTED["stage54_tar"],{
        "input_0001.bin":(24,stage55.EXPECTED["native_96k_first3"]),
        "input_0002.bin":(2048,stage55.EXPECTED["native_96k_next256"]),
        "output_0001.bin":(256,stage55.EXPECTED["native_48k_first32"])})
    old49=stage55.archive_bytes(args.stage49,stage55.EXPECTED["stage49_tar"],{
        "block_0001.bin":(256,stage55.EXPECTED["native_44k_first32"])})
    stage55.validate_provenance(old49,old54)
    wav=stage55.wav_input_2680(args.wav)
    reverse_a=decode_f64(old54["input_0001.bin"])
    reverse_b=decode_f64(old54["input_0002.bin"])
    forward=decode_f64(wav)
    report={"stage":66,"schema_version":1,
            "status":"STANDALONE_CPP_BRIDGE_PARITY_MEASURED",
            "created_utc":datetime.now(timezone.utc).isoformat(),
            "native":provenance,
            "scope":"isolated C ABI compiled against transient patched public r8brain v6.5; production JS unchanged",
            "source":None,"results":{}}
    with tempfile.TemporaryDirectory(prefix="htkpa_stage66_private_") as td:
        root=Path(td)
        src=root/"public";src.mkdir()
        stage55.ensure_checkout(args.source_cache,stage55.PINS[PIN],src)
        path=root/"libhtkpa_native_frac.so"
        report["source"]=compile_bridge(src,path,args.cxx)
        dl=bind_abi(path)
        for side,mode,block_list,partitioned in (
            ("reverse",MODE_REVERSE,[reverse_a,reverse_b],
             [reverse_a,reverse_b[:128],reverse_b[128:]]),
            ("forward",MODE_FORWARD,[forward],
             [forward[:1340],forward[1340:]])):
            output=run_blocks(dl,mode,block_list)
            expected=EXPECTED_NATIVE_COUNTS[side]
            if len(output)!=expected*8:
                raise ValueError(f"{side} output count wrong {len(output)//8} vs {expected}")
            reference_sha=EXPECTED_PATCHED_FULL_SHA[side]
            output_sha=stage55.sha(output)
            if output_sha!=reference_sha:
                raise ValueError(
                    f"{side} C ABI compiled output differs from Stage65 reconstructed public byte SHA")
            actual=metric(data[side],output,expected)
            split=run_blocks(dl,mode,partitioned)
            if len(split)!=len(output):
                raise ValueError("stream split changed output count")
            split_error=metric(output,split,expected)
            if (actual["rms_error"]>MAX_ACCEPT_RMS[side] or
                    split_error["rms_error"]>MAX_ACCEPT_RMS[side]):
                raise ValueError(f"{side} C ABI changed recovered native numerical behavior")
            report["results"][side]={
                "whole_stream":actual,
                "chunked_vs_whole_public":split_error,
                "exact_stage65_public_sha_match":True,
                "chunk_lengths":[len(x) for x in partitioned],
                "reset_replay_bit_equal":True}
            print(f"[BRIDGE] {side} n={expected} "
                  f"RMS_to_native={actual['rms_error']:.17g} "
                  f"max_to_native={actual['max_abs_error']:.17g} "
                  f"split_RMS={split_error['rms_error']:.17g} "
                  f"bit_exact_native={actual['bit_equal']}/{expected}",flush=True)
    dest=os.environ.get("RESEARCH_ARTIFACT_DIR")
    if dest:
        output=Path(dest);output.mkdir(parents=True,exist_ok=True)
        (output/"stage66_bridge_parity.json").write_text(
            json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"[ERROR] Stage66 {type(e).__name__}: {e}",file=sys.stderr)
        raise SystemExit(2)

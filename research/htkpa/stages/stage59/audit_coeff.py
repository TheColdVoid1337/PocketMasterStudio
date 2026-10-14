#!/usr/bin/env python3
"""Stage59: SHA-pin one native 673x72 coefficient table against public MIT banks.

No native app/Frida launch. Public-generated f64 written only to an ephemeral
directory; emitted report contains hashes and aggregate metrics, no raw values.
Use tools/research_run.py to atomically seal stage59_metrics.json as .tar.gz.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
import numpy as np

HERE=Path(__file__).resolve().parent
PINS={"v6.5":"3c930bf6825c0cfea4a813210c83b1a650c820b5",
      "v7.2":"8fff6f3db26f14a8f5e8fb871000613673db5753"}
FILENAME="frac_coeff_bank_673x72.f64le.bin"
N=673*72
BYTES=N*8
DLL_SHA="fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"


def sha(blob:bytes)->str:
    return hashlib.sha256(blob).hexdigest()


def read_native(archive:Path)->tuple[bytes,dict]:
    with tarfile.open(archive,"r:gz") as t:
        names=t.getnames()
        if len(names)!=len(set(names)):
            raise ValueError("duplicate native capture archive members")
        prefix="frida_capture/"
        config=json.loads(t.extractfile(prefix+"config.json").read())
        manifest=json.loads(t.extractfile(prefix+"manifest.json").read())
        events=[json.loads(line) for line in
                t.extractfile(prefix+"events.jsonl").read().splitlines() if line]
        if (manifest.get("status")!="FRACTIONAL_COEFF_BANK_CLO_STABLE" or
                not manifest.get("completion_verified") or
                config.get("sha256")!=DLL_SHA or
                config.get("mode")!="guarded_fractional_io" or
                config.get("coeff_probe") != {
                    "table_rva":0x2C7560,"phase_count":673,"stride_f64":72,
                    "total_max_bytes":BYTES,"trigger_input_f64":3}):
            raise ValueError("native coefficient source not a verified Stage58 capture")
        matches=[e for e in events if e.get("kind")=="fractional_coeff_bank"]
        if len(matches)!=1 or matches[0].get("valid") is not True:
            raise ValueError("native coefficient payload must appear exactly once")
        event=matches[0]
        if (event.get("file")!=FILENAME or event.get("phase_count")!=673
                or event.get("stride_f64")!=72 or event.get("copied_bytes")!=BYTES
                or event.get("table_rva")!=0x2C7560
                or event.get("provenance")!="native_dll_data_phase_bank"
                or event.get("rate_numerator")!=96000
                or event.get("rate_denominator")!=44100):
            raise ValueError("native coefficient event provenance mismatch")
        item=t.getmember(prefix+FILENAME)
        if not item.isfile() or item.size!=BYTES:
            raise ValueError("native coefficient bank has wrong size")
        blob=t.extractfile(item).read()
        if sha(blob)!=event.get("sha256"):
            raise ValueError("native coefficient bank SHA mismatch")
        a=np.frombuffer(blob,dtype="<f8")
        if len(a)!=N or not np.isfinite(a).all() or not np.any(a!=0):
            raise ValueError("native coefficient bank invalid or uninitialized")
        return blob,{"capture_sha256":sha(archive.read_bytes()),
                     "coefficient_sha256":sha(blob),
                     "site_rva":config["sites"][0].get("rva"),
                     "native_32bit_or_64bit_f64":"f64le",
                     "bytes":len(blob)}


def checkout(cache:Path, revision:str, folder:Path):
    if not (cache/"HEAD").is_file() or not (cache/"objects").is_dir():
        raise ValueError("pinned public source cache missing")
    h=subprocess.run(["git","-C",str(cache),"rev-parse",revision+"^{commit}"],
                     capture_output=True,text=True,check=True).stdout.strip()
    if h!=revision:
        raise ValueError("public source revision failed SHA pin")
    data=subprocess.run(["git","-C",str(cache),"archive","--format=tar",revision],
                        capture_output=True,check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data),mode="r:") as t:
        t.extractall(folder,filter="data")


def metrics(native:bytes,public:bytes)->dict:
    if len(native)!=BYTES or len(public)!=BYTES:
        raise ValueError("coefficient count mismatch")
    n=np.frombuffer(native,dtype="<f8")
    p=np.frombuffer(public,dtype="<f8")
    if not np.isfinite(n).all() or not np.isfinite(p).all():
        raise ValueError("nonfinite coefficients")
    delta=n-p
    rows=delta.reshape(673,72)
    rowrms=np.sqrt(np.mean(rows*rows,axis=1))
    peak=float(np.max(np.abs(n)))
    return {"positions":673,"taps":24,"coeffs_per_tap":3,"f64":N,
            "bit_equal":int(np.count_nonzero(n.view("<u8")==p.view("<u8"))),
            "max_abs_error":float(np.max(np.abs(delta))),
            "rms_error":float(np.sqrt(np.mean(delta*delta))),
            "native_peak":peak,
            "relative_max_error":float(np.max(np.abs(delta))/peak) if peak else None,
            "row_rms_p0":float(rowrms[0]),
            "row_rms_p336":float(rowrms[336]),
            "row_rms_p672":float(rowrms[672]),
            "public_sha256":sha(public),
            "native_sha256":sha(native)}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--stage58",type=Path,required=True)
    p.add_argument("--source-cache",type=Path,required=True)
    p.add_argument("--cxx",default="c++")
    a=p.parse_args()
    native,provenance=read_native(a.stage58)
    report={"stage":59,"schema_version":1,"created_utc":datetime.now(timezone.utc).isoformat(),
            "status":"NATIVE_PUBLIC_COEFFICIENT_BANK_COMPARED",
            "native":provenance,
            "public_attn_req":180.15,
            "scope":"direct index-to-index matching of 673x72; no inferred permutation/shift",
            "versions":{}}
    with tempfile.TemporaryDirectory(prefix="htkpa_stage59_private_") as path:
        temp=Path(path)
        for version,revision in PINS.items():
            work=temp/version;work.mkdir()
            source=work/"src";source.mkdir()
            checkout(a.source_cache,revision,source)
            exe=work/"public_bank"
            command=[a.cxx,"-std=c++17","-O2","-fno-fast-math","-pthread",
                     "-I"+str(source),str(HERE/"public_frac_bank.cpp")]
            if (source/"r8bbase.cpp").is_file():
                command.append(str(source/"r8bbase.cpp"))
            command+=["-o",str(exe)]
            built=subprocess.run(command,capture_output=True,text=True)
            if built.returncode:
                raise RuntimeError("public coefficient-bank build failed: "+built.stderr[-2200:])
            output=work/"generated.f64le"
            run=subprocess.run([str(exe),str(output),"180.15"],
                               capture_output=True,text=True)
            if run.returncode:
                raise RuntimeError("public bank generation failed: "+run.stderr[-1500:])
            metadata=json.loads(run.stdout.splitlines()[-1])
            if metadata.get("bytes")!=BYTES:
                raise ValueError("public generated geometry wrong")
            actual=output.read_bytes()
            report["versions"][version]={"commit":revision,
                                         "metrics":metrics(native,actual)}
            m=report["versions"][version]["metrics"]
            print(f"[BANK] {version}: exact {m['bit_equal']}/{N} "
                  f"max_abs={m['max_abs_error']} RMS={m['rms_error']}",flush=True)
    directory=os.environ.get("RESEARCH_ARTIFACT_DIR")
    if directory:
        out=Path(directory);out.mkdir(parents=True,exist_ok=True)
        (out/"stage59_metrics.json").write_text(json.dumps(report,indent=2)+"\n",
                                                encoding="utf-8")
    print(json.dumps(report,indent=2))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"[ERROR] Stage59: {type(e).__name__}: {e}",file=sys.stderr)
        raise SystemExit(2)

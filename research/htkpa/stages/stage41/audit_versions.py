#!/usr/bin/env python3
"""Stage41 historical r8brain filter-spectrum comparison, no vendor executions.

Uses exact upstream commits and original raw FFT captured in Stage23W. Public
getKernelBlock() is POST convertToZP; convert the original raw native spectrum
to the same layout first. Never stores or sends original audio to Git.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import zipfile

import numpy as np

COMMITS = [
    ("v6.5", "3c930bf6825c0cfea4a813210c83b1a650c820b5", "2023-12-07", True),
    ("v7.0", "a7d812d3153b0fda845db9fc0498e78d7337d0f0", "2025-12-18", True),
    ("v7.1", "1ad3b3707b9339a7144b301752318bbb902220d2", "2025-12-28", True),
    ("v7.2", "8fff6f3db26f14a8f5e8fb871000613673db5753", "2026-07-27", True),
    ("v7.6", "cb2abb9977efe2471979b380ed95daa56ab4fdb9", "2026-09-30", False),
]
SOURCE = "https://github.com/avaneev/r8brain-free-src.git"
ROOT = "20261013_overlap_capture/"
ORIGINAL_SHA = [
    ("649adeb70df4bb17f73ca09c0e4bc8bd3511271fa388d989bb2094ead22b0770",
     "2fbd0bb69f5fa2436ef922c073b97abbdecb4a95487ad4978303e3d7aef2f2a9"),
    ("ccb1dcb24dc73dfa5b273a22f96d6093713f52518cadf26e595e94ff9ee6b9cc",
     "ee75eb6eef4e99a47be30c32e8ee76b4f9b549f62f4eb8d0df5eda02baebff41"),
]
TAPS = [1417, 1543]


def cmd(argv, **kwargs):
    return subprocess.run([str(a) for a in argv], check=True, **kwargs)


def prepare_git_cache(cache):
    cache = cache.resolve()
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        print("[SOURCE] Cloning public MIT r8brain history once into ignored local cache", flush=True)
        cmd(["git", "clone", "--quiet", "--bare", SOURCE, cache])
    if not (cache / "HEAD").is_file() or not (cache / "objects").is_dir():
        raise ValueError("Source cache already exists but is not a bare Git repository")
    for version, revision, _, _ in COMMITS:
        have = subprocess.run(["git", "-C", str(cache), "cat-file", "-e", revision+"^{commit}"],
                              capture_output=True)
        if have.returncode:
            print("[SOURCE] Fetching missing historical revision "+version, flush=True)
            cmd(["git", "-C", cache, "fetch", "--quiet", "origin", revision])
        full = subprocess.check_output(
            ["git", "-C", str(cache), "rev-parse", revision+"^{commit}"],
            text=True).strip()
        if full != revision:
            raise ValueError("Source SHA mismatch for "+version)
    return cache


def unpack_revision(cache, revision, destination):
    # Pinned public-source tar produced by Git, extracted only under a temp dir.
    proc = subprocess.run(["git", "-C", str(cache), "archive", "--format=tar", revision],
                          capture_output=True, check=True)
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(proc.stdout), mode="r:") as archive:
        archive.extractall(destination, filter="data")


def load_native(file):
    original = []
    with zipfile.ZipFile(file) as z:
        for i, (time_sha, fft_sha) in enumerate(ORIGINAL_SHA):
            for typ, sha in [("coeff_pre_fft", time_sha), ("coeff_post_fft", fft_sha)]:
                raw = z.read(ROOT+f"{typ}_{i:02d}.f64le.bin")
                if len(raw) != 4096*8 or hashlib.sha256(raw).hexdigest() != sha:
                    raise ValueError("Private native fixture mismatch for "+typ+str(i))
                if typ == "coeff_post_fft":
                    spec = np.frombuffer(raw, dtype="<f8").copy()
                    # Ooura default r8brain zero-phase: copy re_k into imag slot.
                    spec[3::2] = spec[2::2]
                    if not np.isfinite(spec).all():
                        raise ValueError("nonfinite vendor spectrum")
                    original.append(spec)
    return original


def compare(public, original):
    diff = public - original
    peak = float(np.max(np.abs(original)))
    return {
        "compared_f64": 4096,
        "bit_exact": int(np.count_nonzero(public.view("<u8") == original.view("<u8"))),
        "max_abs": float(np.max(np.abs(diff))),
        "rms": float(np.sqrt(np.mean(np.square(diff)))),
        "max_abs_over_vendor_peak": float(np.max(np.abs(diff))/peak) if peak else None,
        "public_dc": float(public[0]),
        "vendor_dc": float(original[0]),
        "public_nyquist": float(public[1]),
        "vendor_nyquist": float(original[1]),
    }


def run_version(cxx, source_cpp, public_src, legacy, original, scratch):
    exe = scratch / "probe"
    paths = [scratch / "1417.bin", scratch / "1543.bin"]
    build = [cxx, "-std=c++17", "-O2", "-fno-fast-math", "-pthread",
             "-DHTKPA_LEGACY_API="+("1" if legacy else "0"),
             "-I"+str(public_src), str(source_cpp)]
    # Old legacy versions declare static library state in r8bbase.cpp;
    # modern versions are header-only. Link it only where it is present.
    old_base = public_src / "r8bbase.cpp"
    if old_base.is_file():
        build.append(str(old_base))
    build.extend(["-o", str(exe)])
    result = subprocess.run(build, capture_output=True, text=True)
    if result.returncode:
        return {"status": "COMPILE_FAILED", "return_code": result.returncode,
                "stderr_tail": result.stderr[-2400:]}
    run = subprocess.run([str(exe), *(str(p) for p in paths)], capture_output=True, text=True)
    if run.returncode:
        return {"status": "RUNTIME_FAILED", "return_code": run.returncode,
                "stderr_tail": run.stderr[-1800:]}
    try:
        info = [json.loads(line) for line in run.stdout.splitlines()]
        if len(info) != 2:
            raise ValueError("Expected 2 C++ JSON summary lines")
        compared = []
        for i, path in enumerate(paths):
            row = {"kernel": i, **info[i]}
            raw = path.read_bytes()
            row["public_spectrum_sha256"] = hashlib.sha256(raw).hexdigest()
            if int(info[i]["fft_f64"]) != 4096 or int(info[i]["filter_taps"]) != TAPS[i]:
                row["status"] = "GEOMETRY_MISMATCH"
            elif len(raw) != 4096*8:
                row["status"] = "BINARY_LENGTH_MISMATCH"
            else:
                public = np.frombuffer(raw, dtype="<f8").copy()
                if not np.isfinite(public).all():
                    raise ValueError("Nonfinite public FFT")
                row["status"] = "COMPARABLE"
                row["public_vs_vendor"] = compare(public, original[i])
            compared.append(row)
        comparable = all(row["status"] == "COMPARABLE" for row in compared)
        return {
            "status": "COMPARABLE" if comparable else "GEOMETRY_MISMATCH",
            "filters": compared,
            "max_abs_across_filters": (
                max(row["public_vs_vendor"]["max_abs"] for row in compared) if comparable else None),
            "rms_across_filters": (
                float(np.sqrt(np.mean([row["public_vs_vendor"]["rms"]**2
                                       for row in compared]))) if comparable else None),
            "total_bit_exact_of_8192": (
                sum(row["public_vs_vendor"]["bit_exact"] for row in compared) if comparable else None),
        }
    except (ValueError, OSError, KeyError) as e:
        return {"status": "INVALID_RESULT", "error": str(e), "stdout_tail": run.stdout[-1000:]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--native-zip", type=Path, required=True)
    p.add_argument("--source-cache", type=Path, required=True,
                   help="ignored local bare Git repo for archived historical source")
    p.add_argument("--cpp", type=Path, default=Path(__file__).with_name("r8b_versions_gate.cpp"))
    p.add_argument("--cxx", default="c++")
    p.add_argument("--out", type=Path)
    args = p.parse_args()

    if not args.native_zip.is_file():
        raise FileNotFoundError("Private native FIR fixture missing: "+str(args.native_zip))
    original = load_native(args.native_zip)
    cache = prepare_git_cache(args.source_cache)
    rows = []
    for version, revision, date, legacy in COMMITS:
        print("[BUILD] "+version+" @ "+revision[:12], flush=True)
        with tempfile.TemporaryDirectory(prefix="htkpa_stage41_"+version.replace(".","_")+"_") as tmp:
            root = Path(tmp)
            public_src = root / "public"
            unpack_revision(cache, revision, public_src)
            row = {
                "version": version,
                "git_commit": revision,
                "release_date": date,
                "legacy_five_argument_getLPFilter": legacy,
                **run_version(args.cxx, args.cpp, public_src, legacy, original, root),
            }
            rows.append(row)
        if row["status"] == "COMPARABLE":
            print("[METRICS] "+version+" max_abs="+format(row["max_abs_across_filters"], ".9g")+
                  " rms="+format(row["rms_across_filters"], ".9g")+
                  " bit_exact="+str(row["total_bit_exact_of_8192"]), flush=True)
        else:
            print("[WARN] "+version+" "+row["status"], flush=True)

    eligible = [row for row in rows if row["status"] == "COMPARABLE"]
    ranking = sorted(eligible, key=lambda row: (
        row["rms_across_filters"], row["max_abs_across_filters"], row["version"]))
    result = {
        "stage": 41,
        "status": "COMPLETED" if len(eligible)==len(COMMITS) else "INCOMPLETE_VERSIONS",
        "evidence_kind": "public historical pinned source versus SAME original FIR zero-phase spectral layout",
        "versions": rows,
        "ranking_by_rms_NOT_PROVENANCE": [row["version"] for row in ranking],
        "warning": "Tiny numerical differences are compiler/FFTs/window-generation sensitive. "
                   "A closer version in this Linux build is NOT proof of the Sonicake source revision.",
        "privacy": "Only public sources and numeric metrics in JSON. Private native source arrays in ignored local ZIP only.",
    }
    output = json.dumps(result, indent=2, ensure_ascii=False)+"\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    print(output)
    if len(eligible) != len(COMMITS):
        raise SystemExit(2)

if __name__ == "__main__":
    main()

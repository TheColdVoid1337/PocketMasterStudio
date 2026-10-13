#!/usr/bin/env python3
"""Stage43: compare original Sonicake FIR output with historical r8brain C++.

Purely offline: reuse exact validated 2680-f64 vendor input and 1972-f64
reference (Stage39) with exact pinned public r8brain versions (Stage41).
Do not modify original vendor DLL, intercept it, or commit original buffers.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np

VERSIONS = [
    ("v6.5", "3c930bf6825c0cfea4a813210c83b1a650c820b5", "2023-12-07", True),
    ("v7.0", "a7d812d3153b0fda845db9fc0498e78d7337d0f0", "2025-12-18", True),
    ("v7.1", "1ad3b3707b9339a7144b301752318bbb902220d2", "2025-12-28", True),
    ("v7.2", "8fff6f3db26f14a8f5e8fb871000613673db5753", "2026-07-27", True),
    ("v7.5", "9e73d2dd59fd5b95108fdb4f590083e35758b45f", "2026-09-02", False),
    ("v7.6", "cb2abb9977efe2471979b380ed95daa56ab4fdb9", "2026-09-30", False),
]

# Change only the probe call to getLPFilter, not the pinned public sources.
MODERN_CALL = (
    "    r8b::CDSPFIRFilter& filter=r8b::CDSPFIRFilterCache::getLPFilter(\n"
    "      0.5, 2.0, 180.15, r8b::fprLinearPhase, 2.0, 1);"
)
COMPAT_CALL = (
    "#if HTKPA_LEGACY_API\n"
    "    r8b::CDSPFIRFilter& filter=r8b::CDSPFIRFilterCache::getLPFilter(\n"
    "      0.5, 2.0, 180.15, r8b::fprLinearPhase, 2.0);\n"
    "#else\n" + MODERN_CALL + "\n#endif"
)


def import_local(module_path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("missing local module: " + str(module_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def native_input_and_reference(native_zip, stage33, stage35):
    stage39 = import_local(
        Path(__file__).resolve().parents[1]/"stage39"/"audit.py",
        "_htkpa_stage39_shared",
    )
    import zipfile
    with zipfile.ZipFile(native_zip) as z:
        a0 = stage39.one(z, "input_pre_fft", 0)
        a1 = stage39.one(z, "input_pre_fft", 1)
        i0 = stage39.one(z, "after_inverse", 0)
    if not np.all(a0[1340:] == 0):
        raise ValueError("Original frame0 history/padding is not empty")
    if not np.array_equal(a1[1340:2048], a0[632:1340]):
        raise ValueError("708-sample history mismatch")
    if not np.all(a1[2048:] == 0):
        raise ValueError("Original frame1 FFT padding not empty")
    x = np.concatenate((a0[:1340], a1[:1340]))
    if x.size != 2680 or not np.array_equal(x[:2048], stage39.stage33_input(stage33)):
        raise ValueError("Original Stage33 input prefix mismatch")
    reference = stage39.stage35_output(stage35)
    if reference != i0[:1972].astype("<f8").tobytes():
        raise ValueError("Original Stage35 output vs FFT prefix not byte-identical")
    return x.astype("<f8").tobytes(), reference


def run_one(cxx, probe, src_dir, legacy, workspace, input_file, reference_file):
    binary = workspace/"convolver"
    cmd = [cxx, "-std=c++17", "-O2", "-fno-fast-math", "-pthread",
           "-DHTKPA_LEGACY_API="+("1" if legacy else "0"),
           "-I"+str(src_dir), str(probe)]
    base = src_dir/"r8bbase.cpp"
    if base.is_file():
        cmd.append(str(base))
    cmd += ["-o", str(binary)]
    build = subprocess.run(cmd, capture_output=True, text=True)
    if build.returncode:
        return {"status":"BUILD_FAILED", "return_code":build.returncode,
                "stderr_tail":build.stderr[-2200:]}
    run = subprocess.run([str(binary), str(input_file), str(reference_file)],
                         capture_output=True, text=True)
    if not run.stdout.strip():
        return {"status":"EXEC_FAILED", "return_code":run.returncode,
                "stderr_tail":run.stderr[-1600:]}
    try:
        report = json.loads(run.stdout.splitlines()[-1])
    except json.JSONDecodeError:
        return {"status":"INVALID_JSON", "return_code":run.returncode,
                "stdout_tail":run.stdout[-1000:]}
    # Numerical mismatch return 3 is itself meaningful; retain metrics.
    return {"status":report.get("status"), "return_code":run.returncode,
            "metrics":report}


def main():
    pa = argparse.ArgumentParser()
    pa.add_argument("--native-zip", type=Path, required=True)
    pa.add_argument("--stage33-archive", type=Path, required=True)
    pa.add_argument("--stage35-archive", type=Path, required=True)
    pa.add_argument("--source-cache", type=Path, required=True)
    pa.add_argument("--cxx", default="c++")
    pa.add_argument("--out", type=Path)
    args = pa.parse_args()
    for p in (args.native_zip, args.stage33_archive, args.stage35_archive):
        if not p.is_file():
            raise FileNotFoundError("Missing private local archive: "+str(p))
    original_input, original_output = native_input_and_reference(
        args.native_zip, args.stage33_archive, args.stage35_archive)

    common = import_local(Path(__file__).resolve().parents[1]/"stage41"/"audit_versions.py",
                          "_htkpa_stage41_shared")
    common.COMMITS = VERSIONS
    cache = common.prepare_git_cache(args.source_cache)
    baseline_cpp = (Path(__file__).resolve().parents[1]/
                    "stage39"/"r8b_convolver_gate.cpp")
    code = baseline_cpp.read_text(encoding="utf-8")
    if code.count(MODERN_CALL) != 1:
        raise ValueError("Stage39 C++ probe signature changed; no implicit patching")
    adapted = code.replace(MODERN_CALL, COMPAT_CALL)

    rows = []
    with tempfile.TemporaryDirectory(prefix="htkpa_stage43_private_") as tmp:
        root = Path(tmp)
        input_path = root/"original_input_2680.f64le.bin"
        ref_path = root/"original_reference_1972.f64le.bin"
        input_path.write_bytes(original_input)
        ref_path.write_bytes(original_output)
        probe = root/"compatible_convolver.cpp"
        probe.write_text(adapted, encoding="utf-8")
        for version, sha, release_date, legacy in VERSIONS:
            print("[BUILD] "+version+" @ "+sha[:12], flush=True)
            revision_src = root/("r8b_"+version.replace(".", "_"))
            common.unpack_revision(cache, sha, revision_src)
            scratch = root/("build_"+version.replace(".", "_"))
            scratch.mkdir()
            outcome = run_one(args.cxx, probe, revision_src, legacy, scratch,
                              input_path, ref_path)
            rows.append({"version":version, "commit":sha,"release_date":release_date,
                         "legacy_API":legacy, **outcome})
            if outcome["status"] == "PASS_NUMERIC_CONVOLVER":
                m = outcome["metrics"]
                print("[METRICS] "+version+
                      " max_abs="+format(m["max_abs"], ".9g")+
                      " rms="+format(m["rms"], ".9g")+
                      " exact="+str(m["bit_exact"])+"/"+str(m["compared"]),flush=True)
            else:
                print("[WARN] "+version+" status="+str(outcome["status"]),flush=True)

    successful = [row for row in rows if row["status"] == "PASS_NUMERIC_CONVOLVER"
                  and row["return_code"] == 0
                  and row["metrics"]["output_f64"] == 1972
                  and row["metrics"]["public_filter_taps"] == 1417
                  and row["metrics"]["public_fft_length"] == 4096]
    ranked = sorted(successful,
                    key=lambda row:(row["metrics"]["rms"],
                                    row["metrics"]["max_abs"],row["version"]))
    result = {
        "stage":43,"status":"COMPLETED" if len(successful)==len(VERSIONS) else "INCOMPLETE",
        "question":"Does real historical r8brain CDSPBlockConvolver reproduce the same original 1972-f64 FIR output better than v7.6?",
        "original_input_sha256":hashlib.sha256(original_input).hexdigest(),
        "original_reference_sha256":hashlib.sha256(original_output).hexdigest(),
        "source":"Original captured input verified against Stage33 and output verified against Stage35; pinned public source compiled on local Linux",
        "versions":rows,"ranking_by_rms_NOT_vendor_provenance":[x["version"] for x in ranked],
        "scope":"First FIR stage only. Numerical output and bit matches do not prove original revision/compiler. Not final 44.1->48k or NAM fitting.",
        "privacy":"No private sample arrays in Git or emitted report, only hashes/error metrics.",
    }
    final = json.dumps(result,indent=2)+"\n"
    print(final)
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(final,encoding="utf-8")
    if len(successful)!=len(VERSIONS):
        raise SystemExit(2)


if __name__=="__main__":
    main()

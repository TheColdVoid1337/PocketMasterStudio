#!/usr/bin/env python3
"""Stage42: pinpoint r8brain FIR-spectrum divergence between 7.2 and 7.6.

Reuses Stage41's source-verified, byte-aligned and private fixture comparisons.
Only public upstream sources are downloaded, compiled, and hashed; the private
vendor spectra live in ignored ZIP files and temporary memory.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

VERSIONS = [
    ("v7.2", "8fff6f3db26f14a8f5e8fb871000613673db5753", "2026-07-27", True),
    ("v7.3", "901cfd827dc6881b45232676670efb54dee9378f", "2026-08-04", True),
    ("v7.4", "26f847bf05853fa9e69a90c088c51a2ee46f3c97", "2026-08-17", True),
    ("v7.5", "9e73d2dd59fd5b95108fdb4f590083e35758b45f", "2026-09-02", False),
    ("v7.6", "cb2abb9977efe2471979b380ed95daa56ab4fdb9", "2026-09-30", False),
]


def load_common():
    common = Path(__file__).resolve().parents[1] / "stage41" / "audit_versions.py"
    if not common.is_file():
        raise FileNotFoundError("Missing canonical Stage41 version scanner: " + str(common))
    spec = importlib.util.spec_from_file_location("_htkpa_stage41_shared", common)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import local Stage41 test")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    # The existing source-cache verifier iterates COMMITS. Set the complete
    # pre-declared commit set before invoking it; never permit user code here.
    module.COMMITS = VERSIONS
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-zip", type=Path, required=True)
    parser.add_argument("--source-cache", type=Path, required=True)
    parser.add_argument("--cxx", default="c++")
    parser.add_argument("--out", type=Path)
    a = parser.parse_args()
    common = load_common()
    if not a.native_zip.is_file():
        raise FileNotFoundError("missing ignored native private FIR fixture: " + str(a.native_zip))
    native = common.load_native(a.native_zip)
    git_cache = common.prepare_git_cache(a.source_cache)
    cpp = Path(__file__).resolve().parents[1] / "stage41" / "r8b_versions_gate.cpp"
    if not cpp.is_file():
        raise FileNotFoundError("missing actual public C++ probe " + str(cpp))
    rows = []
    for version, revision, date, legacy in VERSIONS:
        print("[BUILD] "+version+" "+revision[:12], flush=True)
        with tempfile.TemporaryDirectory(prefix="htkpa_stage42_"+version.replace(".", "_")+"_") as td:
            workspace = Path(td)
            source = workspace/"public"
            common.unpack_revision(git_cache, revision, source)
            outcome = common.run_version(a.cxx, cpp, source, legacy, native, workspace)
        row = {
            "version":version, "git_commit":revision, "date":date,
            "legacy_five_argument_getLPFilter":legacy, **outcome
        }
        rows.append(row)
        if row["status"] == "COMPARABLE":
            print("[METRICS] "+version+
                  " max_abs="+format(row["max_abs_across_filters"], ".9g")+
                  " rms="+format(row["rms_across_filters"], ".9g")+
                  " exact="+str(row["total_bit_exact_of_8192"]), flush=True)
        else:
            print("[WARN] "+version+" "+row["status"], flush=True)

    comparable = [row for row in rows if row["status"] == "COMPARABLE"]
    if len(comparable) == len(VERSIONS):
        control = comparable[0]
        first_divergence = next((
            row["version"] for row in comparable[1:]
            if any(a["public_spectrum_sha256"]!=b["public_spectrum_sha256"]
                   for a,b in zip(row["filters"], control["filters"]))
        ), None)
    else:
        first_divergence = "UNRESOLVED_INCOMPLETE_BUILDS"

    result = {
        "stage":42,
        "status":"COMPLETED" if len(comparable)==len(VERSIONS) else "INCOMPLETE_BUILDS",
        "question":"Which public revision first changes the two FIR spectra relative to v7.2?",
        "first_different_public_spectra":first_divergence,
        "versions":rows,
        "scope":"Same two vendor FIR capture buffers, same zero-phase layout. Public-Linux "
                "revision fingerprint only; vendor embedded source/compiler not established.",
        "privacy":"Private Sonicake arrays remain only in ignored original ZIP and temporary memory.",
    }
    output = json.dumps(result, indent=2)+"\n"
    print(output)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(output, encoding="utf-8")
    if len(comparable)!=len(VERSIONS):
        raise SystemExit(2)


if __name__=="__main__":
    main()

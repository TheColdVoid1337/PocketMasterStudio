#!/usr/bin/env python3
"""Stage98 source-first NAM Core native integration, offline by default.

The vendor DLL is NEVER loaded. Source must be a locally available exact pinned
NeuralAmpModelerCore checkout; building/running is explicit. Private generated
raw PCM and reports go into ignored research/_LOCAL_FILES, not public Git.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import struct
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PIN = "0b3d3c97b0859a3a8c92a8628c4dd89a25eb5842"
REPO_URL = "https://github.com/sdatkinson/NeuralAmpModelerCore.git"
DEFAULT_SOURCE = ROOT / "research/_LOCAL_FILES/public_sources/NeuralAmpModelerCore"
DEFAULT_BUILD = ROOT / "research/_LOCAL_FILES/nam_core_stage98_build"
MARKER = "stage98_nam_core_build.json"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def cmd(argv: list[str], cwd: Path | None = None) -> str:
    proc = subprocess.run(argv, cwd=cwd, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=False)
    if proc.returncode:
        # Don't propagate tool stderr; git/build errors might contain private paths.
        raise RuntimeError(f"command failed ({Path(argv[0]).name}, exit {proc.returncode})")
    return proc.stdout.strip()


def verify_source(source: Path) -> dict:
    if not (source / ".git").exists():
        raise ValueError("local NeuralAmpModelerCore Git checkout missing; no auto-fetch")
    rev = cmd(["git", "-C", str(source), "rev-parse", "HEAD"])
    if rev != PIN:
        raise ValueError("NAM Core source revision does not equal pinned commit")
    if cmd(["git", "-C", str(source), "diff", "--name-only", "HEAD", "--", "NAM", "Dependencies/nlohmann"]):
        raise ValueError("upstream NAM or JSON source contains local tracked changes")
    required = ["LICENSE", "NAM/get_dsp.h", "NAM/get_dsp.cpp", "NAM/dsp.h",
                "NAM/container.cpp", "NAM/slimmable.h", "Dependencies/nlohmann/json.hpp",
                "Dependencies/eigen/Eigen/Dense"]
    for name in required:
        if not (source / name).is_file():
            raise ValueError("missing pinned dependency/source: " + name)
    lic = (source / "LICENSE").read_text(encoding="utf-8")
    if "MIT License" not in lic:
        raise ValueError("upstream NAM Core MIT license missing")
    # Eigen is a pinned upstream submodule; dirty HEAD isn't silently accepted.
    expected_eigen = "bc3b39870ecb690a623a3f49149a358b95c5781d"
    eigen = source / "Dependencies/eigen"
    eigen_rev = cmd(["git", "-C", str(eigen), "rev-parse", "HEAD"])
    if eigen_rev != expected_eigen:
        raise ValueError("Eigen checkout differs from NAM upstream gitlink")
    return {"source_commit": rev, "eigen_commit": eigen_rev,
            "license_sha256": sha(source / "LICENSE")}


def binary_path(build: Path) -> Path:
    return build / ("htkpa_nam_probe.exe" if os.name == "nt" else "htkpa_nam_probe")


def build(source: Path, target: Path) -> dict:
    upstream = verify_source(source)
    target.mkdir(parents=True, exist_ok=True)
    cmd(["cmake", "-S", str(HERE), "-B", str(target),
         f"-DNAMCORE_SOURCE={source.resolve()}", "-DCMAKE_BUILD_TYPE=Release"])
    cmd(["cmake", "--build", str(target), "--target", "htkpa_nam_probe", "--parallel", "2"])
    binary = binary_path(target)
    if not binary.is_file() and os.name == "nt":
        binary = target / "Release/htkpa_nam_probe.exe"
    if not binary.is_file():
        raise ValueError("built NAM Core probe executable missing")
    manifest = {"stage": 98, "backend": "NeuralAmpModelerCore C++ upstream, not proprietary DLL",
                "upstream_repo": REPO_URL, **upstream,
                "bridge_sha256": sha(HERE / "htkpa_nam_probe.cpp"),
                "cmake_sha256": sha(HERE / "CMakeLists.txt"),
                "binary_name": str(binary.relative_to(target)),
                "binary_sha256": sha(binary), "nam_sample_type": "double",
                "a2_fast": False, "real_upstream_compile": True,
                "clo_parity_verified": False}
    (target / MARKER).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def run(build_dir: Path, model: Path, input_file: Path, output_file: Path,
        rate: int, block: int, prewarm: str, slim: float | None):
    manifest_path = build_dir / MARKER
    if not manifest_path.is_file():
        raise ValueError("Stage98 compiled build manifest missing; run build first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("source_commit") != PIN
            or manifest.get("bridge_sha256") != sha(HERE / "htkpa_nam_probe.cpp")
            or manifest.get("cmake_sha256") != sha(HERE / "CMakeLists.txt")):
        raise ValueError("manifest/source bridge mismatch; rebuild required")
    binary = build_dir / manifest["binary_name"]
    if not binary.is_file() or sha(binary) != manifest["binary_sha256"]:
        raise ValueError("probe binary SHA mismatch")
    if not model.is_file() or model.suffix.lower() != ".nam":
        raise ValueError("provided model is not an existing .nam file")
    if not input_file.is_file() or input_file.stat().st_size % 8:
        raise ValueError("raw f64le input missing or malformed")
    if output_file.exists():
        raise ValueError("refusing to overwrite raw output")
    if rate < 8000 or rate > 192000 or block < 1 or block > 4096:
        raise ValueError("invalid sample rate or block size")
    if slim is not None and (not math.isfinite(slim) or not 0.0 <= slim <= 1.0):
        raise ValueError("slim must be finite and in [0,1]")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    argv = [str(binary), "--model", str(model), "--input-f64le", str(input_file),
            "--output-f64le", str(output_file), "--sample-rate", str(rate),
            "--block", str(block), "--prewarm", prewarm]
    if slim is not None:
        argv += ["--slim", str(slim)]
    payload = json.loads(cmd(argv))
    if payload.get("status") != "NAM_CORE_UPSTREAM_INFERENCE_COMPLETED":
        raise ValueError("NAM C++ did not report upstream inference completion")
    frames = input_file.stat().st_size // 8
    if (payload.get("frames") != frames or payload.get("sample_rate") != rate
            or output_file.stat().st_size != frames * 8):
        raise ValueError("native input/output frame accounting failure")
    private = {"stage": 98, "backend": "NeuralAmpModelerCore C++",
               "source_commit": PIN, "binary_sha256": manifest["binary_sha256"],
               "model_sha256": sha(model), "input_f64le_sha256": sha(input_file),
               "output_f64le_sha256": sha(output_file), "sample_rate_hz": rate,
               "block_size": block, "prewarm": prewarm, "slim": slim,
               "frames": frames, "vendor_numeric_parity_verified": False,
               "clo_generated": False, "upstream_inference": payload}
    private_path = output_file.with_suffix(output_file.suffix + ".provenance.json")
    private_path.write_text(json.dumps(private, indent=2) + "\n", encoding="utf-8")
    return {"status": payload["status"], "frames": frames,
            "output_sha256": private["output_f64le_sha256"],
            "vendor_numeric_parity_verified": False, "clo_generated": False}


def smoke(build_dir: Path, model: Path, rate: int | None, block: int, prewarm: str,
          slim: float | None) -> dict:
    """Deterministic probe input; never substitutes for Stage97 vendor audio."""
    if not model.is_file() or model.suffix.lower() != '.nam':
        raise ValueError('smoke requires a local .nam model')
    if model.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('smoke model JSON exceeds 32 MiB')
    try:
        meta = json.loads(model.read_text(encoding='utf-8'))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('invalid .nam JSON') from exc
    expected = meta.get('sample_rate')
    if expected is not None and (not isinstance(expected, (float, int))
                                 or isinstance(expected, bool) or not math.isfinite(expected)
                                 or expected != int(expected)):
        raise ValueError('invalid model expected sample rate')
    if rate is None:
        if expected is None:
            raise ValueError('model sample_rate unknown; specify --sample-rate')
        rate = int(expected)
    if expected is not None and abs(rate - expected) > 0.5:
        raise ValueError('probe source rate differs from NAM expected sample rate')
    if not 8000 <= rate <= 192000:
        raise ValueError('invalid probe sample rate')
    private = ROOT / 'research/_LOCAL_FILES/stage98_smoke'
    private.mkdir(parents=True, exist_ok=True)
    stem = f'{sha(model)[:16]}_{rate}'
    stimulus = private / f'{stem}_excitation.f64le'
    output = private / f'{stem}_nam_output.f64le'
    # Bounded mono impulse + low-level sinusoids. Must stay identical across tests.
    expected_bytes = b''.join(struct.pack('<d',
        (0.3 if i == 64 else 0.) + 0.02 * math.sin(2*math.pi*997*i/rate)
        + 0.01 * math.sin(2*math.pi*241*i/rate)) for i in range(8192))
    if stimulus.exists():
        if stimulus.read_bytes() != expected_bytes:
            raise ValueError('existing stimulus differs; refuse overwrite')
    else:
        stimulus.write_bytes(expected_bytes)
    result = run(build_dir, model, stimulus, output, rate, block, prewarm, slim)
    return {**result, 'stimulus_sha256': sha(stimulus),
            'stimulus_frames': 8192, 'comparison_to_vendor': 'NOT_PERFORMED'}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=["doctor", "build", "run", "smoke"])
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument("--build-dir", type=Path, default=DEFAULT_BUILD)
    ap.add_argument("--model", type=Path)
    ap.add_argument("--input-f64le", type=Path)
    ap.add_argument("--output-f64le", type=Path)
    ap.add_argument("--sample-rate", type=int)
    ap.add_argument("--block", type=int, default=64)
    ap.add_argument("--prewarm", choices=["on", "off"], default="on")
    ap.add_argument("--slim", type=float)
    a = ap.parse_args()
    if a.action == "doctor":
        result = verify_source(a.source)
    elif a.action == "build":
        result = build(a.source, a.build_dir)
    elif a.action == "smoke":
        if not a.model:
            ap.error("smoke requires --model")
        result = smoke(a.build_dir, a.model, a.sample_rate, a.block, a.prewarm, a.slim)
    else:
        if not a.model or not a.input_f64le or not a.output_f64le or a.sample_rate is None:
            ap.error("run requires --model --input-f64le --output-f64le --sample-rate")
        result = run(a.build_dir, a.model, a.input_f64le, a.output_f64le,
                     a.sample_rate, a.block, a.prewarm, a.slim)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
        print("[Stage98] " + str(exc), file=sys.stderr)
        sys.exit(2)

#!/usr/bin/env python3
"""Resampler Lab CLI: build, convert, compare. Run directly under Linux/WSL.

Examples:
  python GO.py build
  python GO.py convert --input mono_44100.wav --output converted_48000.wav
  python GO.py convert --input captured_96000.f64le --rate 96000 \
      --output reconstructed_44100.f64le --chunk 256
  python GO.py compare --actual reconstructed_44100.f64le \
      --reference native_44100.f64le --max-rms 1e-14
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import build
import resampler


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="HTKPA standalone Sonicake-compatible fractional resampler Lab")
    sub = ap.add_subparsers(dest="command", required=True)

    build_cmd = sub.add_parser("build", help="Build and SHA-verify C++ bridge locally")
    build_cmd.add_argument("--source-cache", type=Path, default=build.DEFAULT_CACHE)
    build_cmd.add_argument("--cxx", default="c++", help="C++17 compiler executable")

    status = sub.add_parser("status", help="Check local compiled C++ bridge SHA and ABI")
    status.add_argument("--library-dir", type=Path, default=build.LIB_FOLDER)

    convert = sub.add_parser("convert", help="Process PCM WAV or raw interleaved f64le")
    convert.add_argument("--input", type=Path, required=True)
    convert.add_argument("--output", type=Path, required=True)
    convert.add_argument("--mode", default="auto",
                         choices=("auto", "reverse", "forward",
                                  "96000-to-44100", "44100-to-48000"))
    convert.add_argument("--rate", type=int,
                         help="Input sample rate; required for raw .f64le")
    convert.add_argument("--channels", type=int, choices=(1, 2), default=1,
                         help="Interleaved channel count for raw .f64le; WAV uses header")
    convert.add_argument("--chunk", type=int, default=1024,
                         help="Input frames processed per C++ call, 1..2680")
    convert.add_argument("--pad-input", type=int, default=0,
                         help="Explicit zero input frames at end, 0..16384; no hidden flush")
    convert.add_argument("--library-dir", type=Path, default=build.LIB_FOLDER)
    convert.add_argument("--overwrite", action="store_true")
    convert.add_argument("--report", type=Path, help="Optional JSON report")

    compare = sub.add_parser("compare", help="Same-index Float64 output comparison")
    compare.add_argument("--actual", type=Path, required=True)
    compare.add_argument("--reference", type=Path, required=True)
    compare.add_argument("--max-rms", type=float,
                         help="Nonnegative RMS acceptance bound; fail exit 3 if exceeded")
    compare.add_argument("--report", type=Path, help="Optional JSON report")
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = parser()
    args = ap.parse_args(argv)
    try:
        if args.command == "build":
            library, meta = build.build_library(args.source_cache, cxx=args.cxx)
            result = {
                "status": "BUILT_PINNED_CPP_BRIDGE",
                "library": str(library),
                "abi_id": meta["abi_id"],
                "source_commit": meta["source"]["source_commit"],
                "sha256": meta["shared_object_sha256"],
                "scope": "private Linux/WSL build; production NAM converter unchanged",
            }
        elif args.command == "status":
            library, meta = build.verify_library(args.library_dir)
            build.bridge.bind_abi(library)
            result = {
                "status": "VERIFIED_PINNED_CPP_BRIDGE",
                "library": str(library),
                "abi_id": meta["abi_id"],
                "sha256": meta["shared_object_sha256"],
            }
        elif args.command == "convert":
            if args.report and args.report.resolve() in (
                    args.input.resolve(), args.output.resolve()):
                raise ValueError("--report must differ from input and output")
            result = resampler.convert(
                args.input, args.output, mode=args.mode, rate=args.rate,
                channels=args.channels, chunk=args.chunk,
                pad_input=args.pad_input, overwrite=args.overwrite,
                library_dir=args.library_dir)
            result["status"] = "LAB_CONVERTED"
            if args.report:
                resampler.write_json_atomic(args.report, result)
        elif args.command == "compare":
            if (args.max_rms is not None
                    and (args.max_rms < 0 or not __import__("math").isfinite(args.max_rms))):
                raise ValueError("--max-rms must be a finite nonnegative number")
            if args.report and args.report.resolve() in (
                    args.actual.resolve(), args.reference.resolve()):
                raise ValueError("--report must differ from compared inputs")
            result = resampler.compare(args.actual, args.reference)
            if args.max_rms is not None:
                result["max_rms_allowed"] = args.max_rms
                result["accepted"] = result["rms_error"] <= args.max_rms
            if args.report:
                resampler.write_json_atomic(args.report, result)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("accepted", True) else 3
        else:
            ap.error("Unknown command")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print(f"[RESAMPLER LAB ERROR] {type(error).__name__}: {error}",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build the Stage66-verified C ABI as a LOCAL Linux shared library.

Uses only a SHA-pinned local MIT r8brain v6.5 git cache, the already tested
Stage63 constructor patch, and the Stage66 bridge. Never commits sources,
captured audio, vendor DLLs, or compiled libraries. No network/bootstrap.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from datetime import datetime, timezone

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[2]
NATIVE_COMPAT = LAB.parent / "native_compat"
if str(NATIVE_COMPAT) not in sys.path:
    sys.path.insert(0, str(NATIVE_COMPAT))

import audit_bridge as bridge  # noqa: E402

DEFAULT_CACHE = ROOT / "research" / "_LOCAL_FILES" / "stage41_r8brain_git"
LIB_FOLDER = ROOT / "research" / "_LOCAL_FILES" / "resampler_lab"
LIB_NAME = "libhtkpa_native_frac.so"
MANIFEST_NAME = "build.json"
PIN = bridge.stage55.PINS[bridge.PIN]
BETA_HEX = "0x1.91af20df9e8bap+3"
POWER_HEX = "0x1.83fa5ca7f6a99p+0"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_meta(meta: dict, library: Path) -> None:
    """Never load a stale/wrong or locally altered shared library."""
    if not isinstance(meta, dict) or meta.get("schema_version") != 1:
        raise ValueError("Resampler Lab build manifest schema mismatch")
    source = meta.get("source", {})
    patch = source.get("patch", {})
    if (source.get("source_commit") != PIN
            or source.get("bridge_source_sha256") != sha256(
                (NATIVE_COMPAT / "htkpa_native_frac_bridge.cpp").read_bytes())
            or patch.get("beta_hex") != BETA_HEX
            or patch.get("power_hex") != POWER_HEX
            or patch.get("phase_positions") != 673
            or patch.get("interpolation_mode") != "forced_poly_673"
            or meta.get("abi_id") != bridge.API_ID
            or meta.get("shared_object_sha256") != sha256(library.read_bytes())):
        raise ValueError("C++ library or manifest does not match verified Stage66 source")


def library_path(folder: Path | None = None) -> Path:
    return (Path(folder) if folder else LIB_FOLDER) / LIB_NAME


def verify_library(folder: Path | None = None):
    directory = Path(folder) if folder else LIB_FOLDER
    lib = directory / LIB_NAME
    manifest = directory / MANIFEST_NAME
    if not lib.is_file() or not manifest.is_file():
        raise FileNotFoundError("Lab C++ library missing. Run: python GO.py build")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert_meta(data, lib)
    return lib, data


def build_library(source_cache: Path = DEFAULT_CACHE, out_dir: Path = LIB_FOLDER,
                  cxx: str = "c++") -> tuple[Path, dict]:
    if sys.platform != "linux":
        raise OSError("This Lab build is Linux/WSL only. Use your WSL Python.")
    out_dir = Path(out_dir).resolve()
    if out_dir != LIB_FOLDER.resolve() and (
            not out_dir.is_relative_to((ROOT / "research" / "_LOCAL_FILES").resolve())):
        raise ValueError("Refusing to publish binary outside ignored research/_LOCAL_FILES")
    with tempfile.TemporaryDirectory(prefix="htkpa_lab_build_") as td:
        work = Path(td)
        src = work / "public"
        src.mkdir()
        bridge.stage55.ensure_checkout(Path(source_cache), PIN, src)
        candidate = work / LIB_NAME
        source_info = bridge.compile_bridge(src, candidate, cxx)
        if (not candidate.is_file() or candidate.stat().st_size < 1024
                or source_info.get("source_commit") != PIN
                or source_info.get("patch", {}).get("beta_hex") != BETA_HEX
                or source_info.get("patch", {}).get("power_hex") != POWER_HEX):
            raise ValueError("Pinned Stage66 compilation did not produce the expected bridge")
        # Check the actual compiled ABI before publishing.
        bridge.bind_abi(candidate)
        meta = {
            "schema_version": 1,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "purpose": "private standalone 96k->44.1k or 44.1k->48k resampling Lab",
            "abi_id": bridge.API_ID,
            "source": source_info,
            "shared_object_sha256": sha256(candidate.read_bytes()),
            "vendor_dll_included": False,
            "browser_nam_converter_changed": False,
        }
        assert_meta(meta, candidate)
        out_dir.mkdir(parents=True, exist_ok=True)
        # Publish one complete new binary/manifest from local temp; no Git writes.
        temp_bin = out_dir / (LIB_NAME + ".staging")
        temp_manifest = out_dir / (MANIFEST_NAME + ".staging")
        try:
            shutil.copyfile(candidate, temp_bin)
            temp_manifest.write_text(
                json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8")
            os.replace(temp_bin, out_dir / LIB_NAME)
            os.replace(temp_manifest, out_dir / MANIFEST_NAME)
        finally:
            for item in (temp_bin, temp_manifest):
                item.unlink(missing_ok=True)
        verify_library(out_dir)
        return out_dir / LIB_NAME, meta

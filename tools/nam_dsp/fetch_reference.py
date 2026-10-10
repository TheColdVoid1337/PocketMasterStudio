#!/usr/bin/env python3
"""Fetch the exact SonicMaster reference DI once; verify Git blob SHA before use.

This 12.348 MB asset is not committed into PocketMasterStudio and never served
from the HTML server. Network access is required only for the first download.
"""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import tempfile
from urllib.request import urlopen

REF_COMMIT = "a3059ccd0570640782d36bc0f08defc4fb428cd2"
UPSTREAM_PATH = "app/assets/data/nam_reference_di_44100.f32"
URL = f"https://raw.githubusercontent.com/Skyggedans/SonicMaster/{REF_COMMIT}/{UPSTREAM_PATH}"
EXPECTED_SIZE = 12_348_000
EXPECTED_BLOB_SHA = "e8a4479f292ad096df1edacdd083f19a72d61987"
DEST = Path(__file__).resolve().parent / "data" / "nam_reference_di_44100.f32"

def verified_blob(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size != EXPECTED_SIZE:
        return False
    sha = hashlib.sha1(f"blob {EXPECTED_SIZE}".encode() + bytes([0]))
    with path.open("rb") as fp:
        for part in iter(lambda: fp.read(1024 * 1024), b""):
            sha.update(part)
    return sha.hexdigest() == EXPECTED_BLOB_SHA

def fetch() -> Path:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    if verified_blob(DEST):
        print(f"Verified existing reference DI: {DEST}")
        return DEST
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".nam_di_", suffix=".tmp",
                                         dir=DEST.parent, delete=False) as out:
            temp_path = Path(out.name)
            with urlopen(URL, timeout=90) as reply:
                total = 0
                while True:
                    part = reply.read(1024 * 1024)
                    if not part:
                        break
                    total += len(part)
                    if total > EXPECTED_SIZE:
                        raise ValueError("Reference DI is larger than pinned upstream asset")
                    out.write(part)
        if not verified_blob(temp_path):
            raise ValueError("Reference DI size / Git SHA mismatch; refusing untrusted data")
        os.replace(temp_path, DEST)
        print(f"Downloaded & verified {EXPECTED_SIZE} bytes: {DEST}")
        return DEST
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    opts = parser.parse_args()
    if opts.verify_only:
        if not verified_blob(DEST):
            parser.error("Reference DI missing or SHA mismatch")
        print("Reference DI SHA verified")
    else:
        fetch()

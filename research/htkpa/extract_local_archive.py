#!/usr/bin/env python3
"""Safely expand the user-supplied HTKPA private input package without unzip.

Only extracts paths inside research/_LOCAL_FILES/. Existing files are NEVER
overwritten. Each resulting payload is verified against the ZIP manifest's
SHA256. This private material must NEVER be committed to Git.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path, PurePosixPath


def extract(root: Path, archive: Path) -> int:
    root = root.resolve()
    archive = archive.resolve()
    if not archive.is_file():
        print(f"Archive not found: {archive}", file=sys.stderr)
        return 2

    extracted = skipped = 0
    with zipfile.ZipFile(archive) as bundle:
        bad_member = bundle.testzip()
        if bad_member:
            raise ValueError(f"ZIP CRC failed: {bad_member}")

        members = bundle.infolist()
        for item in members:
            rel = PurePosixPath(item.filename)
            if (rel.is_absolute() or ".." in rel.parts
                    or rel.parts[:2] != ("research", "_LOCAL_FILES")):
                raise ValueError(f"Unexpected archive path: {item.filename}")
            target = root.joinpath(*rel.parts)
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink():
                raise ValueError(f"Refusing to follow symlink: {target}")
            if target.exists():
                skipped += 1
                continue
            # Exclusive creation prevents overwriting concurrent user files.
            with bundle.open(item) as source, target.open("xb") as dest:
                shutil.copyfileobj(source, dest)
            extracted += 1

    manifest_path = root / "research/_LOCAL_FILES/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures = []
    for rec in manifest["files"]:
        rel = PurePosixPath(rec["path"])
        if rel.parts[:2] != ("research", "_LOCAL_FILES") or ".." in rel.parts:
            raise ValueError(f"Bad manifest path: {rel}")
        target = root.joinpath(*rel.parts)
        if not target.is_file():
            failures.append(f"missing: {rel}")
            continue
        sha = hashlib.sha256(target.read_bytes()).hexdigest()
        if sha != rec["sha256"]:
            failures.append(f"SHA256 MISMATCH: {rel}")
    print(f"Extracted {extracted}; preserved existing {skipped}; "
          f"verified {len(manifest['files']) - len(failures)}/{len(manifest['files'])} private files.")
    for msg in failures:
        print(msg, file=sys.stderr)
    if failures:
        print("Existing mismatched files were NOT overwritten.", file=sys.stderr)
        return 1
    print("PASS. research/_LOCAL_FILES is Git-ignored; never stage or publish it.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True,
                   help="User's POCKET_MASTER_HTKPA_CODEX_LOCAL_FILES ZIP")
    args = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    return extract(root, args.archive)


if __name__ == "__main__":
    raise SystemExit(main())

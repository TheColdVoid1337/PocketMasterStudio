#!/usr/bin/env python3
"""Safely repair CRLF-only changes in tracked research/docs files.

Dry-run by default. In --apply mode, changes a worktree file only when
replacing CRLF with LF makes its bytes EXACTLY match Git HEAD. Does not
reset, delete, stage, or touch genuinely edited or untracked files.
"""
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


def git(root: Path, *args: str) -> bytes:
    proc = subprocess.run(
        ["git", *args], cwd=root, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False
    )
    if proc.returncode:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {os.fsdecode(proc.stderr).strip()}"
        )
    return proc.stdout


def repair(root: Path, apply: bool, verbose: bool = False) -> int:
    paths = [
        os.fsdecode(item)
        for item in git(root, "ls-files", "-z", "--", "docs/", "research/").split(b"\0")
        if item
    ]
    exact_crlf = 0
    protected = []
    for rel in paths:
        file = root / rel
        if not file.is_file() or file.is_symlink():
            continue
        raw = file.read_bytes()
        if b"\r\n" not in raw:
            continue
        normalized = raw.replace(b"\r\n", b"\n")
        # Even when all CRLFs disappear, preserve mixed/other CR bytes.
        # Those require manual review, not a blind mass conversion.
        if b"\r" in normalized:
            protected.append(rel + " (mixed line endings)")
            continue
        reference = git(root, "show", f"HEAD:{rel}")
        if normalized != reference:
            protected.append(rel + " (non-line-ending edits)")
            continue
        exact_crlf += 1
        if verbose:
            print(("FIX " if apply else "WOULD FIX ") + rel)
        if apply:
            # Re-check before writing; refuse to overwrite a concurrent edit.
            if file.read_bytes() != raw:
                protected.append(rel + " (changed during scan)")
                exact_crlf -= 1
                continue
            file.write_bytes(normalized)

    print(
        f"CRLF-only tracked files {'fixed' if apply else 'eligible'}: {exact_crlf}; "
        f"preserved for manual review: {len(protected)}"
    )
    for name in protected[:25]:
        print("PRESERVED", name)
    if len(protected) > 25:
        print(f"... and {len(protected) - 25} more; rerun with --verbose to inspect")
    print("No untracked files, binaries, production code or private inputs were changed.")
    return 0 if not protected else 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true", help="Repair only exact CRLF-only changes")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    return repair(root, args.apply, args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())

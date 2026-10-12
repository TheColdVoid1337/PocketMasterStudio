#!/usr/bin/env python3
"""Verify the archived research sources after cloning. Does not require the proprietary DLL."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def verify(root: Path, manifest: Path):
    data=json.loads(manifest.read_text(encoding='utf-8'))
    failed=[]
    for record in data['files']:
        source=root/record['path']
        if not source.is_file(): failed.append(f"MISSING {record['path']}"); continue
        content=source.read_bytes()
        actual=hashlib.sha256(content).hexdigest()
        if actual!=record['sha256']: failed.append(f"SHA256 MISMATCH {record['path']} expected={record['sha256']} got={actual}")
    return len(data['files']),failed

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo-root',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--manifest',type=Path)
    a=p.parse_args()
    root=a.repo_root.resolve(); manifest=a.manifest or root/'research/htkpa/source_archive_manifest.json'
    total,problems=verify(root,manifest)
    print(f"HTKPA archive integrity: {total-len(problems)}/{total} source files validated")
    for problem in problems: print(problem)
    if problems: raise SystemExit(1)
    print('WARNING: Stage05 scripts unavailable. The partial archive does NOT prove end-to-end NAM->CLO parity.')

if __name__=='__main__': main()

#!/usr/bin/env python3
"""Opt-in HTKPA research: sealed private tar.gz runs, one Git finding log, curated rollover."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "research" / "_LOCAL_FILES"
ARCHIVES = PRIVATE / "research_runs"
STAGING = ROOT / "research" / ".research_run_staging"
JOURNAL = ROOT / "research" / "htkpa" / "RE_LOG.md"
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,59}\Z")
MAX_LOG = 8 * 1024 * 1024
MAX_FILES = 2048


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def git_sha():
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              text=True, capture_output=True, check=True,
                              timeout=3).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def valid_name(name):
    if not NAME.fullmatch(name):
        raise ValueError("name must start with letter and contain <=60 ASCII letters/digits/_/-")
    return name


def refs(paths):
    if len(paths) > 40:
        raise ValueError("too many selected reference files")
    result = []
    for raw in paths:
        p = Path(raw).expanduser().resolve()
        if not p.is_file():
            raise ValueError("missing reference: " + raw)
        try:
            label = str(p.relative_to(ROOT))
        except ValueError:
            label = str(p)
        result.append({"path": label, "bytes": p.stat().st_size, "sha256": sha(p)})
    return result


def save_json(p, data):
    tmp = p.with_name(p.name + ".temp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def new_stage(name):
    valid_name(name)
    STAGING.mkdir(parents=True, exist_ok=True)
    for _ in range(30):
        p = STAGING / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ") + "_" + name)
        try:
            p.mkdir(mode=0o700)
            (p / "output").mkdir()
            return p
        except FileExistsError:
            pass
    raise RuntimeError("unable to create unique run directory")


def output_files(folder):
    results = []
    for p in (folder / "output").rglob("*"):
        if p.is_symlink():
            raise ValueError("symlink in output: refusing packaging")
        if p.is_file():
            if len(results) >= MAX_FILES:
                raise ValueError("too many research output files; staging preserved")
            results.append({"path": p.relative_to(folder).as_posix(),
                            "bytes": p.stat().st_size, "sha256": sha(p)})
    return sorted(results, key=lambda x: x["path"])


def seal(folder):
    """Only publish a VERIFIED tar.gz to LOCAL_FILES. Recoverable staging is elsewhere."""
    data = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    data["output_files"] = output_files(folder)
    save_json(folder / "run.json", data)
    ARCHIVES.mkdir(parents=True, exist_ok=True)
    STAGING.mkdir(parents=True, exist_ok=True)
    dest = ARCHIVES / (folder.name + ".tar.gz")
    if dest.exists():
        raise ValueError("archive already exists: " + str(dest))
    temp = STAGING / (folder.name + ".packing.tar.gz")
    try:
        files = [folder / "run.json"]
        if (folder / "console.log").exists():
            files.append(folder / "console.log")
        files.extend(folder / item["path"] for item in data["output_files"])
        with tarfile.open(temp, "w:gz") as tar:
            for file in files:
                tar.add(file, arcname=file.relative_to(folder).as_posix(), recursive=False)
        with tarfile.open(temp, "r:gz") as tar:
            for entry in tar:
                if not entry.isfile() or entry.name.startswith("/") or ".." in Path(entry.name).parts:
                    raise ValueError("invalid archive member")
                h = hashlib.sha256()
                with tar.extractfile(entry) as reader:
                    for block in iter(lambda: reader.read(1048576), b""):
                        h.update(block)
                if h.hexdigest() != sha(folder / entry.name):
                    raise ValueError("packed file digest mismatch")
        # Temp and output are on the same filesystem; rename publishes atomically.
        os.replace(temp, dest)
        shutil.rmtree(folder)
    finally:
        temp.unlink(missing_ok=True)
    return dest


def run(args):
    command = args.command[1:] if args.command and args.command[0] == "--" else args.command
    if not command:
        raise ValueError("run: command is required after --")
    references = refs(args.artifact)
    folder = new_stage(args.name)
    data = {"schema_version": 2, "kind": "command", "name": args.name,
            "started_utc": now(), "status": "RUNNING", "command": command,
            "git_head": git_sha(), "references": references,
            "log_cap_bytes": MAX_LOG}
    save_json(folder / "run.json", data)
    env = os.environ.copy()
    env["RESEARCH_ARTIFACT_DIR"] = str(folder / "output")
    proc = None
    rc, written, trunc = 1, 0, False
    print("[RUN] Private staging; outputs will be sealed to .tar.gz", flush=True)
    try:
        with (folder / "console.log").open("wb") as log:
            proc = subprocess.Popen(command, cwd=ROOT, env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    bufsize=0)
            for chunk in iter(lambda: proc.stdout.read(4096), b""):
                try:
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.buffer.flush()
                except BrokenPipeError:
                    pass
                if written < MAX_LOG:
                    part = chunk[:MAX_LOG-written]
                    log.write(part)
                    written += len(part)
                    trunc |= len(part) != len(chunk)
                else:
                    trunc = True
            rc = proc.wait()
        data["status"] = "SUCCEEDED" if rc == 0 else "FAILED"
    except KeyboardInterrupt:
        rc = 130
        data["status"] = "INTERRUPTED"
        data["child_still_running"] = proc is not None and proc.poll() is None
        print("\n[RUN] Interrupted; sealing available evidence without killing target", flush=True)
    except OSError as exc:
        rc = 127
        data["status"] = "FAILED_TO_START"
        data["error"] = str(exc)[:240]
    finally:
        if proc is not None and proc.stdout is not None:
            proc.stdout.close()
        data.update(finished_utc=now(), exit_code=rc, log_bytes=written,
                    log_truncated=trunc)
        save_json(folder / "run.json", data)
        try:
            dest = seal(folder)
            print(f"\n[ARCHIVE] {dest} | {data['status']} | exit={rc}", flush=True)
        except (ValueError, OSError, tarfile.TarError) as exc:
            print(f"[ERROR] Sealing failed: {exc}; recoverable data at {folder}",
                  file=sys.stderr)
            if rc == 0:
                rc = 2
    return rc


def record(args):
    references = refs(args.artifact)
    if not references and not args.finding:
        raise ValueError("record requires --artifact and/or --finding")
    folder = new_stage(args.name)
    save_json(folder / "run.json", {"schema_version": 2, "kind": "record",
              "name": args.name, "started_utc": now(), "finished_utc": now(),
              "status": args.status, "finding": args.finding,
              "git_head": git_sha(), "references": references})
    print(f"[ARCHIVE] {seal(folder)} | references only, private files not recopied")
    return 0


def recover(args):
    if not STAGING.is_dir():
        print("[RECOVER] Nothing to recover")
        return 0
    success = 0
    for folder in sorted(STAGING.iterdir()):
        if not folder.is_dir() or not (folder / "run.json").exists():
            continue
        data = json.loads((folder / "run.json").read_text(encoding="utf-8"))
        if data.get("status") == "RUNNING":
            data["status"] = "WRAPPER_INTERRUPTED_UNVERIFIED"
            data["recovery_utc"] = now()
            save_json(folder / "run.json", data)
        try:
            print("[RECOVER]", seal(folder))
            success += 1
        except (OSError, ValueError, tarfile.TarError) as exc:
            print(f"[RECOVER] Failed {folder.name}: {exc}", file=sys.stderr)
    print(f"[RECOVER] Sealed {success}; any failed staging is retained outside _LOCAL_FILES")
    return 0


def short(text, limit=500):
    text = text.strip()
    if not text or len(text) > limit or "\n" in text or "\r" in text:
        raise ValueError("finding fields must be nonempty, single-line and bounded")
    return text


def finding(args):
    """Write exactly ONE explicit factual research delta, never a broad docs sync."""
    stage = valid_name(args.stage)
    where = short(args.where)
    what = short(args.what)
    evidence = short(args.evidence)
    boundary = short(args.boundary, 300)
    if not JOURNAL.is_file():
        raise ValueError("missing canonical research journal: " + str(JOURNAL))
    entry = (f"\n## {now()} — {stage}: {args.kind.upper()} finding\n\n"
             f"- **Where:** {where}\n- **Found:** {what}\n"
             f"- **Evidence:** {evidence}\n- **Limit / next gate:** {boundary}\n")
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(entry)
    print("[FINDING] One tracked RE_LOG entry written; review git diff and commit")
    return 0


def rollover(args):
    """No bulk private-folder copying: explicitly chosen critical files only."""
    if not args.include or len(args.include) > 40:
        raise ValueError("rollover needs 1..40 explicit --include paths")
    chosen, seen = [], set()
    for raw in args.include:
        src = Path(raw).expanduser().resolve()
        if not src.is_file() or not src.is_relative_to(PRIVATE.resolve()):
            raise ValueError("each rollover source must be an existing private file")
        rel = src.relative_to(ROOT).as_posix()
        if rel in seen:
            raise ValueError("duplicate rollover source")
        seen.add(rel)
        chosen.append((src, rel))
    dest = Path(args.output).expanduser().resolve()
    if (not dest.name.startswith("POCKET_MASTER_HTKPA_PRIVATE_ROLLOVER_")
            or dest.suffix.lower() != ".zip"):
        raise ValueError("expected POCKET_MASTER_HTKPA_PRIVATE_ROLLOVER_*.zip")
    if not dest.is_relative_to(ROOT.resolve()) or dest.is_relative_to(PRIVATE.resolve()):
        raise ValueError("rollover ZIP must be outside _LOCAL_FILES, inside project")
    if dest.exists():
        raise ValueError("rollover ZIP already exists; refusing overwrite")
    STAGING.mkdir(parents=True, exist_ok=True)
    fd, rawtmp = tempfile.mkstemp(prefix="rollover_", suffix=".zip", dir=STAGING)
    os.close(fd)
    tmp = Path(rawtmp)
    manifest = {"schema_version": 1, "created_utc": now(), "selection": "explicit_only",
                "git_head": git_sha(),
                "files": [{"path": rel, "bytes": p.stat().st_size, "sha256": sha(p)}
                          for p, rel in chosen]}
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            z.writestr("ROLLOVER_MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
            for p, rel in chosen:
                z.write(p, arcname=rel)
        with zipfile.ZipFile(tmp) as z:
            if z.namelist() != ["ROLLOVER_MANIFEST.json"] + [rel for _, rel in chosen]:
                raise ValueError("rollover inventory mismatch")
            for row in manifest["files"]:
                h = hashlib.sha256()
                with z.open(row["path"]) as f:
                    for chunk in iter(lambda: f.read(1048576), b""):
                        h.update(chunk)
                if h.hexdigest() != row["sha256"]:
                    raise ValueError("rollover checksum mismatch")
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)
    print(f"[ROLLOVER] {dest} | {len(chosen)} SHA-verified files; never uploaded")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="HTKPA: sealed private runs, one Git research findings journal, selective rollover")
    sub = ap.add_subparsers(dest="action", required=True)
    a = sub.add_parser("run", help="archive console and RESEARCH_ARTIFACT_DIR even on command failure")
    a.add_argument("--name", required=True)
    a.add_argument("--artifact", action="append", default=[], help="hash reference only; no copy")
    a.add_argument("command", nargs=argparse.REMAINDER)
    b = sub.add_parser("record", help="reference existing artifacts in a sealed local manifest")
    b.add_argument("--name", required=True)
    b.add_argument("--artifact", action="append", default=[])
    b.add_argument("--status", choices=("accepted", "blocked", "observation"), default="observation")
    b.add_argument("--finding", default="")
    sub.add_parser("recover", help="seal retained staging after wrapper crash")
    d = sub.add_parser("finding", help="one deliberate research fact in tracked RE_LOG.md")
    d.add_argument("--stage", required=True)
    d.add_argument("--kind", choices=("confirmed", "hypothesis"), default="confirmed")
    d.add_argument("--where", required=True)
    d.add_argument("--what", required=True)
    d.add_argument("--evidence", required=True)
    d.add_argument("--boundary", required=True)
    e = sub.add_parser("rollover", help="explicitly select critical private files for ZIP handoff")
    e.add_argument("--output", required=True)
    e.add_argument("--include", action="append", default=[])
    args = ap.parse_args(argv)
    try:
        return {"run":run,"record":record,"recover":recover,
                "finding":finding,"rollover":rollover}[args.action](args)
    except (OSError, ValueError, json.JSONDecodeError, tarfile.TarError, zipfile.BadZipFile) as exc:
        ap.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

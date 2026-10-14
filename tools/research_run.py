#!/usr/bin/env python3
"""Minimal local-only research run capsules and one HTKPA status checkpoint.

Explicit opt-in: never records ordinary commands on its own. Raw logs/manifests
live under ignored research/_LOCAL_FILES/research_runs. 'close' is the only
command that writes tracked research/htkpa/STATUS.yaml.

Python stdlib only; intentionally does not touch README, RE_LOG, evidence, or Git.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / "research" / "_LOCAL_FILES" / "research_runs"
STATUS = ROOT / "research" / "htkpa" / "STATUS.yaml"
ID = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{0,59}\Z")
MAX_LOG = 8 * 1024 * 1024
MAX_ARTIFACTS = 20


def utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(file: Path) -> str:
    h = hashlib.sha256()
    with file.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_meta() -> dict:
    def read(*parts: str) -> str | None:
        try:
            return subprocess.run(["git", "-C", str(ROOT), *parts],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=3, check=True, text=True).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
    status = read("status", "--porcelain", "--untracked-files=no")
    changed = [line[3:] for line in status.splitlines()[:80]] if status else []
    return {"head": read("rev-parse", "HEAD"),
            "changed_tracked_files": changed,
            "dirty_tracked_files": bool(status) if status is not None else None}


def artifact_meta(files: list[str]) -> list[dict]:
    if len(files) > MAX_ARTIFACTS:
        raise ValueError(f"at most {MAX_ARTIFACTS} explicit artifact paths")
    result = []
    for raw in files:
        p = Path(raw).expanduser().resolve()
        if not p.is_file():
            raise ValueError(f"missing artifact file: {raw}")
        # Do not read arbitrary directories, copy files, or persist file contents.
        try:
            display = str(p.relative_to(ROOT))
        except ValueError:
            display = str(p)
        result.append({"path": display, "size_bytes": p.stat().st_size,
                       "sha256": digest(p)})
    return result


def new_capsule(name: str) -> Path:
    if not ID.fullmatch(name):
        raise ValueError("run name must be 1..60 characters: letters, numbers, _ or -")
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    # Unique directory, rather than replacing existing evidence.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    for i in range(20):
        p = RUN_ROOT / f"{stamp}_{name}{('-'+str(i)) if i else ''}"
        try:
            p.mkdir(mode=0o700)
            return p
        except FileExistsError:
            continue
    raise RuntimeError("cannot allocate unique research capsule")


def save_manifest(folder: Path, data: dict) -> None:
    target = folder / "run.json"
    contents = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=folder,
                                     prefix=".run_", delete=False) as t:
        t.write(contents)
        temp = Path(t.name)
    os.replace(temp, target)


def cmd_run(args) -> int:
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise ValueError("run needs a command after --")
    # This is an explicit capture wrapper. Avoid passing command-line secrets.
    folder = new_capsule(args.name)
    data = dict(schema_version=1, kind="command", name=args.name, started_utc=utc(),
                outcome="running", command=command, git_before=git_meta(),
                artifacts=[], stdout_log="console.log")
    save_manifest(folder, data)
    print(f"[RUN] Private research capsule: {folder}", flush=True)
    total, truncated, rc = 0, False, 1
    proc = None
    try:
        with (folder / "console.log").open("wb") as log:
            proc = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, bufsize=0)
            while True:
                block = proc.stdout.read(4096)
                if not block:
                    break
                # Preserve live output even after the private log reaches 8 MiB.
                sys.stdout.buffer.write(block)
                sys.stdout.buffer.flush()
                if total < MAX_LOG:
                    part = block[:MAX_LOG-total]
                    log.write(part)
                    total += len(part)
                    if len(part) != len(block):
                        truncated = True
                else:
                    truncated = True
            rc = proc.wait()
        data["outcome"] = "exit_zero" if rc == 0 else "nonzero_exit"
    except KeyboardInterrupt:
        # Ctrl+C was also delivered to the child in the same foreground process
        # group by a real WSL terminal. Do not force-kill any active native GUI.
        rc = 130
        data["outcome"] = "interrupted"
        data["child_still_running"] = proc is not None and proc.poll() is None
        print("\n[RUN] Interrupted; private evidence retained. Never killing an active target.", flush=True)
    except (OSError, ValueError) as exc:
        data["error"] = f"{type(exc).__name__}: {exc}"
        data["outcome"] = "failed_to_start"
        print(f"[RUN] {data['error']}", file=sys.stderr)
        rc = 127
    finally:
        if proc is not None and proc.stdout is not None:
            proc.stdout.close()
        data.update(finished_utc=utc(), exit_code=rc, log_bytes=total,
                    log_truncated=truncated, git_after=git_meta())
        try:
            data["artifacts"] = artifact_meta(args.artifact)
        except ValueError as exc:
            data["artifact_error"] = str(exc)
            if rc == 0:
                data["outcome"] = "missing_required_artifact"
                rc = 2
                data["exit_code"] = rc
        save_manifest(folder, data)
        print(f"\n[RUN] {data['outcome']} (exit {rc}); capsule: {folder/'run.json'}", flush=True)
    return rc


def cmd_record(args) -> int:
    artifacts = artifact_meta(args.artifact)
    if not artifacts and not args.finding:
        raise ValueError("record requires --artifact and/or --finding")
    folder = new_capsule(args.name)
    save_manifest(folder, dict(schema_version=1, kind="record", name=args.name,
         started_utc=utc(), finished_utc=utc(), outcome=args.outcome,
         finding=args.finding, artifacts=artifacts, git_at_record=git_meta()))
    print(f"[RUN] Recorded {len(artifacts)} selected artifact(s): {folder/'run.json'}")
    return 0


def cmd_close(args) -> int:
    """Only write one lightweight canonical state, once after a meaningful gate."""
    capsule = (RUN_ROOT / args.run / "run.json").resolve()
    if not capsule.is_relative_to(RUN_ROOT.resolve()) or not capsule.is_file():
        raise ValueError("--run must be an existing local research capsule directory name")
    record = json.loads(capsule.read_text(encoding="utf-8"))
    if record.get("schema_version") != 1 or record.get("outcome") in (None, "running"):
        raise ValueError("cannot close an incomplete or unknown run capsule")
    if args.decision == "accepted":
        if record.get("artifact_error"):
            raise ValueError("missing required artifact: cannot mark accepted")
        if record.get("kind") == "command" and record.get("exit_code") != 0:
            raise ValueError("command returned nonzero: cannot mark accepted; use blocked")
        if record.get("kind") == "record" and record.get("outcome") != "accepted":
            raise ValueError("record must explicitly be accepted before promotion")
    def scalar(value):
        return json.dumps(value, ensure_ascii=False)
    # YAML 1.2 accepts JSON-quoted strings; no PyYAML dependency or custom parser.
    fields = dict(schema_version="1", project="HTKPA", stage=args.stage,
         updated_utc=utc(), decision=args.decision, run_id=args.run,
         verified=args.finding, blocker=args.blocker or "none", next_action=args.next,
         reference=args.reference or
            f"research/_LOCAL_FILES/research_runs/{args.run}/run.json")
    content = "# Canonical HTKPA progress checkpoint; updated only by an explicit research close.\n"
    content += "# Private run data stays under ignored research/_LOCAL_FILES/research_runs/.\n"
    content += "\n".join(f"{key}: {val if key=='schema_version' else scalar(val)}" for key, val in fields.items())+"\n"
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=STATUS.parent,
                                     prefix=".status_", delete=False) as t:
        t.write(content)
        temp = Path(t.name)
    os.replace(temp, STATUS)
    print(f"[STATUS] Updated ONE checkpoint: {STATUS}")
    print("[STATUS] General README/RE_LOG/handoff were NOT touched. #syncdocs remains separate.")
    return 0


def cli(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Explicit, low-noise HTKPA experiment artifacts")
    sub = parser.add_subparsers(dest="action", required=True)
    a = sub.add_parser("run", help="opt-in command run: live console + private 8 MiB capped log")
    a.add_argument("--name", required=True)
    a.add_argument("--artifact", action="append", default=[], help="explicit file to hash/reference, repeatable")
    a.add_argument("command", nargs=argparse.REMAINDER)
    b = sub.add_parser("record", help="register an existing private archive or significant finding")
    b.add_argument("--name", required=True)
    b.add_argument("--artifact", action="append", default=[])
    b.add_argument("--outcome", choices=("accepted", "blocked", "observation"), default="observation")
    b.add_argument("--finding", default="")
    c = sub.add_parser("close", help="explicit significant-gate promotion to ONE status YAML")
    c.add_argument("--run", required=True, help="capsule directory name (not a path)")
    c.add_argument("--stage", required=True)
    c.add_argument("--decision", choices=("accepted", "blocked", "open"), required=True)
    c.add_argument("--finding", required=True)
    c.add_argument("--blocker", default="")
    c.add_argument("--next", required=True)
    c.add_argument("--reference", help="optional source/evidence path; default private run.json")
    args = parser.parse_args(argv)
    try:
        return {"run": cmd_run, "record": cmd_record, "close": cmd_close}[args.action](args)
    except (ValueError, OSError, json.JSONDecodeError) as err:
        parser.error(str(err))
    return 2


if __name__ == "__main__":
    raise SystemExit(cli())

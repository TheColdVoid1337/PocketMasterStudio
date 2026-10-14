#!/usr/bin/env python3
"""HTKPA Stage48: ONE-HOOK metadata-only probe at native resampler return RVA 0x1190C.

Windows x64 with installed Frida ONLY for explicit user-run; --self-test is
offline/cross-platform. No f64 reads, audio buffers, NAM/CLO or DLL ever
written to capture. Deliberately does NOT spawn or stop Sonicake Manager.
Production code is untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import threading
import time
from datetime import datetime, timezone

EXPECTED_SHA = "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"
MODULE_NAME = "5868USB.dll"
RVA_SITE = 0x1190C
RVA_VTABLE = 0x245170
MAX_VALID_F64 = 4096
MAX_OBSERVATIONS = 256
SOURCE_SHA_NOTE = "This instrument only records metadata; no signal samples."

COLORS = {
    "TARGET": "\x1b[36m", "HOOK": "\x1b[35m", "META": "\x1b[32m",
    "CLO": "\x1b[32m", "WAIT": "\x1b[33m", "NOTE": "\x1b[36m",
    "WARN": "\x1b[33m", "ERROR": "\x1b[31m", "STATUS": "\x1b[32m",
}
# FORCE_COLOR is set by STAGE48_WSL.sh since Windows Python launched from
# WSL does not always report a TTY even in a real interactive terminal.
def report(kind: str, *items: object) -> None:
    enabled = (os.environ.get("NO_COLOR") is None and
               (sys.stdout.isatty() or os.environ.get("FORCE_COLOR") == "1"))
    prefix = "[" + kind + "]"
    if enabled:
        prefix = COLORS.get(kind, "") + prefix + "\x1b[0m"
    print(prefix, *items, flush=True)


# Exactly ONE Frida Interceptor.attach() occurrence. It is NOT installed until
# Python verifies the actual loaded DLL file against the pinned private SHA.
AGENT = r"""
'use strict';
const MODNAME = '5868USB.dll';
const RETURN_RVA = 0x1190c;
const FRAC_VTABLE_RVA = 0x245170;
const MAX_VALID_F64 = 4096;
const MAX_OBSERVATIONS = 256;
let discovered = null, interceptor = null, seen = 0, validSent = false;
let firstRejectionSent = false;

function emit(event) {
  send(Object.assign({thread: Process.getCurrentThreadId()}, event));
}
function readable(p, length) {
  if (p.isNull() || length < 1) return false;
  const r = Process.findRangeByAddress(p);
  if (r === null || r.protection.indexOf('r') < 0) return false;
  return p.compare(r.base) >= 0 &&
         p.add(length - 1).compare(r.base.add(r.size)) < 0;
}
function reject(reason) {
  if (!firstRejectionSent) {
    firstRejectionSent = true;
    emit({kind:'first_rejected_return',reason:reason,observed:seen});
  }
}

rpc.exports = {
  arm() {
    if (interceptor !== null) return false;
    const moduleNow = Process.findModuleByName(MODNAME);
    if (moduleNow === null || discovered === null ||
        !moduleNow.base.equals(discovered.base)) {
      emit({kind:'arm_error',reason:'module disappeared or changed'});
      return false;
    }
    const addr = moduleNow.base.add(RETURN_RVA);
    const code = Process.findRangeByAddress(addr);
    if (code === null || code.protection.indexOf('x') < 0 ||
        RETURN_RVA >= moduleNow.size) {
      emit({kind:'arm_error',reason:'code address outside executable DLL range'});
      return false;
    }
    try {
      interceptor = Interceptor.attach(addr, {
        onEnter() {
          if (validSent || ++seen > MAX_OBSERVATIONS) return;
          // This is a mid-function address immediately AFTER virtual CALL.
          // RCX/RDX/R8/R9 are NOT its new arguments here: use saved RBX/R15
          // and returned EAX exactly as verified by Stage47 disassembly.
          try {
            const context = this.context;
            const rbx = context.rbx, r15 = context.r15;
            if (!readable(rbx.add(0x50), 8)) return reject('last-stage slot unreadable');
            const proc = rbx.add(0x50).readPointer();
            if (!readable(proc, 8)) return reject('last-stage object unreadable');
            const vt = proc.readPointer();
            const expected = moduleNow.base.add(FRAC_VTABLE_RVA);
            if (!vt.equals(expected)) return reject('last-stage vtable not fractional');
            const count = context.rax.and(ptr('0xffffffff')).toUInt32();
            if (count < 1 || count > MAX_VALID_F64)
              return reject('returned EAX count zero or over defensive bound');
            if (!readable(r15, 8)) return reject('output-pointer reference unreadable');
            const output = r15.readPointer();
            if (!output.and(ptr('0x7')).isNull())
              return reject('output pointer not f64 aligned');
            const bytes = count * 8;
            if (!readable(output, bytes))
              return reject('output f64-sized region unreadable');
            // Do not call readByteArray/readDouble/readFloat here. No waveform.
            validSent = true;
            emit({
              kind:'metadata_hit',valid:true,observed:seen,
              last_stage_vtable:vt.toString(),
              expected_vtable:expected.toString(),
              output_pointer:output.toString(),
              output_f64:count,
              output_bytes:bytes,
              output_range_readable:true,
              site:addr.toString(),
              note:'No f64 sample bytes read. CLO completion not known on target.'
            });
          } catch (e) {
            reject('guard exception: '+String(e).slice(0,120));
          }
        }
      });
      emit({kind:'hook_attached',rva:RETURN_RVA,site:addr.toString(),
            hooks_installed:1});
      return true;
    } catch (e) {
      emit({kind:'arm_error',reason:String(e).slice(0,180)});
      return false;
    }
  }
};

Process.attachModuleObserver({
  onAdded(m) {
    if (m.name.toLowerCase() !== MODNAME.toLowerCase()) return;
    discovered = m;
    // Python MUST hash m.path before calling rpc.exports.arm().
    emit({kind:'module_found',name:m.name,path:m.path,
          base:m.base.toString(),size:m.size});
  }
});
"""


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def json_line(path: Path, obj: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=True, sort_keys=True) + "\n")


def snapshot_clo(folder: Path | None) -> dict[str, tuple[int, int]]:
    if folder is None:
        return {}
    result = {}
    # CLO may be saved in a nested preset/profile folder. This never opens
    # the file contents: only stat metadata, bounded to this user-given root.
    for path in folder.rglob("*.clo"):
        try:
            st = path.stat()
            result[str(path.resolve()).casefold()] = (st.st_size, st.st_mtime_ns)
        except OSError:
            pass
    return result


def reconcile_events(folder: Path, state: dict) -> None:
    """Recover real hook/metadata observations after Ctrl+C or host exceptions.

    Never invent a successful CLO completion or module-SHA check from JSONL.
    In particular, a valid metadata_hit is not vendor 48-kHz sample parity.
    """
    stream = folder / "events.jsonl"
    try:
        lines = stream.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        report("WARN", "Cannot read event journal:", e)
        return
    state["events_on_disk"] = len(lines)
    for line in lines:
        try:
            event = json.loads(line)
        except (TypeError, ValueError):
            state["malformed_event_lines"] = state.get("malformed_event_lines", 0) + 1
            continue
        if event.get("kind") == "hook_attached" and event.get("hooks_installed") == 1:
            state["hook_attached"] = True
        elif event.get("kind") == "metadata_hit" and event.get("valid") is True:
            state["metadata_valid"] = True
            state["metadata"] = event
        elif event.get("kind") == "first_rejected_return":
            state["first_rejection"] = event.get("reason")


def self_test() -> None:
    assert AGENT.count("Interceptor.attach(") == 1
    assert "rpc.exports" in AGENT
    assert "Process.attachModuleObserver" in AGENT
    for forbidden in ("readByteArray(", "readDouble(", "readFloat(", "writeByteArray("):
        assert forbidden not in AGENT, forbidden
    assert "module_found" in AGENT and "metadata_hit" in AGENT
    assert RVA_SITE == 0x1190C and RVA_VTABLE == 0x245170
    assert MAX_VALID_F64 * 8 <= 32768
    # Reproduce the actual operator Ctrl+C regression from 2026-10-14:
    # even if the in-memory state vanished, event journal has valid 114 f64.
    import tempfile
    from types import SimpleNamespace
    with tempfile.TemporaryDirectory(prefix="htkpa48_selftest_") as tmp:
        d = Path(tmp)
        events = [
            {"kind": "module_found", "base": "0x7ff862660000"},
            {"kind": "hook_attached", "hooks_installed": 1, "rva": 0x1190C},
            {"kind": "first_rejected_return", "reason": "returned EAX count zero or over defensive bound"},
            {"kind": "metadata_hit", "valid": True, "output_f64": 114,
             "output_bytes": 912, "observed": 18},
        ]
        (d / "events.jsonl").write_text(
            "".join(json.dumps(e)+"\n" for e in events), encoding="utf-8")
        restored = {}
        reconcile_events(d, restored)
        assert restored["hook_attached"] is True
        assert restored["metadata_valid"] is True
        assert restored["metadata"]["output_f64"] == 114
        assert restored["events_on_disk"] == 4
        assert "module_sha_verified" not in restored
        nested = d / "subdir"
        nested.mkdir()
        (nested / "new.clo").write_bytes(b"mock-not-real-clo")
        assert len(snapshot_clo(d)) == 1
    class FakeDevice:
        def enumerate_processes(self):
            return [SimpleNamespace(pid=14000, name="Sonicake Manager.exe"),
                    SimpleNamespace(pid=100, name="explorer.exe")]
    assert choose_pid(FakeDevice(), None) == 14000
    assert choose_pid(FakeDevice(), 14000) == 14000
    print("Stage48 offline tests PASS: one hook; no audio reads; "
          "automatic PID; Ctrl+C event recovery; nested CLO discovery")


def list_processes_only() -> int:
    """Safe Windows/Frida process discovery; NEVER calls device.attach or arms a hook."""
    if os.name != "nt" or platform.architecture()[0] != "64bit":
        raise RuntimeError("Use the existing Windows x64 Python, not WSL Python")
    try:
        import frida
    except ImportError as e:
        raise RuntimeError("Frida missing from the Windows Python") from e
    processes = frida.get_local_device().enumerate_processes()
    hints = ("sonic", "manager", "pocket", "tone", "5868", "usb")
    candidates = sorted(
        (p for p in processes if any(q in p.name.casefold() for q in hints)),
        key=lambda p: (p.name.casefold(), p.pid)
    )
    print("[DISCOVERY] Frida sees", len(processes), "Windows processes", flush=True)
    if candidates:
        print("[DISCOVERY] Candidate executable names and PIDs:", flush=True)
        for process in candidates:
            print("  PID", process.pid, "|", process.name, flush=True)
    else:
        print("[DISCOVERY] No Sonicake/Manager-related process name found.", flush=True)
        print("[DISCOVERY] Make sure Manager is OPEN, then use Windows Task Manager")
        print("[DISCOVERY] Details -> PID, or PowerShell Get-CimInstance Win32_Process.")
    print("[DISCOVERY] ZERO hooks installed. Supply the real Manager PID as --pid <NUMBER>.")
    return 0


def choose_pid(device, specified: int | None) -> int:
    processes = device.enumerate_processes()
    if specified is not None:
        if specified <= 0:
            raise ValueError("PID must be positive")
        target = next((p for p in processes if p.pid == specified), None)
        if target is None:
            raise ValueError("PID "+str(specified)+" not running; Manager may have restarted")
        if "sonicake" not in target.name.casefold():
            raise ValueError("PID "+str(specified)+" is "+repr(target.name)+
                             ", NOT a Sonicake process; refusing to attach")
        report("TARGET", "Verified explicit PID", target.pid, "|", target.name)
        return target.pid
    # Auto-detect ONE live Sonicake process; do not require the additional
    # word 'Manager' in its EXE filename (legacy discovery was too strict).
    matches = [p for p in processes if "sonicake" in p.name.casefold()]
    if len(matches) != 1:
        report("WARN", "Auto-discovery found", len(matches),
               "Sonicake processes among", len(processes), "Windows processes")
        for p in matches:
            report("NOTE", "Candidate", p.pid, "|", p.name)
        raise ValueError("Open exactly one Sonicake Manager, or use "
                         "--list-processes and then --pid <confirmed PID>")
    report("TARGET", "Auto-found", matches[0].name, "| PID", matches[0].pid)
    return matches[0].pid


def execute(args: argparse.Namespace, folder: Path, state: dict) -> str:
    if os.name != "nt" or platform.architecture()[0] != "64bit":
        raise RuntimeError("Use an existing Windows x64 Python+Frida venv, NOT WSL Python")
    try:
        import frida
    except ImportError as e:
        raise RuntimeError("Frida not installed in this Windows Python") from e

    device = frida.get_local_device()
    pid = choose_pid(device, args.pid)
    state.update({"pid": pid, "module_sha_verified": False,
                  "hook_attached": False, "metadata_valid": False,
                  "frida_errors": 0, "first_rejection": None,
                  "metadata_events": 0, "events_logged": 0,
                  "stable_clo_observed": False})
    lock = threading.Lock()
    pending_modules: list[dict] = []
    capture_events = folder / "events.jsonl"
    session = None
    script = None
    baseline = snapshot_clo(args.completion_dir)
    selected = None
    selected_since = None
    arm_attempted = False
    try:
        session = device.attach(pid)
        script = session.create_script(AGENT)

        def on_message(msg, binary) -> None:
            # Stage48 NEVER accepts binary attachments.
            if binary is not None:
                event = {"kind": "binary_payload_REJECTED", "error": True}
            elif msg.get("type") == "send":
                event = msg.get("payload", {})
                if not isinstance(event, dict):
                    event = {"kind": "invalid_payload", "error": True}
            else:
                event = {"kind": "script_error", "error": str(msg)[:400]}
            with lock:
                json_line(capture_events, event)
                kind = event.get("kind")
                state["events_logged"] += 1
                if kind == "module_found":
                    pending_modules.append(event)
                elif kind == "hook_attached":
                    state["hook_attached"] = event.get("hooks_installed") == 1
                elif kind == "metadata_hit":
                    if event.get("valid") is True:
                        state["metadata_valid"] = True
                        state["metadata_events"] += 1
                        state["metadata"] = event
                elif kind == "first_rejected_return":
                    state["first_rejection"] = event.get("reason")
                elif kind in ("arm_error", "script_error", "binary_payload_REJECTED",
                              "invalid_payload"):
                    state["frida_errors"] += 1
            # Print outside the lock. These are messages from Frida to Python,
            # NEVER per-sample reads or logging in the target callback.
            if kind == "metadata_hit":
                report("META", "Native fractional output:",
                       event.get("output_f64"), "f64 /",
                       event.get("output_bytes"), "bytes, event",
                       event.get("observed"),
                       "| pointer", event.get("output_pointer"))
            elif kind == "first_rejected_return":
                report("NOTE", "First return ignored:", event.get("reason"),
                       "(later returns are still evaluated)")
            elif kind == "hook_attached":
                report("HOOK", "Single hook armed at RVA 0x1190C")
            elif kind in ("arm_error", "script_error", "binary_payload_REJECTED",
                          "invalid_payload"):
                report("ERROR", "Frida", kind, event.get("reason", event.get("error", "")))

        script.on("message", on_message)
        script.load()
        report("NOTE", "Attached observer; verifying real loaded DLL SHA before hook")
        start = time.monotonic()
        last_progress = 0.0
        last_clo_poll = 0.0
        last_pid_check = 0.0
        last_mode = None
        watch_count = len(baseline)
        report("CLO", "Watching", str(args.completion_dir),
               "| baseline files:", watch_count, "(recursive, metadata only)")
        report("NOTE", "After [HOOK], perform ONE ordinary NAM-to-CLO conversion")
        while time.monotonic() - start < args.timeout:
            time.sleep(0.2)
            with lock:
                found = pending_modules.pop(0) if pending_modules else None
                errors = state["frida_errors"]
                valid = state["metadata_valid"]
                attached = state["hook_attached"]
            if errors:
                return "BLOCKED_AGENT_ERROR"

            if found is not None and not arm_attempted:
                arm_attempted = True
                loaded = Path(found["path"])
                if loaded.name.casefold() != MODULE_NAME.casefold():
                    raise ValueError("Loaded module name differs from pinned basename")
                loaded_sha = digest_file(loaded)
                if loaded_sha != EXPECTED_SHA:
                    raise ValueError("Loaded module DLL file hash mismatch, never hook")
                with lock:
                    state["module_sha_verified"] = True
                    state["loaded_dll_path"] = str(loaded)
                    state["module_base"] = found.get("base")
                if not script.exports_sync.arm():
                    raise RuntimeError("Refused to install the single post-return hook")
                report("HOOK", "Loaded DLL SHA256 verified; one hook at RVA 0x1190C")
                report("NOTE", "NOW run one conversion in Manager; observing metadata, NOT audio")

            now = time.monotonic()
            # A disconnected Manager is not a successful conversion.
            # Detect it without another Frida hook, read or DLL execution.
            if now - last_pid_check >= 3.0:
                last_pid_check = now
                if not any(proc.pid == pid for proc in device.enumerate_processes()):
                    report("ERROR", "Sonicake Manager PID", pid,
                           "exited or disappeared; preserving captured metadata")
                    state["target_disappeared"] = True
                    return ("BLOCKED_MANAGER_EXITED_AFTER_METADATA" if valid
                            else "BLOCKED_MANAGER_EXITED")
            if attached and valid and last_mode != "metadata":
                last_mode = "metadata"
                report("META", "Validated output metadata. Awaiting NEW/CHANGED stable CLO.")
            elif attached and not valid and last_mode != "hook":
                last_mode = "hook"
                report("WAIT", "Hook active; waiting for a valid fractional return.")
            if now - last_progress >= 15.0:
                last_progress = now
                report("WAIT", "elapsed", int(now-start), "s | attached=", attached,
                       "| metadata=", valid, "| new CLO=", state["stable_clo_observed"])
            # Watch regardless of when metadata arrives so a quickly written
            # CLO is not missed; PASS still requires both independent gates.
            if args.completion_dir is not None and now-last_clo_poll >= 1.0:
                last_clo_poll = now
                current = snapshot_clo(args.completion_dir)
                modified = [(path, meta) for path, meta in current.items()
                            if meta[0] > 0 and baseline.get(path) != meta]
                if modified:
                    newest = max(modified, key=lambda pair: pair[1][1])
                    if newest == selected:
                        if selected_since is not None and now-selected_since >= 3.0:
                            if not state["stable_clo_observed"]:
                                report("CLO", "NEW/CHANGED CLO stable:",
                                       Path(newest[0]).name,
                                       "|", newest[1][0], "bytes")
                            with lock:
                                state["stable_clo_observed"] = True
                                state["stable_clo_size_bytes"] = newest[1][0]
                                state["stable_clo_path"] = newest[0]
                    else:
                        selected = newest
                        selected_since = now
                        report("CLO", "Detected new/changed CLO; checking 3s stability:",
                               Path(newest[0]).name)
                else:
                    selected = None
                    selected_since = None
            with lock:
                success = (state["metadata_valid"] and state["hook_attached"] and
                           state["module_sha_verified"] and
                           state["stable_clo_observed"] and
                           not state["frida_errors"])
            if success:
                return "METADATA_GUARD_PASS_CLO_STABLE"
        if state["metadata_valid"]:
            return "METADATA_OBSERVED_CLO_UNVERIFIED_TIMEOUT"
        return "INCOMPLETE_TIMEOUT"
    finally:
        if script is not None:
            try:
                script.unload()
            except Exception:
                pass
        if session is not None:
            try:
                session.detach()
            except Exception:
                pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--list-processes", action="store_true",
                    help="List likely Sonicake/Manager PIDs and exit with ZERO Frida hooks")
    ap.add_argument("--dll", type=Path, help="Pinned private original DLL, only SHA read")
    ap.add_argument("--pid", type=int, help="Existing Manager PID; never spawn Manager")
    ap.add_argument("--completion-dir", type=Path,
                    help="Existing Windows directory containing NEW/CHANGED CLO after conversion")
    ap.add_argument("--out", type=Path, default=Path("research/_LOCAL_FILES/frida_captures"))
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()
    if args.self_test:
        self_test()
        if args.dll is not None:
            assert digest_file(args.dll) == EXPECTED_SHA, "private DLL SHA mismatch"
            print("Private DLL SHA256 verified")
        return 0
    if args.list_processes:
        return list_processes_only()
    if args.dll is None or not args.dll.is_file():
        ap.error("--dll original private 5868USB.dll is required")
    if not 15 <= args.timeout <= 1800:
        ap.error("--timeout must be 15..1800 seconds")
    if args.completion_dir is not None and not args.completion_dir.is_dir():
        ap.error("--completion-dir must be an existing Windows directory")
    if digest_file(args.dll) != EXPECTED_SHA:
        ap.error("--dll SHA256 differs from the exact original study")
    args.out.mkdir(parents=True, exist_ok=True)
    folder = args.out / ("stage48_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f"))
    folder.mkdir(exist_ok=False)
    (folder / "events.jsonl").touch()
    result = {}
    status = "BLOCKED"
    problem = None
    try:
        status = execute(args, folder, result)
    except KeyboardInterrupt:
        status = ("METADATA_OBSERVED_OPERATOR_INTERRUPTED" if result.get("metadata_valid")
                  else "OPERATOR_INTERRUPTED_BEFORE_METADATA")
        problem = "Operator interrupted (Ctrl+C); original Frida events were preserved"
        report("WARN", problem)
    except Exception as e:
        status = ("BLOCKED_AFTER_METADATA" if result.get("metadata_valid")
                  else "BLOCKED")
        problem = f"{type(e).__name__}: {e}"[:550]
        report("ERROR", problem)
    # Recover observed events even if the host was interrupted while unwinding.
    reconcile_events(folder, result)
    if status == "OPERATOR_INTERRUPTED_BEFORE_METADATA" and result.get("metadata_valid"):
        status = "METADATA_OBSERVED_OPERATOR_INTERRUPTED"
    if status == "BLOCKED" and result.get("metadata_valid"):
        status = "BLOCKED_AFTER_METADATA"
    manifest = {
        "stage": 48,
        "status": status,
        "date_utc": datetime.now(timezone.utc).isoformat(),
        "original_dll_sha256": EXPECTED_SHA,
        "site_rva": "0x1190c",
        "hook_count": 1 if result.get("hook_attached") else 0,
        "contains_audio": False,
        "vendor_fractional_samples_captured": False,
        "ready_to_capture_audio": status == "METADATA_GUARD_PASS_CLO_STABLE",
        "problem": problem,
        "state": result,
        "operator_note": SOURCE_SHA_NOTE,
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                          encoding="utf-8")
    report("STATUS", status, "| hooked:", bool(result.get("hook_attached")),
           "| metadata:", bool(result.get("metadata_valid")),
           "| stable CLO:", bool(result.get("stable_clo_observed")))
    report("NOTE", "Saved", folder / "manifest.json")
    report("NOTE", "Saved", folder / "events.jsonl")
    return 0 if status == "METADATA_GUARD_PASS_CLO_STABLE" else 2


if __name__ == "__main__":
    raise SystemExit(main())

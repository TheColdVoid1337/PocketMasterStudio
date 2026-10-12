"""Stage23W Windows-only, read-only Frida trace for 5868USB.dll FIR sites.

Run this only against a user-authorized local Manager process.  The output
directory is deliberately an explicit argument and must be under the ignored
research/_LOCAL_FILES tree.  The script does not modify the DLL, process
memory, device state, or production sources.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DLL_SHA256 = "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"
PREFERRED_BASE = 0x180000000
ARRAY_BYTES = 4096 * 8

# These are RVAs, so ASLR is handled in the Frida agent from module.base.
SITES = {
    "filter_flag_store": 0xB996,
    "coeff_fft_before": 0xBAC1,
    "coeff_fft_after": 0xBAC6,
    "input_fft_before": 0xC468,
    "input_fft_after": 0xC489,
    "multiply_select": 0xC56E,
    "multiply_lane": 0xC5B0,
    "multiply_complex": 0xC5F0,
    "inverse_before": 0xC668,
    "inverse_after": 0xC689,
    "emit_boundary": 0xC6D2,
    "buffer_swap": 0xC85D,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def agent_source() -> str:
    sites = json.dumps(SITES)
    return f"""
'use strict';
const SITES = {sites};
const MAX_BLOCKS = 2;
const ARRAY_BYTES = {ARRAY_BYTES};
let moduleBase = null;
let snapshotCounts = {{}};
let branchCounts = {{lane: 0, complex: 0}};

function hex(p) {{ return p ? p.toString() : null; }}
function u8(p) {{ try {{ return p.readU8(); }} catch (e) {{ return null; }} }}
function u32(p) {{ try {{ return p.readU32(); }} catch (e) {{ return null; }} }}
function ptrAt(p, off) {{ try {{ return p.add(off).readPointer(); }} catch (e) {{ return NULL; }} }}
function sendEvent(kind, fields) {{ send(Object.assign({{kind: kind, ts_ms: Date.now()}}, fields)); }}
function dump(label, p, fields) {{
  if (p.isNull()) {{ sendEvent('dump_failed', Object.assign({{label: label, reason: 'null'}}, fields)); return; }}
  const n = snapshotCounts[label] || 0;
  if (n >= MAX_BLOCKS) return;
  snapshotCounts[label] = n + 1;
  try {{
    const range = Process.findRangeByAddress(p);
    if (range === null || range.protection.indexOf('r') === -1 || p.add(ARRAY_BYTES).compare(range.base.add(range.size)) > 0) {{
      sendEvent('dump_failed', Object.assign({{label: label, pointer: hex(p), reason: 'unreadable_or_short', range: range ? {{base: hex(range.base), size: range.size, protection: range.protection}} : null}}, fields));
      return;
    }}
    send(Object.assign({{kind: 'dump', label: label, pointer: hex(p), bytes: ARRAY_BYTES, sequence: n, range: {{base: hex(range.base), size: range.size, protection: range.protection}}}}, fields), p.readByteArray(ARRAY_BYTES));
  }} catch (e) {{ sendEvent('dump_failed', Object.assign({{label: label, pointer: hex(p), reason: String(e)}}, fields)); }}
}}
function attach(name, callback) {{
  const address = moduleBase.add(SITES[name]);
  Interceptor.attach(address, {{ onEnter: function(args) {{ try {{ callback.call(this); }} catch (e) {{ sendEvent('hook_error', {{site:name,error:String(e)}}); }} }} }});
  sendEvent('hook_attached', {{site:name, static_va:'0x'+(0x180000000 + SITES[name]).toString(16), rva:'0x'+SITES[name].toString(16), live_va:hex(address)}});
}}
function install(module) {{
  if (moduleBase !== null || module.name.toLowerCase() !== '5868usb.dll') return;
  moduleBase = module.base;
  sendEvent('module_loaded', {{name:module.name, path:module.path, base:hex(module.base), size:module.size, preferred_base:'0x180000000'}});
  attach('filter_flag_store', function() {{
    const filter = this.context.rdi;
    sendEvent('filter_constructor', {{filter:hex(filter), flag_before:u8(filter.add(0x34)), coeff:hex(ptrAt(filter,0x50)), taps:u32(filter.add(0x48)), phase:u32(filter.add(0x4c))}});
  }});
  attach('coeff_fft_before', function() {{
    const filter = this.context.rdi;
    dump('coeff_pre_fft', this.context.r8, {{filter:hex(filter), flag:u8(filter.add(0x34)), coeff_field:hex(ptrAt(filter,0x50)), taps:u32(filter.add(0x48)), phase:u32(filter.add(0x4c))}});
  }});
  attach('coeff_fft_after', function() {{
    const filter = this.context.rdi;
    dump('coeff_post_fft', ptrAt(filter,0x50), {{filter:hex(filter), flag:u8(filter.add(0x34)), taps:u32(filter.add(0x48)), phase:u32(filter.add(0x4c))}});
  }});
  attach('input_fft_before', function() {{
    const state = this.context.rsi, work = ptrAt(state,0x70);
    dump('input_pre_fft', work, {{state:hex(state), filter:hex(ptrAt(state,0x8)), fft_doubles:u32(state.add(0x34)), stage_shift:u32(state.add(0x50))}});
  }});
  attach('input_fft_after', function() {{
    const state = this.context.rsi, work = ptrAt(state,0x70);
    dump('input_post_fft', work, {{state:hex(state), filter:hex(ptrAt(state,0x8)), fft_doubles:u32(state.add(0x34))}});
  }});
  attach('multiply_select', function() {{
    const state = this.context.rsi, filter = ptrAt(state,0x8), work = ptrAt(state,0x70), coeff = ptrAt(filter,0x50);
    dump('input_packed', work, {{state:hex(state), filter:hex(filter), stage:'after_C494_C556_before_C56E'}});
    sendEvent('multiply_select', {{state:hex(state), filter:hex(filter), work:hex(work), coeff:hex(coeff), filter_flag:u8(filter.add(0x34)), state_fft_doubles:u32(state.add(0x34)), caller:hex(this.returnAddress)}});
  }});
  attach('multiply_lane', function() {{ branchCounts.lane++; if (branchCounts.lane <= 2) sendEvent('multiply_branch', {{branch:'lane', hit:branchCounts.lane, rax:hex(this.context.rax), rdx:hex(this.context.rdx)}}); }});
  attach('multiply_complex', function() {{ branchCounts.complex++; if (branchCounts.complex <= 2) sendEvent('multiply_branch', {{branch:'complex', hit:branchCounts.complex, rax:hex(this.context.rax), rdi:hex(this.context.rdi)}}); }});
  attach('inverse_before', function() {{
    const state=this.context.rsi, work=ptrAt(state,0x70);
    dump('after_spectral_multiply', work, {{state:hex(state), filter:hex(ptrAt(state,0x8)), filter_flag:u8(ptrAt(state,0x8).add(0x34))}});
  }});
  attach('inverse_after', function() {{
    const state=this.context.rsi, work=ptrAt(state,0x70);
    sendEvent('inverse_complete', {{state:hex(state), r12:Number(this.context.r12), overlap:u32(state.add(0x38)), skip_before:u32(state.add(0x84))}});
    dump('after_inverse', work, {{state:hex(state), filter:hex(ptrAt(state,0x8))}});
  }});
  attach('emit_boundary', function() {{
    const state=this.context.rsi;
    sendEvent('emit_boundary', {{state:hex(state), skip:u32(state.add(0x84)), output_shift:u32(state.add(0x54)), output_period:u32(state.add(0x2c)), work:hex(ptrAt(state,0x70)), previous:hex(ptrAt(state,0x78)), scratch:hex(ptrAt(state,0x68))}});
  }});
  attach('buffer_swap', function() {{ const state=this.context.rsi; sendEvent('buffer_swap', {{state:hex(state), work_before:hex(ptrAt(state,0x70)), previous_before:hex(ptrAt(state,0x78))}}); }});
}}
Process.attachModuleObserver({{ onAdded(module) {{ install(module); }} }});
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=Path, required=True, help="Windows Manager executable")
    parser.add_argument("--dll", type=Path, required=True, help="DLL expected to be loaded")
    parser.add_argument("--out", type=Path, required=True, help="ignored private output directory")
    parser.add_argument("--pid", type=int, help="attach to an already-running Manager")
    parser.add_argument("--seconds", type=float, default=25.0)
    parser.add_argument("--keep-alive", action="store_true")
    args = parser.parse_args()
    if os.name != "nt" or platform.architecture()[0] != "64bit":
        raise SystemExit("Stage23W requires 64-bit Windows Python")
    if sha256(args.dll).lower() != DLL_SHA256:
        raise SystemExit("refusing to trace: --dll SHA-256 does not match the pinned original")
    if not args.host.is_file():
        raise SystemExit("host executable not found")
    args.out.mkdir(parents=True, exist_ok=True)
    try:
        import frida
    except ImportError as error:
        raise SystemExit("install Frida in a private venv first") from error
    events: list[dict] = []
    dump_rows: list[dict] = []
    event_log = args.out / "trace.private.jsonl"
    started = datetime.now(timezone.utc).isoformat()

    def on_message(message, data):
        if message.get("type") != "send":
            events.append({"kind": "frida_message", "message": message})
            return
        payload = message["payload"]
        if payload.get("kind") == "dump" and data is not None:
            name = f"{payload['label']}_{payload['sequence']:02d}.f64le.bin"
            path = args.out / name
            path.write_bytes(data)
            payload = dict(payload)
            payload.update({"private_file": name, "sha256": hashlib.sha256(data).hexdigest()})
            dump_rows.append(payload)
        events.append(payload)
        with event_log.open("a", encoding="utf-8") as log:
            log.write(json.dumps(payload, sort_keys=True) + "\n")

    device = frida.get_local_device()
    spawned = args.pid is None
    pid = device.spawn([str(args.host)]) if spawned else args.pid
    session = device.attach(pid)
    script = session.create_script(agent_source())
    script.on("message", on_message)
    script.load()
    # Allows an operator to wait for hooks before triggering a one-shot import.
    (args.out / "ready.private.json").write_text(json.dumps({"pid": pid, "dll_sha256": DLL_SHA256, "ready": True}), encoding="utf-8")
    if spawned:
        device.resume(pid)
    time.sleep(args.seconds)
    script.unload()
    session.detach()
    if spawned and not args.keep_alive:
        device.kill(pid)
    manifest = {
        "status": "completed_no_claim_of_conversion",
        "started_utc": started,
        "ended_utc": datetime.now(timezone.utc).isoformat(),
        "host": args.host.name,
        "dll_filename": args.dll.name,
        "dll_sha256": DLL_SHA256,
        "preferred_image_base": hex(PREFERRED_BASE),
        "trace_seconds": args.seconds,
        "spawned_pid": pid,
        "attach_mode": "spawned" if spawned else "existing_process",
        "events": events,
        "dumps": dump_rows,
    }
    (args.out / "manifest.private.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"private_manifest": "manifest.private.json", "event_count": len(events), "dump_count": len(dump_rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

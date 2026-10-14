"""Reusable guarded Frida metadata mode for tools/frida_capture.py.

This module has NO Sonicake, stage, DLL-address or vendor-version constants.
Only a strictly validated JSON descriptor may specify its original
post-call processor object, dynamic vtable and result pointer/count registers.
No waveform bytes are read or saved by this mode.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import re
import threading
import time


AGENT = r"""
'use strict';
const spec = JSON_SPEC;
let moduleFound = null;
let hook = null, observed = 0, metadataSent = false, firstRejectSent = false;
const site = spec.sites[0], g = site.guard;
function emit(d) { send(Object.assign({kind:'note', thread:Process.getCurrentThreadId()}, d)); }
function readable(p, n) {
  if (p.isNull() || n < 1) return false;
  const r = Process.findRangeByAddress(p);
  if (r === null || r.protection.indexOf('r') < 0) return false;
  return p.compare(r.base) >= 0 &&
    p.add(n-1).compare(r.base.add(r.size)) < 0;
}
function reject(reason) {
  if (!firstRejectSent) {
    firstRejectSent = true;
    emit({kind:'first_rejected_return',site:site.name,reason:reason,observed:observed});
  }
}
rpc.exports = {
  arm() {
    if (hook !== null || moduleFound === null) return false;
    const m = Process.findModuleByName(spec.module);
    if (m === null || !m.base.equals(moduleFound.base) || site.rva >= m.size)
      return false;
    const loc = m.base.add(site.rva);
    const mapped = Process.findRangeByAddress(loc);
    if (mapped === null || mapped.protection.indexOf('x') < 0) return false;
    try {
      hook = Interceptor.attach(loc, {onEnter() {
        if (metadataSent) return;
        if (++observed > g.max_observations) {
          if (observed === g.max_observations+1)
            emit({kind:'observation_limit',site:site.name,limit:g.max_observations});
          return;
        }
        try {
          const c = this.context;
          const owner = c[g.owner_reg];
          const slot = owner.add(g.owner_offset);
          if (!readable(slot,Process.pointerSize)) return reject('processor slot unreadable');
          const proc = slot.readPointer();
          if (!readable(proc,Process.pointerSize)) return reject('processor unreadable');
          const vtable = proc.readPointer();
          const expected = m.base.add(g.vtable_rva);
          if (!vtable.equals(expected)) return reject('processor vtable mismatch');
          const count = c[g.count_reg].and(ptr('0xffffffff')).toUInt32();
          if (count < 1 || count > g.max_samples)
            return reject('return count zero or out of bounds');
          const ref = c[g.output_ref_reg];
          if (!readable(ref,Process.pointerSize)) return reject('result pointer reference unreadable');
          const output = ref.readPointer();
          if (!output.and(ptr('0x7')).isNull()) return reject('result not f64 aligned');
          const bytes = count * 8;
          if (!readable(output, bytes)) return reject('result span not readable');
          // Critically, no readByteArray/readDouble/readFloat anywhere in this agent.
          metadataSent = true;
          emit({kind:'metadata_hit',valid:true,site:site.name,observed:observed,
                processor_vtable:vtable.toString(),expected_vtable:expected.toString(),
                output_pointer:output.toString(),output_f64:count,output_bytes:bytes,
                readable_range:true,pc:loc.toString()});
        } catch(e) { reject('guard exception: '+String(e).slice(0,140)); }
      }});
      emit({kind:'hook_attached',site:site.name,rva:site.rva,hooks_installed:1});
      return true;
    } catch(e) {
      emit({kind:'arm_error',site:site.name,error:String(e).slice(0,160)});
      return false;
    }
  }
};
Process.attachModuleObserver({onAdded(m) {
  if(m.name.toLowerCase()!==spec.module.toLowerCase()) return;
  moduleFound=m;
  emit({kind:'module_found',name:m.name,path:m.path,base:m.base.toString(),size:m.size});
}});
"""


def agent_source(cfg: dict) -> str:
    return AGENT.replace("JSON_SPEC", json.dumps(cfg, ensure_ascii=True))


def snapshot(folder: Path | None, recursive: bool) -> dict:
    if folder is None or not folder.is_dir():
        return {}
    glob = folder.rglob("*.clo") if recursive else folder.glob("*.clo")
    result = {}
    for file in glob:
        try:
            st = file.stat()
            result[str(file.resolve()).casefold()] = (st.st_size, st.st_mtime_ns)
        except OSError:
            continue
    return result


def resolve_completion(args, cfg: dict):
    completion = cfg.get("completion") or {}
    if args.completion_dir:
        path = args.completion_dir
    elif completion.get("appdata_subdir"):
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise RuntimeError("APPDATA absent; pass --completion-dir")
        path = Path(appdata).joinpath(*completion["appdata_subdir"].split("/"))
    else:
        path = None
    if path is not None and not path.is_dir():
        raise FileNotFoundError("CLO watch directory missing: "+str(path))
    return path, bool(completion.get("recursive", True)), float(completion.get("stable_seconds", 3))


def choose_pid(device, args, cfg, report):
    processes = device.enumerate_processes()
    pattern = cfg["target"]["process_name_contains"].casefold()
    if args.pid is not None:
        selected = next((p for p in processes if p.pid == args.pid), None)
        if selected is None:
            raise ValueError("Requested PID not running; it may have restarted")
        if pattern not in selected.name.casefold():
            raise ValueError("PID does not match target.process_name_contains; refusing attach")
        report("TARGET", "Verified", selected.name, "| PID", selected.pid)
        return selected.pid
    found = [p for p in processes if pattern in p.name.casefold()]
    if len(found) != 1:
        raise ValueError("Found "+str(len(found))+" target candidates for "+
                         repr(pattern)+"; open exactly one or pass --pid. "+
                         "Use --list-processes for diagnostics.")
    report("TARGET", "Auto-detected", found[0].name, "| PID", found[0].pid)
    return found[0].pid


def list_processes(report, cfg=None):
    if os.name != "nt" or platform.architecture()[0] != "64bit":
        raise RuntimeError("Process discovery requires Windows x64 Python")
    import frida
    processes = frida.get_local_device().enumerate_processes()
    pattern = ((cfg or {}).get("target") or {}).get("process_name_contains", "sonicake").casefold()
    hits = [p for p in processes if pattern in p.name.casefold()]
    report("TARGET", "Frida sees", len(processes), "processes; pattern", repr(pattern))
    for p in sorted(hits, key=lambda x:(x.name.casefold(),x.pid)):
        report("NOTE", p.name, "PID", p.pid)
    report("NOTE", "No process attached; ZERO hooks installed")
    return 0


def reconcile(folder: Path, state: dict):
    """Recover persisted truth even when an exception interrupts capture()."""
    p = folder / "events.jsonl"
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    state["journal_events"] = len(lines)
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            state["invalid_journal_lines"] = state.get("invalid_journal_lines",0)+1
            continue
        kind = e.get("kind")
        if kind == "hook_attached" and e.get("hooks_installed") == 1:
            state["ready"] = True
            state["hook_attached"] = True
        elif kind == "metadata_hit" and e.get("valid") is True:
            state["valid_field_hits"] = max(1,state.get("valid_field_hits",0))
            state["hits"] = max(1,state.get("hits",0))
            state["metadata_valid"] = True
            state["last_metadata"] = e
        elif kind == "first_rejected_return":
            state["first_rejection"] = e.get("reason")


def interrupted_status(state: dict) -> str:
    return ("METADATA_OBSERVED_OPERATOR_INTERRUPTED"
            if state.get("metadata_valid") else "OPERATOR_INTERRUPTED")


def self_test(validate_fn):
    """Pure-Python contract plus real Stage48 journal regression; no Frida."""
    import tempfile
    from types import SimpleNamespace

    cfg = validate_fn({
        "module":"test.dll","sha256":"a"*64,
        "mode":"guarded_metadata",
        "target":{"process_name_contains":"test"},
        "completion":{"type":"changed_clo","appdata_subdir":"Test/App","recursive":True,"stable_seconds":3},
        "sites":[{"name":"aftercall","address":"0x1190c",
                  "guard":{"kind":"processor_output","owner_reg":"rbx",
                           "owner_offset":80,"vtable_rva":"0x245170",
                           "output_ref_reg":"r15","count_reg":"rax",
                           "max_samples":4096,"max_observations":256}}]
    })
    js = agent_source(cfg)
    assert js.count("Interceptor.attach(") == 1
    assert "rpc.exports" in js and "Process.attachModuleObserver" in js
    assert ".readByteArray(" not in js and ".readDouble(" not in js
    assert cfg["sites"][0]["guard"]["vtable_rva"] == 0x245170
    class Device:
        def enumerate_processes(self):
            return [SimpleNamespace(name="Test Manager.exe",pid=14000),
                    SimpleNamespace(name="explorer.exe",pid=222)]
    assert choose_pid(Device(),SimpleNamespace(pid=None),cfg,lambda *a:None)==14000
    assert choose_pid(Device(),SimpleNamespace(pid=14000),cfg,lambda *a:None)==14000
    with tempfile.TemporaryDirectory(prefix="frida_guarded_test_") as td:
        d=Path(td)
        events=[
            {"kind":"module_found","base":"0x7ff862660000"},
            {"kind":"hook_attached","hooks_installed":1},
            {"kind":"first_rejected_return","reason":"return count zero or out of bounds"},
            {"kind":"metadata_hit","valid":True,"output_f64":114,"output_bytes":912},
        ]
        (d/"events.jsonl").write_text("".join(json.dumps(e)+"\n" for e in events),encoding="utf-8")
        state={}
        reconcile(d,state)
        assert state["hook_attached"] and state["last_metadata"]["output_f64"]==114
        assert state["journal_events"]==4
        assert interrupted_status(state)=="METADATA_OBSERVED_OPERATOR_INTERRUPTED"
        sub=d/"profile"
        sub.mkdir()
        (sub/"ok.clo").write_bytes(b"fake")
        assert len(snapshot(d,True))==1 and len(snapshot(d,False))==0
    # Config injection must never permit raw JS supplied by arbitrary stage.
    for bad in ({"mode":"guarded_metadata","sites":[{"name":"x","address":"0x1190c",
                   "guard":{"javascript":"unsafe"}}]},
                {"mode":"guarded_metadata","sites":[{"name":"x","address":"0x1190c"}]}):
        try:
            validate_fn({"module":"test.dll","sha256":"a"*64,**bad})
            raise AssertionError("invalid guarded config accepted")
        except (ValueError,KeyError,TypeError):
            pass
    return "guarded metadata offline tests PASS (single hook, legacy journal recovery, auto PID, CLO recurse)"


def capture(args, cfg, folder: Path, state: dict, report, sha):
    """Windows-only guarded capture; shared state survives interrupts.

    The caller owns manifest + archive creation. No proprietary media persisted.
    """
    if os.name!="nt" or platform.architecture()[0]!="64bit":
        raise RuntimeError("Guarded capture requires Windows x64 Python")
    import frida
    device=frida.get_local_device()
    pid=choose_pid(device,args,cfg,report)
    watch,recursive,stable_seconds=resolve_completion(args,cfg)
    baseline=snapshot(watch,recursive)
    report("CLO","Watching",watch,"| baseline files:",len(baseline))
    state.update(pid=pid,runtime_verified=False,ready=False,hits=0,
                 valid_field_hits=0,metadata_valid=False,hook_attached=False,
                 hook_errors=0,field_errors=0,site_hits={},
                 first_rejection=None,completion_verified=False)
    events=folder/"events.jsonl"
    lock=threading.RLock()
    pending=[]
    disconnect=threading.Event()
    session=None
    script=None
    try:
        session=device.attach(pid)
        def on_detach(reason,*unused):
            disconnect.set()
            state["detached_reason"]=str(reason)
        session.on("detached",on_detach)
        script=session.create_script(agent_source(cfg))

        def on_message(msg,binary):
            if binary is not None:
                e={"kind":"unexpected_binary_payload","error":"guarded metadata mode prohibits bytes"}
            elif msg.get("type")=="send":
                e=msg.get("payload",{})
                if not isinstance(e,dict):e={"kind":"invalid_event"}
            else:
                e={"kind":"frida_error","error":str(msg)[:400]}
            with lock:
                with events.open("a",encoding="utf-8") as f:
                    f.write(json.dumps(e,ensure_ascii=True)+"\n")
                    f.flush()
                kind=e.get("kind")
                if kind=="module_found":pending.append(e)
                elif kind=="hook_attached":
                    state["ready"]=True
                    state["hook_attached"]=True
                elif kind=="metadata_hit" and e.get("valid") is True:
                    state["metadata_valid"]=True
                    state["valid_field_hits"]+=1
                    state["hits"]+=1
                    state["site_hits"][e["site"]]=1
                    state["last_metadata"]=e
                elif kind=="first_rejected_return":state["first_rejection"]=e.get("reason")
                elif kind in ("arm_error","frida_error","unexpected_binary_payload","invalid_event"):
                    state["hook_errors"]+=1
                elif kind=="observation_limit":state["observation_limit_reached"]=True
            if kind=="hook_attached":
                report("HOOK","Verified single hook:",e.get("site"),"| RVA",hex(e.get("rva",0)))
            elif kind=="metadata_hit":
                report("META","Native output:",e.get("output_f64"),"f64 /",
                       e.get("output_bytes"),"bytes",
                       "| observation",e.get("observed"))
            elif kind=="first_rejected_return":
                report("NOTE","Initial return rejected:",e.get("reason"))
            elif kind in ("arm_error","frida_error"):
                report("ERROR",kind,e.get("error"))

        script.on("message",on_message)
        script.load()
        report("FRIDA","Observer attached (NO hook before loaded module SHA verified)")
        start=time.monotonic()
        heartbeat=start
        next_poll=0.0
        next_pid_check=0.0
        discovered=None
        stable_since=None
        armed=False
        while time.monotonic()-start<args.timeout:
            time.sleep(.2)
            now=time.monotonic()
            with lock:
                pending_module=pending.pop(0) if pending else None
                hooked=state["hook_attached"]
                metadata=state["metadata_valid"]
                errors=state["hook_errors"]
                too_many=state.get("observation_limit_reached",False)
            if disconnect.is_set():
                return ("BLOCKED_TARGET_DETACHED","manager_detached",pid)
            if errors:
                return ("BLOCKED_AGENT_ERROR","frida_error",pid)
            if too_many:
                return ("INCOMPLETE_OBSERVATION_LIMIT","guard_limit",pid)
            if pending_module is not None and not armed:
                armed=True
                path=Path(pending_module["path"])
                if path.name.casefold()!=cfg["module"].casefold():
                    raise RuntimeError("loaded module filename mismatch")
                actual=sha(path)
                if actual!=cfg["sha256"]:
                    raise RuntimeError("Loaded module SHA256 mismatch: refused to install hook")
                with lock:
                    state["runtime_verified"]=True
                    state["module_base"]=pending_module.get("base")
                if not script.exports_sync.arm():
                    raise RuntimeError("Frida arm() refused to install guarded hook")
                report("FRIDA","Loaded DLL SHA verified. ONE metadata-only hook armed.")
                report("NOTE","Perform exactly ONE normal conversion in target app.")
            if now>=next_pid_check:
                next_pid_check=now+3.0
                if not any(p.pid==pid for p in device.enumerate_processes()):
                    return ("BLOCKED_TARGET_EXITED","target_exited",pid)
            if watch is not None and now>=next_poll:
                next_poll=now+1.0
                changed=[(path,meta) for path,meta in snapshot(watch,recursive).items()
                         if meta[0]>0 and baseline.get(path)!=meta]
                if changed:
                    newest=max(changed,key=lambda item:item[1][1])
                    if newest!=discovered:
                        discovered=newest
                        stable_since=now
                        report("CLO","New/changed candidate:",Path(newest[0]).name,
                               "|",newest[1][0],"bytes")
                    elif stable_since is not None and now-stable_since>=stable_seconds:
                        if not state["completion_verified"]:
                            report("CLO","Stable new/changed CLO:",Path(newest[0]).name)
                        state["completion_verified"]=True
                        state["completion_path"]=newest[0]
                        state["completion_size_bytes"]=newest[1][0]
                else:
                    discovered=None
                    stable_since=None
            if now-heartbeat>=15:
                heartbeat=now
                report("WAIT","elapsed",round(now-start),"s | hook",hooked,
                       "| metadata",metadata,"| CLO",state["completion_verified"])
            if (state["runtime_verified"] and hooked and metadata and
                    state["completion_verified"] and not errors):
                return ("METADATA_GUARD_PASS_CLO_STABLE","stable_clo_after_guard",pid)
        return ("METADATA_OBSERVED_CLO_UNVERIFIED_TIMEOUT" if state["metadata_valid"]
                else "INCOMPLETE_TIMEOUT","timeout",pid)
    finally:
        if script is not None:
            try:script.unload()
            except Exception:pass
        if session is not None:
            try:session.detach()
            except Exception:pass

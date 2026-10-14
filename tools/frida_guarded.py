"""Reusable guarded Frida metadata mode for tools/frida_capture.py.

This module has NO Sonicake, stage, DLL-address or vendor-version constants.
Only a strictly validated JSON descriptor may specify its original
post-call processor object, dynamic vtable and result pointer/count registers.
No waveform bytes are read or saved by this mode.
"""
from __future__ import annotations

import json
import os
from pathlib import Path, PureWindowsPath
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



def validate_config(cfg: dict, address_fn) -> dict:
    """Strict declarative guard schema; arbitrary script payloads are forbidden."""
    if not isinstance(cfg,dict):
        raise ValueError("config must be an object")
    if cfg.get("mode") != "guarded_metadata":
        raise ValueError("expected guarded_metadata mode")
    if not isinstance(cfg.get("module"),str) or not re.fullmatch(r"[A-Za-z0-9_. -]+\.(dll|exe)",cfg["module"],re.I):
        raise ValueError("simple module basename required")
    if not isinstance(cfg.get("sha256"),str) or not re.fullmatch(r"[A-Fa-f0-9]{64}",cfg["sha256"]):
        raise ValueError("original module SHA256 mandatory")
    base = int(str(cfg.get("image_base","0x180000000")),0)
    sites=cfg.get("sites")
    if not isinstance(sites,list) or len(sites)!=1:
        raise ValueError("guarded_metadata requires exactly one site")
    s=sites[0]
    if not isinstance(s,dict) or set(s)-{"name","address","required","max_hits","guard","fields"}:
        raise ValueError("guarded site has unknown properties")
    if s.get("fields"):
        raise ValueError("guarded mode rejects scalar and binary fields; metadata only")
    if not isinstance(s.get("name"),str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}",s["name"]):
        raise ValueError("invalid site name")
    if s.get("required",True) is not True or s.get("max_hits",1)!=1:
        raise ValueError("guarded site must be required with max_hits=1")
    g=s.get("guard")
    permitted={"kind","owner_reg","owner_offset","vtable_rva","output_ref_reg",
               "count_reg","max_samples","max_observations"}
    if not isinstance(g,dict) or set(g)!=permitted:
        raise ValueError("guard fields must match the fixed processor_output schema exactly")
    if g["kind"]!="processor_output":
        raise ValueError("unknown guarded metadata kind")
    regs={"rax","rbx","rcx","rdx","rsi","rdi","rbp","rsp",
          "r8","r9","r10","r11","r12","r13","r14","r15"}
    for key in ("owner_reg","output_ref_reg","count_reg"):
        if g[key] not in regs:
            raise ValueError("unsupported register in "+key)
    def integer(value,key,minimum,maximum):
        if type(value) is not int or not minimum<=value<=maximum:
            raise ValueError(key+" must be an integer in allowed bounds")
        return value
    off=integer(g["owner_offset"],"owner_offset",0,4096)
    if off%8:
        raise ValueError("owner_offset must be pointer aligned")
    max_samples=integer(g["max_samples"],"max_samples",1,4096)
    max_observations=integer(g["max_observations"],"max_observations",1,1024)
    vtable=address_fn(g["vtable_rva"],base)
    if vtable<0 or vtable>=0x10000000:
        raise ValueError("implausible vtable RVA")
    rv=address_fn(s.get("address"),base)
    if rv>=0x10000000:
        raise ValueError("implausible code RVA")

    target=cfg.get("target")
    if not isinstance(target,dict) or set(target)!={"process_name_contains"}:
        raise ValueError("target must provide process_name_contains only")
    match=target["process_name_contains"]
    if not isinstance(match,str) or not re.fullmatch(r"[A-Za-z0-9_. -]{3,100}",match):
        raise ValueError("invalid process match string")
    # Lifecycle is declarative and OPTIONAL for old guarded configs.
    # All paths are interpreted only on Windows; no app is launched in self-test.
    lifecycle=cfg.get("lifecycle")
    if lifecycle is not None:
        if not isinstance(lifecycle,dict) or set(lifecycle)!={
            "executable","start","close","close_timeout_seconds"
        }:
            raise ValueError("lifecycle must specify executable/start/close/close_timeout_seconds")
        exe=lifecycle["executable"]
        if not isinstance(exe,str) or not re.fullmatch(
            r"[A-Za-z]:/[^\x00-\x1f<>:\"|?*]+",exe):
            raise ValueError("lifecycle.executable must be an absolute C:/... Windows EXE path")
        if (not exe.lower().endswith(".exe") or
                any(part in ("",".","..") for part in exe[3:].split("/")) or
                "\\" in exe or PureWindowsPath(exe).drive==""):
            raise ValueError("unsafe executable path")
        if lifecycle["start"] not in ("fresh","if_missing","attach_only"):
            raise ValueError("lifecycle.start must be fresh, if_missing or attach_only")
        if lifecycle["close"] not in ("if_launched","never"):
            raise ValueError("lifecycle.close must be if_launched or never")
        t=lifecycle["close_timeout_seconds"]
        if type(t) is not int or not 1<=t<=30:
            raise ValueError("lifecycle.close_timeout_seconds must be 1..30")
        lifecycle=dict(lifecycle)

    completion=cfg.get("completion")
    if not isinstance(completion,dict):
        raise ValueError("completion must be a declarative object")
    shared={"type","recursive","stable_seconds"}
    locations=set(completion)-shared
    if (not locations in ({"path"},{"appdata_subdir"}) or
            set(completion)!=shared|locations or completion["type"]!="changed_clo"):
        raise ValueError("completion needs exactly one of path or appdata_subdir")
    if "path" in completion:
        watch=completion["path"]
        if (not isinstance(watch,str) or
                not re.fullmatch(r"[A-Za-z]:/[^\x00-\x1f<>:\"|?*]+",watch) or
                "\\" in watch or
                any(part in ("",".","..") for part in watch[3:].split("/"))):
            raise ValueError("completion.path must be a safe absolute C:/... directory")
    else:
        sub=completion["appdata_subdir"]
        if not isinstance(sub,str) or not sub or ":" in sub or "\\" in sub or sub.startswith("/"):
            raise ValueError("appdata_subdir must be safe slash-separated relative segments")
        if any(part in ("",".","..") or not re.fullmatch(r"[A-Za-z0-9_. -]+",part)
               for part in sub.split("/")):
            raise ValueError("unsafe appdata_subdir")
    if type(completion["recursive"]) is not bool:
        raise ValueError("recursive must be a boolean")
    stable=completion["stable_seconds"]
    if type(stable) not in (int,float) or not 2<=stable<=30:
        raise ValueError("stable_seconds must be 2..30")
    if set(cfg)-{"module","sha256","mode","image_base","target","completion","sites","lifecycle"}:
        raise ValueError("unknown top-level guarded config key")
    return {
        "module":cfg["module"],"sha256":cfg["sha256"].lower(),
        "mode":"guarded_metadata","image_base":base,
        "target":{"process_name_contains":match},
        "completion":dict(completion),
        **({"lifecycle":lifecycle} if lifecycle is not None else {}),
        "sites":[{"name":s["name"],"rva":rv,"required":True,"max_hits":1,
                  "fields":[],"guard":dict(g,owner_offset=off,vtable_rva=vtable,
                                            max_samples=max_samples,
                                            max_observations=max_observations)}],
    }


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
    elif completion.get("path"):
        path = Path(completion["path"])
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



def preflight_paths(args, cfg, report):
    """Verify configured Windows EXE and output directory; ZERO attach/hooks.

    Safe to invoke from universal launcher before any native experiment.
    """
    if os.name!="nt" or platform.architecture()[0]!="64bit":
        raise RuntimeError("Path preflight needs Windows x64 Python; use the shared WSL wrapper")
    lifecycle=cfg.get("lifecycle") or {}
    if lifecycle.get("start") in ("fresh","if_missing"):
        exe=Path(lifecycle["executable"])
        if not exe.is_file():
            raise FileNotFoundError(
                "Configured EXE does not exist: "+str(exe)+
                "; set lifecycle.executable to the actual installed app EXE in this stage JSON")
        report("TARGET","Configured EXE exists:",exe)
    else:
        report("TARGET","attach_only mode; no EXE launch requested")
    completion,_,stable=resolve_completion(args,cfg)
    report("CLO","Configured completion directory exists:",completion,
           "| stable interval:",stable,"s")
    report("NOTE","Preflight complete; no process was launched or attached, no hooks installed")
    return 0


def launch_target(device, args, cfg, report, state):
    """Pick an existing PID or SPAWN a fresh app under this session's ownership.

    Frida device.spawn() starts the target suspended. capture() must install
    the module observer and only then device.resume(pid). This also ensures
    cleanup knows exactly which process this invocation owns.
    """
    lifecycle=cfg.get("lifecycle")
    if lifecycle is None or lifecycle["start"]=="attach_only":
        pid=choose_pid(device,args,cfg,report)
        state.update(launched_by_tool=False,target_pid=pid,target_resumed=True)
        return pid,False
    if args.pid is not None:
        raise ValueError("--pid cannot be combined with lifecycle.start="+
                         lifecycle["start"]+"; choose attach_only for an existing PID")
    match=cfg["target"]["process_name_contains"].casefold()
    current=[p for p in device.enumerate_processes() if match in p.name.casefold()]
    if lifecycle["start"]=="fresh" and current:
        raise ValueError("lifecycle.start=fresh requires the application CLOSED first; "
                         "detected "+str(len(current))+" matching process(es). "
                         "Will NOT terminate a pre-existing user process.")
    if lifecycle["start"]=="if_missing" and len(current)==1:
        pid=current[0].pid
        state.update(launched_by_tool=False,target_pid=pid,target_resumed=True)
        report("TARGET","Reusing",current[0].name,"| PID",pid,
               "(user-owned process will NOT be closed)")
        return pid,False
    if lifecycle["start"]=="if_missing" and len(current)>1:
        raise ValueError("Multiple matching running processes; refusing arbitrary choice")
    exe=Path(lifecycle["executable"])
    if not exe.is_file():
        raise FileNotFoundError("Configured Windows application EXE not found: "+str(exe)+
                                "; edit lifecycle.executable in the stage JSON")
    report("TARGET","Launching configured EXE via Frida spawn:",exe)
    pid=device.spawn([str(exe)])
    state.update(launched_by_tool=True,target_pid=pid,target_resumed=False,
                 configured_executable=str(exe))
    report("TARGET","Spawned own Manager PID",pid,
           "(suspended until Frida observer is ready)")
    return pid,True


def process_exists(device,pid):
    try:
        return any(p.pid==pid for p in device.enumerate_processes())
    except Exception:
        return None


def request_graceful_close_windows(pid: int) -> int:
    """Send WM_CLOSE to TOP-LEVEL windows belonging to this exact owned PID.

    No process kill, no taskkill and no window close for unrelated processes.
    """
    import ctypes
    from ctypes import wintypes
    user32=ctypes.WinDLL("user32",use_last_error=True)
    enum_proc=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    user32.EnumWindows.argtypes=(enum_proc,wintypes.LPARAM)
    user32.EnumWindows.restype=wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes=(wintypes.HWND,ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype=wintypes.DWORD
    user32.PostMessageW.argtypes=(wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM)
    user32.PostMessageW.restype=wintypes.BOOL
    user32.IsWindow.argtypes=(wintypes.HWND,)
    user32.IsWindow.restype=wintypes.BOOL
    windows=[]
    @enum_proc
    def visit(hwnd,_):
        owner=wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
        if owner.value==pid and user32.IsWindow(hwnd):
            windows.append(hwnd)
        return True
    # Win32 BOOL EnumWindows(WNDENUMPROC lpEnumFunc, LPARAM lParam)
    # The second LPARAM is mandatory (0 here); omitting it caused the
    # Stage48 error: "this function takes 2 arguments (1 given)".
    if not user32.EnumWindows(visit, 0):
        raise OSError("EnumWindows failed")
    sent=0
    for hwnd in windows:
        if user32.PostMessageW(hwnd,0x0010,0,0):  # WM_CLOSE
            sent+=1
    return sent


def close_owned_target(device,pid,state,cfg,report):
    """Best-effort graceful shutdown, strictly limited to a tool-owned PID."""
    lifecycle=cfg.get("lifecycle") or {}
    if not state.get("launched_by_tool") or lifecycle.get("close")!="if_launched":
        state["cleanup_status"]="NOT_OWNED_OR_DISABLED"
        return
    alive=process_exists(device,pid)
    if alive is False:
        state["cleanup_status"]="ALREADY_EXITED"
        report("TARGET","Tool-launched process already exited; nothing to close")
        return
    if state.get("target_resumed") is False:
        # Only a STILL SUSPENDED process that WE created may be force-cleaned
        # because no GUI window exists for a graceful WM_CLOSE.
        try:
            device.kill(pid)
            state["cleanup_status"]="KILLED_OWN_SUSPENDED_TARGET"
            report("WARN","Cancelled own unresumed process",pid)
        except Exception as e:
            state["cleanup_status"]="SUSPENDED_PROCESS_CLEANUP_FAILED"
            state["cleanup_error"]=str(e)[:200]
        return
    try:
        sent=request_graceful_close_windows(pid)
        state["close_messages_sent"]=sent
        report("TARGET","Requested graceful WM_CLOSE for owned PID",pid,
               "| top-level windows:",sent)
        deadline=time.monotonic()+lifecycle["close_timeout_seconds"]
        while time.monotonic()<deadline:
            alive=process_exists(device,pid)
            if alive is False:
                state["cleanup_status"]="CLOSED_GRACEFULLY"
                report("TARGET","Tool-launched application closed")
                return
            time.sleep(.25)
        state["cleanup_status"]="STILL_RUNNING_AFTER_WM_CLOSE"
        report("WARN","Owned process",pid,"did not exit within",
               lifecycle["close_timeout_seconds"],"s; LEFT RUNNING (never force-kill active GUI)")
    except Exception as e:
        state["cleanup_status"]="GRACEFUL_CLOSE_FAILED"
        state["cleanup_error"]=str(e)[:200]
        report("WARN","Unable to close owned process gracefully:",str(e)[:200])


def smoke_lifecycle(args,cfg,report):
    """Managed Windows EXE launch/close smoke: ZERO attach, hooks or conversion.

    Deliberately refuses an already-open Manager so the smoke cannot close a
    user-owned process. Windows UI startup is given a short grace interval.
    """
    if os.name!="nt" or platform.architecture()[0]!="64bit":
        raise RuntimeError("Managed lifecycle smoke requires Windows x64 Python")
    lifecycle=cfg.get("lifecycle") or {}
    if lifecycle.get("start")!="fresh" or lifecycle.get("close")!="if_launched":
        raise ValueError("Lifecycle smoke requires JSON start=fresh, close=if_launched")
    if args.pid is not None:
        raise ValueError("Lifecycle smoke cannot target an existing --pid")
    preflight_paths(args,cfg,report)
    import frida
    device=frida.get_local_device()
    state={}
    pid=None
    try:
        pid,spawned=launch_target(device,args,cfg,report,state)
        if not spawned:
            raise RuntimeError("Lifecycle smoke refused a process it does not own")
        device.resume(pid)
        state["target_resumed"]=True
        report("TARGET","Lifecycle smoke: started owned GUI PID",pid)
        report("NOTE","Waiting 4s for GUI window; NO Frida attach/hook and NO conversion")
        time.sleep(4)
    finally:
        if pid is not None:
            report("TARGET","Lifecycle smoke: requesting graceful close for owned PID",pid)
            close_owned_target(device,pid,state,cfg,report)
    result=state.get("cleanup_status","NOT_RUN")
    report("STATUS","LIFECYCLE_SMOKE_"+result,"| PID:",pid,"| ZERO hooks")
    return 0 if result=="CLOSED_GRACEFULLY" else 3


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
    # Watch/config validation happens BEFORE spawning the application.
    watch,recursive,stable_seconds=resolve_completion(args,cfg)
    pid,spawned=launch_target(device,args,cfg,report,state)
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
        if spawned:
            # Module observer has already been registered inside suspended
            # process; loaded DLL SHA still gates any future hook attachment.
            device.resume(pid)
            state["target_resumed"]=True
            report("TARGET","Resumed tool-launched PID",pid)
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
        # Progress markers distinguish a slow Frida detach from a slow GUI
        # close. The old Stage48 console printed only the stable CLO message,
        # leaving the operator unable to tell which cleanup phase was active.
        report("NOTE","Capture loop ended; removing Frida instrumentation")
        if script is not None:
            try:
                script.unload()
                report("NOTE","Frida script unloaded")
            except Exception as exc:
                state["script_unload_error"]=str(exc)[:250]
                report("WARN","Frida script unload:",str(exc)[:250])
        if session is not None:
            try:
                session.detach()
                report("NOTE","Frida session detached")
            except Exception as exc:
                state["session_detach_error"]=str(exc)[:250]
                report("WARN","Frida session detach:",str(exc)[:250])
        report("TARGET","Cleanup phase: closing only owned PID",pid)
        close_owned_target(device,pid,state,cfg,report)

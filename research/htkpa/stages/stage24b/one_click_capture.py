"""Stage24B one-click Windows native FIR scalar capture (user-authorized).

Observational Frida hooks at original 5868USB.dll RVAs BD12 and B981.
NEVER records raw audio, FFT blocks, vendor DLL bytes or CLO/NAM/WAV files.
Every session, including timeouts and failures, produces a small tar.gz.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
import sys
import tarfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

DLL_SHA = "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"
ROOT = Path(__file__).resolve().parents[4]
PRIVATE = ROOT / "research" / "_LOCAL_FILES"
OUT_BASE = PRIVATE / "stage23w_native" / "stage24b_captures"
DLL_DEFAULT = PRIVATE / "vendor" / "5868USB.dll"
EXE_DEFAULT = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Sonicake" / "Sonicake Manager" / "Sonicake Manager.exe"
ARCHIVE_MEMBERS = ("manifest.json", "native_events.jsonl", "STAGE24B_HANDOFF.md", "ready.json")
AGENT = r"""
'use strict';
let installed=false,filters=0,generators=0;
function addr(p){try{return p.toString();}catch(e){return null;}}
function f64(p,o){try{let q=p.add(o);return {value:q.readDouble(),bits:'0x'+q.readU64().toString(16).padStart(16,'0')};}catch(e){return {error:String(e)};}}
function u32(p,o){try{return p.add(o).readU32();}catch(e){return null;}}
function event(kind,fields){send(Object.assign({kind:kind,ts_ms:Date.now(),thread:Process.getCurrentThreadId()},fields));}
function hook(mod,rva,kind,fn){
  Interceptor.attach(mod.base.add(rva),{onEnter(){
    try{fn.call(this);}catch(e){event('hook_error',{site:kind,error:String(e)});}
  }});
  event('hook_attached',{site:kind,rva:'0x'+rva.toString(16),live_address:addr(mod.base.add(rva))});
}
function install(mod){
 if(installed || mod.name.toLowerCase()!=='5868usb.dll')return;
 installed=true;
 event('module_loaded',{path:mod.path,base:addr(mod.base),size:mod.size});
 hook(mod,0xBD12,'filter_arguments',function(){
   if(++filters>8)return;const p=this.context.rcx;
   event('filter_arguments',{filter:addr(p),cutoff:f64(p,0),quality:f64(p,8),attenuation:f64(p,0x10),gain:f64(p,0x20)});
 });
 hook(mod,0xB981,'generator_arguments',function(){
   if(++generators>8)return;const p=this.context.rcx,f=this.context.rdi;
   event('generator_arguments',{filter:addr(f),generator:addr(p),filter_cutoff:f64(f,0),
    G_before_floor:f64(p,0),G_integer:u32(p,0x0c),theta:f64(p,0x18),gamma:f64(p,0x20),
    index:u32(p,0x58),beta:f64(p,0xc0),bessel_denominator:f64(p,0xc8),offset:f64(p,0xd0)});
 });
 event('hooks_ready',{sites:['0x18000BD12','0x18000B981']});
}
Process.attachModuleObserver({onAdded(mod){install(mod);}});
"""

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1 << 20), b''):
            h.update(part)
    return h.hexdigest()


def clo_snapshot(folder: Path) -> dict[str, tuple[int, int]]:
    if not folder.is_dir():
        return {}
    found = {}
    for p in folder.rglob('*'):
        if p.is_file() and p.suffix.lower() == '.clo':
            try:
                st = p.stat()
                found[str(p.relative_to(folder))] = (st.st_size, st.st_mtime_ns)
            except OSError:
                pass
    return found


def stable_changed_output(baseline: dict, current: dict, now: float, seen: dict, stable_seconds=5.0):
    """Require NEW/CHANGED CLO since start AND its size/mtime stable >= N sec."""
    changed = {k: v for k, v in current.items() if baseline.get(k) != v}
    for key in list(seen):
        if key not in changed:
            del seen[key]
    for key, value in changed.items():
        if key not in seen or seen[key][0] != value:
            seen[key] = (value, now)
        elif value[0] > 0 and now-seen[key][1] >= stable_seconds:
            return key
    return None


def pair_counts(events: list[dict]) -> tuple[int, int, int]:
    filters = {e.get('filter') for e in events if e.get('kind') == 'filter_arguments'}
    gens = {e.get('filter') for e in events if e.get('kind') == 'generator_arguments'}
    return (sum(e.get('kind') == 'filter_arguments' for e in events),
            sum(e.get('kind') == 'generator_arguments' for e in events),
            len((filters & gens) - {None}))


def archive_run(folder: Path, output: Path) -> dict:
    """Strict allowlist; verify member names and file checksums by reading tar.gz back."""
    hashes = {}
    with tarfile.open(output, 'w:gz') as tar:
        for name in ARCHIVE_MEMBERS:
            path = folder / name
            if not path.is_file() or path.is_symlink():
                continue
            hashes[name] = sha256(path)
            tar.add(path, arcname='stage24b/' + name, recursive=False)
    with tarfile.open(output, 'r:gz') as tar:
        names = [m.name for m in tar.getmembers()]
        assert set(names) == {'stage24b/' + name for name in hashes}
        assert all(m.isfile() for m in tar.getmembers())
        for m in tar.getmembers():
            actual = hashlib.sha256(tar.extractfile(m).read()).hexdigest()
            assert actual == hashes[m.name.split('/', 1)[1]]
    return hashes


def write_handoff(folder: Path, state: dict, status: str, method: str, problem: str):
    ev = state['events']
    f, g, paired = pair_counts(ev)
    selected = [x for x in ev if x.get('kind') in ('filter_arguments', 'generator_arguments')]
    lines = [
        '# Stage24B — Native FIR generator arguments handoff', '',
        f'**Status:** {status}  ', f'**Completion signal:** {method}  ',
        f'**Problem or limitation:** {problem or "none recorded"}  ',
        f'**DLL SHA256:** \`{DLL_SHA}\`  ',
        f'**Runtime-loaded DLL SHA verified:** {state["runtime_verified"]}  ',
        f'**Filter events:** {f}; **generator events:** {g}; **paired object identities:** {paired}.', '',
        '## Native evidence (if present)', '',
        'The JSON lines below are observed scalar values, including exact IEEE-754 bits; '
        'no reconstructed, fitted or guessed values are marked as native.', '',
        '\`\`\`json', *[json.dumps(x, sort_keys=True) for x in selected], '\`\`\`', '',
        '## Static reference only — do not overwrite observed values', '',
        '- PE original image base: \`0x180000000\`. Hook sites: \`0x18000BD12\` (filter) and \`0x18000B981\` (generator).',
        '- Stage23H candidate: cutoff 0.5 -> G_before_floor 708.9209756461122 -> 1417 taps.',
        '- Alternate branch candidate: cutoff 0.459375 -> G_before_floor 771.614667369918 -> 1543 taps.',
        '- Stage23Z corrected exponent candidate ≈ 0.15823713794954866; predicted theta ≈ 1.5428478841482018 rad.',
        '- Stage23Z maximum native coefficient difference ≈ 9.282550449007586e-10; exact bitwise coefficient parity OPEN.', '',
        '## Next static RE action', '',
        'Pair the events by \`filter\` pointer. Compare each **native IEEE754 bits** of cutoff/G/theta/gamma/beta '
        'to source-derived Stage23H/Z/A values. Trace the first mismatched calculation at '
        '\`0x18000B2B8–0x18000B844\` and \`0x180014810\`. No coefficient fitting.', '',
        '## Included files', '',
        '\`manifest.json\`, \`native_events.jsonl\`, \`ready.json\`, this handoff. '
        'Raw vendor DLL, WAV/NAM/CLO, RAM/FFT arrays and Python environment excluded.', ''
    ]
    (folder/'STAGE24B_HANDOFF.md').write_text('\n'.join(lines), encoding='utf-8')


def choose_pid(frida, preferred_exe: Path, specified_pid: int | None):
    device = frida.get_local_device()
    if specified_pid:
        return device, specified_pid, 'attach'
    running = [p for p in device.enumerate_processes()
               if 'sonicake manager' in p.name.lower()]
    if len(running) == 1:
        print(f'[APP] Attaching to existing Sonicake Manager PID={running[0].pid}')
        print('[NOTE] For a fresh constructor trace, close Manager and rerun if hooks remain silent.')
        return device, running[0].pid, 'attach'
    if len(running) > 1:
        raise RuntimeError('Multiple Sonicake Manager processes; rerun with --pid <PID>')
    exe = preferred_exe
    if not exe.is_file() and sys.stdin.isatty():
        typed = input('Path to Sonicake Manager.exe (Enter to abort): ').strip().strip('"')
        exe = Path(typed) if typed else exe
    if not exe.is_file():
        raise FileNotFoundError(f'Manager.exe not found at {exe}; run Manager first or --exe PATH')
    print(f'[APP] Spawning {exe} paused; hooks will be installed before resume.')
    return device, device.spawn([str(exe)]), 'spawn'


def capture(args, state: dict, folder: Path):
    if os.name != 'nt' or platform.architecture()[0] != '64bit':
        raise RuntimeError('Requires Windows x64 Python; WSL/Linux .venv cannot run this.')
    if not args.dll.is_file() or sha256(args.dll) != DLL_SHA:
        raise RuntimeError('Original vendor DLL missing or SHA-256 mismatch: ' + str(args.dll))
    try:
        import frida
    except ImportError as e:
        raise RuntimeError('Frida not installed in this Windows Python environment.') from e
    device, pid, mode = choose_pid(frida, args.exe, args.pid)
    state['pid'] = pid
    state['attach_mode'] = mode
    state['dll_path_sha_verified'] = True
    session = None
    script = None
    monitor_enter = threading.Event()
    enter_count = {'count': 0}
    def prompt_enter():
        try:
            input('Press ENTER only AFTER the normal NAM -> CLO import has finished: ')
            enter_count['count'] += 1
            monitor_enter.set()
        except (EOFError, OSError):
            pass
    baseline = clo_snapshot(args.watch_dir) if args.watch_dir else {}
    seen = {}
    events_path = folder/'native_events.jsonl'
    done_method = 'none'
    status = 'INCOMPLETE'
    problem = ''
    lock = threading.Lock()
    def on_message(msg, data):
        if msg.get('type') != 'send':
            payload = {'kind': 'frida_error', 'detail': str(msg)[:1000]}
        else:
            payload = msg['payload']
        if payload.get('kind') == 'module_loaded':
            runtime_path = Path(payload.get('path', ''))
            try:
                payload['runtime_dll_sha256'] = sha256(runtime_path)
                state['runtime_verified'] = payload['runtime_dll_sha256'] == DLL_SHA
            except (OSError, ValueError) as ex:
                payload['runtime_sha_error'] = str(ex)
                state['runtime_verified'] = False
        with lock:
            state['events'].append(payload)
            with events_path.open('a', encoding='utf-8') as fd:
                fd.write(json.dumps(payload, sort_keys=True) + '\n')
        if payload.get('kind') in ('filter_arguments', 'generator_arguments', 'hook_error'):
            print(f'[HOOK] {payload.get("kind")}: filter={payload.get("filter", "-")}')
    try:
        session = device.attach(pid)
        script = session.create_script(AGENT)
        script.on('message', on_message)
        script.load()
        if mode == 'spawn':
            device.resume(pid)
        (folder/'ready.json').write_text(json.dumps({'hook_sites': ['0x18000BD12','0x18000B981'],
            'pid': pid, 'mode': mode, 'started_utc': datetime.now(timezone.utc).isoformat()},indent=2)+'\n',encoding='utf-8')
        print('[READY] Hooks armed. Perform ONE normal NAM -> CLO import in Manager.')
        if args.watch_dir:
            print(f'[WATCH] Checking changed stable CLO in: {args.watch_dir}')
        if sys.stdin.isatty():
            threading.Thread(target=prompt_enter, daemon=True).start()
        started = time.monotonic()
        last_print = -1
        while time.monotonic()-started < args.timeout:
            time.sleep(0.4)
            with lock:
                counts = pair_counts(state['events'])
                error_hits = sum(x.get('kind') in ('hook_error','frida_error') for x in state['events'])
                saw_hooks_ready = any(x.get('kind') == 'hooks_ready' for x in state['events'])
            can_validate = bool(state['runtime_verified'] and saw_hooks_ready and counts[1] and counts[2] and not error_hits)
            auto = stable_changed_output(baseline,clo_snapshot(args.watch_dir),time.monotonic(),seen,
                stable_seconds=args.stable_seconds) if args.watch_dir else None
            if auto and can_validate:
                status='NATIVE_SCALARS_CAPTURED';done_method='changed_stable_CLO';break
            if monitor_enter.is_set():
                monitor_enter.clear()
                if can_validate:
                    status='NATIVE_SCALARS_CAPTURED';done_method='operator_confirmed_Enter';break
                print('[WAIT] ENTER received, but native verified paired generator hits not yet present; continuing.')
            elapsed = int(time.monotonic()-started)
            if elapsed//15 != last_print:
                last_print=elapsed//15
                print(f'[WAIT] {elapsed}s / {int(args.timeout)}s; filters={counts[0]}, generators={counts[1]}, paired={counts[2]}, DLL_verified={state["runtime_verified"]}')
        else:
            problem='Timeout before verified native scalar hits AND confirmed import completion'
        if status == 'NATIVE_SCALARS_CAPTURED':
            print('[DONE] Import completion confirmed; verified native parameters captured.')
        else:
            print('[WARN] Incomplete capture; archive will contain diagnostic events.')
    finally:
        if script:
            try: script.unload()
            except Exception: pass
        if session:
            try: session.detach()
            except Exception: pass
        # Intentionally leave the original Manager running even when spawned.
    return status, done_method, problem


def main():
    ap=argparse.ArgumentParser(description='Windows single-import scalar capture + verified tar.gz')
    ap.add_argument('--dll',type=Path,default=DLL_DEFAULT)
    ap.add_argument('--exe',type=Path,default=EXE_DEFAULT)
    ap.add_argument('--pid',type=int)
    ap.add_argument('--watch-dir',type=Path,help='optional CLO output folder for automatic completion')
    ap.add_argument('--timeout',type=float,default=900)
    ap.add_argument('--stable-seconds',type=float,default=5)
    ap.add_argument('--self-test',action='store_true')
    args=ap.parse_args()
    if args.self_test:
        return self_test()
    if not 5<=args.timeout<=7200 or not 1<=args.stable_seconds<=120:
        ap.error('invalid timeout or stable-seconds')
    if args.watch_dir is None and sys.stdin.isatty():
        raw=input('Optional CLO output folder (Enter = manual completion): ').strip().strip('"')
        if raw: args.watch_dir=Path(raw)
    if args.watch_dir and not args.watch_dir.is_dir():
        print('[WARN] Output folder missing; manual completion required:',args.watch_dir)
        args.watch_dir=None
    OUT_BASE.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    folder=OUT_BASE/('stage24b_'+stamp)
    folder.mkdir(parents=False,exist_ok=False)
    state={'events':[],'runtime_verified':False,'dll_path_sha_verified':False}
    status='INCOMPLETE';method='none';problem=''
    print('[SETUP] Stage24B output:',folder)
    try:
        status,method,problem=capture(args,state,folder)
    except (Exception,KeyboardInterrupt) as ex:
        status='BLOCKED' if not isinstance(ex,KeyboardInterrupt) else 'INTERRUPTED'
        problem=f'{type(ex).__name__}: {ex}'
        print('[ERROR]',problem)
    finally:
        (folder/'native_events.jsonl').touch(exist_ok=True)
        write_handoff(folder,state,status,method,problem)
        counts=pair_counts(state['events'])
        manifest={'stage':'Stage24B','status':status,'completion_method':method,'problem':problem,
          'date_utc':datetime.now(timezone.utc).isoformat(),'dll_sha256_expected':DLL_SHA,
          'dll_file_sha_verified':state['dll_path_sha_verified'],
          'runtime_dll_sha_verified':state['runtime_verified'],
          'hook_sites':['0x18000BD12','0x18000B981'],
          'filter_hits':counts[0],'generator_hits':counts[1],'paired_filter_objects':counts[2],
          'source':'Original Windows vendor DLL, observed read-only via Frida only if runtime verified',
          'limitations':'Only generator/filter scalars; no FIR coefficients, PCM/WAV, gains or CLO parity',
          'raw_files_excluded_from_archive':True}
        (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        archive=OUT_BASE/(folder.name+'.tar.gz')
        hashes=archive_run(folder,archive)
        print('[ARCHIVE]',archive)
        print('[CHECK] Verified allowlisted files:',', '.join(hashes))
        print('[RESULT]',status, 'filter=',counts[0],'generator=',counts[1],'paired=',counts[2])
        print('Send this tar.gz to the new ChatGPT RE chat; do not send entire private directory.')
    return 0 if status=='NATIVE_SCALARS_CAPTURED' else 2


def self_test():
    import tempfile
    baseline={'old.clo':(3,4)};seen={}
    assert stable_changed_output(baseline,{'old.clo':(3,4)},0,seen) is None
    assert stable_changed_output(baseline,{'old.clo':(4,5)},0,seen) is None
    assert stable_changed_output(baseline,{'old.clo':(4,5)},6,seen)=='old.clo'
    assert stable_changed_output(baseline,{'old.clo':(4,6)},7,seen) is None
    assert pair_counts([{'kind':'filter_arguments','filter':'f'},
       {'kind':'generator_arguments','filter':'f'}]) == (1,1,1)
    with tempfile.TemporaryDirectory() as tmp:
        folder=Path(tmp)/'run';folder.mkdir()
        for name in ARCHIVE_MEMBERS:
            (folder/name).write_text('fixture_'+name)
        (folder/'5868USB.dll').write_text('private proprietary fixture')
        (folder/'audio.wav').write_text('private audio fixture')
        a=Path(tmp)/'test.tar.gz'; h=archive_run(folder,a)
        assert len(h)==4
        with tarfile.open(a,'r:gz') as t:
            assert all('dll' not in m.name and 'wav' not in m.name for m in t)
    print('Stage24B offline self-tests: PASS (output stability, paired hits, allowlist + hash, private exclusion)')
    return 0


if __name__=='__main__':
    raise SystemExit(main())

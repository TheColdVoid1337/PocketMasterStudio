"""Stage24B: Windows-only, read-only Frida trace of ORIGINAL FIR generator arguments.

Attach to an authorized running Sonicake Manager, wait for ready.private.json,
then trigger one normal local import. Observes two original DLL addresses.
No FFT/PCM dump, device change, on-disk DLL edit or injected values.
ALL output must remain in ignored research/_LOCAL_FILES/.
"""
from __future__ import annotations
import argparse,hashlib,json,os,platform,time
from datetime import datetime,timezone
from pathlib import Path

SHA='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
AGENT=r"""
'use strict';
let installed=false,filterCount=0,genCount=0;
function h(p){try{return p.toString();}catch(e){return 'unavailable';}}
function f64(p,off){try{const q=p.add(off);return {value:q.readDouble(),bits:'0x'+q.readU64().toString(16)};}catch(e){return {error:String(e)};}}
function u32(p,off){try{return p.add(off).readU32();}catch(e){return null;}}
function emit(kind,fields){send(Object.assign({kind:kind,clock_ms:Date.now(),thread_id:Process.getCurrentThreadId()},fields));}
function install(mod){
 if(installed || mod.name.toLowerCase()!=='5868usb.dll')return;
 installed=true;
 emit('module_loaded',{module_path:mod.path,module_base:h(mod.base),size:mod.size,preferred_base:'0x180000000'});
 // 0x18000BD12: RCX is newly initialized filter object.
 Interceptor.attach(mod.base.add(0xBD12),{onEnter(){
   if(++filterCount>4)return;
   const f=this.context.rcx;
   emit('filter_arguments',{event_index:filterCount,site:'0x18000BD12',filter:h(f),
     cutoff:f64(f,0),quality:f64(f,8),attenuation:f64(f,0x10),gain:f64(f,0x20)});
 }});
 // 0x18000B981: RCX=generator at RSP+0x30, RDI=matching filter.
 Interceptor.attach(mod.base.add(0xB981),{onEnter(){
   if(++genCount>4)return;
   const g=this.context.rcx,f=this.context.rdi;
   emit('generator_arguments',{event_index:genCount,site:'0x18000B981',
     filter:h(f),generator:h(g),filter_cutoff:f64(f,0),
     pre_floor_G:f64(g,0),G_integer:u32(g,0xc),
     oscillator_low:f64(g,0x10),theta:f64(g,0x18),gamma:f64(g,0x20),
     window_index:u32(g,0x58),beta:f64(g,0xc0),
     bessel_denominator:f64(g,0xc8),window_offset:f64(g,0xd0)});
 }});
 emit('hooks_attached',{sites:['0x18000BD12','0x18000B981']});
}
Process.attachModuleObserver({onAdded(mod){install(mod);}});
"""
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
 return h.hexdigest()
def main():
 p=argparse.ArgumentParser()
 p.add_argument('--pid',type=int,required=True)
 p.add_argument('--dll',type=Path,required=True)
 p.add_argument('--out',type=Path,required=True)
 p.add_argument('--seconds',type=float,default=30)
 a=p.parse_args()
 if os.name!='nt' or platform.architecture()[0]!='64bit':
  raise SystemExit('Stage24B requires Windows x64 Python (not WSL .venv)')
 if sha(a.dll)!=SHA:raise SystemExit('Vendor DLL SHA-256 mismatch')
 out=a.out.resolve()
 if '_LOCAL_FILES' not in out.parts:
  raise SystemExit('Output MUST be under research/_LOCAL_FILES/')
 if not 5<=a.seconds<=120:raise SystemExit('Use bounded duration 5–120 seconds')
 try:import frida
 except ImportError:raise SystemExit('Install Frida in a private Windows x64 venv')
 out.mkdir(parents=True,exist_ok=True)
 events=[];errors=[]
 def on_message(message,data):
  if message.get('type')!='send':
   errors.append(message);return
  row=message['payload'];events.append(row)
  with (out/'generator_arguments.private.jsonl').open('a',encoding='utf8') as f:
   f.write(json.dumps(row,sort_keys=True)+'\n')
  if row.get('kind')=='module_loaded':
   path=Path(row.get('module_path',''))
   try:
    if sha(path)!=SHA:errors.append({'error':'Runtime-loaded DLL SHA mismatch'})
   except Exception as exc:errors.append({'error':'Runtime DLL hash unreadable','detail':str(exc)})
 device=frida.get_local_device()
 session=device.attach(a.pid)
 script=session.create_script(AGENT)
 script.on('message',on_message)
 try:
  script.load()
  (out/'ready.private.json').write_text(json.dumps({'pid':a.pid,'ready':True,
    'sites':['0x18000BD12','0x18000B981']},indent=2)+'\n',encoding='utf8')
  print('Stage24B hooks ready: trigger one authorized local normal import.',flush=True)
  time.sleep(a.seconds)
 finally:
  script.unload()
  session.detach()
 result={'stage':'Stage24B','timestamp_utc':datetime.now(timezone.utc).isoformat(),
   'pinned_sha256':SHA,'pid':a.pid,
   'filter_events':sum(x.get('kind')=='filter_arguments' for x in events),
   'generator_events':sum(x.get('kind')=='generator_arguments' for x in events),
   'loaded_events':sum(x.get('kind')=='module_loaded' for x in events),
   'errors':errors,
   'status':'NATIVE_SCALARS_CAPTURED' if not errors and any(
      x.get('kind')=='generator_arguments' for x in events) else 'BLOCKED_OR_NO_HIT',
   'trace_file':'generator_arguments.private.jsonl',
   'scope':'only scalar generator fields and exact IEEE754 bits; no audio memory dump'}
 (out/'summary.private.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()

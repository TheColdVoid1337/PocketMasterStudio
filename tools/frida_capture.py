"""Universal Windows x64 read-only Frida scalar observer. No vendor-specific paths or stage logic."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
import re
import sys
import tarfile
import threading
import time
import frida_guarded
from datetime import datetime, timezone
from pathlib import Path

REGS = {'rax','rbx','rcx','rdx','rsi','rdi','rbp','rsp','r8','r9','r10','r11','r12','r13','r14','r15'}
TYPES = {'f64','f32','u8','u16','u32','u64','i32','ptr','reg_ptr','reg_u64','f64_slice','f64_block','f64_binary','xmm_f64','xmm_f32'}
XMM_REGS = {'xmm'+str(i) for i in range(16)}
MAX_SITES, MAX_FIELDS, MAX_HITS = 64, 16, 10000
DEFAULT_OUT = Path(__file__).resolve().parents[1] / 'research' / '_LOCAL_FILES' / 'frida_captures'

COLORS = {'TARGET':'\x1b[36m','NOTE':'\x1b[36m','FRIDA':'\x1b[35m',
          'HOOK':'\x1b[35m','META':'\x1b[32m','CLO':'\x1b[32m',
          'WAIT':'\x1b[33m','WARN':'\x1b[33m','STARTED':'\x1b[32m',
          'STATUS':'\x1b[32m','ARCHIVE':'\x1b[32m','ERROR':'\x1b[31m'}
def report(kind,*parts):
    enabled = os.environ.get('NO_COLOR') is None and (sys.stdout.isatty() or os.environ.get('FORCE_COLOR')=='1')
    prefix='['+kind+']'
    if enabled:prefix=COLORS.get(kind,'')+prefix+'\x1b[0m'
    print(prefix,*parts,flush=True)

def sha(path):
    h = hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1048576),b''):
            h.update(b)
    return h.hexdigest()

def address(value, image_base):
    v = int(str(value),0)
    if v < 0 or v >= 1 << 64: raise ValueError('address out of range')
    if v >= image_base: v -= image_base
    return v

def validate(cfg):
    if isinstance(cfg,dict) and cfg.get('mode')=='guarded_metadata':
        return frida_guarded.validate_config(cfg,address)
    if not isinstance(cfg,dict): raise ValueError('config must be an object')
    required = ('module','sha256','sites')
    for k in required:
        if k not in cfg: raise ValueError('missing '+k)
    if not re.fullmatch(r'[a-fA-F0-9]{64}',cfg['sha256']):
        raise ValueError('expected module SHA256 required')
    if not isinstance(cfg['module'],str) or not re.fullmatch(r'[a-zA-Z0-9_. -]+\.(?:dll|exe)',cfg['module'],re.I):
        raise ValueError('module must be a simple DLL/EXE basename')
    base = int(str(cfg.get('image_base','0x180000000')),0)
    sites = cfg['sites']
    if not isinstance(sites,list) or not (1 <= len(sites) <= MAX_SITES):
        raise ValueError('1..64 sites required')
    names=set()
    normalized=[]
    for s in sites:
        name=s.get('name')
        if not isinstance(name,str) or not re.fullmatch('[a-zA-Z][a-zA-Z0-9_]{0,63}',name) or name in names:
            raise ValueError('invalid or duplicate site name')
        names.add(name)
        rva=address(s.get('address'),base)
        fields=s.get('fields',[])
        if not isinstance(fields,list) or len(fields)>MAX_FIELDS: raise ValueError('too many fields')
        out=[]
        for f in fields:
            label=f.get('name')
            typ=f.get('type')
            reg=f.get('reg')
            offset=f.get('offset',0)
            if not isinstance(label,str) or not re.fullmatch('[a-zA-Z][a-zA-Z0-9_]{0,63}',label):
                raise ValueError('invalid field name')
            if typ not in TYPES or reg not in (XMM_REGS if typ.startswith('xmm_') else REGS):
                raise ValueError('unsupported type or register')
            if typ in ('reg_ptr','reg_u64') and int(str(offset),0)!=0: raise ValueError('direct register offset must be zero')
            if typ.startswith('xmm_') and int(str(offset),0) not in ((0,8) if typ=='xmm_f64' else (0,4,8,12)):
                raise ValueError('invalid XMM lane offset')
            off=int(str(offset),0)
            if off < -4096 or off > 4096: raise ValueError('offset out of bounded range')
            count=int(f.get('count',8))
            if typ in ('f64_slice','f64_block','f64_binary') and not 1<=count<=2048: raise ValueError('f64 block count must be 1..2048')
            out.append(dict(name=label,type=typ,reg=reg,offset=off,count=count if typ in ('f64_slice','f64_block','f64_binary') else 1))
        hits=int(s.get('max_hits',8))
        if not 1<=hits<=MAX_HITS: raise ValueError('max_hits out of range')
        normalized.append(dict(name=name,rva=rva,fields=out,max_hits=hits,required=bool(s.get('required',True))))
    return dict(module=cfg['module'],sha256=cfg['sha256'].lower(),sites=normalized,
                image_base=base)

def agent_source(cfg):
    # Only the validated descriptor is injected. No arbitrary JavaScript snippets.
    return r"""
'use strict';
const spec=SPEC_HERE;
let installed=false;
const counters={};
function tell(data){send(Object.assign({timestamp_ms:Date.now(),thread:Process.getCurrentThreadId()},data));}
function scalar(ctx, f){
  try {
    let value, bits=null;
    if(f.type==='xmm_f64' || f.type==='xmm_f32'){
      const raw=ctx[f.reg];
      // Frida may expose an ArrayBuffer from a different JS realm, so do NOT
      // reject a valid buffer based on instanceof ArrayBuffer.
      const width=f.type==='xmm_f64'?8:4;
      const source=(raw && raw.buffer && typeof raw.byteLength==='number')?raw.buffer:raw;
      let v;
      try { v=new DataView(source); }
      catch(e) {
        throw Error('XMM buffer conversion failed: type='+typeof raw+
          ', tag='+Object.prototype.toString.call(raw)+
          ', byteLength='+(raw && raw.byteLength)+', reason='+String(e));
      }
      const offset=f.offset+((source!==raw && raw.byteOffset)?raw.byteOffset:0);
      if(v.byteLength<offset+width)throw Error('XMM buffer too small: '+v.byteLength);
      value=width===8?v.getFloat64(offset,true):v.getFloat32(offset,true);
      const bytes=new Uint8Array(source,offset,width);
      bits='0x'+Array.from(bytes).reverse().map(b=>b.toString(16).padStart(2,'0')).join('');
      return {value:value,bits:bits};
    }
    if(f.type==='reg_ptr' || f.type==='reg_u64'){
      if(f.offset!==0)throw Error('register direct value disallows offset');
      const regval=ctx[f.reg];
      return {value:f.type==='reg_ptr'?regval.toString():regval.toString(),bits:null};
    }
    const p=ctx[f.reg].add(f.offset);
    if(f.type==='f64_block'){
      const raw=p.readByteArray(f.count*8);
      if(raw===null)throw Error('null memory block');
      const bytes=new Uint8Array(raw),parts=new Array(bytes.length);
      for(let i=0;i<bytes.length;i++)parts[i]=bytes[i].toString(16).padStart(2,'0');
      return {encoding:'hex_f64le',count:f.count,hex:parts.join('')};
    }
    if(f.type==='f64_slice'){
      const values=[], bitStrings=[];
      for(let i=0;i<f.count;i++){
        const q=p.add(i*8);
        values.push(q.readDouble());
        bitStrings.push('0x'+q.readU64().toString(16).padStart(16,'0'));
      }
      return {values:values,bits:bitStrings,count:f.count};
    }
    switch(f.type){
      case 'f64': value=p.readDouble();bits='0x'+p.readU64().toString(16).padStart(16,'0');break;
      case 'f32': value=p.readFloat();bits='0x'+p.readU32().toString(16).padStart(8,'0');break;
      case 'u8': value=p.readU8();break;
      case 'u16': value=p.readU16();break;
      case 'u32': value=p.readU32();break;
      case 'i32': value=p.readS32();break;
      case 'u64': value=p.readU64().toString();break;
      case 'ptr': value=p.readPointer().toString();break;
    }
    return {value:value,bits:bits};
  }catch(e){return {error:String(e).slice(0,200)};}
}
function install(mod) {
 if(installed || mod.name.toLowerCase()!==spec.module.toLowerCase())return;
 installed=true;
 tell({kind:'module_loaded',path:mod.path,base:mod.base.toString(),size:mod.size});
 let count=0;
 for(const site of spec.sites){
  try {
   if(site.rva >= mod.size)throw Error('RVA outside module image');
   counters[site.name]=0;
   Interceptor.attach(mod.base.add(site.rva),{onEnter(){
    if(++counters[site.name]>site.max_hits)return;
    const fields={};
    for(const f of site.fields){
      if(f.type==='f64_binary'){
        try{
          const raw=this.context[f.reg].add(f.offset).readByteArray(f.count*8);
          if(raw===null)throw Error('null memory block');
          send({kind:'binary_block',site:site.name,field:f.name,count:f.count,
            timestamp_ms:Date.now(),thread:Process.getCurrentThreadId()},raw);
          fields[f.name]={encoding:'binary_f64le',count:f.count,bytes:f.count*8};
        }catch(e){fields[f.name]={error:String(e).slice(0,200)};}
      } else fields[f.name]=scalar(this.context,f);
    }
    tell({kind:'hit',site:site.name,rva:site.rva,pc:mod.base.add(site.rva).toString(),
      registers:{rcx:this.context.rcx.toString(),rdx:this.context.rdx.toString(),
      r8:this.context.r8.toString(),r9:this.context.r9.toString()},fields:fields});
   }});
   count++;
   tell({kind:'hook_attached',site:site.name,rva:site.rva});
  }catch(e){tell({kind:'hook_error',site:site.name,error:String(e)});}
 }
 tell({kind:'ready',installed:count,requested:spec.sites.length});
}
Process.attachModuleObserver({onAdded(mod){install(mod);}});
""".replace('SPEC_HERE',json.dumps(cfg,ensure_ascii=True))

def build_config(args):
    if args.config:
        cfg=json.loads(args.config.read_text(encoding='utf-8'))
    else:
        cfg=dict(module=args.module,sha256=args.sha256,image_base=args.image_base,sites=[])
    for value in args.site:
        # --site name:address, followed by any --field name:field:type:register:offset
        name,addr=value.split(':',1)
        cfg['sites'].append(dict(name=name,address=addr,fields=[]))
    for value in args.field:
        parts=value.split(':')
        if len(parts)!=5:raise ValueError('--field site:name:type:register:offset')
        site,field,typ,reg,off=parts
        found=next((x for x in cfg['sites'] if x['name']==site),None)
        if found is None:raise ValueError('unknown field site: '+site)
        found.setdefault('fields',[]).append(dict(name=field,type=typ,reg=reg,offset=off))
    return validate(cfg)

def archive(directory, destination):
    members=['config.json','manifest.json','events.jsonl','HANDOFF.md'] + sorted(p.name for p in directory.glob('block_*.bin'))
    digest={}
    with tarfile.open(destination,'w:gz') as t:
        for name in members:
            path=directory/name
            digest[name]=sha(path)
            t.add(path,arcname='frida_capture/'+name,recursive=False)
    with tarfile.open(destination,'r:gz') as t:
        mm=t.getmembers()
        assert sorted(m.name for m in mm)==sorted('frida_capture/'+x for x in members)
        assert all(m.isfile() for m in mm)
        for m in mm:
            assert hashlib.sha256(t.extractfile(m).read()).hexdigest()==digest[m.name.split('/')[1]]
    return digest

def capture(args,cfg,folder,state):
    if os.name!='nt' or platform.architecture()[0]!='64bit':
        raise RuntimeError('Run under Windows x64 Python (not WSL)')
    try: import frida
    except ImportError as e:raise RuntimeError('Frida missing in this Windows Python') from e
    device=frida.get_local_device()
    if args.pid is not None:
        chosen=next((p for p in device.enumerate_processes() if p.pid==args.pid),None)
        if chosen is None:raise RuntimeError('Explicit PID is no longer running')
        pid=args.pid; spawned=False
        report('TARGET','Verified explicit PID:',pid,chosen.name)
    else:
        matches=[p for p in device.enumerate_processes()
                 if 'sonicake' in p.name.lower()]
        if args.fresh:
            matches=[]
        if len(matches)>1:
            raise RuntimeError('Multiple Manager processes; specify --pid to disambiguate')
        if len(matches)==1:
            pid=matches[0].pid; spawned=False
            report('TARGET','Auto-attaching:',matches[0].name,'PID',pid)
            report('NOTE','Existing process may have passed early hooks; --fresh needs Manager closed first.')
        else:
            if args.exe is None or not args.exe.is_file():
                raise FileNotFoundError('No running Sonicake Manager; --exe path required to spawn')
            if args.fresh and any('sonicake' in p.name.lower()
                                   for p in device.enumerate_processes()):
                raise RuntimeError('--fresh requires Manager to be closed first; will not terminate it')
            report('TARGET','Spawning with hooks before resume:',args.exe)
            pid=device.spawn([str(args.exe)]);spawned=True
    state.update(runtime_verified=False,ready=False,hits=0,hook_errors=0,field_errors=0,valid_field_hits=0,site_hits={},last_hit_monotonic=None)
    events_path=folder/'events.jsonl'
    lock=threading.Lock()
    def on_message(msg,data):
        if msg.get('type')=='send' and msg.get('payload',{}).get('kind')=='binary_block':
            payload=msg['payload']
            name='block_{:d}_{}_{}.bin'.format(int(payload['timestamp_ms']),payload['site'],payload['field'])
            if not re.fullmatch(r'block_[0-9]+_[A-Za-z0-9_]+_[A-Za-z0-9_]+[.]bin',name):
                raise ValueError('invalid block filename')
            body=bytes(data or b'')
            if len(body)!=int(payload['count'])*8 or len(body)>16384:
                raise ValueError('invalid binary block size')
            (folder/name).write_bytes(body)
            payload.update(file=name,sha256=hashlib.sha256(body).hexdigest(),bytes=len(body))
        e=msg.get('payload',{}) if msg.get('type')=='send' else dict(kind='frida_error',error=str(msg)[:500])
        if e.get('kind')=='module_loaded':
            try:
                actual=sha(Path(e['path']))
                e['runtime_sha256']=actual
                state['runtime_verified']=(actual==cfg['sha256'])
            except OSError as ex:e['sha_error']=str(ex)
        if e.get('kind')=='ready':state['ready']=e.get('installed')==e.get('requested')
        if e.get('kind')=='hit':
            state['hits']+=1
            state['site_hits'][e.get('site','?')]=state['site_hits'].get(e.get('site','?'),0)+1
            state['last_hit_monotonic']=time.monotonic()
            fields=e.get('fields',{})
            errors=sum(isinstance(v,dict) and 'error' in v for v in fields.values())
            state['field_errors']+=errors
            if fields and not errors:state['valid_field_hits']+=1
        if e.get('kind') in ('hook_error','frida_error'):state['hook_errors']+=1
        with lock:
            with events_path.open('a',encoding='utf-8') as f:
                f.write(json.dumps(e,ensure_ascii=True)+'\n')
        if e.get('kind') in ('hit','hook_error','ready'):
            report('ERROR' if e.get('kind')=='hook_error' else 'FRIDA',e.get('kind'),e.get('site',''))
    watch_dir=args.completion_dir
    def clo_snapshot():
        if watch_dir is None or not watch_dir.is_dir(): return {}
        result={}
        for f in watch_dir.glob('*.clo'):
            try:
                st=f.stat()
                result[str(f.resolve()).lower()]=(st.st_size,st.st_mtime_ns)
            except OSError: pass
        return result
    baseline=clo_snapshot()
    candidate=None
    candidate_since=None
    session=None;script=None
    try:
        session=device.attach(pid)
        script=session.create_script(agent_source(cfg))
        script.on('message',on_message)
        script.load()
        if spawned:device.resume(pid)
        report('STARTED','PID',pid,'Auto-finish available when configured.')
        input_done=threading.Event()
        if sys.stdin.isatty():
            def read_enter():
                try:input();input_done.set()
                except (EOFError,OSError):pass
            threading.Thread(target=read_enter,daemon=True).start()
        start=time.monotonic()
        while time.monotonic()-start<args.timeout:
            input_done.wait(0.25)
            with lock:
                valid=(state['ready'] and state['runtime_verified'] and state['valid_field_hits']
                    and not state['field_errors'] and not state['hook_errors']
                    and all(state['site_hits'].get(site['name'],0)>0 for site in cfg['sites'] if site['required']))
                quiet=(state['last_hit_monotonic'] is not None and
                    time.monotonic()-state['last_hit_monotonic']>=args.auto_quiet)
            if watch_dir is not None:
                current=clo_snapshot()
                changes=[(p,meta) for p,meta in current.items()
                         if meta[0]>0 and baseline.get(p)!=meta]
                if changes:
                    selected=max(changes,key=lambda x:x[1][1])
                    if selected==candidate:
                        if candidate_since is not None and time.monotonic()-candidate_since>=3 and valid:
                            report('ARCHIVE','Changed CLO stable for 3 seconds; detaching')
                            return ('CAPTURED_HOOKS_ONLY','stable_clo_after_hooks',state,pid)
                    else:
                        candidate=selected;candidate_since=time.monotonic()
                else:
                    candidate=None;candidate_since=None
            if args.auto_quiet and valid and quiet:
                report('ARCHIVE','All configured sites observed, quiet period complete')
                return ('CAPTURED_HOOKS_ONLY','auto_quiet_after_hooks',state,pid)
            if input_done.is_set():
                return ('CAPTURED_HOOKS_ONLY' if valid else 'INCOMPLETE','operator_enter',state,pid)
        return ('INCOMPLETE','timeout',state,pid)
    finally:
        if script:
            try:script.unload()
            except Exception:pass
        if session:
            try:session.detach()
            except Exception:pass

def self_test():
    c=validate(dict(module='5868USB.dll',sha256='a'*64,sites=[dict(name='test',address='0x18000BD12',fields=[dict(name='sample',type='f64',reg='rcx',offset=8)])]))
    assert c['sites'][0]['rva']==0xbd12
    assert 'Interceptor.attach' in agent_source(c)
    x=validate(dict(module='5868USB.dll',sha256='a'*64,sites=[dict(name='xmm',address='0x18000B81C',fields=[dict(name='width',type='xmm_f64',reg='xmm8',offset=0)])]))
    assert x['sites'][0]['fields'][0]['reg']=='xmm8'
    q=validate(dict(module='5868USB.dll',sha256='a'*64,sites=[dict(name='copy',address='0x18000C838',fields=[dict(name='samples',type='f64_slice',reg='rdx',offset=0,count=8)])]))
    assert q['sites'][0]['fields'][0]['count']==8
    z=validate(dict(module='5868USB.dll',sha256='a'*64,sites=[dict(name='block',address='0x18000C838',max_hits=2,fields=[dict(name='samples',type='f64_slice',reg='rdx',offset=0,count=1972)])]))
    assert z['sites'][0]['fields'][0]['count']==1972
    z=validate(dict(module='5868USB.dll',sha256='a'*64,sites=[dict(name='registers',address='0x18000C838',fields=[dict(name='bytes',type='reg_u64',reg='r8',offset=0)])]))
    assert z['sites'][0]['fields'][0]['type']=='reg_u64'
    b=validate(dict(module='5868USB.dll',sha256='a'*64,sites=[dict(name='binary',address='0x18000C838',fields=[dict(name='block',type='f64_block',reg='rdx',count=1972)])]))
    assert b['sites'][0]['fields'][0]['count']==1972
    assert 'p.readByteArray(f.count*8)' in agent_source(b)
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp)
        for x in ['config.json','manifest.json','events.jsonl','HANDOFF.md']:(d/x).write_text('test')
        (d/'secret.wav').write_text('excluded')
        archive(d,d/'run.tar.gz')
        with tarfile.open(d/'run.tar.gz') as t:
            assert not any('secret' in x.name for x in t)
    print('Offline tests PASS: config, RVA, agent construction, archive exclusions')

def main():
    ap=argparse.ArgumentParser(description='Read-only, JSON/CLI configurable Windows Frida scalar capture')
    ap.add_argument('--config',type=Path)
    ap.add_argument('--module')
    ap.add_argument('--sha256')
    ap.add_argument('--image-base',default='0x180000000')
    ap.add_argument('--site',action='append',default=[],help='name:VA-or-RVA')
    ap.add_argument('--field',action='append',default=[],help='site:name:type:register:offset')
    ap.add_argument('--pid',type=int)
    ap.add_argument('--completion-dir',type=Path,help='watch Windows directory for a new/changed stable CLO')
    ap.add_argument('--fresh',action='store_true',help='spawn fresh Manager; requires old instances closed')
    ap.add_argument('--exe',type=Path,default=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Sonicake'/'Sonicake Manager'/'Sonicake Manager.exe')
    ap.add_argument('--module-file',type=Path,help='original DLL/EXE to SHA-verify before hooking')
    ap.add_argument('--timeout',type=int,default=900)
    ap.add_argument('--auto-quiet',type=float,default=0,help='finish after all sites and N quiet seconds; no import completion claim')
    ap.add_argument('--out',type=Path,default=DEFAULT_OUT)
    ap.add_argument('--self-test',action='store_true')
    ap.add_argument('--list-processes',action='store_true',help='list Windows process candidates, ZERO hooks')
    args=ap.parse_args()
    if args.self_test:
        self_test()
        report('NOTE',frida_guarded.self_test(validate))
        return 0
    if not 5<=args.timeout<=7200:ap.error('timeout must be 5..7200')
    if args.auto_quiet and not 3<=args.auto_quiet<=300:ap.error('auto-quiet must be 3..300')
    try:cfg=build_config(args)
    except (ValueError,KeyError,TypeError) as e:ap.error(str(e))
    if args.list_processes:
        return frida_guarded.list_processes(report,cfg)
    guarded=cfg.get('mode')=='guarded_metadata'
    if guarded and args.fresh:
        ap.error('guarded metadata requires an existing process; --fresh is forbidden')
    if guarded and args.auto_quiet:
        ap.error('guarded metadata needs a verified CLO, not --auto-quiet')
    args.out.mkdir(parents=True,exist_ok=True)
    folder=args.out/('frida_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f'))
    folder.mkdir()
    (folder/'config.json').write_text(json.dumps(cfg,indent=2)+'\n')
    (folder/'events.jsonl').touch()
    state={};status='BLOCKED';method='none';problem=''
    try:
        if args.module_file:
            if sha(args.module_file)!=cfg['sha256']:raise RuntimeError('module-file SHA mismatch')
        if guarded:
            status,method,pid=frida_guarded.capture(args,cfg,folder,state,report,sha)
        else:
            status,method,state,pid=capture(args,cfg,folder,state)
    except KeyboardInterrupt:
        problem='Operator Ctrl+C; preserving already emitted event journal'
        status=('METADATA_OBSERVED_OPERATOR_INTERRUPTED' if guarded and state.get('metadata_valid')
                else 'OPERATOR_INTERRUPTED')
        method='operator_interrupt'
        report('WARN',problem)
    except Exception as e:
        problem=f'{type(e).__name__}: {e}'
        status='BLOCKED_AFTER_METADATA' if guarded and state.get('metadata_valid') else 'BLOCKED'
        report('ERROR',problem)
    if guarded:
        frida_guarded.reconcile(folder,state)
        if method=='operator_interrupt':
            status=frida_guarded.interrupted_status(state)
        elif status=='BLOCKED' and state.get('metadata_valid'):
            status='BLOCKED_AFTER_METADATA'
    manifest=dict(status=status,method=method,problem=problem,
        date_utc=datetime.now(timezone.utc).isoformat(),module=cfg['module'],
        mode=('guarded_metadata' if guarded else 'legacy_scalar'),
        expected_sha256=cfg['sha256'],
        hook_count=(1 if state.get('hook_attached') else 0) if guarded
                   else (len(cfg['sites']) if state.get('ready') else 0),
        contains_audio_bytes=bool(not guarded and any(
            f['type'] in ('f64_binary','f64_block','f64_slice','f64')
            for site in cfg['sites'] for f in site['fields'])),
        completion_verified=bool(state.get('completion_verified',False)),
        launched_by_tool=bool(state.get('launched_by_tool',False)),
        process_cleanup_status=state.get('cleanup_status','NOT_APPLICABLE'),
        state=state,
        scope=('guarded metadata; no audio reads' if guarded else 'bounded read-only scalar observation'))
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    evidence_note=('Guarded metadata: ONLY events marked metadata_hit are observations; '
                   'no audio samples were captured. Runtime DLL SHA plus a new stable CLO '
                   'must be checked before any metadata-completion PASS.'
                   if guarded else
                   'Legacy capture: native values require a valid hit event and '
                   'runtime DLL SHA verification; binary data stays in the local archive.')
    (folder/'HANDOFF.md').write_text('# Universal Frida capture\n\nStatus: '+status+
        '\n\nCompletion: '+method+'\n\nIssue: '+problem+
        '\n\n'+evidence_note+'\n')
    dest=folder.with_suffix('.tar.gz')
    archive(folder,dest)
    report('STATUS',status,'| hook:',state.get('hook_attached',state.get('ready',False)),
           '| metadata:',state.get('metadata_valid',False),
           '| stable CLO:',state.get('completion_verified',False))
    report('ARCHIVE',dest,'[RESULT]',status)
    if guarded and state.get('launched_by_tool') and cfg.get('lifecycle',{}).get('close')=='if_launched':
        if state.get('cleanup_status') not in ('CLOSED_GRACEFULLY','ALREADY_EXITED'):
            report('WARN','Native observation status above is independent of application shutdown;',
                   'automatic close did not complete:',state.get('cleanup_status'))
            return 3
    return 0 if status in ('CAPTURED','CAPTURED_HOOKS_ONLY','METADATA_GUARD_PASS_CLO_STABLE') else 2

if __name__=='__main__':raise SystemExit(main())

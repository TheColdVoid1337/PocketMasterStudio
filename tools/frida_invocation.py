"""Stage96 pinned, bounded and read-only native invocation trace.

This is opt-in; legacy and guarded Frida modes never import the agent JS.
Only the eight independently audited original-PE entry RVAs are allowed.
"""
from __future__ import annotations

import json
import re

ORIGINAL_SHA = 'fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
PINNED = {
    'wrapper_ff40': 0xFF40,
    'wrapper_10e70': 0x10E70,
    'nam_worker_e0e0': 0xE0E0,
    'wav_fitter_d4a0': 0xD4A0,
    'clone_f940': 0xF940,
    'clone_10230': 0x10230,
    'resample_be830': 0xBE830,
    'resample_ce00': 0xCE00,
}


def validate(cfg, address):
    if not isinstance(cfg, dict) or cfg.get('mode') != 'invocation_trace':
        raise ValueError('invocation_trace mode required')
    if cfg.get('module') != '5868USB.dll' or cfg.get('sha256') != ORIGINAL_SHA:
        raise ValueError('Stage96 requires pinned original DLL and SHA256')
    if set(cfg) != {'mode', 'module', 'sha256', 'image_base', 'sites', 'max_events', 'max_depth'}:
        raise ValueError('unknown or missing invocation trace configuration key')
    if str(cfg['image_base']).lower() != '0x180000000':
        raise ValueError('Stage96 original PE image base required')
    if type(cfg['max_events']) is not int or not 64 <= cfg['max_events'] <= 128:
        raise ValueError('max_events must be 64..128')
    if type(cfg['max_depth']) is not int or not 4 <= cfg['max_depth'] <= 12:
        raise ValueError('max_depth must be 4..12')
    sites = cfg['sites']
    if not isinstance(sites, list) or len(sites) != len(PINNED):
        raise ValueError('all eight Stage96 sites required')
    normalized = []
    seen = set()
    for s in sites:
        if not isinstance(s, dict) or set(s) != {'name', 'address', 'max_hits', 'required'}:
            raise ValueError('only name/address/max_hits/required allowed')
        name = s['name']
        if name not in PINNED or name in seen:
            raise ValueError('unreviewed or duplicate site')
        seen.add(name)
        rva = address(s['address'], 0x180000000)
        if rva != PINNED[name]:
            raise ValueError('Stage96 entry RVA mismatch: ' + name)
        if type(s['max_hits']) is not int or not 1 <= s['max_hits'] <= 6:
            raise ValueError('per-site limit must be 1..6')
        if type(s['required']) is not bool:
            raise ValueError('required must be a boolean')
        normalized.append({'name': name, 'rva': rva,
                           'max_hits': s['max_hits'], 'required': s['required'], 'fields': []})
    if sum(s['max_hits'] for s in normalized) * 2 > cfg['max_events']:
        raise ValueError('max_events cannot fit all permitted enter/leave pairs')
    if {s['name'] for s in normalized if s['required']} != {'nam_worker_e0e0', 'wav_fitter_d4a0'}:
        raise ValueError('Stage96 only NAM worker and WAV fitter are required')
    return {'mode': 'invocation_trace', 'module': cfg['module'], 'sha256': ORIGINAL_SHA,
            'image_base': 0x180000000, 'sites': normalized,
            'max_events': cfg['max_events'], 'max_depth': cfg['max_depth']}


def agent_source(cfg):
    # cfg was validated above; no arbitrary JS, field read, source URL, or user code.
    return r"""
'use strict';
const spec=SPEC_HERE;
const counts=Object.create(null);
const stacks=Object.create(null);
let installed=false, serial=0, sent=0, poisoned=false;
function emit(e){send(Object.assign({timestamp_ms:Date.now(),thread:Process.getCurrentThreadId()},e));}
function error(reason){
  if(!poisoned){poisoned=true;emit({kind:'trace_error',reason:String(reason).slice(0,100)});}
}
function failLimit(reason){
  if(!poisoned){poisoned=true;emit({kind:'trace_limit',reason:String(reason).slice(0,100)});}
}
function event(e){
  if(sent>=spec.max_events){failLimit('max_events');return;}
  sent++;emit(e);
}
function returnRva(addr,mod){
  if(addr.compare(mod.base)<0 || addr.compare(mod.base.add(mod.size))>=0)return null;
  return addr.sub(mod.base).toString();
}
function install(mod){
  if(installed || mod.name.toLowerCase()!==spec.module.toLowerCase())return;
  installed=true;
  emit({kind:'module_loaded',path:mod.path,base:mod.base.toString(),size:mod.size});
  let attached=0;
  for(const site of spec.sites){
    try{
      if(site.rva>=mod.size)throw Error('RVA beyond module image');
      counts[site.name]=0;
      Interceptor.attach(mod.base.add(site.rva),{
        onEnter(){
          this.stage96id=null;
          try{
            if(poisoned)return;
            if(++counts[site.name]>site.max_hits){failLimit('max_hits:'+site.name);return;}
            const tid=String(this.threadId),stack=stacks[tid]||(stacks[tid]=[]);
            if(stack.length>=spec.max_depth){failLimit('max_depth');return;}
            const id=++serial,parent=stack.length?stack[stack.length-1]:null;
            this.stage96id=id;
            this.stage96thread=tid;
            stack.push(id);
            event({kind:'trace_enter',id:id,parent_id:parent,site:site.name,rva:site.rva,
              return_rva:returnRva(this.returnAddress,mod)});
          }catch(e){error('onEnter:'+String(e));}
        },
        onLeave(){
          if(this.stage96id===null || this.stage96id===undefined)return;
          try{
            const tid=String(this.threadId),stack=stacks[tid];
            if(this.stage96thread!==tid || !stack || stack[stack.length-1]!==this.stage96id){
              error('non-LIFO or changed-thread');return;
            }
            stack.pop();
            if(!poisoned)event({kind:'trace_leave',id:this.stage96id,site:site.name});
          }catch(e){error('onLeave:'+String(e));}
        }
      });
      attached++;
      emit({kind:'hook_attached',site:site.name,rva:site.rva});
    }catch(e){emit({kind:'hook_error',site:site.name,error:String(e).slice(0,150)});}
  }
  emit({kind:'ready',installed:attached,requested:spec.sites.length});
}
Process.attachModuleObserver({onAdded(mod){install(mod);}});
""".replace('SPEC_HERE', json.dumps(cfg, ensure_ascii=True))

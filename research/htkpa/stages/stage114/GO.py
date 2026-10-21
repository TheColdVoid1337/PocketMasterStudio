#!/usr/bin/env python3
"""Stage114: authentic Stage96 Frida archive + Stage113 public evidence sufficiency audit.

No Windows execution, no native capture, no audio/model access. Does not
reinterpret Stage96's prior stack ancestry audit. One private report only.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import tarfile

EXPECTED_CAPTURE_SHA = '24340c1d00f44311376729a2ba8d2813cf774997f0240c8790a7ad6cfa4e0274'
EXPECTED_DLL_SHA = 'fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
MEMBERS = frozenset('frida_capture/'+x for x in ('config.json','manifest.json','events.jsonl','HANDOFF.md'))
SITES = ('wrapper_ff40','wrapper_10e70','nam_worker_e0e0','wav_fitter_d4a0',
         'clone_f940','clone_10230','resample_be830','resample_ce00')
KINDS = {'module_loaded':1,'hook_attached':8,'ready':1,'trace_enter':10,'trace_leave':10}
EVENT_FIELDS = {
 'module_loaded':frozenset(('timestamp_ms','thread','kind','path','base','size','runtime_sha256')),
 'hook_attached':frozenset(('timestamp_ms','thread','kind','site','rva')),
 'ready':frozenset(('timestamp_ms','thread','kind','installed','requested')),
 'trace_enter':frozenset(('timestamp_ms','thread','kind','id','parent_id','return_rva','rva','site')),
 'trace_leave':frozenset(('timestamp_ms','thread','kind','id','site')),
}

def require(condition, msg):
    if not condition:raise ValueError(msg)

def digest(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as inp:
        for data in iter(lambda:inp.read(1<<20),b''):h.update(data)
    return h.hexdigest()

def load_archive(path:Path, expected_sha:str=EXPECTED_CAPTURE_SHA)->tuple[dict,dict,list[dict]]:
    require(path.is_file(),'Stage96 private tar archive missing')
    require(path.stat().st_size <= 1_000_000,'unexpectedly large Stage96 capture')
    require(digest(path)==expected_sha,'Stage96 capture SHA identity mismatch')
    with tarfile.open(path,'r:gz') as t:
        members=t.getmembers()
        require(len(members)==4 and {m.name for m in members}==MEMBERS,'Stage96 archive member allowlist mismatch')
        require(all(m.isfile() and m.size<65536 and not m.issym() and not m.islnk() for m in members),
                'Stage96 archive unsafe member')
        def read(name):
            f=t.extractfile('frida_capture/'+name)
            require(f is not None,'missing tar entry')
            return f.read()
        c=json.loads(read('config.json'))
        m=json.loads(read('manifest.json'))
        raw=read('events.jsonl').decode('utf-8')
        lines=raw.splitlines()
        require(len(lines)<=100,'Stage96 event count over cap')
        es=[json.loads(line) for line in lines]
    return c,m,es

def analyze(config:dict, manifest:dict, events:list[dict], stage113:dict)->dict:
    require(config.get('mode')=='invocation_trace','Stage96 unexpected capture mode')
    require(config.get('sha256')==EXPECTED_DLL_SHA and manifest.get('expected_sha256')==EXPECTED_DLL_SHA,
            'Stage96 original vendor module identity mismatch')
    require(tuple(x.get('name') for x in config.get('sites',[]))==SITES,'Stage96 hook inventory mismatch')
    require(config.get('max_events')==96 and config.get('max_depth')==12,'Stage96 bounded trace caps mismatch')
    require(manifest.get('mode')=='invocation_trace' and manifest.get('status')=='CAPTURED_HOOKS_ONLY',
            'Stage96 manifest status changed')
    require(manifest.get('completion_verified') is False and manifest.get('contains_audio_bytes') is False,
            'Stage96 incorrectly classified as audio or completed capture')
    require(manifest.get('hook_count')==8 and manifest.get('state',{}).get('hook_errors')==0 and
            manifest.get('state',{}).get('field_errors')==0,'Stage96 hook and field gates failed')
    counts=Counter()
    hooks=[];enters={};leaves=set();thread_set=set();have_runtime=False
    for ev in events:
        require(isinstance(ev,dict) and ev.get('kind') in EVENT_FIELDS,'unexpected Stage96 event kind')
        kind=ev['kind']; counts[kind]+=1
        require(set(ev)==EVENT_FIELDS[kind],f'Stage96 unexpected {kind} payload fields')
        if kind=='module_loaded':
            require(ev['runtime_sha256']==EXPECTED_DLL_SHA,'Stage96 actual loaded module SHA mismatch')
            have_runtime=True
        elif kind=='hook_attached':
            hooks.append(ev['site'])
        elif kind=='trace_enter':
            k=ev['id'];require(type(k) is int and k>0 and k not in enters,'invalid/duplicate invocation ID')
            enters[k]=ev;thread_set.add(ev['thread'])
        elif kind=='trace_leave':
            k=ev['id'];require(type(k) is int and k not in leaves,'duplicate leave ID')
            leaves.add(k);thread_set.add(ev['thread'])
    require(counts==KINDS, f'Stage96 exact event counts changed: {dict(counts)}')
    require(have_runtime and set(hooks)==set(SITES) and len(hooks)==8,'Stage96 hook/runtime incomplete')
    require(set(enters)==leaves,'Stage96 incomplete invocation enter/leave pairing')
    for ev in events:
        if ev['kind']=='trace_leave':
            require(ev['thread']==enters[ev['id']]['thread'] and ev['site']==enters[ev['id']]['site'],
                    'Stage96 mismatched invocation pair')
        if ev['kind']=='trace_enter' and ev['parent_id'] is not None:
            require(ev['parent_id'] in enters,'Stage96 orphan parent ID')
    require(len(thread_set)==1,'Stage96 trace crosses threads')
    require(stage113.get('stage')==113 and stage113.get('status')=='STAGE113_OFFLINE_SOURCE_INPUT_TRANSITION_SUPPORT_COMPLETED',
            'Stage113 public provenance status failure')
    require(stage113.get('source_identity_not_vendor_48k_capture') is True and
            stage113.get('vendor_resampler_model_gain_quantizer_fitter_clo_or_device_parity_verified') is False,
            'Stage113 native DI identity falsely promoted')
    require(stage113.get('candidate_f64_last_nonzero_48_index')==1344016 and
            stage113.get('candidate_f64_first_reentry_index')==1439984,
            'Stage113 accepted open candidate DI transition changed')
    return {
      'stage':114,'status':'STAGE114_EXISTING_NATIVE_TRACE_PROVENANCE_GAP_CONFIRMED',
      'source':'genuine original SHA-pinned Stage96 Frida tar + published Stage113 public evidence',
      'stage96_archive_sha_verified':True,'stage96_vendor_runtime_sha_verified':True,
      'stage96_only_invocation_events':True,
      'events_by_kind':{k:counts[k] for k in ('module_loaded','hook_attached','ready','trace_enter','trace_leave')},
      'trace_single_thread':True,'trace_enter_leave_ids_paired':True,
      'audio_sample_payload_in_stage96_capture':False,
      'vendor_input_48k_sample_buffer_address_observed':False,
      'vendor_input_48k_samples_observed':False,
      'vendor_input_resampler_parity_verified':False,
      'original_wav_44100_is_not_vendor_pre_nam_48000':True,
      'stage113_48k_is_open_resampler_candidate_only':True,
      'native_pre_nam_capture_ready':False,
      'required_next_proof':[
        'identify original PE callsite/argument containing NAM inference input rather than generic WAV/fitter output',
        'validate stage-local rate/format/frame count and buffer lifetime on original PE',
        'design SHA-guarded bounded same-invocation metadata-only native probe, operator supervised',
        'only after target identity and crash-aware preflight, plan separately approved bounded private sample capture'
      ],
      'no_vendor_execution_or_private_audio_read':True,
      'vendor_model_quantizer_gain_fitter_clo_device_parity_verified':False,
    }

def run(capture:Path,stage113_evidence:Path,out:Path)->dict:
    require(not out.exists(),'refusing to overwrite existing Stage114 private report')
    c,m,ev=load_archive(capture)
    result=analyze(c,m,ev,json.loads(stage113_evidence.read_text(encoding='utf-8')))
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as file:json.dump(result,file,indent=2,ensure_ascii=False);file.write('\n')
    return result | {'private_report':str(out)}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',type=Path,required=True)
    parser.add_argument('--stage113-evidence',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args()
    try:print(json.dumps(run(a.capture,a.stage113_evidence,a.output),indent=2))
    except (OSError,ValueError,KeyError,TypeError,tarfile.TarError,json.JSONDecodeError) as exc:
        print('[Stage114] '+str(exc),file=sys.stderr);sys.exit(2)

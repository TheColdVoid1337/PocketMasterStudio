#!/usr/bin/env python3
"""HTKPA Stage116: fail-closed preflight/audit for a ONE-SITE scalar Frida probe.

Preflight never executes the DLL, attaches Frida or launches Manager. Config
captures only direct registers at the original SHA-pinned 0xF231 callsite.
Audit reads one pre-existing user-operated Frida TAR as inert data. Raw pointers
and original event journals remain private, never in the public result.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[4]
STAGE115 = ROOT / 'research/htkpa/stages/stage115/GO.py'
EXPECTED_MODULE = '5868USB.dll'
CALLSITE = 0xF231
LIMIT = 8
BLOCK_MAX = 1024
CAPTURE_NAMES = {
    'frida_capture/config.json', 'frida_capture/manifest.json',
    'frida_capture/events.jsonl', 'frida_capture/HANDOFF.md',
}
FIELD_SPEC = (
    ('object_register', 'reg_ptr', 'rcx'),
    ('input_slot_address', 'reg_ptr', 'rdx'),
    ('output_slot_address', 'reg_ptr', 'r8'),
    ('candidate_chunk_count', 'reg_u64', 'r9'),
)
PREFLIGHT_STATUS = 'STAGE116_STATIC_PINNED_ONE_SITE_METADATA_PROBE_READY_RUNTIME_PENDING'
AUDIT_STATUS = 'STAGE116_NEW_RUN_ONE_SITE_REGISTER_METADATA_OBSERVED'


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def load_stage115():
    s = importlib.util.spec_from_file_location('htkpa116_static_stage115_gate', STAGE115)
    require(s is not None and s.loader is not None, 'original Stage115 source missing')
    m = importlib.util.module_from_spec(s)
    sys.modules[s.name] = m
    s.loader.exec_module(m)
    return m


def expected_config(original_sha: str) -> dict:
    return {
        'module': EXPECTED_MODULE,
        'sha256': original_sha,
        'image_base': '0x180000000',
        'sites': [{'name':'nam_candidate_f231_call', 'address':'0xf231',
                   'max_hits':LIMIT, 'required':True,
                   'fields':[{'name':name,'type':kind,'reg':reg,'offset':0}
                             for name,kind,reg in FIELD_SPEC]}],
    }


def normalized_config(cfg: dict) -> dict:
    """Match the existing legacy-scalar universal validation's normalized JSON."""
    site = cfg['sites'][0]
    return {'module':cfg['module'],'sha256':cfg['sha256'],
            'image_base':int(cfg['image_base'],0),
            'sites':[{'name':site['name'],'rva':CALLSITE,
                      'fields':[{'name':x['name'],'type':x['type'],
                                 'reg':x['reg'],'offset':0,'count':1}
                                for x in site['fields']],
                      'max_hits':LIMIT,'required':True}]}


def verify_config(raw: dict, original_sha: str) -> dict:
    require(type(raw) is dict and raw == expected_config(original_sha),
            'Stage116 must use only the reviewed one-site four-register config (no audio reads)')
    return normalized_config(raw)


def preflight(original_pe: bytes, raw_config: dict) -> dict:
    m = load_stage115()
    require(m.ORIGINAL_SHA256 == 'fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa',
            'original DLL SHA constant in Stage115 changed')
    stage115 = m.inspect_bytes(original_pe)
    require(stage115['indirect_call_site_rva'] == '0xF231'
            and stage115['exact_instruction_anchors_verified'] == 29
            and stage115['maximum_candidate_block_frames'] == BLOCK_MAX
            and stage115['indirect_vtable_slot_offset_bytes'] == 16,
            'Stage115 original static NAM boundary proof changed')
    normalized = verify_config(raw_config, m.ORIGINAL_SHA256)
    return {
        'stage':116, 'status':PREFLIGHT_STATUS,
        'source':'Original SHA-pinned vendor x64 PE bytes audited as inert data + exact reviewed config',
        'predecessor_stage115_29_original_opcode_anchors_verified':True,
        'one_original_callsite_rva':'0xF231',
        'exact_static_owner_rva':'0xE0E0–0xF940',
        'probe_mode':'existing_universal_legacy_scalar',
        'fields_only':['rcx pointer value','rdx slot-address value',
                       'r8 slot-address value','r9 integer register value'],
        'maximum_recorded_hit_events':LIMIT,
        'one_site_only':True,
        'any_process_memory_dereference_or_audio_data_captured':False,
        'resampling_or_model_inference_or_native_execution_performed':False,
        'frida_attached_to_live_manager':False,
        'vendor_input_48000_hz_verified':False,
        'model_vtable_target_or_input_buffer_content_verified':False,
        'runtime_visited_callsite_verified':False,
        'native_runtime_capture_required_for_next_claim':True,
        'config_has_no_audio_memory_fields':all(
            f['type'] in ('reg_ptr','reg_u64') and f['offset']==0
            for f in normalized['sites'][0]['fields']),
    }


def read_archive(archive: bytes) -> dict[str,bytes]:
    require(len(archive) <= 4_000_000, 'Frida metadata archive size exceeds bound')
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
        info = tar.getmembers()
        require(len(info)==len(CAPTURE_NAMES), 'unexpected Frida archive member count')
        require({x.name for x in info}==CAPTURE_NAMES and all(x.isfile() for x in info),
                'unexpected Frida archive members / symlinks')
        require(sum(x.size for x in info)<1_000_000 and max(x.size for x in info)<800_000,
                'unbounded Frida metadata payload')
        return {x.name:tar.extractfile(x).read() for x in info}


def is_ptr(value) -> bool:
    if not isinstance(value,str):return False
    if not re.fullmatch(r'0x[0-9a-fA-F]{1,16}',value):return False
    x=int(value,16)
    return x>0 and x<1<<64 and x%8==0


def audit_archive(archive: bytes, raw_config: dict, original_sha: str) -> dict:
    normalized=verify_config(raw_config, original_sha)
    members=read_archive(archive)
    def parse_json(name):
        return json.loads(members['frida_capture/'+name].decode('utf-8'))
    archived=parse_json('config.json')
    require(archived==normalized, 'archived Frida normalized config differs from reviewed Stage116')
    manifest=parse_json('manifest.json')
    require(manifest.get('module')==EXPECTED_MODULE
            and manifest.get('mode')=='legacy_scalar'
            and manifest.get('expected_sha256')==original_sha
            and manifest.get('contains_audio_bytes') is False
            and manifest.get('completion_verified') is False,
            'Frida manifest configuration / audio / completion boundary mismatch')
    state=manifest.get('state')
    require(type(state) is dict and state.get('runtime_verified') is True
            and state.get('ready') is True
            and state.get('field_errors')==0
            and state.get('hook_errors')==0
            and manifest.get('hook_count')==1,
            'runtime DLL SHA / hook/field gates not satisfied')
    allowed_status={'CAPTURED_HOOKS_ONLY','OPERATOR_INTERRUPTED'}
    require(manifest.get('status') in allowed_status,
            'native capture did not preserve acceptable metadata state')
    rows=[json.loads(x) for x in members['frida_capture/events.jsonl'].splitlines() if x.strip()]
    require(3<=len(rows)<=80,'unexpected Frida event volume')
    allowed_kinds={'module_loaded','hook_attached','ready','hit'}
    require(all(type(x) is dict and x.get('kind') in allowed_kinds for x in rows),
            'unexpected Frida native event kind (binary or error event)')
    modules=[x for x in rows if x['kind']=='module_loaded']
    require(len(modules)==1 and modules[0].get('runtime_sha256')==original_sha,
            'runtime-loaded module SHA absent or differs')
    base_str=modules[0].get('base')
    require(is_ptr(base_str),'invalid original runtime module ASLR base')
    base=int(base_str,16)
    hooks=[x for x in rows if x['kind']=='hook_attached']
    require(len(hooks)==1 and hooks[0].get('site')=='nam_candidate_f231_call'
            and hooks[0].get('rva')==CALLSITE,'unexpected original callsite hook')
    ready=[x for x in rows if x['kind']=='ready']
    require(len(ready)==1 and ready[0].get('installed')==1 and ready[0].get('requested')==1,
            'one-hook ready signal missing')
    hits=[x for x in rows if x['kind']=='hit']
    require(1<=len(hits)<=LIMIT and state.get('hits')==len(hits)
            and state.get('site_hits',{}).get('nam_candidate_f231_call')==len(hits)
            and state.get('valid_field_hits')==len(hits),
            'missing/extra/truncated native register hit evidence')
    counts=[]
    order=[r['kind'] for r in rows]
    require(order.index('module_loaded')<order.index('hook_attached')<order.index('ready')<order.index('hit'),
            'hook / ready / callsite event chronology inconsistent')
    for hit in hits:
        require(hit.get('site')=='nam_candidate_f231_call' and hit.get('rva')==CALLSITE,
                'hit from wrong callsite')
        pc=hit.get('pc')
        require(pc==f'0x{base+CALLSITE:x}', 'hit PC not exact ASLR + callsite')
        fields=hit.get('fields')
        require(type(fields) is dict and set(fields)=={x[0] for x in FIELD_SPEC},
                'wrong Frida metadata field list')
        regs=hit.get('registers')
        require(type(regs) is dict and set(regs)=={'rcx','rdx','r8','r9'},
                'wrong scalar universal emitted registers')
        for label,typ,reg in FIELD_SPEC:
            entry=fields[label]
            require(type(entry) is dict and set(entry)=={'value','bits'}
                    and entry['bits'] is None and type(entry['value']) is str,
                    'unexpected native register payload structure')
            require(entry['value']==regs[reg], 'field/register value disagreement')
            if typ=='reg_ptr':
                require(is_ptr(entry['value']), 'null / unaligned metadata pointer')
        rawcount=regs['r9']
        require(bool(re.fullmatch(r'0x[0-9a-fA-F]{1,16}',rawcount)),
                'expected register r9 formatted as hex pointer')
        value=int(rawcount,16)
        require(1<=value<=BLOCK_MAX,'observed chunk count outside Stage115 1..1024 static bound')
        counts.append(value)
    # Only publish statistical metadata. Original module base and runtime pointers
    # are never returned in this sanitized object.
    return {
        'stage':116,'status':AUDIT_STATUS,
        'new_runtime_metadata_hits_verified':len(hits),
        'observed_chunk_count_min':min(counts),
        'observed_chunk_count_max':max(counts),
        'one_site_callsite_executed_in_new_run':True,
        'all_registered_addresses_original_code_runtime':True,
        'pointer_addresses_observed_but_contents_not_read':True,
        'original_loaded_dll_sha_verified':True,
        'sample_rate_48000_hz_proven':False,
        'input_buffer_sample_values_or_model_byte_identity_proven':False,
        'nam_model_method_target_resolved':False,
        'stage97_exact_conversion_byteflow_proven':False,
        'vendor_resampler_or_model_numeric_parity_verified':False,
        'raw_capture_retained_private':True,
    }


def write_private(out:Path,summary:dict)->None:
    require(not out.exists(),'refusing to overwrite existing Stage116 report')
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as f:
        json.dump(summary,f,indent=2);f.write('\n')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action',choices=['preflight','audit'])
    ap.add_argument('--config',type=Path,required=True)
    ap.add_argument('--dll',type=Path,required=True)
    ap.add_argument('--capture',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    try:
        cfg=json.loads(args.config.read_text(encoding='utf-8'))
        original=args.dll.read_bytes()
        pre=preflight(original,cfg)
        if args.action=='preflight':
            require(args.capture is None,'preflight must not be given a capture')
            result=pre
        else:
            require(args.capture is not None,'audit requires one real native Frida archive')
            result=audit_archive(args.capture.read_bytes(),cfg,load_stage115().ORIGINAL_SHA256)
        write_private(args.out,result)
        # User-visible output: no private paths, pointers or origin SHA values.
        print(json.dumps(result,indent=2))
    except (ValueError,OSError,KeyError,TypeError,tarfile.TarError,json.JSONDecodeError) as exc:
        print('[Stage116] '+str(exc),file=sys.stderr)
        sys.exit(2)

if __name__=='__main__':main()

"""Stage116 pure synthetic Frida TAR/config fixtures; no real native Manager process."""
from __future__ import annotations

import copy
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
GO=ROOT/'research/htkpa/stages/stage116/GO.py'
S=importlib.util.spec_from_file_location('htkpa116_fake',GO)
M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
PE=ROOT/'tools/test_htkpa_stage115.py'
SPEC=importlib.util.spec_from_file_location('htkpa115_fixture_for_116',PE)
T=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(T)
SHA=T.M.ORIGINAL_SHA256
CONFIG=M.expected_config(SHA)
BASE=0x180000000


def event(n):
    regs={'rcx':'0x1000','rdx':'0x2000','r8':'0x3000','r9':f'0x{n:x}'}
    return {'kind':'hit','site':'nam_candidate_f231_call','rva':M.CALLSITE,
            'pc':f'0x{BASE+M.CALLSITE:x}',
            'fields':{key:{'value':regs[reg],'bits':None} for key,_,reg in M.FIELD_SPEC},
            'registers':regs,'thread':1}


def archive(*,config=None,events=None,manifest=None,extra=None):
    config=config or M.normalized_config(CONFIG)
    events=events or [
        {'kind':'module_loaded','runtime_sha256':SHA,'base':f'0x{BASE:x}','size':3_000_000},
        {'kind':'hook_attached','site':'nam_candidate_f231_call','rva':M.CALLSITE},
        {'kind':'ready','installed':1,'requested':1},event(1024),event(31),
    ]
    manifest=manifest or {'module':'5868USB.dll','mode':'legacy_scalar',
        'expected_sha256':SHA,'contains_audio_bytes':False,'completion_verified':False,
        'hook_count':1,'status':'CAPTURED_HOOKS_ONLY',
        'state':{'runtime_verified':True,'ready':True,'field_errors':0,'hook_errors':0,
                 'hits':2,'site_hits':{'nam_candidate_f231_call':2},'valid_field_hits':2}}
    blobs={
        'frida_capture/config.json':json.dumps(config).encode(),
        'frida_capture/events.jsonl':b'\n'.join(json.dumps(x).encode() for x in events)+b'\n',
        'frida_capture/manifest.json':json.dumps(manifest).encode(),
        'frida_capture/HANDOFF.md':b'SYNTHETIC FIXTURE ONLY\n',
    }
    if extra:blobs.update(extra)
    raw=io.BytesIO()
    with tarfile.open(fileobj=raw,mode='w:gz') as tar:
        for name,content in blobs.items():
            i=tarfile.TarInfo(name);i.size=len(content)
            tar.addfile(i,io.BytesIO(content))
    return raw.getvalue()


class Tests(unittest.TestCase):
    def test_expected_contract(self):
        self.assertEqual((M.CALLSITE,M.LIMIT,M.BLOCK_MAX),(0xF231,8,1024))
        self.assertEqual(len(CONFIG['sites']),1)
        self.assertEqual([x['type'] for x in CONFIG['sites'][0]['fields']],['reg_ptr']*3+['reg_u64'])
        self.assertNotIn('mode',CONFIG)

    def test_config_normalized_fits_universal_schema(self):
        normalized=M.verify_config(CONFIG,SHA)
        self.assertEqual(normalized['sites'][0]['rva'],0xF231)
        self.assertEqual(normalized['sites'][0]['max_hits'],8)
        self.assertEqual([x['count'] for x in normalized['sites'][0]['fields']],[1]*4)

    def test_reject_changed_address(self):
        x=copy.deepcopy(CONFIG);x['sites'][0]['address']='0xf230'
        with self.assertRaisesRegex(ValueError,'one-site'):M.verify_config(x,SHA)

    def test_reject_extra_second_hook(self):
        x=copy.deepcopy(CONFIG);x['sites'].append(copy.deepcopy(x['sites'][0]))
        with self.assertRaisesRegex(ValueError,'one-site'):M.verify_config(x,SHA)

    def test_reject_audio_memory_field(self):
        x=copy.deepcopy(CONFIG);x['sites'][0]['fields'][1]['type']='f32'
        with self.assertRaisesRegex(ValueError,'no audio reads'):M.verify_config(x,SHA)

    def test_reject_guard_or_unreviewed_mode(self):
        x=copy.deepcopy(CONFIG);x['mode']='guarded_metadata'
        with self.assertRaisesRegex(ValueError,'one-site'):M.verify_config(x,SHA)

    def test_reject_hit_limit_raise(self):
        x=copy.deepcopy(CONFIG);x['sites'][0]['max_hits']=100
        with self.assertRaisesRegex(ValueError,'one-site'):M.verify_config(x,SHA)

    def test_reject_dll_sha_change(self):
        x=copy.deepcopy(CONFIG);x['sha256']='a'*64
        with self.assertRaisesRegex(ValueError,'one-site'):M.verify_config(x,SHA)

    def test_real_sha_must_not_accept_fixture_bytes(self):
        with self.assertRaisesRegex(ValueError,'SHA/size'):T.M.inspect_bytes(bytes(T.fixture()))

    def test_real_static_gate_on_fake_with_explicit_fixture_substitute(self):
        # Stage116 must not silently bypass a changed original-PE gate.
        class Fake115:
            ORIGINAL_SHA256=SHA
            @staticmethod
            def inspect_bytes(data):return T.M.inspect_bytes(data,check_original_hash=False)
        with mock.patch.object(M,'load_stage115',return_value=Fake115):
            result=M.preflight(bytes(T.fixture()),CONFIG)
        self.assertEqual(result['status'],M.PREFLIGHT_STATUS)
        self.assertFalse(result['runtime_visited_callsite_verified'])
        self.assertTrue(result['config_has_no_audio_memory_fields'])

    def test_synthetic_tar_positive_no_runtime_claim_outside_fixture(self):
        x=M.audit_archive(archive(),CONFIG,SHA)
        self.assertEqual(x['new_runtime_metadata_hits_verified'],2)
        self.assertEqual((x['observed_chunk_count_min'],x['observed_chunk_count_max']),(31,1024))
        self.assertFalse(x['input_buffer_sample_values_or_model_byte_identity_proven'])

    def test_reject_binary_sidecar(self):
        with self.assertRaisesRegex(ValueError,'member count'):
            M.audit_archive(archive(extra={'frida_capture/block_0001.bin':b'\0'*8}),CONFIG,SHA)

    def test_reject_wrong_runtime_sha(self):
        x=[{'kind':'module_loaded','runtime_sha256':'0'*64,'base':f'0x{BASE:x}'},
           {'kind':'hook_attached','site':'nam_candidate_f231_call','rva':M.CALLSITE},
           {'kind':'ready','installed':1,'requested':1},event(1),event(1)]
        with self.assertRaisesRegex(ValueError,'module SHA'):
            M.audit_archive(archive(events=x),CONFIG,SHA)

    def test_reject_no_hits(self):
        x=[{'kind':'module_loaded','runtime_sha256':SHA,'base':f'0x{BASE:x}'},
           {'kind':'hook_attached','site':'nam_candidate_f231_call','rva':M.CALLSITE},
           {'kind':'ready','installed':1,'requested':1}]
        with self.assertRaisesRegex(ValueError,'missing/extra'):
            M.audit_archive(archive(events=x),CONFIG,SHA)

    def test_reject_block_over_max(self):
        x=[{'kind':'module_loaded','runtime_sha256':SHA,'base':f'0x{BASE:x}'},
           {'kind':'hook_attached','site':'nam_candidate_f231_call','rva':M.CALLSITE},
           {'kind':'ready','installed':1,'requested':1},event(1025),event(1)]
        with self.assertRaisesRegex(ValueError,'chunk count'):
            M.audit_archive(archive(events=x),CONFIG,SHA)

    def test_reject_manifest_claims_audio(self):
        x={'module':'5868USB.dll','mode':'legacy_scalar','expected_sha256':SHA,
           'contains_audio_bytes':True,'completion_verified':False,'hook_count':1,
           'status':'CAPTURED_HOOKS_ONLY',
           'state':{'runtime_verified':True,'ready':True,'field_errors':0,'hook_errors':0,
                   'hits':2,'site_hits':{'nam_candidate_f231_call':2},'valid_field_hits':2}}
        with self.assertRaisesRegex(ValueError,'audio'):
            M.audit_archive(archive(manifest=x),CONFIG,SHA)

    def test_reject_bad_field_or_register(self):
        e=event(1);e['fields']['input_slot_address']['value']='0x2222'
        x=[{'kind':'module_loaded','runtime_sha256':SHA,'base':f'0x{BASE:x}'},
           {'kind':'hook_attached','site':'nam_candidate_f231_call','rva':M.CALLSITE},
           {'kind':'ready','installed':1,'requested':1},event(1),e]
        with self.assertRaisesRegex(ValueError,'disagreement'):
            M.audit_archive(archive(events=x),CONFIG,SHA)

    def test_reject_wrong_callsite_pc(self):
        e=event(1);e['pc']='0x18000f230'
        x=[{'kind':'module_loaded','runtime_sha256':SHA,'base':f'0x{BASE:x}'},
           {'kind':'hook_attached','site':'nam_candidate_f231_call','rva':M.CALLSITE},
           {'kind':'ready','installed':1,'requested':1},event(1),e]
        with self.assertRaisesRegex(ValueError,'ASLR|PC'):
            M.audit_archive(archive(events=x),CONFIG,SHA)

    def test_report_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'report.json';f.write_text('EXISTING')
            with self.assertRaisesRegex(ValueError,'refusing to overwrite'):
                M.write_private(f,{'status':'x'})
            self.assertEqual(f.read_text(),'EXISTING')

    def test_no_native_or_audio_source(self):
        s=GO.read_text()
        for text in ('readByteArray','frida.attach','ctypes.WinDLL','subprocess.run'):
            self.assertNotIn(text,s)
        self.assertIn('runtime_visited_callsite_verified',s)

if __name__=='__main__':unittest.main()

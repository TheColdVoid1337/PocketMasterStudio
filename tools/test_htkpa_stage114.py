"""Stage114 synthetic contract tests; private Stage96 tar and audio never read here."""
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest import mock

SRC=Path(__file__).resolve().parents[1]/'research/htkpa/stages/stage114/GO.py'
s=importlib.util.spec_from_file_location('stage114_fixture',SRC)
M=importlib.util.module_from_spec(s);s.loader.exec_module(M)

def make():
    config={'mode':'invocation_trace','sha256':M.EXPECTED_DLL_SHA,'max_events':96,'max_depth':12,
            'sites':[{'name':n} for n in M.SITES]}
    manifest={'mode':'invocation_trace','expected_sha256':M.EXPECTED_DLL_SHA,'status':'CAPTURED_HOOKS_ONLY',
              'contains_audio_bytes':False,'completion_verified':False,'hook_count':8,'state':{'hook_errors':0,'field_errors':0}}
    e=[dict(timestamp_ms=1,thread=1,kind='module_loaded',path='mock',base='mock',size=1,runtime_sha256=M.EXPECTED_DLL_SHA)]
    for i,name in enumerate(M.SITES):e.append(dict(timestamp_ms=2+i,thread=1,kind='hook_attached',site=name,rva='0x1'))
    e.append(dict(timestamp_ms=10,thread=1,kind='ready',installed=8,requested=8))
    for i in range(1,11):
        e.append(dict(timestamp_ms=11+i,thread=1,kind='trace_enter',site=M.SITES[0],id=i,
                      parent_id=None,return_rva='0x0',rva='0x0'))
        e.append(dict(timestamp_ms=22+i,thread=1,kind='trace_leave',site=M.SITES[0],id=i))
    stage113={'stage':113,'status':'STAGE113_OFFLINE_SOURCE_INPUT_TRANSITION_SUPPORT_COMPLETED',
              'source_identity_not_vendor_48k_capture':True,
              'vendor_resampler_model_gain_quantizer_fitter_clo_or_device_parity_verified':False,
              'candidate_f64_last_nonzero_48_index':1344016,
              'candidate_f64_first_reentry_index':1439984}
    return config,manifest,e,stage113

class Audit(unittest.TestCase):
    def test_realistic_positive_fixture(self):
        a=M.analyze(*make());self.assertEqual(a['status'],'STAGE114_EXISTING_NATIVE_TRACE_PROVENANCE_GAP_CONFIRMED')
        self.assertFalse(a['native_pre_nam_capture_ready'])
    def test_no_audio_proof(self):
        self.assertFalse(M.analyze(*make())['audio_sample_payload_in_stage96_capture'])
    def test_banned_sample_field(self):
        c,m,e,p=make();e[11]['samples']=[1,2];self.assertRaisesRegex(ValueError,'payload',M.analyze,c,m,e,p)
    def test_changed_trace_mode(self):
        c,m,e,p=make();c['mode']='guarded_f64_binary';self.assertRaisesRegex(ValueError,'mode',M.analyze,c,m,e,p)
    def test_wrong_vendor_sha(self):
        c,m,e,p=make();c['sha256']='wrong';self.assertRaisesRegex(ValueError,'identity',M.analyze,c,m,e,p)
    def test_missing_hook(self):
        c,m,e,p=make();e.pop(1);self.assertRaisesRegex(ValueError,'counts',M.analyze,c,m,e,p)
    def test_duplicate_id(self):
        c,m,e,p=make();e[12]['id']=1;self.assertRaises(ValueError,M.analyze,c,m,e,p)
    def test_missing_leave(self):
        c,m,e,p=make();e.pop(-1);self.assertRaises(ValueError,M.analyze,c,m,e,p)
    def test_stereo_or_audio_not_claimed(self):
        c,m,e,p=make();m['contains_audio_bytes']=True;self.assertRaises(ValueError,M.analyze,c,m,e,p)
    def test_stage113_must_be_open_candidate(self):
        c,m,e,p=make();p['source_identity_not_vendor_48k_capture']=False;self.assertRaises(ValueError,M.analyze,c,m,e,p)
    def test_stage113_boundary_mismatch(self):
        c,m,e,p=make();p['candidate_f64_last_nonzero_48_index']=0;self.assertRaises(ValueError,M.analyze,c,m,e,p)
    def test_archive_strict_allowlist_and_hash(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'fixture.tar.gz'
            with tarfile.open(p,'w:gz') as z:
                raw=b'{}';entry=tarfile.TarInfo('frida_capture/evil.bin');entry.size=len(raw);z.addfile(entry,io.BytesIO(raw))
            with mock.patch.object(M,'digest',return_value='dummy'):
                self.assertRaisesRegex(ValueError,'allowlist',M.load_archive,p,'dummy')
    def test_hash_failure(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'fixture.tar.gz';p.write_bytes(b'bad')
            self.assertRaisesRegex(ValueError,'SHA identity',M.load_archive,p)
    def test_no_overwrite_preexisting_report(self):
        with tempfile.TemporaryDirectory() as td:
            q=Path(td)/'report.json';q.write_text('private preserve')
            self.assertRaisesRegex(ValueError,'overwrite',M.run,Path('none'),Path('none'),q)
            self.assertEqual(q.read_text(),'private preserve')
    def test_source_privacy(self):
        txt=SRC.read_text();self.assertNotIn('subprocess.run',txt)
        self.assertNotIn('frida.attach',txt);self.assertNotIn('shutil.rmtree',txt)

if __name__=='__main__':unittest.main()

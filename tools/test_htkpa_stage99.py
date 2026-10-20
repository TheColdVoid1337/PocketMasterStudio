"""Stage99 source-first matched raw-inference comparison offline tests.

Synthetic Node worker tests only orchestrator, NOT SonicMaster DSP numerical parity.
"""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT=Path(__file__).resolve().parents[1]/'research/htkpa/stages/stage99/GO.py'
S=importlib.util.spec_from_file_location('htkpa_stage99_test_module',SCRIPT)
M=importlib.util.module_from_spec(S)
sys.modules[S.name]=M
S.loader.exec_module(M)

class TestStage99(unittest.TestCase):
    def test_stimulus_is_stage98_exact_known_operator_hash(self):
        data=M.stimulus()
        self.assertEqual(len(data),8192*8)
        self.assertEqual(hashlib.sha256(data).hexdigest(),
          'f54ab8b3d61cd8d36fafa316f6542f18ede669febd88901b7c974b299de7745e')
        self.assertEqual(struct.unpack_from('<d',data,0)[0],0.0)
        self.assertGreater(struct.unpack_from('<d',data,64*8)[0],0.29)
        with self.assertRaisesRegex(ValueError,'48000'):
            M.stimulus(44100)

    def test_metrics_identity_and_known_offset(self):
        a=[0.25]*M.FRAMES
        z=M.metrics(a,a)
        self.assertEqual(z['max_abs_error'],0)
        self.assertEqual(z['rms_error'],0)
        self.assertTrue(z['bitwise_equal'])
        b=[0.5]*M.FRAMES
        d=M.metrics(a,b)
        self.assertAlmostEqual(d['max_abs_error'],.25)
        self.assertAlmostEqual(d['rms_error'],.25)
        self.assertAlmostEqual(d['normalized_rms_error'],1.0)
        self.assertFalse(d['bitwise_equal'])
        with self.assertRaisesRegex(ValueError,'Mismatched'):
            M.metrics([1.0],b)
        b[7]=math.nan
        with self.assertRaisesRegex(ValueError,'Nonfinite'):
            M.metrics(a,b)

    def test_source_patch_only_adds_private_callable(self):
        content='''// SonicMaster test fixture
const int _srcRate = 48000;
(List<_LayerArray>, double) _parseModel(String s) => throw 1;
Float64List _runWavenet(Float64List x, List<_LayerArray> a, double b)=>x;
'''
        patched=M.diagnostic_source(content)
        self.assertTrue(patched.startswith(content))
        self.assertIn('stage99RawInference',patched)
        self.assertIn('_runWavenet(mono, las, headScale)',patched)
        self.assertNotIn('finishFromProbeResponses',patched[len(content):])
        with self.assertRaisesRegex(ValueError,'already contains'):
            M.diagnostic_source(patched)
        with self.assertRaisesRegex(ValueError,'anchors changed'):
            M.diagnostic_source(content.replace('Float64List _runWavenet(', 'void _runWavenet('))
        with self.assertRaisesRegex(ValueError,'48000'):
            M.diagnostic_source(content.replace('48000','44100'))

    def test_sources_stage99_do_not_modify_prod(self):
        self.assertFalse('src/assets/nam_dsp_worker.js' in SCRIPT.read_text())
        worker=M.WORKER_SOURCE.read_text()
        self.assertIn("import 'clo_dsp.dart'",worker)
        self.assertIn('stage99RawInference',worker)
        self.assertFalse('finishFromProbeResponses' in worker)
        self.assertIn('js_interop',worker)
        self.assertEqual(M.MODEL_RATE,48000)

    def test_private_file_validation_and_nonfinite(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);p=d/'x.f64le'
            p.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'8192'):
                M.doubles(p)
            p.write_bytes(struct.pack('<d',math.inf)*8192)
            with self.assertRaisesRegex(ValueError,'Nonfinite'):
                M.doubles(p)
            p.write_bytes(M.stimulus())
            self.assertEqual(len(M.doubles(p)),8192)

    def test_model_mode_gate_and_slim_semantics(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.nam'
            p.write_text(json.dumps({'sample_rate':48000,'architecture':'WaveNet'}))
            self.assertEqual(M.model_mode(p),'plain_wavenet')
            base={'sample_rate':48000,'architecture':'SlimmableContainer','config':{'submodels':[
                {'max_value':.5,'model':{'architecture':'WaveNet'}},
                {'max_value':1.0,'model':{'architecture':'WaveNet'}}]}}
            p.write_text(json.dumps(base))
            self.assertEqual(M.model_mode(p),'slim_1.0_last_wavenet')
            base['config']['submodels'].reverse()
            p.write_text(json.dumps(base))
            with self.assertRaisesRegex(ValueError,'Cannot prove'):
                M.model_mode(p)
            base['sample_rate']=44100
            p.write_text(json.dumps(base))
            with self.assertRaisesRegex(ValueError,'48000'):
                M.model_mode(p)
            p.unlink()
            with self.assertRaisesRegex(ValueError,'private'):
                M.model_mode(p)

    def test_missing_dart_exits_safely_without_build_dir(self):
        with tempfile.TemporaryDirectory() as d:
            bd=Path(d)/'build'
            with mock.patch.object(M.shutil,'which',return_value=None):
                with self.assertRaisesRegex(RuntimeError,'Dart SDK executable missing'):
                    M.prepare(bd)
            self.assertFalse(bd.exists())

    @unittest.skipUnless(shutil.which('node'),'Node.js unavailable')
    def test_node_runner_accepts_synthetic_worker_only(self):
        # Explicitly FAKE worker: no real Dart inference is claimed.
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            model=p/'test.nam'
            model.write_text(json.dumps({'architecture':'WaveNet','config':{}}))
            inp=p/'test.f64le';inp.write_bytes(M.stimulus())
            fake=p/'fake_worker.js'
            fake.write_text('''globalThis.onmessage=function(evt){
              const x=evt.data.input;
              globalThis.postMessage({type:'raw',output:x},[x.buffer]);
            };''')
            out=p/'output.f64le'
            cmd=['node',str(M.NODE_RUNNER),'--model',str(model),
                '--worker-js',str(fake),'--input-f64le',str(inp),
                '--output-f64le',str(out)]
            x=subprocess.run(cmd,capture_output=True,text=True,timeout=15)
            self.assertEqual(x.returncode,0,x.stderr[:700])
            payload=json.loads(x.stdout)
            self.assertEqual(payload['status'],'SONICMASTER_DART_RAW_DIAGNOSTIC_COMPLETED')
            self.assertEqual(out.read_bytes(),inp.read_bytes())
            y=subprocess.run(cmd,capture_output=True,text=True,timeout=15)
            self.assertNotEqual(y.returncode,0)
            self.assertIn('overwrite',y.stderr)

    @unittest.skipUnless(shutil.which('node'),'Node.js unavailable')
    def test_node_rejects_wrong_input_and_missing_response(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            model=p/'test.nam';model.write_text('{"architecture":"WaveNet","config":{}}')
            inp=p/'bad';inp.write_bytes(b'bad')
            fake=p/'worker.js';fake.write_text('globalThis.onmessage=()=>{}')
            out=p/'output.f64le'
            proc=subprocess.run(['node',str(M.NODE_RUNNER),'--model',str(model),
                '--worker-js',str(fake),'--input-f64le',str(inp),
                '--output-f64le',str(out)],capture_output=True,text=True,timeout=15)
            self.assertNotEqual(proc.returncode,0)
            self.assertIn('8192',proc.stderr)
            self.assertFalse(out.exists())

    def test_compare_requires_prepared_dart_before_creating_audio(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            model=p/'x.nam';model.write_text(json.dumps({'architecture':'WaveNet','sample_rate':48000}))
            bd=p/'build';private=p/'private'
            with self.assertRaisesRegex(ValueError,'prepare'):
                M.compare(model,bd,private)
            self.assertFalse(private.exists())

if __name__=='__main__':unittest.main()

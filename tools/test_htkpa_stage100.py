"""Stage100 offline tests: fake DSP verifies orchestration, NOT numerical fidelity."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / 'research/htkpa/stages/stage100/GO.py'
SPEC = importlib.util.spec_from_file_location('htkpa_stage100_testing', SOURCE)
M = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = M
SPEC.loader.exec_module(M)


class TestStage100(unittest.TestCase):
    def test_matrix_exact(self):
        self.assertEqual(M.FRAMES, 8192)
        self.assertEqual(M.RATE, 48000)
        self.assertEqual(M.BLOCKS, (16, 64, 1024))
        self.assertEqual(dict(M.LEVELS), {'quiet': .1, 'reference': 1., 'drive': 2., 'inverted': -1.})
        self.assertEqual(M.BASELINE_BLOCK, 64)

    def test_stimulus_matches_stage99_identity(self):
        import types
        fake = types.SimpleNamespace(stimulus=lambda r: self._same_input(r), sha=lambda p: 'dummy')
        b = M.make_stimulus(fake, 1.0)
        self.assertEqual(hashlib.sha256(b).hexdigest(), M.BASELINE_INPUT_SHA)
        self.assertEqual(len(b), M.FRAMES * 8)
        for scale in (.1, 2., -1.):
            v = M.make_stimulus(fake, scale)
            self.assertEqual(len(v), len(b))
            x = struct.unpack_from('<d', b, 64 * 8)[0]
            y = struct.unpack_from('<d', v, 64 * 8)[0]
            self.assertAlmostEqual(y, x * scale, places=15)
        with self.assertRaisesRegex(ValueError, 'outside fixed'):
            M.make_stimulus(fake, 1.4)
        with self.assertRaises(ValueError):
            M.make_stimulus(fake, math.nan)

    @staticmethod
    def _same_input(rate):
        assert rate == 48000
        # exact generator matched with old Stage98 / Stage99 source
        return b''.join(struct.pack('<d',
            (0.3 if i == 64 else 0.) + 0.02 * math.sin(2 * math.pi * 997 * i / rate)
            + 0.01 * math.sin(2 * math.pi * 241 * i / rate)) for i in range(8192))

    def test_stimulus_does_not_accept_changed_sha(self):
        import types
        fake = types.SimpleNamespace(stimulus=lambda r: b'\0' * (M.FRAMES * 8), sha=lambda _: '')
        with self.assertRaisesRegex(ValueError, 'accepted SHA'):
            M.make_stimulus(fake, 1.0)

    def test_labels_are_model_hash_truncated(self):
        import types
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'x.nam'; p.write_bytes(b'example')
            fake = types.SimpleNamespace(sha=lambda f: hashlib.sha256(f.read_bytes()).hexdigest())
            self.assertEqual(M.label_for(fake, p, 'plain_wavenet'),
                             hashlib.sha256(b'example').hexdigest()[:16] + '_48k_scale_block_v1_plain_wavenet')

    def test_missing_node_fails_before_model(self):
        with mock.patch.object(M.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(ValueError, 'Node.js'):
                M.preflight(Path('/unknown.nam'))

    def test_fake_pair_sweep_metrics_and_strict_no_overwrite(self):
        # All fake outputs contain controlled known samples; this does NOT run
        # either real core or Dart DSP and MUST NOT be claimed as such.
        import types
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model = root/'private.nam'; model.write_text('{}')
            build = root/'dart_build'; build.mkdir()
            (build/'sonicmaster_raw.js').write_text('synthetic')
            worker=build/'sonicmaster_raw.js'
            native = root/'native'; native.mkdir()
            binary = native/'fake_core'; binary.write_text('synthetic binary')
            cpp = native/'htkpa_nam_probe.cpp'; cpp.write_text('synthetic source')
            cm = native/'CMakeLists.txt'; cm.write_text('synthetic cmake')
            src = root/'source'; src.mkdir()
            def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
            (build/'stage99_sonicmaster_build.json').write_text(json.dumps({
                'source_pin': 'dummy','compile_mode':'dart compile js -O2',
                'model_rate_hz':48000,'frames':8192,'resampler_used':False,
                'fitter_used':False,'worker_js_sha256':sha(worker)}))
            (native/'stage98_nam_core_build.json').write_text(json.dumps({
                'source_commit':'pinned', 'real_upstream_compile':True,
                'bridge_sha256':sha(cpp),'cmake_sha256':sha(cm),
                'binary_name':'fake_core','binary_sha256':sha(binary)}))
            def m(seq1,seq2):
                diffs=[a-b for a,b in zip(seq2,seq1)]
                return {'rms_error':math.sqrt(sum(x*x for x in diffs)/len(diffs)),
                        'max_abs_error':max(abs(x) for x in diffs),
                        'normalized_rms_error':0.0,
                        'bitwise_equal':all(a==b for a,b in zip(seq1,seq2))}
            def unpack(p):return [v[0] for v in struct.iter_unpack('<d',p.read_bytes())]
            def mock_node(args):
                inp=Path(args[args.index('--input-f64le')+1]);out=Path(args[args.index('--output-f64le')+1]);out.write_bytes(inp.read_bytes())
                return json.dumps({'status':'SONICMASTER_DART_RAW_DIAGNOSTIC_COMPLETED',
                                   'frames':8192,'input_sha256':sha(inp),'output_sha256':sha(out)})
            def mock_core(_,mod,inp,out,rate,block,prewarm,slim):
                self.assertEqual(mod, model)
                self.assertEqual(rate, 48000)
                self.assertEqual(prewarm, 'off')
                self.assertEqual(slim, 1.0)
                self.assertIn(block, M.BLOCKS)
                # Identical across all chunk sizes, 0.02 perturbation vs JS.
                vals=[v+.02 for v in unpack(inp)]
                out.write_bytes(b''.join(struct.pack('<d',v) for v in vals))
                return {'status':'NAM_CORE_UPSTREAM_INFERENCE_COMPLETED'}
            s98=types.SimpleNamespace(DEFAULT_SOURCE=src,DEFAULT_BUILD=native,
                MARKER='stage98_nam_core_build.json', PIN='pinned',HERE=native,
                verify_source=lambda _: {'verified':True},sha=sha,run=mock_core)
            s99=types.SimpleNamespace(BUILD=build,model_mode=lambda _: 'slim_1.0_last_wavenet',
                sources=lambda :{'source_pin':'dummy'},sha=sha,stimulus=self._same_input,
                load_stage98=lambda:s98,execute=mock_node,doubles=unpack,metrics=m,NODE_RUNNER=Path('/synthetic.js'))
            private = root/'private_out'
            with mock.patch.object(M, 'stage99_module', return_value=s99), mock.patch.object(M.shutil,'which',return_value='/node'):
                r = M.run(model,private,build)
                self.assertEqual(r['core_runs'],12)
                self.assertEqual(r['sonicmaster_runs'],4)
                self.assertEqual(len(r['levels']),4)
                self.assertAlmostEqual(r['levels'][0]['core_vs_sonicmaster'][0]['rms_error'],.02,places=12)
                self.assertTrue(r['levels'][0]['core_chunk_invariance']['16']['bitwise_equal'])
                target=private/'sweeps'/M.label_for(s99,model,'slim_1.0_last_wavenet')
                report=json.loads((target/'sweep_private.json').read_text())
                self.assertEqual(report['status'], 'STAGE100_OPERATOR_REAL_SWEEP_COMPLETED')
                self.assertFalse(report['vendor_dll_parity_verified'])
                self.assertEqual(json.loads((target/'RUN_STATUS.json').read_text())['status'],'COMPLETED')
                with self.assertRaisesRegex(ValueError,'already exists'):
                    M.run(model,private,build)

    def test_bad_compiled_worker_marker_fails_closed(self):
        import types
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); (p/'sonicmaster_raw.js').write_bytes(b'js')
            (p/'stage99_sonicmaster_build.json').write_text('{}')
            fake=types.SimpleNamespace(BUILD=p,model_mode=lambda _:'plain_wavenet',
                sources=lambda:{},sha=lambda _: 'expected')
            with mock.patch.object(M,'stage99_module',return_value=fake),mock.patch.object(M.shutil,'which',return_value='/node'):
                with self.assertRaisesRegex(ValueError, 'provenance mismatch'):
                    M.preflight(p/'x.nam',p)

    def test_doctor_does_not_write_files(self):
        import types
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            fake99=types.SimpleNamespace(sha=lambda _: 'a'*64)
            self.assertFalse((p/'sweeps').exists())
            self.assertEqual(M.label_for(fake99,p/'not-real.nam','plain_wavenet'),
                            'a'*16+'_48k_scale_block_v1_plain_wavenet')
            self.assertFalse((p/'sweeps').exists())

    def test_public_contract_no_dll_and_no_sonicmaster_modification(self):
        content=SOURCE.read_text()
        self.assertNotIn('5868USB.dll',content)
        self.assertNotIn('src/assets/nam_dsp_worker.js',content)
        self.assertNotIn('unlink(',content)
        self.assertNotIn('rmtree(',content)
        self.assertIn('vendor_dll_parity_verified',content)
        self.assertIn('IN_PROGRESS',content)
        self.assertIn('COMPLETED',content)

    def test_manifest_writes_only_private_samples(self):
        self.assertIn("_LOCAL_FILES/stage100",SOURCE.read_text())
        self.assertIn('refuse to overwrite',SOURCE.read_text())


if __name__ == '__main__':
    unittest.main()

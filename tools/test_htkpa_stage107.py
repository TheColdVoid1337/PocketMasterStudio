"""Stage107 synthetic tests: no real vendor WAV, no C++/Dart execution."""
from __future__ import annotations
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import wave

SRC=Path(__file__).resolve().parents[1]/'research/htkpa/stages/stage107/GO.py'
SPEC=importlib.util.spec_from_file_location('stage107_test',SRC)
M=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def pack_data(samples):
    di=b''.join(struct.pack('<d',x) for x in samples)
    open_=b''.join(struct.pack('<d',0.000204393) for _ in samples)
    pcm=b''.join(struct.pack('<hh',2,2) for _ in samples)
    return pcm,di,open_


class TestStage107(unittest.TestCase):
    def test_constant_floor_is_one_vendor_pcm16_word(self):
        wav,di,op=pack_data([0.0]*6)
        with patch.object(M,'TOTAL_FRAMES',6):
            val=M.analyze_window(wav,di,op,0,6)
        self.assertEqual(val['vendor_pcm16_unique_values_count'],1)
        self.assertEqual(val['vendor_pcm16_top_values'][0],{'sample_int16':2,'frames':6})
        self.assertEqual(val['candidate_di_nonzero_frames'],0)
        self.assertAlmostEqual(val['vendor_rms'],2/32768,places=14)
        self.assertAlmostEqual(val['vendor_std'],0,places=13)
        self.assertAlmostEqual(val['open_std'],0,places=13)

    def test_active_vs_silent_input(self):
        wav,di,op=pack_data([0,0,0.1,-0.1])
        with patch.object(M,'TOTAL_FRAMES',4):
            a=M.analyze_window(wav,di,op,0,2)
            b=M.analyze_window(wav,di,op,2,4)
        self.assertEqual(a['candidate_di_nonzero_frames'],0)
        self.assertEqual(b['candidate_di_nonzero_frames'],2)
        self.assertAlmostEqual(b['candidate_di_rms'],0.1)

    def test_fitted_gain_not_hardcoded_vendor_parameter(self):
        wav,di,op=pack_data([0.]*4)
        with patch.object(M,'TOTAL_FRAMES',4):
            r=M.analyze_window(wav,di,op,0,4)
        self.assertAlmostEqual(r['gain_fit_open_to_vendor_diagnostic_only'],(2/32768)/0.000204393)
        self.assertGreater(r['fixed_0p31_residual_rms_not_fitted'],0)
        self.assertFalse(r['proprietary_gain_parameter_proven'])

    def test_boundaries_and_sizes(self):
        wav,di,op=pack_data([0.]*3)
        with patch.object(M,'TOTAL_FRAMES',3):
            for bad in [(0,0),(-1,2),(0,4),(2,1)]:
                with self.subTest(bad=bad),self.assertRaises(ValueError):
                    M.analyze_window(wav,di,op,*bad)
            with self.assertRaises(ValueError):
                M.analyze_window(wav[:-4],di,op,0,1)

    def test_pcm_histogram_is_signed_and_counts(self):
        wav=b''.join(struct.pack('<hh',v,v) for v in (-2,2,-2,-2))
        di=b''.join(struct.pack('<d',0.) for _ in range(4))
        op=b''.join(struct.pack('<d',0.1) for _ in range(4))
        with patch.object(M,'TOTAL_FRAMES',4):
            res=M.analyze_window(wav,di,op,0,4)
        self.assertEqual(res['vendor_pcm16_unique_values_count'],2)
        self.assertEqual(res['vendor_pcm16_top_values'][0],{'sample_int16':-2,'frames':3})

    def test_reject_nonfinite(self):
        wav,di,op=pack_data([0.]*4)
        op=op[:8]+struct.pack('<d',float('nan'))+op[16:]
        with patch.object(M,'TOTAL_FRAMES',4),self.assertRaisesRegex(ValueError,'nonfinite'):
            M.analyze_window(wav,di,op,0,4)

    def test_fine_rows_count_and_continuity(self):
        with patch.object(M,'FIT_START',0),patch.object(M,'BIN',2):
            rows={f'fine_{i+1:02d}':{'start':i*2,'stop_exclusive':i*2+2,'frames':2,'silent_or_degenerate':False,'candidate_di_rms':0.1} for i in range(60)}
            self.assertEqual(len(M.get_fine_rows({'fine_20k':rows})),60)
            del rows['fine_03']
            with self.assertRaises(ValueError):M.get_fine_rows({'fine_20k':rows})

    def test_fine_rows_reject_nan_bool(self):
        with patch.object(M,'FIT_START',0),patch.object(M,'BIN',2):
            for bad in [float('nan'),True,-0.1]:
                rows={f'fine_{i+1:02d}':{'start':i*2,'stop_exclusive':i*2+2,'frames':2,'silent_or_degenerate':False,'candidate_di_rms':0.1} for i in range(60)}
                rows['fine_01']['candidate_di_rms']=bad
                with self.subTest(bad=bad),self.assertRaises(ValueError):
                    M.get_fine_rows({'fine_20k':rows})

    def _fixture(self,dir:Path):
        work=dir/'one_stage102_run'
        work.mkdir(parents=True)
        data=[0.0 if k in (12,13,14,15) else 0.01 for k in range(120)]
        wav,di,op=pack_data(data)
        inp=work/'open_source_resampled_input_48000.f64le';inp.write_bytes(di)
        out=work/'open_nam_prewarm_off.f64le';out.write_bytes(op)
        p102=work/'comparison_private.json'
        p102.write_text(json.dumps({'stage':102,'status':'SOURCE_DERIVED_DI_CANDIDATE_VS_VENDOR_OUTPUT_COMPARISON_COMPLETED',
            'frames_compared_from_start':120,'di_44100_pcm16_identical':True,
            'vendor_resampler_parity_verified':False,'resampled_input_sha256':M.sha(inp),
            'conditions':{'off':{'open_output_sha256':M.sha(out)}}}))
        fine={}
        for i in range(60):
            fine[f'fine_{i+1:02d}']={'start':2*i,'stop_exclusive':2*i+2,'frames':2,
                'silent_or_degenerate':False,'candidate_di_rms':0.0 if i in (6,7) else 0.01}
        p105=work/'stage105_error_topology_private.json'
        p105.write_text(json.dumps({'stage':105,'status':'STAGE105_OFFLINE_GAIN_ENERGY_LAG_TOPOLOGY_COMPLETED',
             'no_new_inference_or_vendordll':True,'fine_20k':fine}))
        p106=work/'stage106_metrics_audit_private.json'
        p106.write_text(json.dumps({'stage':106,'status':'STAGE106_PRIVATE_METRICS_ONLY_ENERGY_ASSOCIATION_COMPLETED',
            'source_stage105_report_sha256':M.sha(p105),
            'top_5_absolute_residual_energy_20k_bins':[{'start':2*i} for i in range(5)]}))
        with io.BytesIO() as f:
            with wave.open(f,'wb') as w:
                w.setnchannels(2);w.setsampwidth(2);w.setframerate(48000)
                w.writeframes(wav)
            wav_file=f.getvalue()
        return work,p102,p105,p106,wav_file

    def test_integrated_fake_inputs_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            work,p102,p105,p106,wav=self._fixture(root)
            with patch.object(M,'PRIVATE_ROOT',root),patch.object(M,'TOTAL_FRAMES',120),patch.object(M,'FIT_START',0),patch.object(M,'BIN',2),patch.object(M,'imported_stage102',return_value=type('S',(),{'authentic_wavs':lambda _self,zip:(b'',wav)})()):
                result=M.run(p102,root/'dummy.zip')
                self.assertEqual(result['silence_bin_count'],2)
                self.assertEqual(result['silence_starts'],[12,14])
                self.assertEqual(result['zero_input_output_floor'][0]['vendor_pcm16_unique_values_count'],1)
                self.assertTrue((work/M.OUTPUT_NAME).exists())
                with self.assertRaisesRegex(ValueError,'overwrite'):
                    M.run(p102,root/'dummy.zip')

    def test_sha_gate_rejects_modified_f64(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            work,p102,p105,p106,wav=self._fixture(root)
            p=work/'open_nam_prewarm_off.f64le'
            p.write_bytes(p.read_bytes()+b'\0')
            with patch.object(M,'PRIVATE_ROOT',root),patch.object(M,'TOTAL_FRAMES',120),patch.object(M,'FIT_START',0),patch.object(M,'BIN',2),patch.object(M,'imported_stage102',return_value=type('S',(),{'authentic_wavs':lambda _self,zip:(b'',wav)})()):
                with self.assertRaisesRegex(ValueError,'SHA256 or frame-size'):
                    M.run(p102,root/'dummy.zip')

    def test_stage106_upstream_report_sha_gate(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            work,p102,p105,p106,wav=self._fixture(root)
            p105.write_text(p105.read_text()+'\n')
            with patch.object(M,'PRIVATE_ROOT',root),patch.object(M,'TOTAL_FRAMES',120),patch.object(M,'FIT_START',0),patch.object(M,'BIN',2):
                with self.assertRaisesRegex(ValueError,'provenance'):
                    M.run(p102,root/'dummy.zip')

    def test_private_source_path_gate(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            work,p102,p105,p106,wav=self._fixture(root)
            with patch.object(M,'PRIVATE_ROOT',root/'other'):
                with self.assertRaisesRegex(ValueError,'Source must'):
                    M.run(p102,root/'dummy.zip')

    def test_no_vendor_dll_or_new_inference(self):
        code=SRC.read_text()
        self.assertNotIn('5868USB.dll',code)
        self.assertNotIn('rmtree(',code)
        self.assertNotIn('subprocess.',code)
        self.assertIn('refusing to overwrite',code)
        self.assertIn('vendor_resampler_or_model_identity_verified',code)

if __name__=='__main__': unittest.main()

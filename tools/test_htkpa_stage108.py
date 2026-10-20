"""Stage108 synthetic tests. No proprietary data or real NAM execution."""
from __future__ import annotations
from contextlib import contextmanager
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
import wave
from unittest import mock

CODE=Path(__file__).resolve().parents[1]/'research/htkpa/stages/stage108/GO.py'
SPEC=importlib.util.spec_from_file_location('stage108_synthetic',CODE)
M=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)

@contextmanager
def tiny_layout():
    with (mock.patch.object(M,'FRAMES',12), mock.patch.object(M,'FIT_START',4),
          mock.patch.object(M,'FIT_END',8), mock.patch.object(M,'WINDOW_WIDTH',2),
          mock.patch.object(M,'STAGE107_SILENT_BINS',(4,))):
        yield


def fake_bytes(vals):
    return b''.join(struct.pack('<hh',v,v) for v in vals)


def fake_f64(vals):
    return b''.join(struct.pack('<d',v) for v in vals)


class Stage108Test(unittest.TestCase):
    def test_fixed_gain_constant(self):
        self.assertEqual(M.FIXED_GAIN,.31)
        self.assertEqual(M.FRAMES,1_600_000)
    def test_nearest_even_positive_half(self):
        self.assertEqual(M.quantize_sample(0.5/32768,1.,'nearest_even'),0)
        self.assertEqual(M.quantize_sample(1.5/32768,1.,'nearest_even'),2)
    def test_nearest_away_positive_half(self):
        self.assertEqual(M.quantize_sample(0.5/32768,1.,'nearest_away'),1)
        self.assertEqual(M.quantize_sample(1.5/32768,1.,'nearest_away'),2)
    def test_nearest_away_negative_half(self):
        self.assertEqual(M.quantize_sample(-0.5/32768,1.,'nearest_away'),-1)
        self.assertEqual(M.quantize_sample(-1.5/32768,1.,'nearest_away'),-2)
    def test_truncation_toward_zero(self):
        self.assertEqual(M.quantize_sample(1.9/32768,1.,'trunc'),1)
        self.assertEqual(M.quantize_sample(-1.9/32768,1.,'trunc'),-1)
    def test_clipping_at_boundaries(self):
        self.assertEqual(M.quantize_sample(3.,1.,'nearest_even'),32767)
        self.assertEqual(M.quantize_sample(-3.,1.,'trunc'),-32768)
    def test_refuse_nonfinite_and_bad_gain(self):
        for x,g in [(float('nan'),.31),(float('inf'),.31),(.1,0),(.1,-2),(.1,float('nan'))]:
            with self.assertRaises(ValueError):M.quantize_sample(x,g,'nearest_even')
        with self.assertRaisesRegex(ValueError,'unknown'):
            M.quantize_sample(.1,.31,'unknown')
    def test_counts(self):
        c=M.empty_counts()
        M.add(c,2,2,clipped=False)
        M.add(c,-1,1,clipped=True)
        self.assertEqual((c['frames'],c['exact'],c['within_1'],c['squared_err_sum'],c['clipped_candidate']),(2,1,1,4,1))
        r=M.finalize(c)
        self.assertAlmostEqual(r['rms_difference_pcm16_lsb'],2**.5)
    def test_join_and_max(self):
        a=M.empty_counts(); b=M.empty_counts()
        M.add(a,0,3,clipped=False);M.add(b,0,-4,clipped=False)
        c=M.join_counts([a,b])
        self.assertEqual((c['max_abs_err'],c['squared_err_sum']), (4,25))
    def test_refuse_empty(self):
        with self.assertRaises(ValueError):M.finalize(M.empty_counts())
    def test_tiny_evaluate_exact_fixed_gain(self):
        with tiny_layout():
            vals=[0,1,2,3,4,5,6,7,8,9,10,11]
            x=[v/(32768*.31) for v in vals]
            r=M.evaluate(fake_bytes(vals),fake_f64(x),gains={'fixed_0p31':.31,'stage103_global_fit_control':.3098390026147448})
            result=r['aggregates']['fixed_0p31__nearest_even']
            self.assertEqual(result['fit_full_300k_1500k']['frames'],4)
            self.assertEqual(result['all_0_1600k']['exact_pcm16_fraction'],1.)
            self.assertEqual(result['seven_zero_candidate_DI_bins']['frames'],8)
            self.assertEqual(r['vendor_7x20k_zero_di_pcm16_distinct_values'],list(range(4,12)))
    def test_tiny_evaluate_wrong_vendor_channels(self):
        with tiny_layout():
            v=bytearray(fake_bytes([2]*12))
            v[2:4]=struct.pack('<h',3)
            with self.assertRaisesRegex(ValueError,'stereo'):
                M.evaluate(bytes(v),fake_f64([0.]*12),gains={'fixed_0p31':.31,'stage103_global_fit_control':.31})
    def test_tiny_evaluate_reject_malformed(self):
        with tiny_layout():
            gains={'fixed_0p31':.31,'stage103_global_fit_control':.31}
            with self.assertRaises(ValueError): M.evaluate(b'',fake_f64([0.]*12),gains=gains)
            with self.assertRaises(ValueError): M.evaluate(fake_bytes([0]*12),fake_f64([float('inf')]*12),gains=gains)
    def test_window_ranges_contiguous(self):
        w=M.window_ranges()
        self.assertEqual(len(w),8)
        self.assertEqual(w[0][1:],(0,300000))
        self.assertEqual(w[-1][1:],(1500000,1600000))
        self.assertTrue(all(a[2]==b[1] for a,b in zip(w,w[1:])))
    def test_integrated_fake_run_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            source=folder/'comparison_private.json'
            values=[2]*12
            samples=[2/(32768*.31)]*12
            f64=folder/'open_nam_prewarm_off.f64le'
            f64.write_bytes(fake_f64(samples))
            stage102={'stage':102,'status':'SOURCE_DERIVED_DI_CANDIDATE_VS_VENDOR_OUTPUT_COMPARISON_COMPLETED',
                'frames_compared_from_start':12,'di_44100_pcm16_identical':True,
                'vendor_resampler_parity_verified':False,
                'conditions':{'off':{'open_output_sha256':M.sha256(f64)}}}
            source.write_text(json.dumps(stage102))
            stage103={'stage':103,'status':'STAGE103_OFFLINE_GAIN_WINDOW_DIAGNOSTIC_COMPLETED',
                      'conditions':{'off':{'metrics':{'fit_full_300k_1500k':{'gain_open_to_manager_least_squares':0.3098390026147448}}}}}
            (folder/'stage103_gain_audit_private.json').write_text(json.dumps(stage103))
            stage107={'stage':107,'status':'STAGE107_SHA_GATED_SILENCE_FLOOR_INSPECTION_COMPLETED','silence_starts':[4]}
            (folder/'stage107_silence_floor_private.json').write_text(json.dumps(stage107))
            b=io.BytesIO()
            with wave.open(b,'wb') as w:
                w.setnchannels(2);w.setsampwidth(2);w.setframerate(48000);w.writeframes(fake_bytes(values))
            class Fake102:
                VENDOR_ARCHIVE_SHA='fake-zip-sha'
                @staticmethod
                def authentic_wavs(_):return b'fake44',b.getvalue()
            with tiny_layout(),mock.patch.object(M,'PRIVATE_ROOT',folder.parent),mock.patch.object(M,'load_stage102',return_value=Fake102):
                actual=M.run(source,folder/'bundle.zip')
                self.assertEqual(actual['status'],'STAGE108_OFFLINE_FIXED_GAIN_PCM16_OUTPUT_TEST_COMPLETED')
                self.assertEqual(actual['fixed_0p31_nearest_even']['fit_full_300k_1500k']['exact_pcm16_fraction'],1.)
                saved=folder/M.REPORT_NAME
                self.assertTrue(saved.exists())
                with self.assertRaisesRegex(ValueError,'refusing overwrite'):
                    M.run(source,folder/'bundle.zip')
                result=json.loads(saved.read_text())
                self.assertFalse(result['vendor_fitter_parity_verified'])
    def test_privacy_in_source(self):
        t=CODE.read_text()
        self.assertIn('research/_LOCAL_FILES/stage102',t)
        self.assertNotIn('shutil.rmtree',t)
        self.assertNotIn('os.unlink',t)
        self.assertIn('original_vendor_stage97_zip_sha256',t)

if __name__ == '__main__':unittest.main()

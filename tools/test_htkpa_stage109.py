"""Stage109 pure synthetic tests; no proprietary data are loaded by tests."""
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

CODE = Path(__file__).resolve().parents[1]/'research/htkpa/stages/stage109/GO.py'
spec = importlib.util.spec_from_file_location('stage109_fake',CODE)
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


def pcm(vals):
    return b''.join(struct.pack('<hh',v,v) for v in vals)


def f64(vals):
    return b''.join(struct.pack('<d',v) for v in vals)


@contextmanager
def tiny():
    with (mock.patch.object(M,'FRAMES',14),mock.patch.object(M,'FIT_START',4),
          mock.patch.object(M,'LATE_START',8),mock.patch.object(M,'FIT_STOP',12),
          mock.patch.object(M,'BIN',2),mock.patch.object(M,'SILENCE_STARTS',(6,10))):
        yield


class Stage109Tests(unittest.TestCase):
    def test_contract_values(self):
        self.assertEqual(M.GAIN,0.31)
        self.assertEqual(M.FRAMES,1_600_000)
        self.assertEqual(len(M.SILENCE_STARTS),7)
        self.assertEqual((M.FIT_START,M.LATE_START,M.FIT_STOP),(300000,1100000,1500000))

    def test_floor_near_zero(self):
        self.assertEqual(M.encode_pcm16(0.,'floor'),0)
        self.assertEqual(M.encode_pcm16(-0.2/(M.GAIN*32768),'floor'),-1)
        self.assertEqual(M.encode_pcm16(0.8/(M.GAIN*32768),'floor'),0)
        self.assertEqual(M.encode_pcm16(0.8/(M.GAIN*32768),'nearest_even'),1)

    def test_floor_vs_trunc_negative(self):
        x = -1.8/(M.GAIN*32768)
        self.assertEqual(M.encode_pcm16(x,'floor'),-2)
        self.assertEqual(M.encode_pcm16(x,'nearest_even'),-2)

    def test_floor_clipping(self):
        self.assertEqual(M.encode_pcm16(100.,'floor'),32767)
        self.assertEqual(M.encode_pcm16(-100.,'floor'),-32768)

    def test_invalid_quantizer_and_nonfinite(self):
        with self.assertRaises(ValueError): M.encode_pcm16(0.1,'trunc')
        with self.assertRaises(ValueError): M.encode_pcm16(float('nan'),'floor')
        with self.assertRaises(ValueError): M.encode_pcm16(float('inf'),'nearest_even')

    def test_count_summary(self):
        a=M.empty()
        M.add(a,4,4)
        M.add(a,6,4)
        M.add(a,1,4)
        self.assertEqual(a['frames'],3)
        s=M.summary(a)
        self.assertEqual(s['exact_pcm16_count'],1)
        self.assertEqual(s['positive_error_frame_count'],1)
        self.assertEqual(s['negative_error_frame_count'],1)
        self.assertEqual(s['abs_error_gt_1_lsb_frames'],2)
        self.assertAlmostEqual(s['rms_error_pcm16_lsb'],(13/3)**0.5)

    def test_empty_summary(self):
        with self.assertRaisesRegex(ValueError,'empty'): M.summary(M.empty())

    def test_count_histogram_other(self):
        a=M.empty()
        M.add(a,10,0)
        M.add(a,-10,0)
        s=M.summary(a)
        self.assertEqual(s['integer_error_histogram_bounded'], {'<-3':1,'>3':1})

    def test_fake_compare_filters_silent_bins(self):
        with tiny():
            values=[0,0,0,0,5,-3,2,2,4,-5,2,2,0,0]
            q=[v+0.2 for v in values]
            # Nearest differs for selected active samples but floor is exact.
            q[5] = -2.2
            q[8] = 4.8
            r=M.compare(pcm(values),f64([v/(M.GAIN*32768) for v in q]))
            early=r['groups']['early_active']['floor']
            late=r['groups']['late_active']['floor']
            self.assertEqual((early['frames'],late['frames']),(2,2))
            self.assertEqual(early['exact_pcm16_count'],2)
            self.assertEqual(late['exact_pcm16_count'],2)
            self.assertEqual(late['exact_pcm16_fraction'],1.)
            self.assertEqual(r['late_floor_mismatch_frames'],0)
            self.assertEqual(len(r['fine_nonzero_di_20k_bins']),2)
            self.assertTrue(r['no_nam_or_vendor_inference_or_dsp_rerun'])

    def test_fake_compare_localizes_late_error(self):
        with tiny():
            vals=[0,0,0,0,1,1,2,2,3,-3,2,2,0,0]
            q=[v+0.2 for v in vals]
            q[8]=6.2 # mismatches vendor 3 by +3
            r=M.compare(pcm(vals),f64([v/(M.GAIN*32768) for v in q]))
            self.assertEqual(r['late_floor_mismatch_frames'],1)
            self.assertEqual((r['late_floor_first_mismatch_index'],r['late_floor_last_mismatch_index']),(8,8))
            self.assertEqual(r['top_late_floor_mismatch_bins'][0]['start'],8)
            self.assertEqual(r['top_late_floor_mismatch_bins'][0]['mismatch_frames'],1)

    def test_malformed_lengths(self):
        with self.assertRaisesRegex(ValueError,'length'): M.compare(b'',b'')

    def test_mismatching_vendor_channels(self):
        with tiny():
            v=bytearray(pcm([0]*14))
            v[4*4+2:4*4+4]=struct.pack('<h',2)
            with self.assertRaisesRegex(ValueError,'stereo'):M.compare(bytes(v),f64([0.]*14))

    def test_nonfinite_open_sample(self):
        with tiny():
            vals=[0]*14
            x=[0.]*14
            x[5]=float('nan')
            with self.assertRaisesRegex(ValueError,'nonfinite'): M.compare(pcm(vals),f64(x))

    def test_integrated_run_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            work=Path(td)
            s102p=work/'comparison_private.json'
            values=[2]*14
            values[9]=-2
            xs=[(v+0.2)/(M.GAIN*32768) for v in values]
            x=work/'open_nam_prewarm_off.f64le'
            x.write_bytes(f64(xs))
            s102={'stage':102,'status':'SOURCE_DERIVED_DI_CANDIDATE_VS_VENDOR_OUTPUT_COMPARISON_COMPLETED',
                  'frames_compared_from_start':14,'vendor_resampler_parity_verified':False,
                  'conditions':{'off':{'open_output_sha256':M.sha256(x)}}}
            s102p.write_text(json.dumps(s102))
            s107p=work/'stage107_silence_floor_private.json'
            s107p.write_text(json.dumps({'stage':107,'status':'STAGE107_SHA_GATED_SILENCE_FLOOR_INSPECTION_COMPLETED','silence_starts':[6,10]}))
            s108p=work/'stage108_fixed_gain_pcm16_private.json'
            baseline={'quiet_early_300k_1100k':{'frames':4,'exact_pcm16_count':4},
                      'loud_late_1100k_1500k':{'frames':4,'exact_pcm16_count':4}}
            s108={'stage':108,'status':'STAGE108_OFFLINE_FIXED_GAIN_PCM16_OUTPUT_TEST_COMPLETED',
                  'source_stage102_report_sha256':M.sha256(s102p),
                  'original_vendor_stage97_zip_sha256':'fixture-stage97-sha',
                  'open_source_cpp_sha256':M.sha256(x),
                  'analysis':{'aggregates':{'fixed_0p31__nearest_even':baseline}}}
            s108p.write_text(json.dumps(s108))
            wav=io.BytesIO()
            with wave.open(wav,'wb') as w:
                w.setnchannels(2);w.setsampwidth(2);w.setframerate(48000);w.writeframes(pcm(values))
            class Fake102:
                VENDOR_ARCHIVE_SHA='fixture-stage97-sha'
                @staticmethod
                def authentic_wavs(_):return b'original44',wav.getvalue()
            with tiny(),mock.patch.object(M,'PRIVATE_ROOT',work.parent),mock.patch.object(M,'load_stage102',return_value=Fake102):
                o=M.run(s108p,work/'source.zip')
                self.assertEqual(o['status'],'STAGE109_OFFLINE_FIXED_FLOOR_RESIDUAL_TOPOLOGY_COMPLETED')
                self.assertEqual(o['active_floor_vs_nearest_even']['late_active']['floor']['exact_pcm16_fraction'],1.)
                self.assertTrue((work/M.REPORT).exists())
                with self.assertRaisesRegex(ValueError,'refusing to overwrite'):M.run(s108p,work/'source.zip')

    def test_source_privacy_guards(self):
        s=CODE.read_text(encoding='utf-8')
        self.assertIn('research/_LOCAL_FILES/stage102',s)
        self.assertNotIn('shutil.rmtree',s)
        self.assertNotIn('subprocess.run',s)
        self.assertIn('refusing to overwrite',s)

if __name__=='__main__': unittest.main()

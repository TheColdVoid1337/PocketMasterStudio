"""Stage113 synthetic tests; never load original vendor audio/model or private reports."""
from __future__ import annotations
from fractions import Fraction
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
import wave
from unittest import mock
from zipfile import ZipFile

CODE=Path(__file__).resolve().parents[1]/'research/htkpa/stages/stage113/GO.py'
sp=importlib.util.spec_from_file_location('stage113_synthetic',CODE)
M=importlib.util.module_from_spec(sp);sp.loader.exec_module(M)

def pcm(a):return b''.join(struct.pack('<hh',v,v) for v in a)
def f64(a):return b''.join(struct.pack('<d',v) for v in a)

class Cases(unittest.TestCase):
    def test_time_mapping_rational(self):
        self.assertEqual(M.source_frame_time_48(147),Fraction(160,1))
        self.assertEqual(M.source_frame_time_48(1),Fraction(160,147))
    def test_negative_time_rejected(self):
        with self.assertRaisesRegex(ValueError,'negative'):M.source_frame_time_48(-1)
    def test_source_bounds_cover_interval(self):
        self.assertEqual(M.source_bounds_for_48_window(0,160),(0,147))
        self.assertEqual(M.source_bounds_for_48_window(1,2),(0,2))
    def test_source_bounds_invalid(self):
        with self.assertRaisesRegex(ValueError,'window'):M.source_bounds_for_48_window(10,1)
    def test_pcm44_scans_first_last(self):
        a=M.scan_pcm44(pcm([0,3,0,-2,0]),0,5)
        self.assertEqual((a['nonzero_frames'],a['first_nonzero_index'],a['last_nonzero_index']),(2,1,3))
    def test_pcm44_zero_window(self):
        a=M.scan_pcm44(pcm([0,0,0]),0,3)
        self.assertEqual((a['nonzero_frames'],a['first_nonzero_index'],a['last_nonzero_index']),(0,None,None))
    def test_pcm44_channel_rejection(self):
        a=bytearray(pcm([1,2]));struct.pack_into('<h',a,2,4)
        with self.assertRaisesRegex(ValueError,'stereo'):M.scan_pcm44(bytes(a),0,2)
    def test_pcm44_shape_rejection(self):
        with self.assertRaises(ValueError):M.scan_pcm44(b'a',0,1)
    def test_candidate_scan_exact_signed_zero(self):
        a=M.scan_f64(f64([0.0,-0.0,1e-11,0.0,-2e-15]),0,5)
        self.assertEqual((a['nonzero_frames'],a['first_nonzero_index'],a['last_nonzero_index']),(2,2,4))
    def test_candidate_nonfinite_rejection(self):
        for invalid in (float('nan'),float('inf'),-float('inf')):
            with self.assertRaisesRegex(ValueError,'nonfinite'):M.scan_f64(f64([0.,invalid]),0,2)
    def test_candidate_shape_rejection(self):
        with self.assertRaises(ValueError):M.scan_f64(f64([0.]),0,2)
    def test_authentic_input_wav_structure(self):
        b=io.BytesIO()
        with wave.open(b,'wb') as w:
            w.setnchannels(2);w.setsampwidth(2);w.setframerate(44100);w.writeframes(pcm([0,1,-1,0]))
        with tempfile.TemporaryDirectory() as td:
            z=Path(td)/'original.zip'
            with ZipFile(z,'w') as archive:
                for name in ('clo/','logs/','wavs/','clo/cloFile.clo','logs/tone_import.log','wavs/outputFile.wav'):
                    archive.writestr(name,b'')
                archive.writestr('wavs/nam_input_wav.wav',b.getvalue())
            with mock.patch.object(M,'FRAMES_44',4):
                self.assertEqual(M.input44_wave(z),pcm([0,1,-1,0]))
    def test_authentic_input_wav_allowlist_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'bad.zip'
            with ZipFile(p,'w') as z:z.writestr('wavs/nam_input_wav.wav','not a real WAV')
            with self.assertRaisesRegex(ValueError,'allowlist'):M.input44_wave(p)
    def test_synthetic_transition_mapping_and_bridge(self):
        # Tiny, purely synthetic source and candidate; no fitted or proprietary DSP.
        original=[0]*250;original[22:61]=[1]*39;original[151:245]=[2]*94
        candidate=[0.]*320;candidate[24:65]=[.1]*41;candidate[162:240]=[.2]*78
        prior={'stage111':{'candidate_di_last_nonzero_index':64,'primary_gt1_after_di_end':408},
               'stage112':{'candidate_di_last_nonzero_index':64,'gt1_primary_post_DI_zero':408,'gt1_secondary_active_200':32}}
        # Map 44.1 and 48 rate here naturally; predeclare synthetic search ranges.
        with mock.patch.multiple(M,FRAMES_44=250,FRAMES_48=320,
                PRIMARY_SEARCH=(20,100),REENTRY_SEARCH=(130,260),
                SECONDARY_WINDOWS=((200,220),(220,240)),
                EXPECTED_SOURCE_LAST=60,EXPECTED_CANDIDATE_LAST=64,
                EXPECTED_SOURCE_REENTRY=151,EXPECTED_CANDIDATE_REENTRY=162,
                EXPECTED_SECONDARY_NONZERO_DI=20):
            r=M.analyze(pcm(original),f64(candidate),prior)
            self.assertEqual(r['status'],'STAGE113_OFFLINE_SOURCE_INPUT_TRANSITION_SUPPORT_COMPLETED')
            self.assertEqual(r['original_source_exact_zero_bridge_frames_44'],90)
            self.assertEqual(r['candidate_exact_zero_bridge_frames_48'],97)
            self.assertEqual(len(r['secondary_three_active_input_windows']),2)
    def test_change_in_expected_boundary_is_not_silently_accepted(self):
        source=[0]*250;source[22:61]=[1]*39;source[151:220]=[1]*69
        cand=[0.]*320;cand[24:65]=[.1]*41;cand[162:240]=[.1]*78
        prior={'stage111':{'candidate_di_last_nonzero_index':64,'primary_gt1_after_di_end':408},
               'stage112':{'candidate_di_last_nonzero_index':64,'gt1_primary_post_DI_zero':408,'gt1_secondary_active_200':32}}
        with mock.patch.multiple(M,FRAMES_44=250,FRAMES_48=320,PRIMARY_SEARCH=(20,100),REENTRY_SEARCH=(130,260),
                SECONDARY_WINDOWS=((200,220),),EXPECTED_SOURCE_LAST=61,EXPECTED_CANDIDATE_LAST=64,
                EXPECTED_SOURCE_REENTRY=151,EXPECTED_CANDIDATE_REENTRY=162,EXPECTED_SECONDARY_NONZERO_DI=20):
            with self.assertRaisesRegex(ValueError,'anchors'):M.analyze(pcm(source),f64(cand),prior)
    def test_integrated_private_report_guard(self):
        # Existence check is before authentication, so previous results cannot be overwritten.
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'stage113.json';p.write_text('unchanged')
            with self.assertRaisesRegex(ValueError,'overwrite'):
                M.run(Path('missing.zip'),Path('missing97.zip'),Path('110.json'),Path('111.json'),Path('112.json'),p)
            self.assertEqual(p.read_text(),'unchanged')
    def test_source_scope_never_runs_external_inference(self):
        s=CODE.read_text()
        self.assertNotIn('subprocess.run(',s)
        self.assertNotIn('shutil.rmtree(',s)
        self.assertIn("output.open('x'",s)
        self.assertIn('vendor_resampler_model_gain_quantizer_fitter_clo_or_device_parity_verified',s)

if __name__=='__main__': unittest.main()

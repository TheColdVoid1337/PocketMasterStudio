"""Stage102 offline orchestration/math tests; no vendor DLL and no real model inference."""
from __future__ import annotations
import importlib.util
import io
from pathlib import Path
import math
import struct
import tempfile
import unittest
import wave
from unittest import mock

PATH=Path(__file__).resolve().parents[1]/'research/htkpa/stages/stage102/GO.py'
S=importlib.util.spec_from_file_location('stage102_test',PATH)
M=importlib.util.module_from_spec(S);S.loader.exec_module(M)


class Stage102Test(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(M.FRAMES,1600000)
        self.assertEqual(M.FIT_START,300000)
        self.assertEqual(M.FIT_END,1500000)
        self.assertEqual(M.ORIGINAL_FRAMES,3360000)

    def test_equal_metrics(self):
        m=M.metrics([0.1,-0.3,0.5],[0.1,-0.3,0.5])
        self.assertEqual(m['rms_error'],0.0)
        self.assertEqual(m['max_abs_error'],0.0)
        self.assertEqual(m['normalized_rms_error'],0.0)
        self.assertFalse(m['gain_fitted'])
        self.assertFalse(m['lag_aligned'])

    def test_known_metrics(self):
        m=M.metrics([1.,-1.],[0.,0.])
        self.assertEqual(m['rms_error'],1.)
        self.assertEqual(m['max_abs_error'],1.)
        self.assertIsNone(m['zero_lag_cosine_similarity'])

    def test_reject_malformed(self):
        for x,y in [([],[]),([1],[2,3]),([math.nan],[0.1]),([0.1],[math.inf])]:
            with self.assertRaises(ValueError):M.metrics(x,y)

    def test_vendor_pcm16_conversion(self):
        vals=[(32767,32767),(-32768,-32768),(0,0)]
        raw=b''.join(struct.pack('<hh',*v) for v in vals)
        buff=io.BytesIO()
        with wave.open(buff,'wb') as w:
            w.setnchannels(2);w.setsampwidth(2);w.setframerate(48000);w.writeframes(raw)
        out=M.wav_first_n_vendor_samples(buff.getvalue(),3)
        self.assertEqual(out,[32767/32768,-1,0])

    def test_private_confinement_and_no_vendor_code(self):
        t=PATH.read_text()
        self.assertIn('research/_LOCAL_FILES/stage102',t)
        self.assertNotIn('5868USB.dll',t)
        self.assertNotIn('rmtree(',t)
        self.assertNotIn('unlink(',t)
        self.assertIn('vendor_resampler_parity_verified',t)

    def test_source_anchor(self):
        self.assertIn('SOURCE_ANCHOR',PATH.read_text())
        self.assertIn('stage102OpenSourceDiTo48', PATH.read_text())

if __name__=='__main__':unittest.main()

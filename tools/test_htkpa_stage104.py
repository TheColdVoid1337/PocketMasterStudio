"""Stage104 synthetic bitwise f64 localization tests; no vendor files or inference."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import struct
import unittest
import tempfile
import json
from unittest import mock

SOURCE=Path(__file__).resolve().parents[1]/'research/htkpa/stages/stage104/GO.py'
spec=importlib.util.spec_from_file_location('stage104',SOURCE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def pack(samples):return b''.join(struct.pack('<d',x) for x in samples)

class Stage104Tests(unittest.TestCase):
    def test_equal(self):
        x=pack([1,-.5,3])
        z=m.localized_diff(x,x,0,3)
        self.assertTrue(z['bitwise_equal'])
        self.assertEqual(z['different_f64_word_count'],0)
        self.assertEqual(z['rms_difference'],0)
        self.assertIsNone(z['first_different_sample_absolute'])

    def test_one_difference(self):
        z=m.localized_diff(pack([1,2,3]),pack([1,4,3]),0,3)
        self.assertEqual(z['different_f64_word_count'],1)
        self.assertEqual(z['first_different_sample_absolute'],1)
        self.assertEqual(z['last_different_sample_absolute'],1)
        self.assertAlmostEqual(z['rms_difference'],(4/3)**.5)
        self.assertEqual(z['max_abs_difference'],2.)

    def test_absolute_indices(self):
        z=m.localized_diff(pack([1,2,3,4,5]),pack([1,2,6,4,8]),2,5)
        self.assertEqual(z['first_different_sample_absolute'],2)
        self.assertEqual(z['last_different_sample_absolute'],4)
        self.assertEqual(z['frames'],3)

    def test_bitwise_signed_zero(self):
        z=m.localized_diff(pack([0.0]),pack([-0.0]),0,1)
        self.assertEqual(z['different_f64_word_count'],1)
        self.assertEqual(z['numerically_equal_but_bitwise_different_count'],1)
        self.assertEqual(z['rms_difference'],0.)

    def test_bitwise_nan_rejected(self):
        with self.assertRaisesRegex(ValueError,'nonfinite'):
            m.localized_diff(pack([float('nan')]),pack([1]),0,1)

    def test_reject_bad_data(self):
        for a,b,left,right in [(b'',b'',0,1),(pack([1]),pack([2,3]),0,1),(pack([1]),pack([1]),0,0),(pack([1]),pack([1]),-1,1),(pack([1]),pack([1]),0,2),(b'123',b'123',0,1)]:
            with self.assertRaises(ValueError):m.localized_diff(a,b,left,right)

    def test_windows_coverage(self):
        self.assertEqual(m.WINDOWS['initial_0_300k'],(0,300000))
        self.assertEqual(m.WINDOWS['tail_1500k_1600k'],(1500000,1600000))
        blocks=[w for k,w in m.WINDOWS.items() if k.startswith('fit_block_')]
        self.assertEqual(len(blocks),6)
        self.assertEqual(blocks[0],(300000,500000))
        self.assertEqual(blocks[-1],(1300000,1500000))
        self.assertEqual(sum(b-a for a,b in blocks),1200000)

    def _fake_report_files(self, root):
        root.mkdir(parents=True,exist_ok=True)
        x=pack([0.5]*16)
        y=pack([0.5]*4 + [0.6]*12)
        off=root/'open_nam_prewarm_off.f64le'
        on=root/'open_nam_prewarm_on.f64le'
        off.write_bytes(x);on.write_bytes(y)
        sha_off=m.sha256(off);sha_on=m.sha256(on)
        st102={'stage':102,'status':'SOURCE_DERIVED_DI_CANDIDATE_VS_VENDOR_OUTPUT_COMPARISON_COMPLETED',
               'frames_compared_from_start':16,'di_44100_pcm16_identical':True,
               'vendor_resampler_parity_verified':False,
               'conditions':{'off':{'open_output_sha256':sha_off},'on':{'open_output_sha256':sha_on}}}
        st103={'stage':103,'status':'STAGE103_OFFLINE_GAIN_WINDOW_DIAGNOSTIC_COMPLETED',
               'prewarm_output_bitwise_equal':False,
               'conditions':{'off':{'open_output_sha256':sha_off},'on':{'open_output_sha256':sha_on}}}
        report=root/'comparison_private.json'
        report.write_text(json.dumps(st102))
        (root/'stage103_gain_audit_private.json').write_text(json.dumps(st103))
        return report

    def test_integration_private_output_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp)/'private_run'
            report=self._fake_report_files(work)
            windows={'initial_0_300k':(0,4),'fit_block_01_4_12':(4,12),
                     'tail_1500k_1600k':(12,16),'fit_full_300k_1500k':(4,12),
                     'all_0_1600k':(0,16)}
            with mock.patch.object(m,'PRIVATE_ROOT',Path(tmp)),mock.patch.object(m,'BYTES',16*8),mock.patch.object(m,'FRAMES',16),mock.patch.object(m,'WINDOWS',windows):
                result=m.run(report)
                self.assertEqual(result['status'],'STAGE104_OFFLINE_PREWARM_DIFFERENCE_LOCALIZED')
                self.assertEqual(result['overall']['different_f64_word_count'],12)
                self.assertEqual(result['overall']['first_different_sample_absolute'],4)
                self.assertEqual(result['overall']['last_different_sample_absolute'],15)
                self.assertTrue(result['first_300k']['bitwise_equal'])
                self.assertEqual(result['fit_subwindows_differing'],['fit_block_01_4_12'])
                with self.assertRaisesRegex(ValueError,'overwrite'):
                    m.run(report)

    def test_integration_refuses_untrusted_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'private_run';report=self._fake_report_files(root)
            (root/'open_nam_prewarm_on.f64le').write_bytes(pack([0.5]*16))
            with mock.patch.object(m,'PRIVATE_ROOT',Path(tmp)),mock.patch.object(m,'BYTES',16*8),mock.patch.object(m,'FRAMES',16):
                with self.assertRaisesRegex(ValueError,'SHA mismatch'):
                    m.run(report)

    def test_integration_refuses_outside_private_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'private_run';report=self._fake_report_files(root)
            with mock.patch.object(m,'PRIVATE_ROOT',Path(tmp)/'not_this_root'):
                with self.assertRaisesRegex(ValueError,'private Stage102'):
                    m.run(report)

    def test_private_path_and_no_execution(self):
        s=SOURCE.read_text(encoding='utf-8')
        self.assertIn('research/_LOCAL_FILES/stage102',s)
        self.assertIn('stage104_prewarm_diff_private.json',s)
        self.assertNotIn('subprocess',s)
        self.assertNotIn('rmtree(',s)
        self.assertNotIn('unlink(',s)

if __name__=='__main__':unittest.main()

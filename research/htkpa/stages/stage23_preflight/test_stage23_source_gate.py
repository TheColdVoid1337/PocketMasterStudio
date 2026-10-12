import hashlib
import io
import sys
import tempfile
import unittest
import wave
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import stage23_source_gate as s

class Stage23SourceGateSyntheticTests(unittest.TestCase):
    def test_member_uniqueness_and_case(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'a.zip'
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('Sonicake Manager/assets/5868USB.dll', b'fixture')
            with zipfile.ZipFile(p) as z:
                self.assertEqual(s.matching_member(z, '/5868USB.dll'), 'Sonicake Manager/assets/5868USB.dll')
                self.assertRaises(ValueError, s.matching_member, z, 'clo/cloFile.clo')
            self.assertEqual(s.validate_zip(p)['zip_crc'], 'PASS')

    def test_duplicate_zip_member_suffix_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'b.zip'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('a/assets/5868USB.dll', b'a')
                z.writestr('b/assets/5868USB.dll', b'b')
            with zipfile.ZipFile(p) as z:
                self.assertRaises(ValueError, s.matching_member, z, '/5868USB.dll')

    @staticmethod
    def fake_wav(stereo_identical=True):
        raw=io.BytesIO()
        with wave.open(raw, 'wb') as f:
            f.setnchannels(2);f.setsampwidth(2);f.setframerate(44100)
            f.writeframes(b'\x01\x00'+(b'\x01\x00' if stereo_identical else b'\x02\x00'))
        return raw.getvalue()

    def test_wav_metadata_not_native_fs(self):
        x=s.wav_metadata(self.fake_wav())
        self.assertTrue(x['stereo_channels_byte_identical'])
        self.assertEqual(x['sample_rate_hz_in_file'], 44100)
        self.assertEqual(x['native_context_fs'], 'NOT_PROVEN')
        self.assertFalse(s.wav_metadata(self.fake_wav(False))['stereo_channels_byte_identical'])

    def test_context_and_call_index_regex(self):
        line='  1800bede4: call   1800bdbe0 <symbol>'
        m=s.INSTR_RE.match(line)
        self.assertEqual(int(m.group(1),16), 0x1800BEDE4)
        self.assertEqual(s.CALL_RE.search(line).group(1).lower(),'1800bdbe0')
        self.assertEqual(s.FIELD_RE.findall('mov rax,QWORD PTR [rcx+0x243e8]'), ['243e8'])

    def test_hash_and_handoff_pins(self):
        self.assertEqual(s.sha256_bytes(b'abc'),hashlib.sha256(b'abc').hexdigest())
        self.assertEqual(len(s.DLL_SHA),64)
        self.assertEqual(s.PINNED['fit_call'], 0x1800BEDE4)
        self.assertLess(s.PINNED['fit_call'], s.PINNED['later_iir_call'])

if __name__ == '__main__':
    unittest.main(verbosity=2)

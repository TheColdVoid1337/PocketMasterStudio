"""Stage97 deterministic tests. Does not require vendor DLL, CLO, or Frida."""
import importlib.util
import io
import struct
import sys
import unittest
import wave
from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / 'research' / 'htkpa'
          / 'stages' / 'stage97' / 'audit_clo_bundle.py')
SPEC = importlib.util.spec_from_file_location('stage97_audit', SOURCE)
AUDIT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)


def clo_fixture():
    buf = bytearray(8840)
    buf[:4] = b'VTSI'
    struct.pack_into('<I', buf, 4, 8840)
    struct.pack_into('<I', buf, 20, 8704)
    struct.pack_into('<III', buf, 124, 128, 128, 2048)
    struct.pack_into('<f', buf, 648, 0.5)
    struct.pack_into('>H', buf, 8, AUDIT.crc16_modbus(buf[12:]))
    return buf


def log_fixture(crc):
    tokens = (
        'start import,',
        'native namConvertCloData returned 8840',
        'process=3281, total=3281, percent=100',
        'process=-1, total=-1, percent=100',
        'native convert callback state=3',
        'convert finished, success=true, nativeDataSize=8840',
        'write clo file path=private/omitted exists=true, size=8840',
        'calculatedCrc={0}, fileCrc={0}'.format(crc),
        '[TcHelper.checkTcFile] check success',
        'low-model conversion success, resultLength=2696',
        'received tcImportExport ack, status=0',
        'wait importTC result=true',
    )
    return ('\n'.join('[2026-10-19T02:53:{:02d}.000000] {}'.format(i, token)
                      for i, token in enumerate(tokens)) + '\n').encode()


class Stage97AuditorTests(unittest.TestCase):
    def test_crc_standard_vector(self):
        self.assertEqual(AUDIT.crc16_modbus(b'123456789'), 0x4B37)

    def test_clo_valid_and_low_conversion(self):
        original = bytes(clo_fixture())
        result = AUDIT.inspect_clo(original)
        self.assertEqual(result['size'], 8840)
        self.assertEqual(result['crc_stored_be'], result['crc_calculated'])
        self.assertEqual(result['low_model_bytes'], 2696)
        self.assertEqual(result['fir_taps'], 2048)
        self.assertTrue(result['finite_coefficients'])
        self.assertEqual(original, bytes(clo_fixture()))

    def test_reject_mutated_checksum(self):
        invalid = clo_fixture()
        invalid[800] ^= 1
        with self.assertRaisesRegex(ValueError, 'CRC16'):
            AUDIT.inspect_clo(invalid)

    def test_reject_wrong_declared_fir_shape(self):
        invalid = clo_fixture()
        struct.pack_into('<I', invalid, 132, 512)
        struct.pack_into('>H', invalid, 8, AUDIT.crc16_modbus(invalid[12:]))
        with self.assertRaisesRegex(ValueError, 'FIR layout'):
            AUDIT.inspect_clo(invalid)

    def test_reject_nonfinite_fir_even_with_valid_crc(self):
        invalid = clo_fixture()
        struct.pack_into('<f', invalid, 648, float('nan'))
        struct.pack_into('>H', invalid, 8, AUDIT.crc16_modbus(invalid[12:]))
        with self.assertRaisesRegex(ValueError, 'non-finite'):
            AUDIT.inspect_clo(invalid)

    def test_manager_log_order_crc_ack_and_failure(self):
        parsed = AUDIT.inspect_clo(clo_fixture())
        prefix = '2026-10-19T02:53:'
        good = log_fixture(parsed['header_crc_raw_as_le'])
        result = AUDIT.inspect_log(good, prefix, parsed)
        self.assertTrue(result['evidence_flags']['device_ack'])
        with self.assertRaisesRegex(ValueError, 'device_ack'):
            AUDIT.inspect_log(good.replace(b'received tcImportExport ack, status=0',
                                           b'received tcImportExport ack, status=1'),
                              prefix, parsed)
        with self.assertRaisesRegex(ValueError, 'ordering'):
            lines = good.splitlines()
            lines[10], lines[11] = lines[11], lines[10]
            AUDIT.inspect_log(b'\n'.join(lines), prefix, parsed)
        with self.assertRaisesRegex(ValueError, 'CRC log'):
            AUDIT.inspect_log(good.replace(b'fileCrc=', b'fileCrc=1'), prefix, parsed)

    def test_wav_reject_wrong_rate_and_silence(self):
        stream = io.BytesIO()
        with wave.open(stream, 'wb') as writer:
            writer.setnchannels(2)
            writer.setsampwidth(2)
            writer.setframerate(44100)
            writer.writeframes(b'\0' * 44100 * 4)
        with self.assertRaisesRegex(ValueError, 'unexpected WAV'):
            AUDIT.inspect_wav(stream.getvalue(), 48000)
        with self.assertRaisesRegex(ValueError, 'unexpected WAV'):
            AUDIT.inspect_wav(stream.getvalue(), 44100)


if __name__ == '__main__':
    unittest.main()

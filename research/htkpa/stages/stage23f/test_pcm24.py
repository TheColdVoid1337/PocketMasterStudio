import unittest
import numpy as np
from pcm24_source import float_to_int32, pack_pcm24, decode_pcm24, roundtrip, experiment


class PCM24Tests(unittest.TestCase):
    def test_clip_and_sign(self):
        np.testing.assert_array_equal(float_to_int32([-2,-1,-.5,0,.5,1,2]),
                                      [-2147483648,-2147483648,-1073741824,0,1073741824,2147483647,2147483647])

    def test_arithmetic_shift_and_bytes(self):
        self.assertEqual(pack_pcm24([-2147483648,-1,0,256,2147483647]),
                         bytes.fromhex('000080 ffffff 000000 010000 ffff7f'))
        np.testing.assert_array_equal(decode_pcm24(bytes.fromhex('000080 ffffff 000000 010000 ffff7f')),
                                      [-1,-2**-23,0,2**-23,1-2**-23])

    def test_all_pcm16_values_through_writer(self):
        codes = np.arange(-32768,32768,dtype=np.int32)
        x = codes.astype(np.float32)/32768
        expected = x.copy()
        expected[codes > 16384] -= np.float32(2**-23)
        np.testing.assert_array_equal(roundtrip(x),expected)

    def test_random_float_bit_patterns(self):
        self.assertEqual(experiment()['int32_oracle_mismatches'],0)

    def test_pcm24_decode_full_integer_domain(self):
        # Every signed 24-bit word is exactly representable after normalization.
        for first in range(-8388608,8388608,65536):
            codes=np.arange(first,first+65536,dtype=np.int32)
            decoded=decode_pcm24(pack_pcm24(codes << 8))
            np.testing.assert_array_equal(decoded,(codes.astype(np.float64)/8388608).astype(np.float32))

    def test_nonfinite_scope_rejected(self):
        with self.assertRaises(ValueError):float_to_int32([np.nan])


if __name__=='__main__':unittest.main()

"""Independent mathematical and malformed-input checks; no vendor execution."""
import struct
import unittest

import numpy as np

from stage23e_audio_source import (decode_pcm16_words, loader_channel_zero,
                                  parse_pcm16, resampled_count)


def riff(samples, channels=2, tag=1, junk=b'abc'):
    payload = np.asarray(samples, dtype='<i2').tobytes()
    chunks = b'JUNK' + struct.pack('<I', len(junk)) + junk + b'\0'*(len(junk) & 1)
    chunks += b'fmt ' + struct.pack('<IHHIIHH', 16, tag, channels, 48000,
                                   48000*channels*2, channels*2, 16)
    chunks += b'data' + struct.pack('<I', len(payload)) + payload
    return b'RIFF' + struct.pack('<I', len(chunks)+4) + b'WAVE' + chunks


class AudioSourceTests(unittest.TestCase):
    def test_every_signed_pcm16_code(self):
        words = np.arange(-32768, 32768, dtype=np.int32).astype('<i2')
        decoded = decode_pcm16_words(words.tobytes(), 1)[:, 0]
        # Independent double division is exact for every integer in this range.
        expected = (words.astype(np.float64)/32768).astype(np.float32)
        np.testing.assert_array_equal(decoded, expected)
        self.assertEqual(float(decoded[0]), -1.)
        self.assertEqual(float(decoded[-1]), 32767/32768)

    def test_distinct_stereo_channels_and_endianness(self):
        samples = [[1, -32768], [0x1234, -1], [32767, -0x1234]]
        blob = riff(samples)
        meta, payload = parse_pcm16(blob)
        result = decode_pcm16_words(payload, meta['channels'])
        np.testing.assert_array_equal(result, np.asarray(samples)/32768)
        self.assertEqual(meta['frames'], 3)

    def test_odd_unknown_chunk_is_skipped(self):
        meta, _ = parse_pcm16(riff([[0, 1]]))
        self.assertEqual(meta['chunks'][1]['offset'], 32)

    def test_truncated_riff_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_pcm16(riff([[0, 1]])[:-1])

    def test_float_tag_is_not_mislabeled_pcm(self):
        with self.assertRaises(ValueError):
            parse_pcm16(riff([[0, 1]], tag=3))

    def test_loader_copies_only_channel_zero_and_pads(self):
        decoded = np.full((75, 2), [0.25, -0.75], dtype=np.float32)
        result = loader_channel_zero(decoded, 1)
        np.testing.assert_array_equal(result[:70], np.full(70, .25))
        np.testing.assert_array_equal(result[70:], np.zeros(600))
        self.assertEqual(result.dtype, np.float32)

    def test_loader_rejects_short_source(self):
        with self.assertRaises(ValueError):
            loader_channel_zero(np.zeros((69, 2)), 1)

    def test_resampler_count_at_actual_rates(self):
        self.assertEqual(resampled_count(3087000, 44100, 48000), 3360000)
        self.assertEqual(resampled_count(3360000, 48000, 44100), 3087000)
        self.assertEqual(resampled_count(1, 44100, 48000), 1)

    def test_binary32_count_differs_from_rational_floor(self):
        # A concrete rounding boundary; guards against replacing mulss/divss
        # with a seemingly more accurate rational count.
        for n, native, rational in [(3086014, 3358927, 3358926),
                                    (3086073, 3358990, 3358991)]:
            self.assertEqual(resampled_count(n, 44100, 48000), native)
            self.assertEqual(n*160//147, rational)


if __name__ == '__main__':
    unittest.main()

"""Offline tests for the intentionally small HTKPA Resampler Lab.

No public repo checkout, C++ compiler, Frida, proprietary DLL or external
audio is used. Real numerical provenance remains Stage62..66 evidence.
"""
from __future__ import annotations

import io
import json
import math
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock
import wave

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "research" / "htkpa" / "resampler_lab"
sys.path.insert(0, str(LAB))
import build as lab_build
import resampler as lab
import GO as go


class FakeStream:
    instances = []
    def __init__(self, bias=0):
        self.position = 0
        self.bias = bias
        self.closed = False
        FakeStream.instances.append(self)
    def process(self, values):
        if self.closed:
            raise RuntimeError("closed stream")
        data = [v + self.bias * (self.position + i) for i, v in enumerate(values)]
        self.position += len(values)
        return lab.encode_f64le(data)
    def close(self):
        self.closed = True


def make_pcm_wav(path, frames, channels=1, rate=44100):
    with wave.open(str(path), "wb") as target:
        target.setnchannels(channels)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(struct.pack("<" + "h"*len(frames), *frames))


class LabTests(unittest.TestCase):
    def test_stage66_pins_modes_and_no_code_rewrite(self):
        self.assertEqual(lab.MODELS["reverse"],(1,96000,44100))
        self.assertEqual(lab.MODELS["forward"],(2,44100,48000))
        self.assertEqual(lab.CHUNK_MAX,2680)
        self.assertEqual(lab_build.PIN,
                         "3c930bf6825c0cfea4a813210c83b1a650c820b5")
        self.assertEqual(lab_build.BETA_HEX,"0x1.91af20df9e8bap+3")
        self.assertEqual(lab_build.POWER_HEX,"0x1.83fa5ca7f6a99p+0")
        self.assertTrue((LAB.parent/"native_compat"/"htkpa_native_frac_bridge.cpp").exists())

    def test_pcm_byte_exact_decoding_at_all_supported_depths(self):
        self.assertEqual(lab.decode_pcm(b"\x00\x80\xff",1),
                         [-1.0,0.0,127/128])
        self.assertEqual(lab.decode_pcm(struct.pack("<3h",-32768,0,32767),2),
                         [-1.0,0.0,32767/32768])
        packed=b"\0\0\x80"+b"\0\0\0"+b"\xff\xff\x7f"
        self.assertEqual(lab.decode_pcm(packed,3),
                         [-1.0,0.0,8388607/8388608])
        self.assertEqual(lab.decode_pcm(struct.pack("<3i",-2147483648,0,2147483647),4),
                         [-1.0,0.0,2147483647/2147483648])
        with self.assertRaises(ValueError):
            lab.decode_pcm(b"\x00",3)

    def test_pcm24_signed_conversion_and_clipping(self):
        values=[-1.1,-1.0,-0.25,0.0,0.5,0.999,1.0,2.0]
        data,clipped=lab.encode_pcm24(values)
        self.assertEqual(clipped,3)
        recon=lab.decode_pcm(data,3)
        self.assertEqual(len(recon),len(values))
        self.assertEqual(recon[:2],[-1.0,-1.0])
        self.assertEqual(recon[3],0.0)
        self.assertEqual(recon[-1],8388607/8388608)
        for val in (float("nan"),float("inf"),-float("inf")):
            with self.assertRaises(ValueError):
                lab.encode_pcm24([val])

    def test_reverse_float64_stream_with_chunked_fake_and_padding(self):
        FakeStream.instances=[]
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            samples=[0.125,-0.25,0.5,0.75,-0.125]
            inp=root/"input.f64le"
            out=root/"reverse.f64le"
            inp.write_bytes(lab.encode_f64le(samples))
            report=lab.convert(inp,out,mode="reverse",rate=96000,channels=1,
                               chunk=2,pad_input=3,stream_factory=lambda:FakeStream())
            self.assertEqual(report["input_hz"],96000)
            self.assertEqual(report["output_hz"],44100)
            self.assertEqual(report["real_input_frames"],5)
            self.assertEqual(report["output_frames"],8)
            self.assertEqual(lab.decode_f64le(out.read_bytes()),samples+[0.0]*3)
            self.assertTrue(all(s.closed for s in FakeStream.instances))
            self.assertEqual(report["bridge_sha256"],"TEST_DOUBLE_NO_NATIVE_BINARY")
            with self.assertRaises(FileExistsError):
                lab.convert(inp,out,rate=96000,stream_factory=lambda:FakeStream())

    def test_stereo_pcm_wav_to_exact_interleaved_raw_float64(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            inp=root/"stereo.wav"
            out=root/"stereo.f64le"
            source=[32767,-32768,1000,-1000,0,1,500,-400]
            make_pcm_wav(inp,source,channels=2,rate=44100)
            factory=lambda:FakeStream()
            result=lab.convert(inp,out,chunk=2,mode="auto",stream_factory=factory)
            self.assertEqual(result["channels"],2)
            self.assertEqual(result["output_frames"],4)
            self.assertEqual(lab.decode_f64le(out.read_bytes()),
                             [s/32768.0 for s in source])
            self.assertEqual(result["clipped_samples"],0)

    def test_wav_24_output_has_correct_header_rate_and_quantized_audio(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            inp=root/"signal.wav"
            out=root/"signal_out.wav"
            samples=[0,8192,-8192,16384,-16384,32767]
            make_pcm_wav(inp,samples,rate=44100)
            result=lab.convert(inp,out,mode="44100-to-48000",chunk=3,
                               stream_factory=lambda:FakeStream())
            with wave.open(str(out),"rb") as reader:
                self.assertEqual(reader.getframerate(),48000)
                self.assertEqual(reader.getnchannels(),1)
                self.assertEqual(reader.getsampwidth(),3)
                actual=lab.decode_pcm(reader.readframes(10),3)
            self.assertEqual(actual,[s/32768.0 for s in samples])
            self.assertEqual(result["output_frames"],6)
            self.assertEqual(result["format"],"PCM24 WAV (quantized)")

    def test_reject_non_native_rate_and_unsigned_values(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            inp=p/"bad.wav"
            out=p/"result.wav"
            make_pcm_wav(inp,[0]*8,rate=48000)
            with self.assertRaisesRegex(ValueError,"Only 44100"):
                lab.convert(inp,out,stream_factory=lambda:FakeStream())
            make_pcm_wav(inp,[0]*8,rate=44100)
            with self.assertRaisesRegex(ValueError,"expects 96000"):
                lab.convert(inp,out,mode="reverse",stream_factory=lambda:FakeStream())
            with self.assertRaisesRegex(ValueError,"chunk"):
                lab.convert(inp,out,chunk=2681,stream_factory=lambda:FakeStream())
            with self.assertRaisesRegex(ValueError,"same file"):
                lab.convert(inp,inp,stream_factory=lambda:FakeStream())
            bad=p/"bad.f64le"
            bad.write_bytes(struct.pack("<d",float("nan")))
            with self.assertRaisesRegex(ValueError,"NaN"):
                lab.convert(bad,out,rate=44100,stream_factory=lambda:FakeStream())
            self.assertFalse(out.exists())

    def test_comparison_exact_index_and_signed_zero_is_not_bit_equal(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            x=root/"public.f64le"
            y=root/"native.f64le"
            x.write_bytes(lab.encode_f64le([0.0,1.0,0.25,-1.0]))
            y.write_bytes(lab.encode_f64le([-0.0,1.0,0.25,-1.0]))
            compared=lab.compare(x,y)
            self.assertEqual(compared["f64"],4)
            self.assertEqual(compared["bit_equal"],3)
            self.assertEqual(compared["rms_error"],0)
            self.assertEqual(compared["max_abs_error"],0)
            self.assertEqual(compared["status"],"COMPARED_SAME_INDEX_NO_SHIFT")
            with self.assertRaisesRegex(ValueError,"independent"):
                lab.compare(x,x)
            y.write_bytes(b"\x00")
            with self.assertRaisesRegex(ValueError,"sizes"):
                lab.compare(x,y)
            y.write_bytes(b"")
            x.write_bytes(b"")
            with self.assertRaisesRegex(ValueError,"empty"):
                lab.compare(x,y)
            y.rename(root/"native.f64le.bin")
            y=root/"native.f64le.bin"
            y.write_bytes(lab.encode_f64le([1.0]))
            x.write_bytes(lab.encode_f64le([1.0]))
            self.assertEqual(lab.compare(x,y)["bit_equal"],1)

    def test_sha_guard_rejects_mutated_cpp_and_missing_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            lib=root/lab_build.LIB_NAME
            lib.write_bytes(b"\x7fELFfake-lab-test")
            with self.assertRaises(FileNotFoundError):
                lab_build.verify_library(root)
            meta={
                "schema_version":1,"abi_id":lab_build.bridge.API_ID,
                "source":{
                    "source_commit":lab_build.PIN,
                    "bridge_source_sha256":lab_build.sha256(
                        (lab_build.NATIVE_COMPAT/"htkpa_native_frac_bridge.cpp").read_bytes()),
                    "patch":{
                        "beta_hex":lab_build.BETA_HEX,
                        "power_hex":lab_build.POWER_HEX,
                        "phase_positions":673,
                        "interpolation_mode":"forced_poly_673"
                    }
                },
                "shared_object_sha256":lab_build.sha256(lib.read_bytes())
            }
            (root/lab_build.MANIFEST_NAME).write_text(json.dumps(meta))
            self.assertEqual(lab_build.verify_library(root)[0],lib)
            lib.write_bytes(b"\x7fELFtampered")
            with self.assertRaisesRegex(ValueError,"match"):
                lab_build.verify_library(root)

    def test_go_parser_and_failure_limit(self):
        parser=go.parser()
        cmds=parser.parse_args(["convert","--input","in.wav",
                               "--output","out.wav","--mode","auto"])
        self.assertEqual(cmds.mode,"auto")
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/"a.f64le"
            b=Path(td)/"b.f64le"
            a.write_bytes(lab.encode_f64le([0.0,1.1]))
            b.write_bytes(lab.encode_f64le([0.0,1.0]))
            self.assertEqual(go.main(["compare","--actual",str(a),
                 "--reference",str(b),"--max-rms","0.01"]),3)
            self.assertEqual(go.main(["compare","--actual",str(a),
                 "--reference",str(b),"--max-rms","0.1"]),0)


if __name__ == "__main__":
    unittest.main()

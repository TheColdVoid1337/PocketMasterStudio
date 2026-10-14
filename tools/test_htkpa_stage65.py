"""Stage65 deterministic offline tests: no vendor runtime, no audio uploads."""
from __future__ import annotations
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"research"/"htkpa"/"stages"/"stage65"/"audit_extended.py"
spec=importlib.util.spec_from_file_location("_htkpa_test_stage65",SCRIPT)
assert spec and spec.loader
audit=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=audit
spec.loader.exec_module(audit)


class Stage65Tests(unittest.TestCase):
    def test_fixed_numerical_contracts_and_independent_sha(self):
        self.assertEqual(audit.LONG_EXPECTED["total_max_bytes"],9448)
        self.assertEqual(audit.LONG_EXPECTED["forward"]["copied_f64"],1067)
        self.assertEqual(audit.LONG_EXPECTED["reverse"]["copied_f64"],114)
        self.assertEqual(audit.STAGE63_SHA,
            "4b4f1452551b11019b57ff76267f81770061bb02707b26ca6d3dbc119b1dc04e")
        self.assertTrue((ROOT/"research"/"htkpa"/"stages"/"stage64"/"frida.json").is_file())
        self.assertEqual(len(audit.FIRST_32),2)
        self.assertEqual(len(audit.PATCH_FIRST32),2)

    def test_exact_long_buffer_metric_and_segment_geometry(self):
        for count,expected_segments in ((1067,4),(114,3)):
            arr=struct.pack("<"+str(count)+"d",*(float(i+1) for i in range(count)))
            m=audit.detailed_metrics(arr,arr,count)
            self.assertEqual(m["bit_equal"],count)
            self.assertEqual(m["rms_error"],0)
            self.assertEqual(m["max_abs_error"],0)
            self.assertEqual(len(m["segments"]),expected_segments)
            self.assertEqual(sum(v["f64"] for v in m["segments"]),count)
            self.assertEqual(m["segments"][0]["range"],[0,31])
            self.assertEqual(m["segments"][-1]["range"][-1],count-1)
            altered=bytearray(arr)
            altered[32*8:33*8]=struct.pack("<d",10000.0)
            changed=audit.detailed_metrics(arr,bytes(altered),count)
            self.assertLess(changed["bit_equal"],count)
            self.assertGreater(changed["rms_error"],0)
            with self.assertRaises(ValueError):
                audit.detailed_metrics(arr,arr[:-8],count)

    def test_read_stage64_guarded_two_events_first32_and_recovery(self):
        cfg={
            "module":"5868USB.dll",
            "sha256":"fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa",
            "mode":"guarded_fractional_io",
            "sites":[{"name":"fractional_entry_io","rva":0x135c0}],
            "long_probe":audit.LONG_EXPECTED
        }
        manifest={
            "status":"FRACTIONAL_EXTENDED_OUTPUTS_CLO_STABLE",
            "completion_verified":True,
            "process_cleanup_status":"CLOSED_GRACEFULLY",
            "hook_count":1
        }
        fwd=bytes(range(256))+b"\x00"*(1067*8-256)
        rev=bytes(reversed(range(256)))+b"\x01"*(114*8-256)
        fixtures={"forward":fwd,"reverse":rev}
        first32={side:hashlib.sha256(blob[:256]).hexdigest()
                 for side,blob in fixtures.items()}

        def emit_tar(path, mutate=None):
            events=[]
            for side,blob in fixtures.items():
                exp=audit.LONG_EXPECTED[side]
                evt={
                    "kind":"fractional_extended_output","valid":True,
                    "side":side,"site":"fractional_entry_io",
                    "observed":exp["observed"],
                    "processor_pointer":"0x1234" if side=="forward" else "0x5678",
                    "input_f64":exp["input_f64"],"output_f64":exp["output_f64"],
                    "copied_f64":exp["copied_f64"],"copied_bytes":len(blob),
                    "rate_numerator":exp["numerator"],
                    "rate_denominator":exp["denominator"],
                    "first32_sha256":first32[side],
                    "provenance":"fractional_r9_ref_onleave_extended",
                    "file":audit.FILE_NAMES[side],
                    "sha256":hashlib.sha256(blob).hexdigest()}
                if mutate is not None and side=="reverse":
                    mutate(evt)
                events.append(evt)
            payload={
                "config.json":json.dumps(cfg).encode(),
                "manifest.json":json.dumps(manifest).encode(),
                "events.jsonl":("\n".join(json.dumps(e) for e in events)+"\n").encode(),
                audit.FILE_NAMES["forward"]:fwd,
                audit.FILE_NAMES["reverse"]:rev}
            with tarfile.open(path,"w:gz") as tar:
                for name,blob in payload.items():
                    info=tarfile.TarInfo("frida_capture/"+name)
                    info.size=len(blob)
                    tar.addfile(info,io.BytesIO(blob))
        with tempfile.TemporaryDirectory() as d, patch.dict(audit.FIRST_32,first32):
            where=Path(d)/"capture.tar.gz"
            emit_tar(where)
            content,provenance=audit.read_extended(where)
            self.assertEqual(content,fixtures)
            self.assertEqual(provenance["native_f64_total"],1181)
            self.assertEqual(provenance["native_forward_sha256"],
                             hashlib.sha256(fwd).hexdigest())
            emit_tar(where,lambda e:e.update(processor_pointer="0x1234"))
            with self.assertRaises(ValueError):
                audit.read_extended(where)
            emit_tar(where,lambda e:e.update(copied_bytes=1024))
            with self.assertRaises(ValueError):
                audit.read_extended(where)

    def test_source_patch_reuses_exact_stage63_proven_coefficients(self):
        previous=audit.prior
        self.assertEqual(previous.stage62.NATIVE_BETA,12.55262798)
        self.assertEqual(previous.stage62.NATIVE_POWER,1.51553897)
        self.assertEqual(audit.stage55.PINS["v6.5"],
                         "3c930bf6825c0cfea4a813210c83b1a650c820b5")
        self.assertEqual(audit.stage57.BASELINE_REVERSE_SHA,
                         "1741985a4fc6c5cb1d937b9f11a262642ec3fc24a9ac615088448ecf9619ff96")


if __name__=="__main__":
    unittest.main()

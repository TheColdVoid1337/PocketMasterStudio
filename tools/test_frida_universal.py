"""Offline contract tests for universal tools/frida_capture.py (no Frida required)."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import frida_capture as core
import frida_guarded as guarded

STAGE48=HERE.parent/"research"/"htkpa"/"stages"/"stage48"/"frida.json"

class UniversalFridaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=json.loads(STAGE48.read_text(encoding="utf-8"))
        cls.cfg=core.validate(cls.raw)

    def test_stage48_single_guarded_site(self):
        self.assertEqual(self.cfg["mode"],"guarded_metadata")
        self.assertEqual(len(self.cfg["sites"]),1)
        self.assertEqual(self.cfg["sites"][0]["rva"],0x1190c)
        self.assertEqual(self.cfg["sites"][0]["guard"]["vtable_rva"],0x245170)
        self.assertEqual(self.cfg["sha256"],
            "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa")

    def test_one_delayed_hook_no_audio_reads(self):
        js=guarded.agent_source(self.cfg)
        self.assertEqual(js.count("Interceptor.attach("),1)
        self.assertIn("rpc.exports",js)
        self.assertIn("Process.attachModuleObserver",js)
        for forbidden in (".readByteArray(", ".readDouble(", ".readFloat(", ".writeByteArray("):
            self.assertNotIn(forbidden,js)

    def test_legacy_unchanged(self):
        old=core.validate({"module":"5868USB.dll","sha256":"f"*64,
             "sites":[{"name":"block","address":"0x18000c838",
                       "fields":[{"name":"block","type":"f64_binary",
                                  "reg":"rdx","count":1972}]}]})
        self.assertEqual(old["sites"][0]["rva"],0xc838)
        self.assertEqual(old["sites"][0]["fields"][0]["count"],1972)
        self.assertIn("Interceptor.attach(",core.agent_source(old))
        self.assertNotIn("mode",old)

    def test_no_unchecked_user_js(self):
        for modifications in [
            lambda x:x["sites"][0]["guard"].update(javascript="send('bad')"),
            lambda x:x["sites"][0].update(fields=[{"name":"audio","type":"f64_binary","reg":"rdx","count":64}]),
            lambda x:x["sites"][0]["guard"].update(max_samples=100000),
            lambda x:x["sites"][0]["guard"].update(owner_reg="xmm8"),
            lambda x:x["sites"][0]["guard"].update(owner_offset=-8),
            lambda x:x["completion"].update(appdata_subdir="../secret"),
            lambda x:x["target"].update(process_name_contains=""),
            lambda x:x["sites"].append(copy.deepcopy(x["sites"][0])),
        ]:
            with self.subTest(modification=str(modifications)):
                candidate=copy.deepcopy(self.raw)
                modifications(candidate)
                with self.assertRaises((ValueError,TypeError,KeyError)):
                    core.validate(candidate)

    def test_ctrl_c_journal_recovery_and_clo_recursive(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            ev=[
                {"kind":"module_found","name":"5868USB.dll"},
                {"kind":"hook_attached","site":"post_fractional_output","hooks_installed":1},
                {"kind":"first_rejected_return","reason":"return count zero or out of bounds"},
                {"kind":"metadata_hit","site":"post_fractional_output","valid":True,
                 "output_f64":114,"output_bytes":912,"observed":18},
            ]
            (root/"events.jsonl").write_text(
                "".join(json.dumps(x)+"\n" for x in ev),encoding="utf-8")
            state={}
            guarded.reconcile(root,state)
            self.assertEqual(state["journal_events"],4)
            self.assertEqual(state["last_metadata"]["output_f64"],114)
            self.assertTrue(state["hook_attached"])
            self.assertEqual(guarded.interrupted_status(state),
                "METADATA_OBSERVED_OPERATOR_INTERRUPTED")
            sub=root/"nested";sub.mkdir()
            (sub/"new.clo").write_bytes(b"fake")
            self.assertEqual(len(guarded.snapshot(root,True)),1)
            self.assertEqual(len(guarded.snapshot(root,False)),0)

    def test_tar_archive_remains_allowlisted(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for file in ("config.json","manifest.json","events.jsonl","HANDOFF.md"):
                (root/file).write_text("test",encoding="utf-8")
            (root/"private_audio.wav").write_bytes(b"NO")
            dest=root/"output.tar.gz"
            core.archive(root,dest)
            import tarfile
            with tarfile.open(dest) as t:
                names=[x.name for x in t]
            self.assertTrue(all("private_audio" not in n for n in names))

    def test_js_syntax_if_node_exists(self):
        node=shutil.which("node")
        if not node:self.skipTest("node not installed")
        with tempfile.TemporaryDirectory() as d:
            fn=Path(d)/"agent.js"
            fn.write_text(guarded.agent_source(self.cfg),encoding="utf-8")
            result=subprocess.run([node,"--check",str(fn)],text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)

if __name__=="__main__":
    unittest.main()

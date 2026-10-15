"""Stage67 local Emscripten output contract and atomic private artifact gates.

Pure offline fixtures: does NOT need proprietary DLL, public r8brain checkout,
node, em++, or any network. If em++ is present, run the separate real build
through build_wasm.py --source-cache ... and validate in Stage68.
"""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"research"/"htkpa"/"native_compat"/"build_wasm.py"
spec=importlib.util.spec_from_file_location("_htkpa_stage67_build_test",SCRIPT)
assert spec and spec.loader
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)


class Stage67BuildTests(unittest.TestCase):
    def test_exact_wasm_exports_source_identity_and_no_main_converter_edit(self):
        self.assertTrue(m.BRIDGE.is_file())
        self.assertTrue((ROOT/"src"/"htkpa_wasm_adapter.js").is_file())
        self.assertEqual(len(m.EXPORTS),8)
        self.assertEqual(len(set(m.EXPORTS)),8)
        self.assertIn("_htkpa_v1_process",m.EXPORTS)
        self.assertIn("_malloc",m.EXPORTS)
        self.assertIn("_free",m.EXPORTS)
        self.assertTrue(m.STAGE63.is_file())

    def test_wasm_build_flags_enforce_es_module_and_no_fast_math(self):
        command=m.command("em++",Path("/tmp/pinned_public"),Path("/tmp/output.mjs"))
        for flag in ("-O2","-fno-fast-math","-sMODULARIZE=1","-sEXPORT_ES6=1",
                     "-sENVIRONMENT=web,worker,node","-sALLOW_MEMORY_GROWTH=1",
                     "-sFILESYSTEM=0","-sDISABLE_EXCEPTION_CATCHING=0"):
            self.assertIn(flag,command)
        functions=[x for x in command if x.startswith("-sEXPORTED_FUNCTIONS=")]
        self.assertEqual(len(functions),1)
        self.assertEqual(json.loads(functions[0].split("=",1)[1]),m.EXPORTS)
        runtime=[x for x in command if x.startswith("-sEXPORTED_RUNTIME_METHODS=")]
        self.assertEqual(len(runtime),1)
        self.assertEqual(json.loads(runtime[0].split("=",1)[1]),
                         ["HEAPU8","HEAPF64"])
        self.assertEqual(command[-2:],["-o","/tmp/output.mjs"])

    def test_refuse_missing_emscripten_before_extracting_any_public_code(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"output"
            with patch.object(m.shutil,"which",return_value=None):
                with self.assertRaisesRegex(RuntimeError,"Emscripten em\\+\\+"):
                    m.build(Path(td)/"git",out,"em++")
            self.assertFalse(out.exists())

    def test_stub_emxx_publishes_both_assets_and_sha_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            top=Path(td)
            target=top/"private_outputs"
            compiled=[]
            def checkout(cache,commit,destination):
                self.assertEqual(commit,"3c930bf6825c0cfea4a813210c83b1a650c820b5")
                (destination/"CDSPFracInterpolator.h").write_text("PINNED ORIGINAL HEADER",encoding="utf-8")
            def patch_public(original,mode):
                self.assertEqual(original,"PINNED ORIGINAL HEADER")
                self.assertEqual(mode,"native_window_poly_673")
                return ("HTKPA_Stage62_Params\nIsWhole = false;\n"
                        "FilterFracs = 673;\n"),{
                        "beta_hex":"0x1.91af20df9e8bap+3",
                        "power_hex":"0x1.83fa5ca7f6a99p+0"}
            st63=SimpleNamespace(
                stage55=SimpleNamespace(
                    PINS={"v6.5":"3c930bf6825c0cfea4a813210c83b1a650c820b5"},
                    ensure_checkout=checkout),
                patch_header=patch_public)
            def fake_compiler(argv,**kwargs):
                compiled.append(argv)
                output=Path(argv[-1])
                output.write_bytes(b"generated-test-js"*100)
                output.with_suffix(".wasm").write_bytes(b"generated-test-wasm"*100)
                return SimpleNamespace(returncode=0,stderr="")
            with (patch.object(m,"load_stage63",return_value=st63),
                  patch.object(m.shutil,"which",return_value="/opt/emsdk/upstream/emscripten/em++"),
                  patch.object(m.subprocess,"run",side_effect=fake_compiler)):
                result=m.build(top/"offline-cache",target,"em++")
            self.assertEqual(len(compiled),1)
            self.assertEqual(result["public_source_commit"],
                "3c930bf6825c0cfea4a813210c83b1a650c820b5")
            self.assertTrue((target/"htkpa_native_frac.mjs").is_file())
            self.assertTrue((target/"htkpa_native_frac.wasm").is_file())
            manifest=json.loads((target/"htkpa_wasm_build.json").read_text())
            for file in ("htkpa_native_frac.mjs","htkpa_native_frac.wasm"):
                self.assertEqual(m.sha(target/file),
                    manifest["output"][file]["sha256"])
            self.assertFalse(any(p.suffix==".staging" for p in target.iterdir()))
            self.assertFalse(manifest["vendor_binary_included"])

    def test_stub_compiler_failure_never_creates_output_dir(self):
        with tempfile.TemporaryDirectory() as td:
            top=Path(td)
            def checkout(cache,commit,destination):
                (destination/"CDSPFracInterpolator.h").write_text("expected")
            def patch(*args):
                return ("HTKPA_Stage62_Params IsWhole = false; FilterFracs = 673;",
                        {"beta_hex":"0x1.91af20df9e8bap+3",
                         "power_hex":"0x1.83fa5ca7f6a99p+0"})
            st63=SimpleNamespace(stage55=SimpleNamespace(
                PINS={"v6.5":"3c930bf6825c0cfea4a813210c83b1a650c820b5"},
                ensure_checkout=checkout),patch_header=patch)
            with (patch.object(m,"load_stage63",return_value=st63),
                  patch.object(m.shutil,"which",return_value="em++"),
                  patch.object(m.subprocess,"run",return_value=SimpleNamespace(
                      returncode=1,stderr="intentional compiler failure"))):
                with self.assertRaisesRegex(RuntimeError,"intentional compiler failure"):
                    m.build(top/"cache",top/"not-created","em++")
            self.assertFalse((top/"not-created").exists())


if __name__=="__main__":
    unittest.main()

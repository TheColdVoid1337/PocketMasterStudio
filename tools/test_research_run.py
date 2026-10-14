"""No-GitHub offline tests. Always run in an isolated temporary repo layout."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile

ORIGINAL_SCRIPT = Path(__file__).with_name("research_run.py")


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="htkpa_capsules_test_")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "tools").mkdir()
        self.script = self.root / "tools" / "research_run.py"
        shutil.copyfile(ORIGINAL_SCRIPT, self.script)
        (self.root / "research" / "htkpa").mkdir(parents=True)
        self.journal = self.root / "research" / "htkpa" / "RE_LOG.md"
        self.journal.write_text("# Historic research log\n", encoding="utf-8")
        self.private = self.root / "research" / "_LOCAL_FILES"
        self.output = self.private / "research_runs"
        self.staging = self.root / "research" / ".research_run_staging"

    def call(self, *args):
        return subprocess.run([sys.executable, str(self.script), *args],
                              cwd=self.root, capture_output=True, text=True)

    def archives(self):
        return sorted(self.output.glob("*.tar.gz"))

    def read_archive(self, path):
        with tarfile.open(path) as tar:
            names = tar.getnames()
            data = json.loads(tar.extractfile("run.json").read().decode())
            return names, data, {n:tar.extractfile(n).read() for n in names if n!="run.json"}

    def test_success_seals_stdout_and_files_into_one_tar(self):
        code="import os,pathlib; p=pathlib.Path(os.environ['RESEARCH_ARTIFACT_DIR']);(p/'sample.bin').write_bytes(b'PRIVATE');print('FINISHED')"
        result=self.call("run", "--name", "wave", "--", sys.executable, "-c", code)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(len(self.archives()),1)
        names, manifest, files = self.read_archive(self.archives()[0])
        self.assertEqual(manifest["status"],"SUCCEEDED")
        self.assertIn("output/sample.bin", names)
        self.assertEqual(files["output/sample.bin"],b"PRIVATE")
        self.assertIn(b"FINISHED", files["console.log"])
        self.assertEqual(manifest["output_files"][0]["sha256"],hashlib.sha256(b"PRIVATE").hexdigest())
        self.assertEqual(list(self.private.rglob("*")),[self.output,self.archives()[0]])
        self.assertEqual(list(self.staging.glob("*")),[])

    def test_child_exception_still_seals_partial_output_and_traceback(self):
        code="import os,pathlib;pathlib.Path(os.environ['RESEARCH_ARTIFACT_DIR'],'partial.bin').write_bytes(b'PARTIAL');raise RuntimeError('FAIL_MARKER')"
        result=self.call("run", "--name", "crash", "--", sys.executable,"-c",code)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(len(self.archives()),1)
        _, manifest, files=self.read_archive(self.archives()[0])
        self.assertEqual(manifest["status"],"FAILED")
        self.assertEqual(files["output/partial.bin"],b"PARTIAL")
        self.assertIn(b"FAIL_MARKER", files["console.log"])

    def test_failed_spawn_still_seals_error(self):
        result=self.call("run","--name","noexe","--","__missing_executable___")
        self.assertEqual(result.returncode,127)
        self.assertEqual(len(self.archives()),1)
        _, manifest,_=self.read_archive(self.archives()[0])
        self.assertEqual(manifest["status"],"FAILED_TO_START")
        self.assertIn("error",manifest)

    def test_recover_wrapper_kill_marks_unverified_and_seals_outputs(self):
        stage=self.staging/"20261014T000000_abc_stage50"
        (stage/"output").mkdir(parents=True)
        (stage/"output"/"working.bin").write_bytes(b"PREVIOUS_BYTES")
        (stage/"console.log").write_text("before SIGKILL")
        (stage/"run.json").write_text(json.dumps({"schema_version":2,"status":"RUNNING"}))
        result=self.call("recover")
        self.assertEqual(result.returncode,0,result.stderr)
        _, manifest, files=self.read_archive(self.archives()[0])
        self.assertEqual(manifest["status"],"WRAPPER_INTERRUPTED_UNVERIFIED")
        self.assertEqual(files["output/working.bin"],b"PREVIOUS_BYTES")
        self.assertFalse(stage.exists())

    def test_record_references_not_copy_proprietary(self):
        file=self.private/"vendor"/"5868USB.dll"
        file.parent.mkdir(parents=True)
        file.write_bytes(b"DO_NOT_COPY")
        result=self.call("record","--name","native32","--status","accepted",
                         "--finding","32 genuine f64", "--artifact",str(file))
        self.assertEqual(result.returncode,0,result.stderr)
        names,manifest,_=self.read_archive(self.archives()[0])
        self.assertEqual(names,["run.json"])
        self.assertEqual(manifest["references"][0]["sha256"],hashlib.sha256(b"DO_NOT_COPY").hexdigest())
        self.assertEqual(file.read_bytes(),b"DO_NOT_COPY")
        self.assertFalse((self.root/"README.md").exists())

    def test_one_explicit_research_fact_not_status_or_general_docs(self):
        args=("finding","--stage","stage50","--where","5868USB.dll V1.5.2 RVA 0x1190c",
              "--what","114 f64 written before return","--evidence","SHA-pinned DLL + native block tar.gz",
              "--boundary","Absolute sample stream offset not yet proven")
        result=self.call(*args)
        self.assertEqual(result.returncode,0,result.stderr)
        found=self.journal.read_text()
        self.assertIn("RVA 0x1190c",found)
        self.assertIn("Absolute sample stream",found)
        self.assertFalse((self.root/"research"/"htkpa"/"STATUS.yaml").exists())
        self.assertFalse((self.root/"README.md").exists())
        self.assertEqual(list(self.output.glob("*")),[])

    def test_selected_private_rollover_is_sha_verified_and_stays_outside_local(self):
        f1=self.private/"frida"/"stage49.tar.gz"
        f1.parent.mkdir(parents=True)
        f1.write_bytes(b"CAPTURE")
        f2=self.private/"vendor"/"5868USB.dll"
        f2.parent.mkdir(parents=True)
        f2.write_bytes(b"VENDOR")
        dst=self.root/"POCKET_MASTER_HTKPA_PRIVATE_ROLLOVER_2026-10-14.zip"
        result=self.call("rollover","--output",str(dst),"--include",str(f1),"--include",str(f2))
        self.assertEqual(result.returncode,0,result.stderr)
        with zipfile.ZipFile(dst) as z:
            j=json.loads(z.read("ROLLOVER_MANIFEST.json"))
            self.assertEqual(len(j["files"]),2)
            self.assertEqual(z.read("research/_LOCAL_FILES/vendor/5868USB.dll"),b"VENDOR")
        self.assertFalse((self.private/"ROLLOVER_MANIFEST.json").exists())
        again=self.call("rollover","--output",str(dst),"--include",str(f1))
        self.assertNotEqual(again.returncode,0)

    def test_no_unsafe_paths_or_silent_unwanted_documentation(self):
        result=self.call("run","--name","../bad","--",sys.executable,"-c","pass")
        self.assertNotEqual(result.returncode,0)
        result=self.call("finding","--stage","stage50","--where","x",
                         "--what","line1\\nline2","--evidence","e","--boundary","b")
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse((self.root/"docs").exists())


if __name__=="__main__":
    unittest.main()

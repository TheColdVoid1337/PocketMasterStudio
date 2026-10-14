"""Stdlib-only offline tests, ALWAYS isolated from a user's real repo/state."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ORIGINAL_SCRIPT = Path(__file__).with_name("research_run.py")


class ResearchRunTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory(prefix="research_run_test_")
        self.addCleanup(self.sandbox.cleanup)
        self.root = Path(self.sandbox.name)
        (self.root/"tools").mkdir()
        self.script = self.root/"tools"/"research_run.py"
        shutil.copyfile(ORIGINAL_SCRIPT, self.script)
        self.runs = self.root/"research"/"_LOCAL_FILES"/"research_runs"
        self.status = self.root/"research"/"htkpa"/"STATUS.yaml"

    def launch(self,*args):
        return subprocess.run([sys.executable,str(self.script),*args],cwd=self.root,
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)

    def latest(self):
        return max((p for p in self.runs.iterdir() if p.is_dir()),
                   key=lambda p:p.stat().st_mtime_ns)

    def test_opt_in_record_artifact_and_one_status_promotion(self):
        art=self.root/"private.bin"
        art.write_bytes(b"LOCAL PRIVATE AUDIO BYTES")
        r=self.launch("record","--name","native32_proof","--artifact",str(art),
                      "--outcome","accepted","--finding","Verified sample digest")
        self.assertEqual(r.returncode,0,r.stderr)
        capsule=self.latest()
        manifest=json.loads((capsule/"run.json").read_text())
        self.assertEqual(manifest["kind"],"record")
        self.assertEqual(manifest["artifacts"][0]["sha256"],hashlib.sha256(art.read_bytes()).hexdigest())
        self.assertFalse((capsule/"private.bin").exists())
        self.assertFalse((capsule/"console.log").exists())
        self.assertFalse(self.status.exists())
        closed=self.launch("close","--run",capsule.name,"--stage","stage49",
                           "--decision","accepted","--finding","32 native f64 verified",
                           "--blocker","stream position unknown",
                           "--next","resolve exact streaming state")
        self.assertEqual(closed.returncode,0,closed.stderr)
        data=self.status.read_text()
        self.assertIn('verified: "32 native f64 verified"',data)
        self.assertIn('stage: "stage49"',data)
        self.assertIn('run_id: "'+capsule.name+'"',data)
        self.assertNotIn("LOCAL PRIVATE AUDIO BYTES",data)
        self.assertFalse((self.root/"README.md").exists())
        self.assertFalse((self.root/"research"/"htkpa"/"RE_LOG.md").exists())

    def test_nonzero_exit_capsule_preserved_but_not_accepted(self):
        cmd="import sys; print('STDOUT_MARKER'); print('STDERR_MARKER',file=sys.stderr); sys.exit(3)"
        r=self.launch("run","--name","probe_failure","--",sys.executable,"-c",cmd)
        self.assertEqual(r.returncode,3,r.stderr)
        self.assertIn("STDOUT_MARKER",r.stdout)
        self.assertIn("STDERR_MARKER",r.stdout)
        cap=self.latest()
        manifest=json.loads((cap/"run.json").read_text())
        self.assertEqual(manifest["outcome"],"nonzero_exit")
        self.assertEqual(manifest["exit_code"],3)
        self.assertIn(b"STDERR_MARKER",(cap/"console.log").read_bytes())
        rejected=self.launch("close","--run",cap.name,"--stage","stage50",
                             "--decision","accepted","--finding","bad","--next","none")
        self.assertNotEqual(rejected.returncode,0)
        self.assertFalse(self.status.exists())

    def test_success_tracks_git_head_and_rejects_invalid_identifiers(self):
        r=self.launch("run","--name","probe_success","--",sys.executable,"-c","print('OK')")
        self.assertEqual(r.returncode,0,r.stderr)
        manifest=json.loads((self.latest()/"run.json").read_text())
        self.assertEqual(manifest["outcome"],"exit_zero")
        self.assertIn("git_before",manifest)
        self.assertIn("git_after",manifest)
        bad=self.launch("record","--name","../../bad","--finding","x")
        self.assertNotEqual(bad.returncode,0)
        bad=self.launch("close","--run","../../outside","--stage","x",
                        "--decision","blocked","--finding","x","--next","n")
        self.assertNotEqual(bad.returncode,0)

    def test_missing_artifact_no_capsule_and_refuse_unverified_record(self):
        r=self.launch("record","--name","nope","--artifact","missing/private.wav")
        self.assertNotEqual(r.returncode,0)
        self.assertFalse(self.runs.exists())
        r=self.launch("record","--name","weak","--outcome","observation",
                      "--finding","Unconfirmed idea")
        self.assertEqual(r.returncode,0)
        blocked=self.launch("close","--run",self.latest().name,"--stage","stage49",
                            "--decision","accepted","--finding","bad","--next","n")
        self.assertNotEqual(blocked.returncode,0)
        self.assertFalse(self.status.exists())

    def test_declared_missing_postrun_artifact_is_not_success(self):
        r=self.launch("run","--name","missing_artifact","--artifact","not_produced.bin",
                      "--",sys.executable,"-c","print('OK')")
        self.assertEqual(r.returncode,2,r.stderr)
        data=json.loads((self.latest()/"run.json").read_text())
        self.assertEqual(data["outcome"],"missing_required_artifact")
        self.assertTrue(data["artifact_error"])


if __name__=="__main__":
    unittest.main()

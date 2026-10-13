"""Portable no-Frida checks of Stage24B capture and private-archive contract."""
from __future__ import annotations
import hashlib
import tarfile
import tempfile
import unittest
from pathlib import Path
import one_click_capture as c

class Stage24BCaptureTests(unittest.TestCase):
    def test_modified_existing_clo_must_stabilize(self):
        baseline={'existing.clo':(400,10)}
        seen={}
        self.assertIsNone(c.stable_changed_output(baseline,{'existing.clo':(400,10)},0,seen))
        self.assertIsNone(c.stable_changed_output(baseline,{'existing.clo':(200,11)},1,seen))
        self.assertIsNone(c.stable_changed_output(baseline,{'existing.clo':(350,12)},5,seen))
        self.assertIsNone(c.stable_changed_output(baseline,{'existing.clo':(350,12)},9,seen))
        self.assertEqual(c.stable_changed_output(baseline,{'existing.clo':(350,12)},11,seen),'existing.clo')

    def test_new_clo_and_zero_length_rejected(self):
        seen={}
        self.assertIsNone(c.stable_changed_output({}, {'new.clo':(0,33)},0,seen))
        self.assertIsNone(c.stable_changed_output({}, {'new.clo':(0,33)},7,seen))
        self.assertIsNone(c.stable_changed_output({}, {'new.clo':(20,35)},8,seen))
        self.assertEqual(c.stable_changed_output({}, {'new.clo':(20,35)},14,seen),'new.clo')

    def test_pair_requires_same_filter_address(self):
        a=[{'kind':'filter_arguments','filter':'A'},{'kind':'generator_arguments','filter':'B'}]
        self.assertEqual(c.pair_counts(a),(1,1,0))
        a.append({'kind':'generator_arguments','filter':'A'})
        self.assertEqual(c.pair_counts(a),(1,2,1))

    def test_archive_exact_allowlist_and_sha(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);session=root/'session';session.mkdir()
            for name in c.ARCHIVE_MEMBERS:
                (session/name).write_text('fixture:'+name,encoding='utf-8')
            (session/'5868USB.dll').write_bytes(b'dont bundle vendor')
            (session/'user-input.nam').write_bytes(b'dont bundle audio')
            (session/'user-output.clo').write_bytes(b'dont bundle clo')
            out=root/'result.tar.gz'
            hashes=c.archive_run(session,out)
            self.assertEqual(len(hashes),len(c.ARCHIVE_MEMBERS))
            with tarfile.open(out,'r:gz') as tf:
                self.assertEqual(set(tf.getnames()),{'stage24b/'+x for x in c.ARCHIVE_MEMBERS})
                for obj in tf.getmembers():
                    self.assertEqual(
                        hashlib.sha256(tf.extractfile(obj).read()).hexdigest(),
                        hashes[obj.name.split('/',1)[1]]
                    )

    def test_handoff_does_not_claim_native_success_for_empty_trace(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            c.write_handoff(root,{'events':[],'runtime_verified':False},'BLOCKED','none','missing Frida')
            handoff=(root/'STAGE24B_HANDOFF.md').read_text(encoding='utf-8')
            self.assertIn('BLOCKED',handoff)
            self.assertIn('missing Frida',handoff)
            self.assertIn('Filter events:** 0',handoff)

if __name__=='__main__':
    unittest.main(verbosity=2)

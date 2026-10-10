"""Optional real numerical parity test against pinned upstream SonicMaster goldens.

Run after:
  python tools/nam_dsp/fetch_reference.py
  cargo build --release --manifest-path tools/nam_dsp/Cargo.toml
  python -m unittest discover -s tests -p test_nam_dsp_golden.py -v

Not part of the default short studio_server smoke tests: inference is CPU-heavy.
"""
import base64
import struct
import subprocess
import unittest
from pathlib import Path
from tools.studio_server import NAM_BINARY, NAM_REFERENCE, ROOT, nam_readiness, valid_clo_binary


class NativeDSPGolden(unittest.TestCase):
    def test_reference_nam_against_sonicmaster_golden_clo(self):
        if not nam_readiness()["ready"]:
            self.skipTest("Build native DSP and fetch verified reference DI first")
        source = (ROOT / "tests/fixtures/sonicmaster_ref_input.nam").read_bytes()
        reference = base64.b64decode((ROOT / "tests/fixtures/sonicmaster_golden_ref.clo.b64").read_text())
        converted = subprocess.run(
            [str(NAM_BINARY), "--reference", str(NAM_REFERENCE)], input=source,
            capture_output=True, timeout=600, check=True
        ).stdout
        self.assertTrue(valid_clo_binary(converted))
        self.assertTrue(valid_clo_binary(reference))
        self.assertEqual(len(converted), len(reference))
        # Numerical f32 agreement is the invariant. No fabricated fit coefficients.
        for offset, count in ((104, 4), (136, 128), (648, 2048)):
            actual = struct.unpack_from("<" + str(count) + "f", converted, offset)
            expected = struct.unpack_from("<" + str(count) + "f", reference, offset)
            for i, (a, b) in enumerate(zip(actual, expected)):
                self.assertAlmostEqual(a, b, delta=1e-5 + abs(b) * 1e-4,
                    msg=f"Numerical mismatch at byte {offset + i * 4}")
        self.assertEqual(converted[64:104], reference[64:104])

if __name__ == "__main__":
    unittest.main()

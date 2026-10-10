"""Smoke tests for START.bat's private Python loopback server.

Run: python -m unittest discover -s tests -p test_studio_server.py -v
"""
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from tools.studio_server import BIND_HOST, HTML, ROOT, make_server


class StudioServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server(port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://{BIND_HOST}:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def get(self, path):
        return urlopen(self.base + path, timeout=3)

    def test_bind_is_loopback_only(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        self.assertTrue((ROOT / HTML).is_file())

    def test_html_is_served_directly_or_from_root(self):
        for path in ("/", "/" + HTML, "/" + HTML + "?fresh=1"):
            with self.subTest(path=path), self.get(path) as response:
                content = response.read()
                self.assertEqual(response.status, 200)
                self.assertIn(b"PocketMaster", content)
                self.assertIn(b"Void", content)
                self.assertIn("no-store", response.headers["Cache-Control"])
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_private_config_and_other_repo_files_are_not_exposed(self):
        for path in ("/config/studio_state.json", "/config/nam_clone.json",
                     "/.git/config", "/README.md", "/tools/studio_server.py",
                     "/../README.md", "/%2e%2e/README.md"):
            with self.subTest(path=path), self.assertRaises(HTTPError) as ctx:
                self.get(path)
            self.assertEqual(ctx.exception.code, 404)
            ctx.exception.close()  # Avoid ResourceWarning from retained HTTPError response

    def test_nam_availability_reports_real_local_prerequisites(self):
        with self.get("/api/nam/availability") as response:
            obj = json.load(response)
            self.assertIsInstance(obj["ready"], bool)
            self.assertIn("requirements", obj)
            self.assertIn("Rust DSP", obj["backend"])

    def test_nam_endpoint_rejects_external_origins_and_wrong_content_types(self):
        target = self.base + "/api/nam/convert"
        outside = Request(target, data=b"{}", headers={
            "Origin": "https://evil.example", "Content-Type": "application/x-nam"
        }, method="POST")
        with self.assertRaises(HTTPError) as error:
            urlopen(outside, timeout=3)
        self.assertEqual(error.exception.code, 403)
        error.exception.close()
        wrong = Request(target, data=b"{}", headers={
            "Content-Type": "text/plain"
        }, method="POST")
        with self.assertRaises(HTTPError) as error:
            urlopen(wrong, timeout=3)
        self.assertEqual(error.exception.code, 415)
        error.exception.close()

    def test_cancel_unknown_job_has_no_side_effects(self):
        target = self.base + "/api/nam/cancel?job=123e4567-e89b-42d3-a456-426614174000"
        request = Request(target, data=b"", headers={
            "Content-Type": "application/x-nam"
        }, method="POST")
        with urlopen(request, timeout=3) as response:
            self.assertFalse(json.load(response)["cancel_requested"])

    def test_head_serves_only_html(self):
        from urllib.request import Request
        with urlopen(Request(self.base + "/" + HTML, method="HEAD"), timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), b"")
        with self.assertRaises(HTTPError) as ctx:
            urlopen(Request(self.base + "/config/studio_state.json", method="HEAD"), timeout=3)
        self.assertEqual(ctx.exception.code, 404)
        ctx.exception.close()  # Avoid ResourceWarning from retained HTTPError response


if __name__ == "__main__":
    unittest.main()

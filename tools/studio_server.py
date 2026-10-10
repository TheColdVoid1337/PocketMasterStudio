#!/usr/bin/env python3
"""Launch PocketMaster Studio locally without exposing private config files.

Standard library only; the HTML is self-contained. Run via START.bat on Windows,
or: python3 tools/studio_server.py [--no-browser] [--port 8765]
"""
from __future__ import annotations

import argparse
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import shutil
import subprocess
import sys
import webbrowser


ROOT = Path(__file__).resolve().parent.parent
HTML = "PocketMasterStudio.html"
BIND_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

import json
import re
import threading
import uuid
from urllib.parse import urlsplit, parse_qs
import hashlib

NAM_DSP_ROOT = ROOT / "tools" / "nam_dsp"
NAM_REFERENCE = NAM_DSP_ROOT / "data" / "nam_reference_di_44100.f32"

def nam_reference_verified(path):
    if not path.is_file() or path.stat().st_size != 12_348_000:
        return False
    sha = hashlib.sha1(b"blob 12348000" + bytes([0]))
    with path.open("rb") as src:
        for block in iter(lambda: src.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest() == "e8a4479f292ad096df1edacdd083f19a72d61987"

NAM_BINARY = NAM_DSP_ROOT / "target" / "release" / ("pocketmaster_nam_dsp.exe" if os.name == "nt" else "pocketmaster_nam_dsp")
NAM_LIMIT = 32 * 1024 * 1024
NAM_SEMAPHORE = threading.BoundedSemaphore(1)
NAM_LOCK = threading.Lock()
NAM_JOBS = {}

def nam_readiness():
    missing = []
    if not NAM_BINARY.is_file():
        missing.append("Build local Rust DSP: cargo build --release --manifest-path tools/nam_dsp/Cargo.toml")
    if not nam_reference_verified(NAM_REFERENCE):
        missing.append("Download verified reference DI: python tools/nam_dsp/fetch_reference.py")
    return {"ready": not missing, "backend": "SonicMaster Rust DSP (local)", "requirements": missing}

def valid_clo_binary(data):
    if len(data) != 8840 or data[:4] != b"VTSI":
        return False
    if int.from_bytes(data[4:8], "little") != 8840:
        return False
    if int.from_bytes(data[20:24], "little") != 8704:
        return False
    if int.from_bytes(data[124:128], "little") != 128:
        return False
    if int.from_bytes(data[128:132], "little") != 128:
        return False
    if int.from_bytes(data[132:136], "little") != 2048:
        return False
    crc = 0xffff
    for value in data[12:]:
        crc ^= value
        for _ in range(8):
            crc = (crc >> 1) ^ (0xa001 if crc & 1 else 0)
    return crc == int.from_bytes(data[8:10], "big")



class StudioHandler(SimpleHTTPRequestHandler):
    """Loopback-only HTML + gated DSP API; never serve private repo files."""

    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=directory or str(ROOT), **kwargs)


    def _nam_send(self, status, content, media_type="application/json"):
        if isinstance(content, (dict, list)):
            content = json.dumps(content).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Cancelled browser request: backend still observes cancellation.

    def _same_origin(self):
        origin = self.headers.get("Origin", "")
        host = self.headers.get("Host", "")
        if not re.fullmatch(r"127\.0\.0\.1:\d{1,5}", host):
            return False
        if origin and origin != "http://" + host:
            return False
        return True

    def do_GET(self):
        if urlsplit(self.path).path == "/api/nam/availability":
            if not self._same_origin():
                self._nam_send(403, {"error": "Loopback origin required"})
                return
            self._nam_send(200, nam_readiness())
            return
        super().do_GET()

    def do_POST(self):
        target = urlsplit(self.path)
        if target.path not in ("/api/nam/convert", "/api/nam/cancel"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not self._same_origin():
            self._nam_send(403, {"error": "Loopback origin required"})
            return
        if self.headers.get("Content-Type", "").split(";")[0] != "application/x-nam":
            self._nam_send(415, {"error": "Expected application/x-nam"})
            return
        if target.path == "/api/nam/cancel":
            job_id = parse_qs(target.query).get("job", [""])[0]
            if not re.fullmatch(r"[0-9a-fA-F-]{36}", job_id):
                self._nam_send(400, {"error": "Invalid conversion ID"})
                return
            with NAM_LOCK:
                job = NAM_JOBS.get(job_id)
                if job is not None:
                    job["cancelled"] = True
                    process = job["process"]
                    if process is not None and process.poll() is None:
                        process.kill()
            self._nam_send(200, {"cancel_requested": job is not None})
            return
        if not nam_readiness()["ready"]:
            self._nam_send(503, {"error": "NAM DSP prerequisites missing", **nam_readiness()})
            return
        size = self.headers.get("Content-Length", "")
        if not size.isdecimal() or int(size) < 1 or int(size) > NAM_LIMIT:
            self._nam_send(413, {"error": "NAM must be 1 byte to 32 MiB"})
            return
        job_id = self.headers.get("X-Conversion-ID", "")
        try:
            if str(uuid.UUID(job_id)) != job_id:
                raise ValueError("Noncanonical UUID")
        except (ValueError, AttributeError):
            self._nam_send(400, {"error": "X-Conversion-ID must be a UUID"})
            return
        if not NAM_SEMAPHORE.acquire(blocking=False):
            self._nam_send(409, {"error": "Another NAM conversion is already running"})
            return
        with NAM_LOCK:
            NAM_JOBS[job_id] = {"process": None, "cancelled": False}
        try:
            raw = self.rfile.read(int(size))
            try:
                model = json.loads(raw.decode("utf-8"))
                arch = model.get("architecture") if isinstance(model, dict) else None
                if arch not in ("WaveNet", "SlimmableContainer"):
                    raise ValueError("Unsupported NAM architecture")
            except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
                self._nam_send(422, {"error": "Invalid NAM: " + str(exc)[:200]})
                return
            process = subprocess.Popen(
                [str(NAM_BINARY), "--reference", str(NAM_REFERENCE)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            with NAM_LOCK:
                job = NAM_JOBS[job_id]
                job["process"] = process
                if job["cancelled"]:
                    process.kill()
            try:
                output, stderr = process.communicate(input=raw, timeout=600)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                self._nam_send(504, {"error": "NAM DSP timed out after 600 s"})
                return
            with NAM_LOCK:
                cancelled = NAM_JOBS[job_id]["cancelled"]
            if cancelled:
                self._nam_send(409, {"error": "NAM conversion cancelled"})
            elif process.returncode != 0:
                msg = stderr.decode("utf-8", "replace")[-600:].strip()
                self._nam_send(422, {"error": "NAM DSP failed: " + (msg or "worker process failed")})
            elif not valid_clo_binary(output):
                self._nam_send(500, {"error": "DSP produced invalid CLO layout or CRC"})
            else:
                self._nam_send(200, output, "application/octet-stream")
        except OSError as exc:
            self._nam_send(503, {"error": "Cannot launch local DSP: " + str(exc)[:200]})
        finally:
            with NAM_LOCK:
                NAM_JOBS.pop(job_id, None)
            NAM_SEMAPHORE.release()

    def send_head(self):
        # We only need this single self-contained HTML. Never expose local
        # config/studio_state.json or any other project files over HTTP.
        from urllib.parse import urlsplit

        requested = urlsplit(self.path).path
        if requested not in ("/", "/" + HTML):
            self.send_error(HTTPStatus.NOT_FOUND, "Only PocketMasterStudio.html is served")
            return None
        self.path = "/" + HTML
        return super().send_head()

    def end_headers(self):
        # Avoid showing an outdated HTML after Git pulls / app upgrades.
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, format, *args):
        print("[Studio HTTP] " + format % args, flush=True)


def make_server(port: int = DEFAULT_PORT, root: Path = ROOT) -> ThreadingHTTPServer:
    root = Path(root).resolve()
    if not (root / HTML).is_file():
        raise FileNotFoundError(f"Missing {root / HTML}. Run this script from a full Studio checkout.")
    handler = partial(StudioHandler, directory=str(root))
    # Bound explicitly to 127.0.0.1, never 0.0.0.0 or LAN interfaces.
    return ThreadingHTTPServer((BIND_HOST, port), handler)


def find_chrome() -> str | None:
    candidates = [shutil.which("chrome.exe"), shutil.which("chrome"),
                  shutil.which("google-chrome"), shutil.which("google-chrome-stable")]
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe") as key:
                candidates.append(winreg.QueryValueEx(key, None)[0])
        except (OSError, ImportError):
            pass
        for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = os.environ.get(env)
            if base:
                candidates.append(os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"))
    return next((str(p) for p in candidates if p and (
        shutil.which(p) or Path(p).is_file())), None)


def open_browser(url: str) -> None:
    chrome = find_chrome()
    if chrome:
        try:
            subprocess.Popen([chrome, "--new-tab", url],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            print("[Studio] Opened Google Chrome.", flush=True)
            return
        except OSError as exc:
            print(f"[Studio] Chrome launch failed: {exc}", flush=True)
    print("[Studio] Google Chrome not found. Trying the default browser.", flush=True)
    if not webbrowser.open_new_tab(url):
        print(f"[Studio] Open this URL manually in Chrome: {url}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PocketMaster Studio private local server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"Loopback HTTP port (default: {DEFAULT_PORT})")
    parser.add_argument("--no-browser", action="store_true",
                        help="Keep server running without opening a browser")
    args = parser.parse_args(argv)
    if args.port < 1 or args.port > 65535:
        parser.error("--port must be between 1 and 65535")
    try:
        server = make_server(args.port)
    except OSError as exc:
        print(f"[Studio] Could not start on {BIND_HOST}:{args.port}: {exc}", file=sys.stderr)
        print("[Studio] If another instance is running, close its terminal first.", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"[Studio] {exc}", file=sys.stderr)
        return 1

    url = f"http://{BIND_HOST}:{server.server_port}/{HTML}"
    try:
        print("[Studio] Void's MOD local server", flush=True)
        print(f"[Studio] Serving ONLY {HTML} from: {ROOT}", flush=True)
        print(f"[Studio] URL: {url}", flush=True)
        print("[Studio] Leave this window open; press Ctrl+C to stop.", flush=True)
        print("[Studio] Your private config/ files are never served over HTTP.", flush=True)
        if not args.no_browser:
            open_browser(url)
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        print("\n[Studio] Stopped.", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

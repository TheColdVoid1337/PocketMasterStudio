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


class StudioHandler(SimpleHTTPRequestHandler):
    """Read-only, loopback-only HTML server; do NOT serve config/ or .git/."""

    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=directory or str(ROOT), **kwargs)

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

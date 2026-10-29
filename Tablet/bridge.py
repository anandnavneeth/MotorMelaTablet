"""Local, opt-in tablet bridge. No dependencies, editor APIs, or device commands.

The game listens on localhost:18741 only with -TabletTuning. USB uses adb reverse
tcp:18740 tcp:18740. Pass --lan to permit your private-network tablet to pair.
"""
import argparse
import http.cookies
import ipaddress
import json
import mimetypes
import secrets
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAX_BODY = 262144


class Bridge(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, upstream="http://127.0.0.1:18741/tuning"):
        super().__init__(address, Handler)
        self.upstream = upstream
        self.pin = f"{secrets.randbelow(1000000):06d}"
        self.token = secrets.token_urlsafe(32)
        self.failed = {}
        self.lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server_version = "HandlingLab/1"

    def log_message(self, *_):
        pass  # Never log pairing tokens or tuning payloads.

    def send_data(self, data, status=200, content_type="application/json", cookie=None):
        if not isinstance(data, bytes):
            data = json.dumps(data, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def origin_ok(self):
        # Reject DNS rebinding and cross-origin writes. App and browser are same origin.
        host = self.headers.get("Host", "").split(":")[0]
        try:
            allowed = ipaddress.ip_address(host).is_private
        except ValueError:
            allowed = host == "localhost"
        origin = self.headers.get("Origin")
        return allowed and (origin is None or origin == "http://" + self.headers.get("Host", ""))

    def authenticated(self):
        c = http.cookies.SimpleCookie()
        try:
            c.load(self.headers.get("Cookie", ""))
            return "lab" in c and secrets.compare_digest(c["lab"].value, self.server.token)
        except http.cookies.CookieError:
            return False

    def do_GET(self):
        if not self.origin_ok():
            return self.send_data({"ok": False, "error": "Invalid origin"}, 403)
        path = self.path.split("?", 1)[0]
        if path == "/health":
            return self.send_data({"ok": True, "service": "handling-tablet", "schema": 1})
        files = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}
        if path not in files:
            return self.send_data({"ok": False, "error": "Not found"}, 404)
        file = ROOT / "web" / files[path]
        return self.send_data(file.read_bytes(), content_type=mimetypes.guess_type(file.name)[0] or "text/plain")

    def do_POST(self):
        if not self.origin_ok():
            return self.send_data({"ok": False, "error": "Invalid origin"}, 403)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                raise ValueError("Invalid request size")
            body = self.rfile.read(length)
            obj = json.loads(body, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite number")))
            if not isinstance(obj, dict):
                raise ValueError("Expected object")
        except (ValueError, UnicodeError):
            return self.send_data({"ok": False, "error": "Invalid JSON or size"}, 400)
        if self.path == "/pair":
            peer = self.client_address[0]
            with self.server.lock:
                attempts, since = self.server.failed.get(peer, (0, time.monotonic()))
                if time.monotonic() - since > 60:
                    attempts, since = 0, time.monotonic()
                if attempts >= 5:
                    return self.send_data({"ok": False, "error": "Wait one minute before trying again"}, 429)
                pin = obj.get("pin", "")
                if not isinstance(pin, str) or not secrets.compare_digest(pin, self.server.pin):
                    self.server.failed[peer] = (attempts + 1, since)
                    return self.send_data({"ok": False, "error": "Incorrect pairing code"}, 403)
                self.server.failed.pop(peer, None)
            return self.send_data({"ok": True}, cookie=f"lab={self.server.token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400")
        if self.path != "/api" or not self.authenticated():
            return self.send_data({"ok": False, "error": "Pair with this PC first", "pair": True}, 401)
        if obj.get("action") not in {"catalog", "state", "apply", "undo", "defaults", "save", "load"}:
            return self.send_data({"ok": False, "error": "Unknown action"}, 400)
        try:
            request = urllib.request.Request(self.server.upstream, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=2) as response:
                result = response.read(MAX_BODY * 8)
            json.loads(result)
            self.send_data(result)
        except (OSError, ValueError, urllib.error.URLError):
            self.send_data({"ok": False, "error": "Game unavailable. Start a Tablet Lab driving session on the PC."}, 503)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--port", type=int, default=18740)
    parser.add_argument("--state", type=Path, default=ROOT.parent / "Saved/Tablet/connection.json")
    args = parser.parse_args()
    server = Bridge(("0.0.0.0" if args.lan else "127.0.0.1", args.port))
    args.state.parent.mkdir(parents=True, exist_ok=True)
    args.state.write_text(json.dumps({"pin": server.pin, "port": args.port, "lan": args.lan}), encoding="utf-8")
    print(f"Handling Lab on port {args.port}. Pairing code: {server.pin}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

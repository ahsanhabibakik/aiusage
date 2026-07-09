"""Loopback-only HTTP API: GET /v1/usage, GET /v1/usage/<providerId>, GET / (dashboard)."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import DEFAULT_PORT
from .providers import claude as claude_provider
from .dashboard import DASHBOARD_HTML

PROVIDERS = {
    "claude": claude_provider,
}

_cache_lock = threading.Lock()
_cache = {}  # providerId -> snapshot dict
_cache_time = {}
# Matches tray.py's poll interval and OpenUsage's own default -- keeps the
# request rate against api.anthropic.com's usage endpoint conservative.
CACHE_TTL_SECONDS = 300


def _get_snapshot(provider_id: str):
    with _cache_lock:
        cached = _cache.get(provider_id)
        age = time.time() - _cache_time.get(provider_id, 0)
        if cached and age < CACHE_TTL_SECONDS:
            return cached
    module = PROVIDERS.get(provider_id)
    if not module:
        return None
    snapshot = module.fetch_snapshot().to_dict()
    with _cache_lock:
        _cache[provider_id] = snapshot
        _cache_time[provider_id] = time.time()
    return snapshot


def refresh_all():
    for provider_id in PROVIDERS:
        try:
            module = PROVIDERS[provider_id]
            snapshot = module.fetch_snapshot().to_dict()
            with _cache_lock:
                _cache[provider_id] = snapshot
                _cache_time[provider_id] = time.time()
        except Exception:
            continue


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # keep stdout quiet; use --verbose flag territory later if needed

    def _send_json(self, status: int, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            body = DASHBOARD_HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/v1/usage":
            results = []
            for provider_id in PROVIDERS:
                snap = _get_snapshot(provider_id)
                if snap:
                    results.append(snap)
            self._send_json(200, results)
            return

        if self.path.startswith("/v1/usage/"):
            provider_id = self.path.rsplit("/", 1)[-1]
            if provider_id not in PROVIDERS:
                self._send_json(404, {"error": "provider_not_found"})
                return
            snap = _get_snapshot(provider_id)
            if not snap:
                self.send_response(204)
                self.end_headers()
                return
            self._send_json(200, snap)
            return

        self._send_json(404, {"error": "not_found"})


def run_server(port: int = DEFAULT_PORT):
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:
        print(f"aiusage: port {port} already in use — another aiusage instance is probably already serving it. Skipping.")
        return
    print(f"aiusage: serving http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

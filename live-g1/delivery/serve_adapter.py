#!/usr/bin/env python3
"""LIVE-G1 read-only HTTP service.

Serves the adapter's status/snapshot/history over HTTP so the dashboard
transport (window.LIVE_G1) can refresh against live data.

Read-only: no writes, no mutations, no provider polling beyond what
live_g1_adapter.py already does.

Usage:
    python3 serve_adapter.py [--port 8899]

Endpoints:
    GET /adapter/v1/status
    GET /adapter/v1/snapshot
    GET /adapter/v1/history?limit=N
"""
import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

def run_adapter(*args):
    """Run the adapter CLI and return parsed JSON. No caching."""
    here = __import__('pathlib').Path(__file__).parent
    adapter = here.parent / "live_g1_adapter.py"
    cmd = [sys.executable, str(adapter)] + list(args)
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        raise RuntimeError(f"adapter failed: {out.stderr[:200]}")
    return json.loads(out.stdout)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # quiet

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path == "/adapter/v1/status":
                self._json(run_adapter("status"))
            elif u.path == "/adapter/v1/snapshot":
                self._json(run_adapter("snapshot"))
            elif u.path == "/adapter/v1/history":
                q = parse_qs(u.query)
                limit = q.get("limit", ["50"])[0]
                self._json(run_adapter("history", "--limit", str(limit)))
            elif u.path == "/adapter/v1/heatmap":
                q = parse_qs(u.query)
                limit = q.get("limit", ["50"])[0]
                self._json(run_adapter("heatmap", "--limit", str(limit)))
            else:
                self._json({"error": "not found"}, 404)
        except Exception as e:
            self._json({"error": str(e)[:200]}, 500)

def main():
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8899
    srv = HTTPServer(("127.0.0.1", port), Handler)
    print(f"live-g1 read-only service on http://127.0.0.1:{port}/adapter/v1", flush=True)
    srv.serve_forever()

if __name__ == "__main__":
    main()

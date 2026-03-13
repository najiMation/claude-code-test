#!/usr/bin/env python3
"""Local proxy + static file server for Scribe.

Routes:
  GET /             → serves index.html
  GET /static/<f>   → serves any file in project dir
  GET /api/chat?message=... → proxies to n8n webhook, returns JSON
"""

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

PORT = 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load .env file if present (stdlib only, no pip required)
_env_path = os.path.join(BASE_DIR, ".env")
if os.path.isfile(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

N8N_URL = os.environ.get("N8N_WEBHOOK_URL", "")
if not N8N_URL:
    print("WARNING: N8N_WEBHOOK_URL is not set. Set it in .env or as an environment variable.")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parsed.query

        if path == "/" or path == "/index.html":
            self._serve_file("index.html", "text/html; charset=utf-8")

        elif path.startswith("/static/"):
            filename = path[len("/static/"):]
            self._serve_file(filename, None)

        elif path == "/api/chat":
            self._proxy_chat(query)

        else:
            self.send_error(404, "Not found")

    def _serve_file(self, filename, content_type):
        filepath = os.path.join(BASE_DIR, filename)
        if not os.path.isfile(filepath):
            self.send_error(404, f"File not found: {filename}")
            return
        # Guess content type if not provided
        if content_type is None:
            ext = os.path.splitext(filename)[1].lower()
            content_type = {
                ".html": "text/html; charset=utf-8",
                ".css":  "text/css; charset=utf-8",
                ".js":   "application/javascript; charset=utf-8",
                ".json": "application/json",
                ".png":  "image/png",
                ".jpg":  "image/jpeg",
                ".svg":  "image/svg+xml",
            }.get(ext, "application/octet-stream")

        with open(filepath, "rb") as f:
            data = f.read()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _proxy_chat(self, query):
        params = parse_qs(query)
        message = params.get("message", [""])[0]

        n8n_url = f"{N8N_URL}?message={quote(message)}"
        print(f"[proxy] → {n8n_url}")

        try:
            req = Request(n8n_url, headers=BROWSER_HEADERS)
            with urlopen(req, timeout=30) as resp:
                body = resp.read()
                content_type = resp.headers.get("Content-Type", "application/json")
        except HTTPError as e:
            body = e.read()
            content_type = e.headers.get("Content-Type", "application/json")
            self.send_response(e.code)
            self.send_header("Content-Type", content_type)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        except URLError as e:
            error_body = json.dumps({"error": str(e)}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(error_body)))
            self.end_headers()
            self.wfile.write(error_body)
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        print(f"[proxy] ← {len(body)}b  {content_type}")


if __name__ == "__main__":
    server = HTTPServer(("", PORT), Handler)
    print(f"Serving on http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")

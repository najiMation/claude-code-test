import json
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

N8N_URL = os.environ.get("N8N_WEBHOOK_URL", "")

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        message = parse_qs(parsed.query).get("message", [""])[0]
        n8n_url = f"{N8N_URL}?message={quote(message)}"
        try:
            req = Request(n8n_url, headers=BROWSER_HEADERS)
            with urlopen(req, timeout=30) as resp:
                body = resp.read()
                ct = resp.headers.get("Content-Type", "application/json")
        except HTTPError as e:
            body = e.read()
            ct = e.headers.get("Content-Type", "application/json")
            self._respond(e.code, ct, body)
            return
        except URLError as e:
            body = json.dumps({"error": str(e)}).encode()
            self._respond(502, "application/json", body)
            return
        self._respond(200, ct, body)

    def _respond(self, code, ct, body):
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

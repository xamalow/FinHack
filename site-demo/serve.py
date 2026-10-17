"""Serve the simulated publisher website locally.

Usage: python site-demo/serve.py [--port 8001] [--gateway http://localhost:8000]

Serves site-demo/public. /.well-known/ai-data.json is proxied to the
gateway manifest, so the site shows it only once the publisher has
activated (the gateway answers 404 before that). sitemap.xml and
robots.txt are rewritten on the fly with the host actually used.
"""
import argparse
import os
import re
import urllib.error
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PUBLIC = Path(__file__).parent / "public"
MANIFEST_PATH = "/.well-known/ai-data.json"
ABSOLUTE_URL = re.compile(r"https?://[^/\s<]+")


class SiteHandler(SimpleHTTPRequestHandler):
    gateway = "http://localhost:8000"

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == MANIFEST_PATH:
            return self.proxy_manifest()
        if path in ("/sitemap.xml", "/robots.txt"):
            return self.rewritten(path)
        return super().do_GET()

    def proxy_manifest(self):
        try:
            with urllib.request.urlopen(self.gateway.rstrip("/") + MANIFEST_PATH, timeout=3) as res:
                body, status = res.read(), res.status
        except urllib.error.HTTPError as err:
            body, status = b'{"error": "not activated"}', err.code
        except (urllib.error.URLError, TimeoutError):
            body, status = b'{"error": "not activated"}', 404
        self.send_bytes(status, body, "application/json")

    def rewritten(self, path):
        text = (PUBLIC / path.lstrip("/")).read_text(encoding="utf-8")
        here = f"http://{self.headers.get('Host', 'localhost')}"
        ctype = "application/xml" if path.endswith(".xml") else "text/plain"
        self.send_bytes(200, ABSOLUTE_URL.sub(here, text).encode("utf-8"), ctype)

    def send_bytes(self, status, body, ctype):
        self.send_response(status)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--gateway", default=os.environ.get("GATEWAY_URL", "http://localhost:8000"))
    args = ap.parse_args()
    SiteHandler.gateway = args.gateway
    server = ThreadingHTTPServer(("0.0.0.0", args.port), partial(SiteHandler, directory=str(PUBLIC)))
    print(f"Simulated site on http://localhost:{args.port} (manifest proxied to {args.gateway})")
    server.serve_forever()


if __name__ == "__main__":
    main()

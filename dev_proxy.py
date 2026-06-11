"""Simple reverse proxy for dev: serves frontend static + proxies /api to backend."""
import http.server
import urllib.request
import urllib.error
import os
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5173
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")
BACKEND = "http://localhost:8000"


class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def end_headers(self):
        # Prevent browser caching so fresh builds always load
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._proxy()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            self._proxy()
        else:
            super().do_POST()

    def do_PATCH(self):
        if self.path.startswith("/api/"):
            self._proxy()
        else:
            super().do_PATCH()

    def do_PUT(self):
        if self.path.startswith("/api/"):
            self._proxy()
        else:
            super().do_PUT()

    def do_DELETE(self):
        if self.path.startswith("/api/"):
            self._proxy()
        else:
            super().do_DELETE()

    def _proxy(self):
        url = BACKEND + self.path
        body = None
        content_len = self.headers.get("Content-Length")
        if content_len:
            body = self.rfile.read(int(content_len))

        req = urllib.request.Request(
            url,
            data=body,
            headers={k: v for k, v in self.headers.items() if k.lower() not in ("host",)},
            method=self.command,
        )

        try:
            resp = urllib.request.urlopen(req, timeout=60)
            self.send_response(resp.status)
            for k, v in resp.headers.items():
                if k.lower() not in ("transfer-encoding", "connection"):
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(resp.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.end_headers()
            self.wfile.write(e.read())


if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), ProxyHandler)
    print(f"Dev proxy on http://localhost:{PORT} -> backend {BACKEND}")
    server.serve_forever()

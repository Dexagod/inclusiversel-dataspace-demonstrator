"""Serve the profile form (default http://127.0.0.1:8095). POST /generate turns a state into markdown.

Nothing is stored or logged; the state lives in the browser until the user saves it. Paths are relative,
so the page also works behind a reverse proxy under a prefix such as /profile/.
"""

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from generate import CROSSWALK, generate

HERE = Path(__file__).parent
# The page uses the viewer's stylesheet and icon, so both interfaces look alike without a copy.
VIEWER_STATIC = Path(os.environ.get("VIEWER_STATIC", HERE.parent.parent / "viewer" / "static"))
# Link to the viewer. Unset: /viewer/ next to /profile/ behind a reverse proxy, else the local viewer port.
VIEWER_URL = os.environ.get("VIEWER_URL") or None
SHARED = {"/styles.css": ("styles.css", "text/css"), "/favicon.svg": ("favicon.svg", "image/svg+xml")}


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: str | bytes, ctype: str) -> None:
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8" if ctype.startswith("text") or "json" in ctype else ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            viewer = VIEWER_URL or ("../viewer/" if self.headers.get("X-Forwarded-For") else "http://localhost:8090/")
            page = (HERE / "form.html").read_text(encoding="utf-8").replace("{{VIEWER_URL}}", viewer)
            self._send(200, page, "text/html")
        elif path == "/crosswalk.json":
            self._send(200, json.dumps(CROSSWALK, ensure_ascii=False), "application/json")
        elif path == "/health":
            self._send(200, "ok", "text/plain")
        elif path in SHARED:
            name, ctype = SHARED[path]
            file = VIEWER_STATIC / name
            if file.is_file():
                self._send(200, file.read_bytes(), ctype)
            else:
                self._send(404, f"{name} not found; set VIEWER_STATIC to the viewer's static folder", "text/plain")
        else:
            self._send(404, "not found", "text/plain")

    do_HEAD = do_GET

    def do_POST(self):
        if self.path != "/generate":
            return self._send(404, "not found", "text/plain")
        length = int(self.headers.get("Content-Length") or 0)
        if length > 100_000:
            return self._send(413, "state too large", "text/plain")
        try:
            state = json.loads(self.rfile.read(length) or b"{}")
            self._send(200, generate(state), "text/markdown")
        except (ValueError, TypeError, AttributeError) as e:
            self._send(400, f"invalid state: {e}", "text/plain")

    def log_message(self, *args):  # no request logging: states hold health data
        pass


def make_server(port: int, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("PROFILE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8095")))
    args = parser.parse_args()
    print(f"Profile context tool on http://{args.host}:{args.port}", flush=True)
    make_server(args.port, args.host).serve_forever()

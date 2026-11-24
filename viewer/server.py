"""Local, read-only viewer. Standard library only; no keys or source records."""

import argparse
import json
import os
import re
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from call_logs import read_snapshot

STATIC = Path(__file__).parent / "static"
MAX_RESPONSE = 16 * 1024 * 1024
USER_AGENT = "accessibility-dataspace-demo/0.1 (open research demonstrator)"
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/logs.mjs": ("logs.mjs", "text/javascript; charset=utf-8"),
    "/model.mjs": ("model.mjs", "text/javascript; charset=utf-8"),
    "/markdown.mjs": ("markdown.mjs", "text/javascript; charset=utf-8"),
    "/vendor/markdown-it.mjs": ("vendor/markdown-it.mjs", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
}
ROUTES = {
    ("catalog", "/health"): set(),
    ("catalog", "/catalogs"): set(),
    ("catalog", "/datasets"): {"q", "spatial", "language", "catalog"},
    ("catalog", "/catalog"): {"format"},
    ("vochub", "/health"): set(),
    ("vochub", "/documents"): set(),
    ("vochub", "/context"): set(),
    ("vochub", "/search"): {"q", "k", "language", "tag"},
}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def base_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("Upstream URLs must be HTTP(S) base URLs without credentials, query or fragment")
    return value.rstrip("/")


def proxy_route(target):
    """Return only an explicitly allowed upstream path; never accept a caller URL."""
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or parsed.fragment or len(parsed.query) > 8000:
        raise ValueError("Invalid request URL")
    match = re.fullmatch(r"/api/(catalog|vochub)(/.*)", parsed.path)
    if not match:
        raise LookupError("Unknown viewer endpoint")
    service, path = match.groups()
    allowed = ROUTES.get((service, path))
    if service == "catalog" and re.fullmatch(r"/datasets/[a-z0-9][a-z0-9-]{1,62}", path):
        allowed = set()
    if allowed is None:
        raise LookupError("This endpoint is not available in the read-only viewer")
    query = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=12)
    if set(query) - allowed or any(len(values) != 1 for values in query.values()):
        raise ValueError("Unsupported or repeated query parameter")
    query = {key: values[0] for key, values in query.items()}
    if path == "/catalog" and query.get("format", "turtle") not in {"turtle", "jsonld"}:
        raise ValueError("Choose turtle or jsonld")
    if path == "/search":
        if not 2 <= len(query.get("q", "").strip()) <= 2000:
            raise ValueError("Enter a question between 2 and 2000 characters")
        if not query.get("k", "5").isdigit() or not 1 <= int(query.get("k", "5")) <= 50:
            raise ValueError("Result count must be between 1 and 50")
    suffix = "?" + urlencode(query) if query else ""
    return service, path + suffix


def make_handler(catalog_url, vochub_url, timeout=45, log_file=None):
    upstreams = {"catalog": base_url(catalog_url), "vochub": base_url(vochub_url)}
    opener = build_opener(ProxyHandler({}), NoRedirect())

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Queries can contain user questions: do not log their contents.
            if args and isinstance(args[0], str):
                print(f"viewer: {self.command} {urlsplit(self.path).path} {args[1] if len(args) > 1 else ''}", flush=True)

        def respond(self, status, data, content_type="application/json; charset=utf-8"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
            if status == 405:
                self.send_header("Allow", "GET, HEAD")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def error(self, status, message):
            self.respond(status, json.dumps({"error": message}).encode())

        def do_GET(self):
            parsed = urlsplit(self.path)
            if self.path == '/api/logs':
                try:
                    self.respond(200, json.dumps(read_snapshot(log_file)).encode())
                except (OSError, ValueError, UnicodeError):
                    self.error(502, 'Cannot read the log snapshot. Check the collector and its file permissions or size.')
                return
            if not parsed.scheme and not parsed.netloc and parsed.path in ASSETS:
                name, kind = ASSETS[parsed.path]
                self.respond(200, (STATIC / name).read_bytes(), kind)
                return
            if self.path == "/health":
                self.respond(200, b'{"status":"ok"}')
                return
            try:
                service, path = proxy_route(self.path)
            except LookupError as exc:
                self.error(404, str(exc))
                return
            except ValueError as exc:
                self.error(400, str(exc))
                return
            try:
                req = Request(upstreams[service] + path, headers={"User-Agent": USER_AGENT, "Accept": "application/json, text/turtle, application/ld+json"})
                with opener.open(req, timeout=timeout) as response:
                    data = response.read(MAX_RESPONSE + 1)
                    if len(data) > MAX_RESPONSE:
                        self.error(502, "Service response is too large to display")
                        return
                    kind = response.headers.get_content_type()
                    if kind not in {"application/json", "application/ld+json", "text/turtle"}:
                        self.error(502, "Service returned an unexpected response format")
                        return
                    self.respond(200, data, kind + "; charset=utf-8")
            except HTTPError as exc:
                status = exc.code if 400 <= exc.code < 500 else 502
                exc.close()
                self.error(status, f"The {service} service returned HTTP {exc.code}. Refresh or check the service.")
            except (TimeoutError, socket.timeout):
                self.error(504, f"The {service} service took too long to respond. Please try again.")
            except (URLError, OSError):
                self.error(502, f"Cannot reach the {service} service. Start the data space and check the viewer's upstream URL.")

        do_HEAD = do_GET

        def readonly(self):
            self.error(405, "The viewer is read-only; only GET and HEAD are allowed")

        do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = readonly

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("VIEWER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("VIEWER_PORT", "8090")))
    args = parser.parse_args()
    handler = make_handler(os.environ.get("CATALOG_URL", "http://localhost:8001"),
                           os.environ.get("VOCHUB_URL", "http://localhost:8002"),
                           log_file=os.environ.get('VIEWER_LOG_FILE'))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Data space viewer: http://{args.host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

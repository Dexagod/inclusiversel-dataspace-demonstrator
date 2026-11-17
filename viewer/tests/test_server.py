"""Offline HTTP contract tests. All data is fictional; no external requests."""
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import base_url, make_handler, proxy_route

CATALOGS = [{"id": "belgium", "country": "BEL", "title": "Accessibility data space catalog: Belgium", "datasets": ["fictional-venues"]},
            {"id": "france", "country": "FRA", "title": "Accessibility data space catalog: France", "datasets": ["fictional-museums"]},
            {"id": "belgium-mobility", "country": "BEL", "title": "Accessibility data space catalog: Belgium, mobility", "datasets": ["fictional-parking"]},
            {"id": "france-mobility", "country": "FRA", "title": "Accessibility data space catalog: France, mobility", "datasets": []}]
DATASETS = [{"id": "fictional-venues", "title": "Fictional accessible venues", "catalog": "belgium", "publisher": {"name": "Example research publisher", "url": "https://example.org"}, "description": "Fictional public fixture for interface verification. No real places.", "spatial": ["Example region"], "languages": ["nl", "en"], "licence": None, "licence_note": "Fictional fixture: reuse terms not confirmed", "endpoint_url": "http://example.invalid/venues", "openapi_url": "http://example.invalid/openapi.json", "themes": ["accessibility"], "modified": "2026-11-16T10:00:00Z"},
            {"id": "fictional-museums", "title": "Fictional museum accessibility", "catalog": "france", "publisher": {"name": "Example cultural publisher"}, "description": "Fictional museum descriptions.", "spatial": ["Example city"], "languages": ["fr"], "licence": "https://example.org/licence", "themes": ["accessibility"]},
            {"id": "fictional-parking", "title": "Fictional adapted parking spaces", "catalog": "belgium-mobility", "publisher": {"name": "Example mobility publisher"}, "description": "Fictional parking metadata.", "spatial": ["Example region"], "languages": ["nl"], "licence": "https://example.org/licence", "themes": ["mobility"]}]
DOCUMENTS = [{"doc_id": "fixture-guide", "title": "Fictional accessibility terminology guide", "url": "https://example.org/guide", "kind": "pdf", "language": "en", "tags": ["criteria", "labels"], "licence": "https://example.org/licence", "ingested_at": "2026-11-16T09:00:00Z", "chunks": 12},
             {"doc_id": "fixture-schema", "title": "Fictional field documentation", "url": "https://example.org/schema", "kind": "html", "language": "fr", "tags": ["schema"], "licence": None, "chunks": 8}]
PASSAGES = [{"doc_id": "fixture-guide", "title": DOCUMENTS[0]["title"], "url": DOCUMENTS[0]["url"], "text": "Fictional example: a recorded measurement describes one feature of a place. Missing measurements remain unknown; they do not establish accessibility.", "score": 0.7132, "page": 3, "heading": "Interpreting measurements", "language": "en", "tags": ["criteria"], "licence": DOCUMENTS[0]["licence"]}]


class Stub(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, *_args):
        pass

    def do_GET(self):
        self.requests.append(self.path)
        path = urlsplit(self.path).path
        query = parse_qs(urlsplit(self.path).query)
        if path == "/datasets/redirect":
            self.send_response(302)
            self.send_header("Location", "/should-not-follow")
            self.end_headers()
            return
        if path == "/datasets/failure":
            self.send_error(503)
            return
        if path == "/datasets/missing":
            self.send_error(404)
            return
        if path == "/datasets/html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<script>not allowed</script>")
            return
        data = {"/health": {"status": "ok"}, "/catalogs": CATALOGS, "/datasets": DATASETS, "/documents": DOCUMENTS, "/search": [] if query.get("tag") == ["empty"] else PASSAGES}.get(path)
        if path.startswith("/datasets/"):
            data = next((d for d in DATASETS if path.endswith('/' + d['id'])), None)
        if path == "/catalog":
            kind = "application/ld+json" if query.get("format") == ["jsonld"] else "text/turtle"
            body = b'[{"@id":"https://example.org/catalog"}]' if kind == "application/ld+json" else b"@prefix dcat: <http://www.w3.org/ns/dcat#> ."
        else:
            kind, body = "application/json", json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.end_headers()
        self.wfile.write(body)


def start_server(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}"


class ViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upstream, cls.upstream_url = start_server(Stub)
        cls.viewer, cls.url = start_server(make_handler(cls.upstream_url, cls.upstream_url, timeout=1))

    @classmethod
    def tearDownClass(cls):
        for server in [cls.viewer, cls.upstream]:
            server.shutdown()
            server.server_close()

    def request(self, path, method="GET"):
        try:
            response = urlopen(Request(self.url + path, method=method), timeout=3)
        except HTTPError as exc:
            response = exc
        with response:
            return response.status, response.headers, response.read()

    def test_assets_and_health(self):
        for path in ["/", "/app.js", "/styles.css", "/model.mjs", "/favicon.svg", "/health"]:
            status, headers, body = self.request(path)
            self.assertEqual(status, 200)
            self.assertTrue(body)
            self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(self.request("/", "HEAD")[2], b"")

    def test_metadata_and_full_registration(self):
        for path, expected in [("/api/catalog/catalogs", CATALOGS), ("/api/catalog/datasets", DATASETS), ("/api/vochub/documents", DOCUMENTS), ("/api/catalog/datasets/fictional-venues", DATASETS[0])]:
            status, _, body = self.request(path)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body), expected)

    def test_rag_parameters_and_citations_are_preserved(self):
        path = "/api/vochub/search?q=What+does+A%2B+%26+B+mean%3F&k=3&language=en&tag=criteria"
        status, _, body = self.request(path)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), PASSAGES)
        self.assertEqual(parse_qs(urlsplit(Stub.requests[-1]).query), {"q": ["What does A+ & B mean?"], "k": ["3"], "language": ["en"], "tag": ["criteria"]})
        self.assertEqual(json.loads(self.request('/api/vochub/search?q=unknown&tag=empty')[2]), [])

    def test_dcat_exports(self):
        for fmt, kind in [("turtle", "text/turtle"), ("jsonld", "application/ld+json")]:
            status, headers, _ = self.request('/api/catalog/catalog?format=' + fmt)
            self.assertEqual(status, 200)
            self.assertIn(kind, headers['Content-Type'])

    def test_writes_never_reach_upstream(self):
        before = len(Stub.requests)
        for method in ['POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS']:
            self.assertEqual(self.request('/api/catalog/datasets', method)[0], 405)
        self.assertEqual(len(Stub.requests), before)

    def test_unknown_paths_and_invalid_queries_never_reach_upstream(self):
        before = len(Stub.requests)
        for path in ['/../server.py', '/server.py', '/api/catalog/sparql', '/api/vochub/documents/url', '/api/catalog/datasets/%2e%2e', '/api/catalog//example.org']:
            self.assertEqual(self.request(path)[0], 404, path)
        for path in ['/api/catalog/datasets?url=https://example.org', '/api/catalog/catalog?format=html', '/api/vochub/search?q=x', '/api/vochub/search?q=ok&k=51', '/api/vochub/search?q=ok&q=again', '/api/vochub/search?q=ok&k=one']:
            self.assertEqual(self.request(path)[0], 400, path)
        self.assertEqual(len(Stub.requests), before)

    def test_upstream_errors_and_redirects(self):
        for name, code in [('redirect', 502), ('failure', 502), ('missing', 404), ('html', 502)]:
            self.assertEqual(self.request('/api/catalog/datasets/' + name)[0], code)
        self.assertNotIn('/should-not-follow', Stub.requests)
        with patch('urllib.request.OpenerDirector.open', side_effect=TimeoutError):
            self.assertEqual(self.request_direct('/api/catalog/health')[0], 504)
        with patch('urllib.request.OpenerDirector.open', side_effect=OSError):
            self.assertEqual(self.request_direct('/api/catalog/health')[0], 502)

    def request_direct(self, path):
        # http.client avoids patching the test client's own urllib request.
        from http.client import HTTPConnection
        conn = HTTPConnection('127.0.0.1', self.viewer.server_port, timeout=3)
        conn.request('GET', path)
        response = conn.getresponse()
        result = response.status, response.read()
        conn.close()
        return result

    def test_response_size_limit(self):
        with patch('server.MAX_RESPONSE', 10):
            self.assertEqual(self.request('/api/catalog/datasets')[0], 502)

    def test_url_configuration_and_absolute_request_rejection(self):
        for value in ['file:///etc/passwd', 'https://user:secret@example.org', 'http://example.org?q=x']:
            with self.assertRaises(ValueError):
                base_url(value)
        with self.assertRaises(ValueError):
            proxy_route('https://example.org/api/catalog/health')
        self.assertEqual(base_url('http://catalog:8000/'), 'http://catalog:8000')


if __name__ == '__main__':
    unittest.main()

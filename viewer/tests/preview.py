"""Explicit fictional browser QA server; never used by the normal viewer."""
from http.server import ThreadingHTTPServer
from test_server import Stub, make_handler, start_server

upstream, upstream_url = start_server(Stub)
viewer = ThreadingHTTPServer(('127.0.0.1', 8091), make_handler(upstream_url, upstream_url))
print('FICTIONAL FIXTURE PREVIEW: http://localhost:8091', flush=True)
try:
    viewer.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    viewer.server_close()
    upstream.shutdown()
    upstream.server_close()

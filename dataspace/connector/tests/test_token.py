from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from server import require_token

ok = lambda _r: PlainTextResponse("ok")
client = TestClient(require_token(Starlette(routes=[Route("/mcp", ok, methods=["POST"]), Route("/health", ok)]), "s3cret"))


def test_bearer_token_required_except_health():
    assert client.post("/mcp").status_code == 401
    assert client.post("/mcp", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.post("/mcp", headers={"Authorization": "s3cret"}).status_code == 401
    assert client.post("/mcp", headers={"Authorization": "Bearer s3cret"}).text == "ok"
    assert client.get("/health").status_code == 200

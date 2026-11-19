"""MCP connector: the single, read-only door between a user agent and the data space."""

import hmac
import json
import os
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
import yaml
from mcp.server.mcpserver import MCPServer
from starlette.responses import JSONResponse

from openapi_calls import CallError, build_request, condense, load_credentials, parse_url_map, reachable

CATALOG = os.environ.get("CATALOG_URL", "http://localhost:8001").rstrip("/")
VOCHUB = os.environ.get("VOCHUB_URL", "http://localhost:8002").rstrip("/")
# Registered source URLs may only resolve where the catalog runs (e.g. Docker names); map them for this connector.
SOURCE_URL_MAP = parse_url_map(os.environ.get("SOURCE_URL_MAP", ""))
CREDENTIALS_FILE = os.environ.get("CREDENTIALS_FILE", "config/credentials.yaml")
TIMEOUT = float(os.environ.get("SOURCE_TIMEOUT_S", "20"))
MAX_CHARS = int(os.environ.get("MAX_RESPONSE_CHARS", "20000"))
# When set, every request except /health needs `Authorization: Bearer <MCP_TOKEN>`. Empty: no authentication.
TOKEN = os.environ.get("MCP_TOKEN", "")

mcp = MCPServer("accessibility-dataspace", version="0.1.0",
                instructions="Read-only access to an accessibility data space. Workflow: vochub_search, "
                             "catalog_search, get_openapi, call_source_operation. If no source in the data "
                             "space covers the question, or the results are insufficient (needed facts missing, "
                             "outdated, or only a summary label), search external sources with your own web "
                             "tools. Start from the websites, labels and verification pages named in the "
                             "vochub passages, and interpret what you find with that same domain knowledge "
                             "(what a label certifies, who assessed it, what it does not cover). Missing data "
                             "means unknown, not absent. Cite provenance for every claim and say whether it "
                             "came from the data space or from an external source.")


async def _get_json(url: str, **params):
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as c:
        r = await c.get(url, params={k: v for k, v in params.items() if v is not None})
        r.raise_for_status()
        return r.json()


async def _dataset(dataset_id: str) -> dict:
    return await _get_json(f"{CATALOG}/datasets/{dataset_id}")


async def _spec(dataset: dict) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as c:
        r = await c.get(reachable(dataset["openapi_url"], SOURCE_URL_MAP))
        r.raise_for_status()
        return yaml.safe_load(r.text)


@mcp.custom_route("/health", methods=["GET"])
async def health(_request):
    return JSONResponse({"status": "ok"})


@mcp.tool()
async def vochub_search(question: str, k: int = 5, language: str | None = None, tag: str | None = None) -> dict:
    """Search the vocabulary hub for domain knowledge (terminology, accessibility criteria, how each source rates them).
    Use this FIRST, before looking for data. Returns cited passages with document title, URL and page.
    The passages also name labels, publishers and verification sites: use them to guide any external search."""
    return {"results": await _get_json(f"{VOCHUB}/search", q=question, k=k, language=language, tag=tag)}


@mcp.tool()
async def catalog_search(query: str = "", theme: str | None = None, spatial: str | None = None,
                         language: str | None = None) -> dict:
    """Find datasets in the data space that could answer the question. Filter by theme slug, covered area
    (substring, e.g. 'Ghent') or ISO 639-1 language. Each hit has openapi_url and credentials_configured."""
    hits = await _get_json(f"{CATALOG}/datasets", q=query, theme=theme, spatial=spatial, language=language)
    creds = load_credentials(CREDENTIALS_FILE)
    return {"results": [{**h, "credentials_configured": h["id"] in creds} for h in hits]}


@mcp.tool()
async def catalog_get_dataset(id: str) -> dict:
    """Full catalog record of one dataset: licence, coverage, update frequency, publisher, access note."""
    return await _dataset(id)


@mcp.tool()
async def get_openapi(dataset_id: str, full: bool = False) -> dict:
    """Learn how to query one dataset: a condensed list of its read operations and parameters
    (full=true returns the whole OpenAPI document). Never guess parameters; read them here."""
    spec = await _spec(await _dataset(dataset_id))
    return spec if full else condense(spec, dataset_id in load_credentials(CREDENTIALS_FILE))


@mcp.tool()
async def call_source_operation(dataset_id: str, operation_id: str, params: dict | None = None) -> dict:
    """Run one read operation of a dataset's API, using operation_id and parameter names from get_openapi.
    The connector adds the configured API key itself. Returns the source JSON plus provenance to cite."""
    dataset = await _dataset(dataset_id)
    cred = load_credentials(CREDENTIALS_FILE).get(dataset_id)
    secret = cred["api_key"] if cred else None
    try:
        method, url, query, headers = build_request(await _spec(dataset), reachable(dataset["endpoint_url"], SOURCE_URL_MAP),
                                                    operation_id, params or {}, cred)
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as c:
            r = await c.request(method, url, params=query, headers=headers)
    except (CallError, httpx.HTTPError) as e:
        return {"error": str(e).replace(secret, "***") if secret else str(e)}

    shown_query = {k: ("***" if secret and secret in str(v) else v) for k, v in query.items()}
    try:
        body = r.json()
    except ValueError:
        body = r.text
    text = json.dumps(body, ensure_ascii=False)
    truncated = len(text) > MAX_CHARS
    return {
        "provenance": {
            "dataset_id": dataset_id, "source": dataset["title"], "publisher": dataset["publisher"]["name"],
            "licence": dataset["licence"], "request_url": url + ("?" + urlencode(shown_query, doseq=True) if shown_query else ""),
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "status": r.status_code,
        },
        "data": text[:MAX_CHARS] if truncated else body,
        **({"truncated": True, "hint": "Response cut; narrow the query or lower 'limit'."} if truncated else {}),
        **({"error": "the source refused the call without an API key; none is configured for this dataset "
                     "in the connector's credentials.yaml"} if r.status_code in (401, 403) and not cred else {}),
    }


def require_token(app, token: str):
    """ASGI wrapper: only /health passes without the bearer token (constant-time compare)."""
    expected = f"Bearer {token}".encode()

    async def guarded(scope, receive, send):
        if scope["type"] == "http" and scope["path"] != "/health" and \
                not hmac.compare_digest(dict(scope["headers"]).get(b"authorization", b""), expected):
            return await JSONResponse({"error": "missing or wrong bearer token"}, 401,
                                      headers={"WWW-Authenticate": "Bearer"})(scope, receive, send)
        await app(scope, receive, send)
    return guarded


if __name__ == "__main__":
    import uvicorn

    app = mcp.streamable_http_app(stateless_http=True, host="0.0.0.0")
    uvicorn.run(require_token(app, TOKEN) if TOKEN else app, host="0.0.0.0", port=int(os.environ.get("PORT", "8800")))

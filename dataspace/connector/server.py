"""MCP connector: the single, read-only door between a user agent and the data space."""

import asyncio
import functools
import json
import os
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
import yaml
from mcp.server.mcpserver import MCPServer
from mcp.types import TextContent
from starlette.responses import JSONResponse

from evidence import records
from request_identity import capture_requester, http_identity, requester
from openapi_calls import (CallError, build_request, compact, condense, load_credentials, parse_url_map, reachable,
                           shrink)

CATALOG = os.environ.get("CATALOG_URL", "http://localhost:8001").rstrip("/")
VOCHUB = os.environ.get("VOCHUB_URL", "http://localhost:8002").rstrip("/")
# Registered source URLs may only resolve where the catalog runs (e.g. Docker names); map them for this connector.
SOURCE_URL_MAP = parse_url_map(os.environ.get("SOURCE_URL_MAP", ""))
CREDENTIALS_FILE = os.environ.get("CREDENTIALS_FILE", "config/credentials.yaml")
TIMEOUT = float(os.environ.get("SOURCE_TIMEOUT_S", "20"))
MAX_CHARS = int(os.environ.get("MAX_RESPONSE_CHARS", "20000"))
SPEC_TTL = float(os.environ.get("SPEC_CACHE_S", "3600"))  # OpenAPI documents rarely change; refetching cost up to 0.45 s
HIT_DESCRIPTION = 300  # characters of a dataset's description in catalog_search hits; get_openapi gives all of it
# One JSON line per tool call on stdout. Off by default: the arguments hold the users' questions.
CALL_LOG = os.environ.get("CALL_LOG", "").lower() in {"1", "true", "yes"}

mcp = MCPServer("accessibility-dataspace", version="0.1.0", middleware=[capture_requester],
                instructions="Read-only access to an accessibility data space. Workflow: vochub_search, "
                             "catalog_search, get_openapi, call_source_operation. If no source in the data "
                             "space covers the question, or the results are insufficient (needed facts missing, "
                             "outdated, or only a summary label), search external sources with your own web "
                             "tools. Start from the websites, labels and verification pages named in the "
                             "vochub passages, and interpret what you find with that same domain knowledge "
                             "(what a label certifies, who assessed it, what it does not cover). Missing data "
                             "means unknown, not absent. Cite every claim with the record's own page (url in "
                             "provenance.records), say who backs it (its basis: certified, official, self-declared, "
                             "crowd-sourced), and whether it came from the data space or from an external source.")


async def _get_json(url: str, **params):
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as c:
        r = await c.get(url, params={k: v for k, v in params.items() if v is not None})
        r.raise_for_status()
        return r.json()


async def _dataset(dataset_id: str) -> dict:
    return await _get_json(f"{CATALOG}/datasets/{dataset_id}")


_specs: dict[str, tuple[float, dict]] = {}


async def _spec(dataset: dict) -> dict:
    url = reachable(dataset["openapi_url"], SOURCE_URL_MAP)
    if url in _specs and time.monotonic() - _specs[url][0] < SPEC_TTL:
        return _specs[url][1]
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as c:
        r = await c.get(url)
        r.raise_for_status()
        spec = yaml.safe_load(r.text)
    _specs[url] = (time.monotonic(), spec)
    return spec


def _short(text: str) -> str:
    return text if len(text) <= HIT_DESCRIPTION else text[:HIT_DESCRIPTION].rsplit(" ", 1)[0] + " …"


def _summary(tool: str, result) -> dict:
    """The part of a tool result worth logging: never the data itself."""
    if not isinstance(result, dict):
        return {}
    out = {"chars": len(json.dumps(result, ensure_ascii=False, default=str))}
    if "results" in result:
        out["results"] = len(result["results"])
    if tool == "call_source_operation":
        out.update({k: v for k, v in (("status", result.get("provenance", {}).get("status")),
                                      ("truncated", result.get("truncated")), ("records_cut", result.get("records_cut")),
                                      ("error", result.get("error"))) if v})
    elif "error" in result:
        out["error"] = result["error"]
    return out


def as_text(fn):
    """Send a result as compact JSON: the SDK indents it otherwise, which costs the agent a third more tokens."""
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        result = await fn(*args, **kwargs)
        return TextContent(type="text", text=json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str))
    return wrapper


def logged(fn):
    """Log each call of a tool when CALL_LOG is set: start time, tool, arguments, duration, size of the answer."""
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        if not CALL_LOG:
            return await fn(*args, **kwargs)
        start, t0 = datetime.now(timezone.utc).isoformat(timespec="milliseconds"), time.perf_counter()
        entry = {"call_log": 1, "call_id": uuid.uuid4().hex, "start": start,
                 "tool": fn.__name__, "args": kwargs, "requester": dict(requester.get())}
        try:
            result = await fn(*args, **kwargs)
            entry.update(_summary(fn.__name__, result))
            return result
        except Exception as e:
            entry["exception"] = f"{type(e).__name__}: {e}"[:300]
            raise
        finally:
            entry["ms"] = round((time.perf_counter() - t0) * 1000)
            print(json.dumps(entry, ensure_ascii=False, default=str), flush=True)
    return wrapper


@mcp.custom_route("/health", methods=["GET"])
async def health(_request):
    return JSONResponse({"status": "ok"})


REPLAY_TOOLS = {'vochub_search', 'catalog_search', 'catalog_get_dataset', 'get_openapi', 'call_source_operation'}


@mcp.custom_route('/demo/replay', methods=['POST'])
async def replay_call(request):
    """Repeat an existing read-only MCP tool, with the same SDK argument validation."""
    if request.headers.get('content-type', '').split(';')[0] != 'application/json':
        return JSONResponse({'error': 'JSON required'}, status_code=415)
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 65536:
            return JSONResponse({'error': 'Replay request too large'}, status_code=413)
    try:
        body = json.loads(raw)
        if not isinstance(body, dict) or body.get('tool') not in REPLAY_TOOLS or not isinstance(body.get('args'), dict):
            raise ValueError()
    except (ValueError, TypeError):
        return JSONResponse({'error': 'Choose a supported read-only tool and its arguments'}, status_code=400)
    token = requester.set({**http_identity(request), 'client_name': 'Data space viewer replay',
                           'request_id': uuid.uuid4().hex})
    try:
        result = await mcp.call_tool(body['tool'], body['args'])
        return JSONResponse({'replayed_at': datetime.now(timezone.utc).isoformat(),
                             'result': result.model_dump(mode='json', by_alias=True)})
    except Exception:
        return JSONResponse({'error': 'Replay failed: check the tool arguments and connector logs'}, status_code=502)
    finally:
        requester.reset(token)


@mcp.tool()
@as_text
@logged
async def vochub_search(question: str, k: int = 5, language: str | None = None, tag: str | None = None) -> dict:
    """Search the vocabulary hub for domain knowledge (terminology, accessibility criteria, how each source rates them).
    Use this FIRST, before looking for data. Returns `context`, rules that hold for every question (how to compare
    and combine sources); follow them. Then cited passages with document title, URL and page.
    The passages also name labels, publishers and verification sites: use them to guide any external search."""
    results, context = await asyncio.gather(
        _get_json(f"{VOCHUB}/search", q=question, k=k, language=language, tag=tag), _get_json(f"{VOCHUB}/context"))
    return {"context": context["text"], "results": results}


@mcp.tool()
@as_text
@logged
async def catalog_search(query: str = "", theme: str | None = None, spatial: str | None = None,
                         language: str | None = None) -> dict:
    """Find datasets in the data space that could answer the question. Filter by theme slug, covered area
    (substring, e.g. 'Ghent') or ISO 639-1 language. Each hit has the start of the description and
    credentials_configured; get_openapi gives the full description, with how to query the dataset."""
    hits = await _get_json(f"{CATALOG}/datasets", q=query, theme=theme, spatial=spatial, language=language)
    creds = load_credentials(CREDENTIALS_FILE)
    return {"results": [{**{k: v for k, v in h.items() if k not in ("endpoint_url", "openapi_url")},
                         "description": _short(h["description"]), "credentials_configured": h["id"] in creds}
                        for h in hits]}


@mcp.tool()
@as_text
@logged
async def catalog_get_dataset(id: str) -> dict:
    """Full catalog record of one dataset: licence, coverage, update frequency, publisher, access note."""
    return await _dataset(id)


@mcp.tool()
@as_text
@logged
async def get_openapi(dataset_id: str, full: bool = False) -> dict:
    """Learn how to query one dataset: its full description (which says how to query it, and its fields) and a
    condensed list of its read operations and parameters (full=true returns the whole OpenAPI document).
    Never guess parameters; read them here."""
    dataset = await _dataset(dataset_id)
    spec = await _spec(dataset)
    if full:
        return spec
    return {"dataset_description": dataset["description"],
            **condense(spec, dataset_id in load_credentials(CREDENTIALS_FILE), dataset.get("operations"))}


@mcp.tool()
@as_text
@logged
async def call_source_operation(dataset_id: str, operation_id: str, params: dict | None = None) -> dict:
    """Run one read operation of a dataset's API, using operation_id and parameter names from get_openapi.
    The connector adds the configured API key itself. Returns the source JSON plus provenance to cite.
    provenance.records lists, per record in the answer: name, url (the record's own page: cite this link for
    every fact from that record), basis (certified, official, self_declared, crowd_sourced or unknown), by whom,
    label, and date. Sources without per-record evidence give provenance.basis for the whole dataset instead."""
    dataset = await _dataset(dataset_id)
    cred = load_credentials(CREDENTIALS_FILE).get(dataset_id)
    secret = cred["api_key"] if cred else None
    try:
        method, url, query, headers = build_request(await _spec(dataset), reachable(dataset["endpoint_url"], SOURCE_URL_MAP),
                                                    operation_id, params or {}, cred)
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as c:
            r = await c.request(method, url, params=query, headers=headers)
    except (CallError, httpx.HTTPError) as e:
        msg = str(e) if isinstance(e, CallError) else f"{type(e).__name__}: {e}".rstrip(": ")  # timeouts have no text
        return {"error": msg.replace(secret, "***") if secret else msg}

    shown_query = {k: ("***" if secret and secret in str(v) else v) for k, v in query.items()}
    try:
        body = r.json()
    except ValueError:
        body = r.text
    # Too big: drop whole records, so the agent still gets valid JSON. Evidence is read before compacting:
    # a null field and a missing one give a different basis.
    body, cut = shrink(body, lambda b: len(json.dumps(compact(b), ensure_ascii=False)) <= MAX_CHARS)
    data = compact(body)
    text = json.dumps(data, ensure_ascii=False)
    truncated = len(text) > MAX_CHARS  # a single record is still too big
    spec = dataset.get("records")
    evidence = ({"records": records(body, spec)} if spec and r.is_success
                else {"basis": dataset["assessment"]} if dataset.get("assessment") else {})
    return {
        "provenance": {
            "dataset_id": dataset_id, "source": dataset["title"], "publisher": dataset["publisher"]["name"],
            "licence": dataset["licence"], "request_url": url + ("?" + urlencode(shown_query, doseq=True) if shown_query else ""),
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "status": r.status_code,
            **({"dataset_page": dataset["landing_page"]} if dataset.get("landing_page") else {}), **evidence,
        },
        "data": text[:MAX_CHARS] if truncated else data,
        **({"records_cut": cut, "hint": f"Only the first {cut['kept']} of the {cut['of']} records in this answer fit; "
                                        "narrow the query or page on for the rest."} if cut else {}),
        **({"truncated": True, "hint": "Response cut; narrow the query or lower 'limit'."} if truncated else {}),
        **({"error": "the source refused the call without an API key; none is configured for this dataset "
                     "in the connector's credentials.yaml"} if r.status_code in (401, 403) and not cred else {}),
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=int(os.environ.get("PORT", "8800")),
            stateless_http=True)

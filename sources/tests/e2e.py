"""End-to-end check against a running stack (`docker compose up`). Run with `make e2e` in sources/ after `make up register`."""

import asyncio
import json
import os

import httpx
from mcp import Client

CATALOG = os.environ.get("CATALOG", "http://localhost:8001")
VOCHUB = os.environ.get("VOCHUB", "http://localhost:8002")
MCP = os.environ.get("MCP", "http://localhost:8800/mcp")

DOC = b"""# Picto Access levels

## Level A
A green pictogram (level A) means the place can be used autonomously.

## Level C
A red pictogram (level C) means the place is not accessible for this disability.
"""


def check(cond, msg):
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        raise SystemExit(1)


def payload(result):
    return json.loads(result.content[0].text)


async def main():
    ids = [d["id"] for d in httpx.get(f"{CATALOG}/datasets").json()]
    check({"iedereenoveral-food-and-drink", "iedereenoveral-toilets", "pictoaccess", "acceslibre"} <= set(ids), f"catalog lists the registered datasets ({ids})")
    check("endpointDescription" in httpx.get(f"{CATALOG}/catalog").text, "catalog exports DCAT with endpointDescription")

    # Fictional test document: searched only within its own tag, and always removed again.
    r = httpx.post(f"{VOCHUB}/documents", files={"file": ("e2e-levels.md", DOC, "text/markdown")},
                   data={"language": "en", "tags": "e2e-test"}, timeout=60)
    check(r.status_code == 201, f"vochub ingests a Markdown file ({r.status_code})")
    try:
        hits = httpx.get(f"{VOCHUB}/search",
                         params={"q": "Que signifie un pictogramme vert ?", "k": 1, "tag": "e2e-test"}).json()
        check(hits and hits[0]["heading"].endswith("Level A"), "French question finds the English 'Level A' passage")
    finally:
        httpx.delete(f"{VOCHUB}/documents/{r.json()['doc_id']}")
    left = [d for d in httpx.get(f"{VOCHUB}/documents").json() if "e2e-test" in d["tags"]]
    check(not left, "the test document is removed from vochub again")

    async with Client(MCP) as mcp:
        tools = {t.name for t in (await mcp.list_tools()).tools}
        check(tools == {"vochub_search", "catalog_search", "catalog_get_dataset", "get_openapi",
                        "call_source_operation"}, f"connector lists the five tools")
        vh = payload(await mcp.call_tool("vochub_search", {"question": "accessibility label", "k": 1}))
        check(vh.get("context"), "vochub_search returns the permanent context (make knowledge sets it)")
        hits = payload(await mcp.call_tool("catalog_search", {"query": "wheelchair restaurant Ghent"}))["results"]
        check(any(h["id"] == "iedereenoveral-food-and-drink" for h in hits), "catalog_search via MCP")
        api = payload(await mcp.call_tool("get_openapi", {"dataset_id": "pictoaccess"}))
        check("pictoaccess_search_places" in [o["operation_id"] for o in api["operations"]], "get_openapi condenses operations")
        res = payload(await mcp.call_tool("call_source_operation", {
            "dataset_id": "pictoaccess", "operation_id": "pictoaccess_search_places",
            "params": {"city": "Limoges", "mobility": ["autonomous"], "limit": 1}}))
        check(res["provenance"]["status"] == 200 and res["data"]["total"] > 0,
              "call_source_operation returns data with provenance (PictoAccess snapshot)")
        bad = payload(await mcp.call_tool("call_source_operation", {
            "dataset_id": "pictoaccess", "operation_id": "pictoaccess_search_places", "params": {"town": "Gent"}}))
        check("not in the OpenAPI" in bad.get("error", ""), "invented parameters are refused")

        # Live, with a real key: only when ACCESLIBRE_API_KEY is set for the connector.
        al = payload(await mcp.call_tool("catalog_search", {"query": "Acceslibre"}))["results"]
        if next(h for h in al if h["id"] == "acceslibre")["credentials_configured"]:
            res = payload(await mcp.call_tool("call_source_operation", {
                "dataset_id": "acceslibre", "operation_id": "listErps", "params": {"commune": "Rouen", "page_size": 1}}))
            check(res["provenance"]["status"] == 200, "call_source_operation injects the Acceslibre API key")
        else:
            print("skip Acceslibre key check: ACCESLIBRE_API_KEY not configured")

        # Live: needs internet, calls the IedereenOveral API through its adapter.
        res = payload(await mcp.call_tool("call_source_operation", {
            "dataset_id": "iedereenoveral-food-and-drink", "operation_id": "iedereenoveral_food_and_drink_search_places",
            "params": {"town": "Gent", "limit": 5}}))
        places = res["data"]["places"]
        check(res["provenance"]["status"] == 200 and places and len(json.dumps(res)) < 6000,
              f"IedereenOveral search for Gent returns {res['data']['total']} compact places")
        res = payload(await mcp.call_tool("call_source_operation", {
            "dataset_id": "iedereenoveral-food-and-drink", "operation_id": "iedereenoveral_food_and_drink_get_place",
            "params": {"place_id": places[0]["id"]}}))
        check(res["data"].get("accessibility") is not None and not res.get("truncated"),
              f"IedereenOveral place detail fits untruncated ({len(json.dumps(res))} chars)")
    print("e2e passed")


asyncio.run(main())

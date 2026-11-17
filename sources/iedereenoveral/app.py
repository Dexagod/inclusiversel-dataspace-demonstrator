"""IedereenOveral adapter: a compact, read-only, well-described API in front of the IedereenOveral (Xano) API.

Live proxy: every call goes upstream; only the reference tables are cached.
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Path, Query

from transform import CATEGORIES, SITE, Lookups, detail, summary

UPSTREAM = os.environ.get("IEDEREENOVERAL_API", "https://xcli-wrwg-eljt.f2.xano.io/api:SuAo_4fA").rstrip("/")
LOOKUP_TTL_S = int(os.environ.get("LOOKUP_TTL_S", str(6 * 3600)))
USER_AGENT = "accessibility-dataspace-demo/0.1 (open research demonstrator)"
LICENCE = None  # shortcut: reuse terms not yet confirmed with Inter; set the licence URL once known
LICENCE_NOTE = "Reuse terms not yet confirmed with Inter, the operator of IedereenOveral."
Medal = Literal["gold", "silver", "bronze", "ok", "none"]

_lookups: dict = {}


async def upstream(path: str, params: dict | None = None):
    try:
        async with httpx.AsyncClient(timeout=20, headers={"user-agent": USER_AGENT}) as c:
            r = await c.get(f"{UPSTREAM}/{path}", params=params)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"IedereenOveral is unreachable: {e}") from e
    if r.status_code == 404:
        raise HTTPException(404, "place not found")
    if r.status_code == 429:
        raise HTTPException(503, "IedereenOveral rate limit reached; retry later")
    if not r.is_success:
        raise HTTPException(502, f"IedereenOveral returned {r.status_code}")
    return r.json()


async def lookups() -> Lookups:
    if not _lookups or time.monotonic() - _lookups["at"] > LOOKUP_TTL_S:
        tables = {n: await upstream(n) for n in ("city", "valuation", "locationtype", "filter", "targetaudience")}
        _lookups.update(value=Lookups(**tables), at=time.monotonic())
    return _lookups["value"]


def provenance() -> dict:
    return {"source": "IedereenOveral", "source_site": SITE, "licence": LICENCE, "licence_note": LICENCE_NOTE,
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "mode": "live"}


app = FastAPI(
    title="IedereenOveral accessibility API (adapter)",
    version="0.1.0",
    description=(
        "Accessibility information about places in Flanders and Brussels from IedereenOveral "
        "(https://iedereen.overal.info), run by Inter. Places are cafes and restaurants, public toilets, "
        "Changing Places, museums and parking spaces. Each place has a medal (gold, silver, bronze, ok, none) "
        "and answers to an accessibility questionnaire, grouped by area (Toegang = entrance, Verbruiksruimte = "
        "dining area, Toilet, Andere voorzieningen = other facilities). Texts are in Dutch. "
        "Use iedereenoveral_search_places to find places, then iedereenoveral_get_place for the details."
    ),
)


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "upstream": UPSTREAM}


@app.get("/places", operation_id="iedereenoveral_search_places",
         summary="Search places by town, category, medal or facility",
         description="Returns short place summaries (name, address, medal, id). Use the id with "
                     "iedereenoveral_get_place for the accessibility details.")
async def search_places(
    town: str | None = Query(None, description="Town name or postcode, e.g. 'Gent', 'Leuven', '9000'. "
                                               "Dutch names; Ghent, Bruges, Antwerp, Louvain and Bruxelles also work."),
    q: str | None = Query(None, description="Text in the place name, e.g. 'kroonrad'"),
    category: Literal[tuple(CATEGORIES)] | None = Query(None, description="Kind of place"),
    needs: list[str] = Query([], description="Facilities the place must have, by IedereenOveral filter name, "
                                             "e.g. 'Toegankelijk toilet', 'Drempelloze toegang'. "
                                             "All names are listed by iedereenoveral_facets."),
    medal: list[Medal] = Query([], description="Only places with one of these medals"),
    confirmed_by_inter: bool = Query(False, description="Only places whose information Inter has checked"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50, description="Places per page"),
):
    lk = await lookups()
    params = {"current_page": page, "items_per_page": limit}
    if q:
        params["name_search"] = q
    if town:
        ids = lk.city_ids(town)
        if not ids:
            raise HTTPException(422, f"unknown town {town!r}; use the Dutch name or a postcode")
        params["city_select"] = json.dumps(ids)  # upstream reads arrays only as JSON, not as repeated params
    if category:
        params["type_filter"] = json.dumps([lk.type_ids[CATEGORIES[category]]])
    if needs:
        unknown = [n for n in needs if n.lower() not in lk.filter_ids]
        if unknown:
            raise HTTPException(422, f"unknown needs {unknown}; see iedereenoveral_facets")
        params["filter_id"] = json.dumps(sorted({i for n in needs for i in lk.filter_ids[n.lower()]}))
    if medal:
        params["valuation_filter"] = json.dumps([lk.medal_ids[m] for m in medal])
    if confirmed_by_inter:
        params["confirmed_by_inter_filter"] = "true"
    raw = await upstream("location", params)
    return {"total": raw.get("itemsTotal"), "page": raw.get("curPage"), "pages": raw.get("pageTotal"),
            "places": [summary(i, lk) for i in raw.get("items") or []], "provenance": provenance()}


@app.get("/places/{place_id}", operation_id="iedereenoveral_get_place",
         summary="Accessibility details of one place",
         description="Address, medal, facilities, and the answered accessibility questions per area "
                     "(criterion, value, optional detail and target audiences). Use 'area' to get one area only.")
async def get_place(
    place_id: str = Path(description="Place id from iedereenoveral_search_places, e.g. '00015-t-kroonrad'"),
    area: str | None = Query(None, description="Only this area, e.g. 'Toilet', 'Toegang', 'Verbruiksruimte'"),
):
    lk = await lookups()
    return {**detail(await upstream(f"location/{place_id}"), lk, area), "provenance": provenance()}


@app.get("/facets", operation_id="iedereenoveral_facets",
         summary="Values accepted by the search filters")
async def facets():
    lk = await lookups()
    return {"categories": CATEGORIES, "medals": list(Medal.__args__),
            "needs": sorted({n for n in lk.filter_by_id.values()}),
            "target_audiences": sorted(lk.audience_by_id.values()),
            "towns": f"{len(lk.cities)} towns and postcodes in Flanders and Brussels; pass a name or postcode"}


@app.get("/about", operation_id="iedereenoveral_about", summary="Source metadata")
def about():
    return {"name": "IedereenOveral", "operator": "Inter (Flemish agency for accessibility)", "site": SITE,
            "coverage": "Flanders and Brussels", "language": "nl", "upstream_api": UPSTREAM,
            "licence": LICENCE, "licence_note": LICENCE_NOTE, "mode": "live proxy"}

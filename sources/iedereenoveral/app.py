"""IedereenOveral adapter: a compact, read-only, well-described API in front of the IedereenOveral (Xano) API.

Live proxy: every call goes upstream; only the reference tables are cached.
"""

import asyncio
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
CONFIRMED_MAX = 500  # shortcut: hits are marked confirmed from at most this many checked places; raise if searches grow
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


# One catalog dataset per kind of place, as on the website; each is a sub-API with the category fixed.
GROUPS = {
    "food-and-drink": ("cafes and restaurants", ["food_and_drink"]),
    "toilets": ("public toilets and Changing Places", ["public_toilet", "changing_place"]),
    "museums": ("museums", ["museum"]),
    "parking": ("reserved parking spaces", ["parking"]),
}


def build(prefix: str, places: str, kinds: list[str]) -> FastAPI:
    """The adapter API, limited to the given categories; operation ids start with `prefix`."""
    sub = FastAPI(
        title="IedereenOveral accessibility API (adapter)" + ("" if len(kinds) == len(CATEGORIES) else f": {places}"),
        version="0.1.0",
        description=(
            "Accessibility information about places in Flanders and Brussels from IedereenOveral "
            f"(https://iedereen.overal.info), run by Inter. This API covers {places}. "
            "Each place has a medal (gold, silver, bronze, ok, none) "
            "and answers to an accessibility questionnaire, grouped by area (Toegang = entrance, Verbruiksruimte = "
            "dining area, Toilet, Andere voorzieningen = other facilities). Texts are in Dutch. "
            f"Use {prefix}_search_places to find places, then {prefix}_get_place for the details."
        ),
    )

    @sub.get("/places", operation_id=f"{prefix}_search_places",
             summary="Search places by town, category, medal or facility" if len(kinds) > 1 else
             "Search places by town, medal or facility",
             description="Returns short place summaries (name, address, medal, id). Use the id with "
                         f"{prefix}_get_place for the accessibility details.")
    async def search_places(
        town: str | None = Query(None, description="Town name or postcode, e.g. 'Gent', 'Leuven', '9000'. "
                                                   "Dutch names; Ghent, Bruges, Antwerp, Louvain and Bruxelles also work."),
        q: str | None = Query(None, description="Text in the place name, e.g. 'kroonrad'"),
        category: Literal[tuple(kinds)] | None = Query(None, description="Kind of place; empty means all of "
                                                                         + ", ".join(kinds)),
        needs: list[str] = Query([], description="Facilities the place must have, by IedereenOveral filter name, "
                                                 "e.g. 'Toegankelijk toilet', 'Drempelloze toegang'. "
                                                 f"All names are listed by {prefix}_facets."),
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
        if category or len(kinds) < len(CATEGORIES):
            params["type_filter"] = json.dumps([lk.type_ids[CATEGORIES[k]] for k in ([category] if category else kinds)])
        if needs:
            unknown = [n for n in needs if n.lower() not in lk.filter_ids]
            if unknown:
                raise HTTPException(422, f"unknown needs {unknown}; see {prefix}_facets")
            params["filter_id"] = json.dumps(sorted({i for n in needs for i in lk.filter_ids[n.lower()]}))
        if medal:
            params["valuation_filter"] = json.dumps([lk.medal_ids[m] for m in medal])
        if confirmed_by_inter:
            params["confirmed_by_inter_filter"] = "true"
        if confirmed_by_inter:
            raw = await upstream("location", params)
            confirmed, complete = {i.get("slug") for i in raw.get("items") or []}, True
        else:  # search hits do not say whether Inter checked a place: ask the same search with that filter too
            raw, checked = await asyncio.gather(upstream("location", params), upstream("location", {
                **params, "confirmed_by_inter_filter": "true", "current_page": 1, "items_per_page": CONFIRMED_MAX}))
            confirmed = {i.get("slug") for i in checked.get("items") or []}
            complete = (checked.get("itemsTotal") or 0) <= CONFIRMED_MAX
        places = []
        for i in raw.get("items") or []:
            hit = summary(i, lk)
            # true or false; null when more than CONFIRMED_MAX places match and this one was not among them
            hit["confirmed_by_inter"] = True if i.get("slug") in confirmed else (False if complete else None)
            places.append(hit)
        return {"total": raw.get("itemsTotal"), "page": raw.get("curPage"), "pages": raw.get("pageTotal"),
                "places": places, "provenance": provenance()}

    @sub.get("/places/{place_id}", operation_id=f"{prefix}_get_place",
             summary="Accessibility details of one place",
             description="Address, medal, facilities, and the answered accessibility questions per area "
                         "(criterion, value, optional detail and target audiences). Use 'area' to get one area only.")
    async def get_place(
        place_id: str = Path(description=f"Place id from {prefix}_search_places, e.g. '00015-t-kroonrad'"),
        area: str | None = Query(None, description="Only this area, e.g. 'Toilet', 'Toegang', 'Verbruiksruimte'"),
    ):
        lk = await lookups()
        return {**detail(await upstream(f"location/{place_id}"), lk, area), "provenance": provenance()}

    @sub.get("/facets", operation_id=f"{prefix}_facets", summary="Values accepted by the search filters")
    async def facets():
        lk = await lookups()
        return {"categories": {k: CATEGORIES[k] for k in kinds}, "medals": list(Medal.__args__),
                "needs": sorted({n for n in lk.filter_by_id.values()}),
                "target_audiences": sorted(lk.audience_by_id.values()),
                "towns": f"{len(lk.cities)} towns and postcodes in Flanders and Brussels; pass a name or postcode"}

    @sub.get("/about", operation_id=f"{prefix}_about", summary="Source metadata")
    def about():
        return {"name": "IedereenOveral", "operator": "Inter (Flemish agency for accessibility)", "site": SITE,
                "covers": places, "coverage": "Flanders and Brussels", "language": "nl", "upstream_api": UPSTREAM,
                "licence": LICENCE, "licence_note": LICENCE_NOTE, "mode": "live proxy"}

    return sub


app = build("iedereenoveral", "cafes and restaurants, public toilets, Changing Places, museums and parking spaces",
            list(CATEGORIES))


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "upstream": UPSTREAM}


for _slug, (_places, _kinds) in GROUPS.items():
    app.mount(f"/{_slug}", build(f"iedereenoveral_{_slug.replace('-', '_')}", _places, _kinds))

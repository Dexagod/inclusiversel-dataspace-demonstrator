"""PictoAccess adapter: a read-only, described API over a PictoAccess export (one JSON file per place).

Snapshot mode: the export is loaded into memory at start-up; nothing goes upstream.
"""

import json
import math
import os
import unicodedata
from contextlib import asynccontextmanager
from pathlib import Path as FsPath
from typing import Literal

from fastapi import FastAPI, HTTPException, Path, Query

PLACES_DIR = FsPath(os.environ.get("PICTOACCESS_PLACES", "/data/places"))
SITE = "https://www.pictoaccess.fr"
LICENCE = None  # shortcut: reuse terms not yet confirmed with PictoAccess; set the licence URL once known
LICENCE_NOTE = "Reuse terms not yet confirmed with PictoAccess."

# PictoAccess disability types -> English parameter names used by this API.
TYPES = {
    "mobility": "moteur",                    # unable to walk (wheelchair user)
    "walking_difficulty": "senior",          # difficulty walking
    "cognitive": "psychique",                # understanding, communication, decision
    "blind": "mal-voyant",
    "low_vision": "mal-voyant-partiel",
    "deaf": "mal-entendant",
    "hard_of_hearing": "mal-entendant-partiel",
    "temporary_mobility": "femme-enceinte",  # pushchair, luggage, pregnancy
}
# PictoAccess numeric levels; verified against readable_handicaps[].level in the export.
LEVELS = {2: "autonomous", 1: "with_help", -1: "autonomous_or_with_help", 0: "inaccessible", -2: "unknown"}
Level = Literal["autonomous", "with_help", "autonomous_or_with_help", "inaccessible", "unknown"]
COUNTRIES = {"france": "FR", "italie": "IT", "italy": "IT", "united kingdom": "GB", "netherlands": "NL",
             "bulgaria": "BG", "germany": "DE", "spain": "ES", "ukraine": "UA", "united states": "US",
             "poland": "PL", "colombia": "CO", "austria": "AT", "guadeloupe": "GP", "belgium": "BE",
             "romania": "RO", "sweden": "SE"}

places: dict[str, dict] = {}


def fold(s) -> str:
    """Lowercase, accents removed: 'Évreux' matches 'evreux'."""
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower().strip()


def country_code(p: dict) -> str | None:
    c = (p["localisation"].get("country") or "").strip()
    return c.upper() if len(c) == 2 else COUNTRIES.get(c.lower())


def levels(p: dict) -> dict:
    h = p["accessibility"]["handicaps"]
    return {k: LEVELS.get(h.get(src), "unknown") for k, src in TYPES.items()}


def distance_km(lat1, lon1, lat2, lon2) -> float:
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def summary(p: dict) -> dict:
    loc = p["localisation"]
    return {"id": p["uuid"], "name": p["content"]["display_title"] or p["content"]["title"],
            "address": loc["address"], "postal_code": loc["postal_code"], "city": loc["city"],
            "country": country_code(p), "latitude": loc["latitude"], "longitude": loc["longitude"],
            "categories": [c["name"] for c in p["categories"]], "groups": [b["name"] for b in p["brands"]],
            "accessibility": levels(p), "has_questionnaire": bool((p.get("referential") or {}).get("readable"))}


def provenance(p: dict | None = None) -> dict:
    return {"source": "PictoAccess", "source_site": SITE, "licence": LICENCE, "licence_note": LICENCE_NOTE,
            "updated_at": p and p.get("updated_at"), "mode": "snapshot"}


def load(directory: FsPath) -> None:
    places.clear()
    for f in directory.glob("*.json"):
        p = json.loads(f.read_text(encoding="utf-8"))
        if p.get("published") and p.get("uuid"):
            places[p["uuid"]] = p


@asynccontextmanager
async def lifespan(_app):
    load(PLACES_DIR)
    yield


app = FastAPI(
    title="PictoAccess accessibility API (adapter)",
    version="0.1.0",
    description=(
        "Accessibility of places (offices, shops, transport stops, hotels, university and hospital buildings, "
        "culture, ...), mostly in France, from PictoAccess (https://www.pictoaccess.fr). Each place has a level "
        "per disability type: autonomous (accessible on one's own), with_help (with assistance or partially), "
        "autonomous_or_with_help (one of these two, not specified), inaccessible, or unknown. Many places also "
        "have a questionnaire per area (entrance, toilets, reception, ...) under referential.readable. "
        "Places are grouped by the organisation or site they belong to (a university, a campus, a transport "
        "network). Texts are in French. Use pictoaccess_search_places to find places, pictoaccess_get_place for "
        "the full record, and pictoaccess_related_places for other buildings of the same group or nearby."
    ),
    lifespan=lifespan,
)


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "places": len(places)}


@app.get("/places", operation_id="pictoaccess_search_places",
         summary="Search places by name, address, location, category, group or accessibility level",
         description="Returns place summaries (id, name, address, categories, groups, level per disability type). "
                     "All filters combine with AND; a list filter matches any of its values. "
                     "With latitude and longitude, results are sorted by distance. "
                     "Use the id with pictoaccess_get_place for the full record.")
def search_places(
    q: str | None = Query(None, description="Text in the place name or description, e.g. 'mairie', 'IUT'"),
    address: str | None = Query(None, description="Text in the street address, e.g. 'boulevard Gambetta'"),
    city: str | None = Query(None, description="Town, e.g. 'Rouen', 'la rochelle'; accents and case are ignored"),
    postal_code: str | None = Query(None, description="Postcode or its start, e.g. '76' for Seine-Maritime"),
    country: str | None = Query(None, description="ISO 3166 alpha-2 code, e.g. 'FR'"),
    category: list[str] = Query([], description="Kind of place (building function), by name or slug, e.g. "
                                                 "'Hébergement', 'arret-de-bus', 'Enseignement'. "
                                                 "All values are listed by pictoaccess_facets"),
    group: str | None = Query(None, description="Text in a group name, e.g. 'Université de Rouen', "
                                                "'Campus Madrillet'. Groups are listed by pictoaccess_facets"),
    latitude: float | None = Query(None, ge=-90, le=90),
    longitude: float | None = Query(None, ge=-180, le=180),
    radius_km: float = Query(5, gt=0, le=500, description="Search radius around latitude/longitude"),
    mobility: list[Level] = Query([], description="Level for people unable to walk (wheelchair users)"),
    walking_difficulty: list[Level] = Query([], description="Level for people with difficulty walking"),
    cognitive: list[Level] = Query([], description="Level for people with cognitive or mental disabilities"),
    blind: list[Level] = Query([], description="Level for blind people"),
    low_vision: list[Level] = Query([], description="Level for people with low vision"),
    deaf: list[Level] = Query([], description="Level for deaf people"),
    hard_of_hearing: list[Level] = Query([], description="Level for hard-of-hearing people"),
    temporary_mobility: list[Level] = Query([], description="Level for temporarily reduced mobility "
                                                            "(pushchair, luggage, pregnancy)"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50, description="Places per page"),
):
    if (latitude is None) != (longitude is None):
        raise HTTPException(422, "give both latitude and longitude, or neither")
    wanted = {k: set(v) for k, v in {
        "mobility": mobility, "walking_difficulty": walking_difficulty, "cognitive": cognitive, "blind": blind,
        "low_vision": low_vision, "deaf": deaf, "hard_of_hearing": hard_of_hearing,
        "temporary_mobility": temporary_mobility}.items() if v}
    cats = {fold(c) for c in category}
    hits = []
    for p in places.values():
        loc, c = p["localisation"], p["content"]
        if q and fold(q) not in fold(f"{c['title']} {c['display_title']} {c['description']}"):
            continue
        if address and fold(address) not in fold(loc["address"]):
            continue
        if city and fold(city) != fold(loc["city"]):
            continue
        if postal_code and not str(loc["postal_code"] or "").startswith(postal_code):
            continue
        if country and country_code(p) != country.upper():
            continue
        if cats and not cats & {fold(x[k]) for x in p["categories"] for k in ("name", "slug")}:
            continue
        if group and not any(fold(group) in fold(b["name"]) for b in p["brands"]):
            continue
        lv = levels(p)
        if any(lv[k] not in v for k, v in wanted.items()):
            continue
        d = None
        if latitude is not None:
            d = distance_km(latitude, longitude, loc["latitude"], loc["longitude"])
            if d > radius_km:
                continue
        hits.append((d, p))
    hits.sort(key=lambda h: (h[0] or 0, fold(summary(h[1])["name"])))
    start = (page - 1) * limit
    out = [{**summary(p), **({"distance_km": round(d, 3)} if d is not None else {})}
           for d, p in hits[start:start + limit]]
    return {"total": len(hits), "page": page, "pages": math.ceil(len(hits) / limit), "places": out,
            "provenance": provenance()}


def get_or_404(place_id: str) -> dict:
    if place_id not in places:
        raise HTTPException(404, "place not found")
    return places[place_id]


@app.get("/places/{place_id}", operation_id="pictoaccess_get_place",
         summary="Full record of one place",
         description="The complete PictoAccess entry: address and coordinates, categories, groups (brands), "
                     "levels per disability type (accessibility.readable_handicaps), questionnaire answers per "
                     "area (referential.readable), photo links, contact and opening hours.")
def get_place(place_id: str = Path(description="Place id (uuid) from pictoaccess_search_places")):
    return {"place": get_or_404(place_id), "provenance": provenance(places[place_id])}


@app.get("/places/{place_id}/related", operation_id="pictoaccess_related_places",
         summary="Other buildings of the same group (campus, university, network) and places nearby",
         description="same_group: places sharing a PictoAccess group with this place, per group (e.g. all "
                     "buildings of a campus). nearby: other places within radius_km, nearest first. "
                     "Use this to find, for instance, the other buildings of a campus or hospital.")
def related_places(
    place_id: str = Path(description="Place id (uuid)"),
    radius_km: float = Query(0.3, gt=0, le=5, description="Radius for nearby places"),
    limit: int = Query(20, ge=1, le=100, description="Maximum places per group and nearby"),
):
    p = get_or_404(place_id)
    groups = []
    for b in p["brands"]:
        members = [summary(o) for o in places.values()
                   if o["uuid"] != place_id and any(x["uuid"] == b["uuid"] for x in o["brands"])]
        groups.append({"group": b["name"], "total": len(members), "places": members[:limit]})
    loc = p["localisation"]
    near = sorted(((distance_km(loc["latitude"], loc["longitude"], o["localisation"]["latitude"],
                               o["localisation"]["longitude"]), o) for o in places.values() if o["uuid"] != place_id),
                  key=lambda h: (h[0], h[1]["uuid"]))
    nearby = [{**summary(o), "distance_km": round(d, 3)} for d, o in near if d <= radius_km][:limit]
    return {"place": summary(p), "same_group": groups, "nearby": nearby, "provenance": provenance()}


@app.get("/facets", operation_id="pictoaccess_facets", summary="Values accepted by the search filters")
def facets():
    cats, groups, countries = {}, {}, {}
    for p in places.values():
        for c in p["categories"]:
            cats.setdefault(c["slug"], {"slug": c["slug"], "name": c["name"], "places": 0})["places"] += 1
        for b in p["brands"]:
            groups[b["name"]] = groups.get(b["name"], 0) + 1
        countries[country_code(p)] = countries.get(country_code(p), 0) + 1
    return {"categories": sorted(cats.values(), key=lambda c: -c["places"]),
            "groups": [{"name": n, "places": c} for n, c in sorted(groups.items(), key=lambda g: -g[1])],
            "countries": {str(k): v for k, v in sorted(countries.items(), key=lambda c: -c[1])},
            "disability_types": list(TYPES), "levels": list(Level.__args__)}


@app.get("/about", operation_id="pictoaccess_about", summary="Source metadata")
def about():
    return {"name": "PictoAccess", "site": SITE, "coverage": "mostly France", "language": "fr",
            "places": len(places), "licence": LICENCE, "licence_note": LICENCE_NOTE,
            "mode": "snapshot of the PictoAccess accessibility export"}

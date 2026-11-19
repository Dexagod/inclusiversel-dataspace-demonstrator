"""Toerisme Vlaanderen adapter: a small, described API over the accessibility information in Toerisme Vlaanderen's
linked open data (https://linked.toerismevlaanderen.be, SPARQL).

About a thousand places carry accessibility information, so the adapter loads them all with two SPARQL queries,
keeps them in memory, refreshes them every REFRESH_HOURS, and searches locally. Nothing is written to disk.
"""

import math
import os
import re
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Path, Query

SPARQL = os.environ.get("TV_SPARQL", "https://linked.toerismevlaanderen.be/sparql")
REFRESH_S = float(os.environ.get("REFRESH_HOURS", "6")) * 3600
RETRY_S = 600  # after a failed refresh, keep serving the old data and try again this much later
UA = {"user-agent": "accessibility-dataspace-demo/0.1 (open research demonstrator)",
      "accept": "application/sparql-results+json"}
ACC = "http://linked.toerismevlaanderen.be/vocabularies/accessibility/"
LICENCE_NOTE = ("No licence published yet; Toerisme Vlaanderen's open data page says its datasets may be used "
                "without registration ('mogen zonder registratie gebruikt worden').")
TOPIC_NOTE = ("Topics are as published in Toerisme Vlaanderen's linked data, which files most places that are not "
              "accommodation (museums, monuments, churches, restaurants, tourist offices; about 400) one topic too far: "
              "the entrance text under route_and_levels, the route text under common_toilet_facilities, the toilet "
              "text under extra_facilities (checked 2026-11-19 against their own search site). Accommodation is filed "
              "correctly. Read all texts before concluding that something is not described.")
SUPPORT = {"MotoricalHandicap": "motor", "VisualHandicap": "visual", "Blind": "blind", "AuditiveHandicap": "auditive",
           "Deaf": "deaf", "MentalHandicap": "mental", "Autism": "autism", "Allergies": "allergies",
           "FoodAllergies": "food_allergies", "ExtraCare": "extra_care"}
Support = Literal[tuple(SUPPORT.values())]

PREFIXES = """PREFIX acc: <http://linked.toerismevlaanderen.be/vocabularies/accessibility/>
PREFIX schema: <http://schema.org/>
PREFIX locn: <http://www.w3.org/ns/locn#>
PREFIX geo: <http://www.w3.org/2003/01/geo/wgs84_pos#>
PREFIX adres: <https://data.vlaanderen.be/ns/adres#>
PREFIX logies: <https://data.vlaanderen.be/ns/logies#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX adms: <http://www.w3.org/ns/adms#>
"""
# Most of the 57,000 AccessibilityInformation records are empty. A place counts when it has text or a flag, or an
# A-label. The property path %s lists the accessibility properties TEXTS_QUERY (run first) returned: the endpoint
# answers in seconds, while a FILTER on "any accessibility property" or a VALUES list of ids takes over a minute.
PLACES_QUERY = PREFIXES + """SELECT ?prod ?id ?key ?value WHERE {
  { SELECT DISTINCT ?prod WHERE {
      { ?a a acc:AccessibilityInformation ; dct:subject ?prod ; %s ?x . }
      UNION { ?prod logies:heeftKwaliteitslabel/skos:prefLabel ?l . FILTER(STRSTARTS(STR(?l), "Toegankelijkheidslabel")) } } }
  ?prod adms:identifier/skos:notation ?id .
  { ?prod schema:name ?value . BIND("name" AS ?key) }
  UNION { ?prod schema:alternativeName ?value . BIND("alt_name" AS ?key) }
  UNION { ?prod dct:type|logies:heeftRegistratie/dct:type ?t . ?t skos:prefLabel ?value . BIND("category" AS ?key) }
  UNION { ?prod dct:modified ?value . BIND("modified" AS ?key) }
  UNION { ?prod locn:geometry|locn:location ?g . ?g geo:lat ?value . BIND("lat" AS ?key) }
  UNION { ?prod locn:geometry|locn:location ?g . ?g geo:long ?value . BIND("lon" AS ?key) }
  UNION { ?prod locn:address/locn:thoroughfare ?value . BIND("street" AS ?key) }
  UNION { ?prod locn:address/adres:Adresvoorstelling.huisnummer ?value . BIND("number" AS ?key) }
  UNION { ?prod locn:address/locn:postCode ?value . BIND("postcode" AS ?key) }
  UNION { ?prod locn:address/adres:gemeentenaam ?value . BIND("municipality" AS ?key) }
  UNION { ?prod locn:address/locn:postName ?value . BIND("post_name" AS ?key) }
  UNION { ?prod logies:heeftKwaliteitslabel/skos:prefLabel ?value . BIND("label" AS ?key) }
  UNION { ?prod schema:contactPoint/schema:url ?value . BIND("website" AS ?key) }
}"""
TEXTS_QUERY = PREFIXES + """SELECT ?id ?p ?o WHERE {
  ?a a acc:AccessibilityInformation ; dct:subject ?prod ; ?p ?o .
  FILTER(STRSTARTS(STR(?p), STR(acc:)) || ?p IN (schema:accessibilitySummary, schema:description))
  ?prod adms:identifier/skos:notation ?id .
}"""

_data: dict = {"places": None, "next_refresh": 0.0, "loaded_at": None}
_lock = threading.Lock()


def sparql(query: str) -> list[dict]:
    r = httpx.post(SPARQL, data={"query": query}, headers=UA, timeout=60)
    r.raise_for_status()
    return r.json()["results"]["bindings"]


def topic(predicate: str) -> str:
    """acc:informationAboutRouteAndLevels -> route_and_levels; schema:accessibilitySummary -> summary."""
    name = predicate.rsplit("/", 1)[-1]
    name = {"accessibilitySummary": "summary"}.get(name, name)
    name = re.sub(r"^information(About|For)", "", name)
    return re.sub(r"(?<!^)([A-Z])", r"_\1", name).lower()


def build(place_rows: list[dict], text_rows: list[dict]) -> dict[str, dict]:
    places: dict[str, dict] = {}
    for r in place_rows:
        p = places.setdefault(r["id"]["value"], {"id": r["id"]["value"], "uri": r["prod"]["value"], "category": {},
                                                 "labels": set(), "texts": {}, "support": set()})
        key, value, lang = r["key"]["value"], r["value"]["value"], r["value"].get("xml:lang")
        if key == "category":
            p["category"].setdefault(lang or "nl", value)
        elif key == "label":
            p["labels"].add(value)
        else:
            p.setdefault(key, value)
    for r in text_rows:
        p = places.get(r["id"]["value"])
        if p is None:
            continue
        pred, value, lang = r["p"]["value"], r["o"]["value"].strip(), r["o"].get("xml:lang")
        if lang and value:
            p["texts"].setdefault(topic(pred), {})[lang] = value
        elif pred.startswith(ACC + "supportFor") and value in ("1", "true"):
            p["support"].add(SUPPORT.get(pred.removeprefix(ACC + "supportFor"), topic(pred)))
    for p in places.values():
        p["a_label"] = "A+" if "Toegankelijkheidslabel A+" in p["labels"] else (
            "A" if "Toegankelijkheidslabel A" in p["labels"] else None)
        cat = p["category"].get("en") or p["category"].get("nl")
        # Tourist information offices have no name in the linked data.
        p["name"] = p.get("name") or p.get("alt_name") or ", ".join(x for x in (cat, p.get("post_name")) if x) or p["id"]
        for k in ("lat", "lon"):
            p[k] = float(p[k]) if p.get(k) else None
    return places


def places() -> dict[str, dict]:
    if _data["places"] is not None and time.time() < _data["next_refresh"]:
        return _data["places"]
    with _lock:
        if _data["places"] is None or time.time() >= _data["next_refresh"]:
            try:
                texts = sparql(TEXTS_QUERY)
                path = "|".join(sorted({"<%s>" % r["p"]["value"] for r in texts if ">" not in r["p"]["value"]}))
                _data["places"] = build(sparql(PLACES_QUERY % path), texts)
                _data["loaded_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                _data["next_refresh"] = time.time() + REFRESH_S
            except (httpx.HTTPError, KeyError, ValueError) as e:
                if _data["places"] is None:
                    raise HTTPException(503, f"Toerisme Vlaanderen's linked data is unreachable ({e}); retry in a minute",
                                        headers={"Retry-After": "60"}) from e
                _data["next_refresh"] = time.time() + RETRY_S  # serve the old data meanwhile
    return _data["places"]


def distance_m(lat1, lon1, lat2, lon2) -> float:
    a = (math.sin(math.radians(lat2 - lat1) / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6371000 * math.asin(math.sqrt(a))


def address(p: dict) -> str | None:
    street = " ".join(x for x in (p.get("street"), p.get("number")) if x)
    town = " ".join(x for x in (p.get("postcode"), p.get("post_name")) if x)
    return ", ".join(x for x in (street, town) if x) or None


def summary(p: dict, distance: float | None = None) -> dict:
    out = {"id": p["id"], "name": p["name"], "category": p["category"].get("en") or p["category"].get("nl"),
           "address": address(p), "municipality": p.get("municipality"), "latitude": p["lat"], "longitude": p["lon"],
           "a_label": p["a_label"], "support": sorted(p["support"]), "topics": sorted(p["texts"])}
    if distance is not None:
        out["distance_m"] = round(distance)
    return out


def provenance() -> dict:
    return {"source": "Toerisme Vlaanderen, linked open data", "source_url": SPARQL,
            "publisher": "Toerisme Vlaanderen", "licence": None, "licence_note": LICENCE_NOTE,
            "data_loaded_at": _data["loaded_at"], "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "mode": f"cached copy of the linked data, refreshed every {REFRESH_S / 3600:g} hours"}


@asynccontextmanager
async def lifespan(_app):
    def warm():
        try:
            places()
        except HTTPException:
            pass  # the first request will try again
    threading.Thread(target=warm, daemon=True).start()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Toerisme Vlaanderen accessibility API (adapter)",
    version="0.1.0",
    description=(
        "Accessibility information about about a thousand tourist places in Flanders and Brussels (museums, "
        "restaurants, youth hostels, hotels, holiday homes, tourist offices, nature areas, attractions), from "
        "Toerisme Vlaanderen's linked open data. Each place may have the official accessibility label "
        "(A or A+, awarded by Toerisme Vlaanderen after an audit), flags for the groups it caters for "
        "(motor, visual, blind, auditive, deaf, mental, autism, allergies, food_allergies, extra_care), and texts per "
        "topic (entrances, route_and_levels, common_toilet_facilities, room, bedroom, parking, ...) in Dutch and "
        "English. A missing flag or topic means no information, not that the facility is absent. The 'summary' topic "
        "is sometimes a general description of the place rather than about accessibility. " + TOPIC_NOTE +
        " Use toerismevlaanderen_search_places to find places, then toerismevlaanderen_get_place for the texts."
    ),
)


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "places_loaded": None if _data["places"] is None else len(_data["places"])}


@app.get("/places", operation_id="toerismevlaanderen_search_places",
         summary="Search places by location, municipality, name, category, A-label or group catered for",
         description="Returns place summaries: name, category, address, coordinates, A-label, support flags and the "
                     "topics that have text. Sorted by distance when a point is given, else by name. Use the id with "
                     "toerismevlaanderen_get_place for the texts.")
def search_places(
    latitude: float | None = Query(None, ge=-90, le=90, description="With longitude: search around this point"),
    longitude: float | None = Query(None, ge=-180, le=180),
    radius_m: int = Query(2000, ge=50, le=50000, description="Search radius around the point, in metres"),
    municipality: str | None = Query(None, description="Municipality, town or postcode in Dutch, e.g. 'Gent', 'Brugge', "
                                                       "'Antwerpen', '8000'"),
    name: str | None = Query(None, description="Text in the place name"),
    category: str | None = Query(None, description="Text in the category, Dutch or English, e.g. 'museum', "
                                                   "'Eetgelegenheid', 'youth'"),
    a_label: list[Literal["A", "A+"]] = Query([], description="Only places with one of these accessibility labels"),
    support: list[Support] = Query([], description="Only places flagged as catering for all of these groups"),
    limit: int = Query(20, ge=1, le=100),
):
    if (latitude is None) != (longitude is None):
        raise HTTPException(422, "give both latitude and longitude, or neither")
    hits = []
    for p in places().values():
        if municipality and municipality.lower() not in {str(p.get(k, "")).lower()
                                                          for k in ("municipality", "post_name", "postcode")}:
            continue
        if name and name.lower() not in p["name"].lower():
            continue
        if category and not any(category.lower() in c.lower() for c in p["category"].values()):
            continue
        if a_label and p["a_label"] not in a_label:
            continue
        if not set(support) <= p["support"]:
            continue
        d = None
        if latitude is not None:
            if p["lat"] is None or (d := distance_m(latitude, longitude, p["lat"], p["lon"])) > radius_m:
                continue
        hits.append((d if d is not None else 0, p["name"].lower(), p, d))
    hits.sort(key=lambda h: h[:2])
    return {"count": len(hits), "results": [summary(p, d) for *_, p, d in hits[:limit]], "provenance": provenance()}


@app.get("/places/{place_id}", operation_id="toerismevlaanderen_get_place",
         summary="All accessibility information of one place",
         description="Summary plus the accessibility texts per topic in the chosen language (falling back to the "
                     "other language), the website and the date of the last change. " + TOPIC_NOTE)
def get_place(place_id: str = Path(description="The place id from toerismevlaanderen_search_places"),
              lang: Literal["en", "nl"] = Query("en", description="Language of the texts")):
    p = places().get(place_id)
    if p is None:
        raise HTTPException(404, "no place with accessibility information has this id")
    other = "nl" if lang == "en" else "en"
    texts = {t: v.get(lang) or v.get(other) for t, v in sorted(p["texts"].items())}
    return {**summary(p), "texts": texts,
            "texts_in_other_language": sorted(t for t, v in p["texts"].items() if lang not in v),
            "topic_note": TOPIC_NOTE, "website": p.get("website"), "modified": p.get("modified"),
            "linked_data_uri": p["uri"], "provenance": provenance()}

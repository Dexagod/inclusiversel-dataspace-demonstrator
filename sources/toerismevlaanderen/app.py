"""Toerisme Vlaanderen adapter: a small, described API over the accessibility information in Toerisme Vlaanderen's
linked open data (https://linked.toerismevlaanderen.be).

About a thousand places carry accessibility information. Once a day the adapter downloads Toerisme Vlaanderen's own
daily export ("Basisregister Vlaams Logiesaanbod", about 660 MB of N-Triples, which also holds the attractions),
keeps only the lines it needs (about 240 MB), loads them into an in-memory RDF store (pyoxigraph), runs two queries,
and keeps the resulting places in memory and in DATA_DIR/places.json, so a restart serves them at once. Its SPARQL
endpoint is only asked small questions: where the latest export is, and the names of the place categories. The big
queries the adapter used to send there time out (504) since November 2026.
"""

import json
import math
import os
import re
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path as FsPath
from typing import Literal

import httpx
import pyoxigraph as ox
from fastapi import FastAPI, HTTPException, Path, Query

SPARQL = os.environ.get("TV_SPARQL", "https://linked.toerismevlaanderen.be/sparql")
REFRESH_S = float(os.environ.get("REFRESH_HOURS", "24")) * 3600  # the export is published daily, around 02:15 UTC
RETRY_S = 600  # after a failed refresh, keep serving the old data and try again this much later
DATA_DIR = FsPath(os.environ.get("DATA_DIR", "/data"))
DUMP_URL = os.environ.get("TV_DUMP_URL")  # fixed export URL; empty: the latest one, as listed in the endpoint's DCAT
DUMP_TITLE = "Basisregister Vlaams Logiesaanbod"
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
# Most of the 57,000 AccessibilityInformation records are empty. A place counts when it has an accessibility text or
# flag, or an A-label; %s is the VALUES list of those places. Each alternative is its own UNION branch: property paths
# with "|" take minutes in pyoxigraph, and the export names the website with foaf:page where the endpoint has schema:url.
# Category names are not in the export: they come from the endpoint (CATEGORY_QUERY).
def _via(first: str, second: str, key: str) -> str:
    return f'UNION {{ ?prod {first} ?n . ?n {second} ?value . BIND("{key}" AS ?key) }}'


PLACES_QUERY = PREFIXES + "PREFIX foaf: <http://xmlns.com/foaf/0.1/>\nSELECT ?prod ?id ?key ?value WHERE {\n  VALUES ?prod { %s }" + """
  ?prod adms:identifier/skos:notation ?id .
  { ?prod schema:name ?value . BIND("name" AS ?key) }
  UNION { ?prod schema:alternativeName ?value . BIND("alt_name" AS ?key) }
  UNION { ?prod dct:type ?value . BIND("category_concept" AS ?key) }
  UNION { ?prod dct:modified ?value . BIND("modified" AS ?key) }
  UNION { ?prod logies:heeftKwaliteitslabel/skos:prefLabel ?value . BIND("label" AS ?key) }
  """ + "\n  ".join(_via(*v) for v in [
    ("logies:heeftRegistratie", "dct:type", "category_concept"), ("locn:geometry", "geo:lat", "lat"),
    ("locn:location", "geo:lat", "lat"), ("locn:geometry", "geo:long", "lon"), ("locn:location", "geo:long", "lon"),
    ("locn:address", "locn:thoroughfare", "street"), ("locn:address", "adres:Adresvoorstelling.huisnummer", "number"),
    ("locn:address", "locn:postCode", "postcode"), ("locn:address", "adres:gemeentenaam", "municipality"),
    ("locn:address", "locn:postName", "post_name"), ("schema:contactPoint", "schema:url", "website"),
    ("schema:contactPoint", "foaf:page", "website")]) + "\n}"
LABELLED_QUERY = PREFIXES + """SELECT DISTINCT ?prod WHERE {
  ?prod logies:heeftKwaliteitslabel/skos:prefLabel ?l . FILTER(STRSTARTS(STR(?l), "Toegankelijkheidslabel")) }"""
CATEGORY_QUERY = PREFIXES + "SELECT ?t ?l WHERE { VALUES ?t { %s } ?t skos:prefLabel ?l }"
DUMP_QUERY = PREFIXES + """PREFIX dcat: <http://www.w3.org/ns/dcat#>
SELECT ?url ?modified WHERE {
  ?ds dct:title "%s" ; dcat:distribution ?d . ?d dcat:downloadURL|dcat:accessURL ?url ; dct:format|dcat:mediaType ?type ;
  dct:modified|dct:issued ?modified . FILTER(CONTAINS(STR(?type), "turtle")) } ORDER BY DESC(?modified) LIMIT 1""" % DUMP_TITLE
# The predicates the queries use; every other line of the export is dropped while downloading.
KEEP = ["http://linked.toerismevlaanderen.be/vocabularies/accessibility/", "http://schema.org/accessibilitySummary",
        "http://schema.org/description", "http://purl.org/dc/terms/subject", "http://www.w3.org/ns/adms#identifier",
        "http://www.w3.org/2004/02/skos/core#notation", "http://schema.org/name", "http://schema.org/alternativeName",
        "http://purl.org/dc/terms/type", "https://data.vlaanderen.be/ns/logies#heeftRegistratie",
        "http://purl.org/dc/terms/modified", "http://www.w3.org/ns/locn#geometry", "http://www.w3.org/ns/locn#location",
        "http://www.w3.org/2003/01/geo/wgs84_pos#lat", "http://www.w3.org/2003/01/geo/wgs84_pos#long",
        "http://www.w3.org/ns/locn#address", "http://www.w3.org/ns/locn#thoroughfare",
        "https://data.vlaanderen.be/ns/adres#Adresvoorstelling.huisnummer", "http://www.w3.org/ns/locn#postCode",
        "https://data.vlaanderen.be/ns/adres#gemeentenaam", "http://www.w3.org/ns/locn#postName",
        "https://data.vlaanderen.be/ns/logies#heeftKwaliteitslabel", "http://www.w3.org/2004/02/skos/core#prefLabel",
        "http://schema.org/contactPoint", "http://schema.org/url", "http://xmlns.com/foaf/0.1/page"]
TEXTS_QUERY = PREFIXES + """SELECT ?prod ?id ?p ?o WHERE {
  ?a a acc:AccessibilityInformation ; dct:subject ?prod ; ?p ?o .
  FILTER(STRSTARTS(STR(?p), STR(acc:)) || ?p IN (schema:accessibilitySummary, schema:description))
  ?prod adms:identifier/skos:notation ?id .
}"""

_data: dict = {"places": None, "next_refresh": 0.0, "loaded_at": None, "export": None, "export_modified": None,
               "categories": {}}


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


def keep(line: str) -> bool:
    return any("<" + k in line for k in KEEP) or "vocabularies/accessibility/AccessibilityInformation" in line


def download(url: str, dest: FsPath) -> FsPath:
    """Stream the export and keep only the lines the queries need."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(".part")
    with httpx.stream("GET", url, headers=UA, timeout=httpx.Timeout(60, read=300), follow_redirects=True) as r, \
            open(part, "w", encoding="utf-8") as out:
        r.raise_for_status()
        for line in r.iter_lines():
            if keep(line):
                out.write(line + "\n")
    part.replace(dest)
    return dest


def bindings(solutions) -> list[dict]:
    """pyoxigraph solutions in the shape of SPARQL JSON results, which build() reads."""
    out = []
    for s in solutions:
        row = {}
        for v in solutions.variables:
            term = s[v]
            if term is not None:
                lang = getattr(term, "language", None)
                row[v.value] = {"value": term.value, **({"xml:lang": lang} if lang else {})}
        out.append(row)
    return out


def query_export(path: FsPath) -> tuple[list[dict], list[dict], set[str]]:
    """Place rows, text rows and category concept URIs from the filtered export."""
    store = ox.Store()  # in memory: about 1.2 million triples
    store.bulk_load(path=str(path), format=ox.RdfFormat.TURTLE)  # Turtle: a few lines hold two triples
    texts = bindings(store.query(TEXTS_QUERY))
    with_content = {r["prod"]["value"] for r in texts if r["o"]["value"].strip()}
    with_content |= {r["prod"]["value"] for r in bindings(store.query(LABELLED_QUERY))}
    rows = bindings(store.query(PLACES_QUERY % " ".join(f"<{u}>" for u in sorted(with_content))))
    concepts = {r["value"]["value"] for r in rows if r["key"]["value"] == "category_concept"}
    return rows, texts, concepts


def fetch_rows() -> tuple[list[dict], list[dict], dict]:
    """Download the latest export, query it, and name the categories: (place rows, text rows, export info)."""
    if DUMP_URL:
        url, modified = DUMP_URL, None
    else:
        latest = sparql(DUMP_QUERY)
        if not latest:
            raise ValueError(f"no Turtle export of '{DUMP_TITLE}' listed in the DCAT")
        url, modified = latest[0]["url"]["value"], latest[0]["modified"]["value"]
    path = download(url, DATA_DIR / "export.nt")
    try:
        rows, texts, concepts = query_export(path)
    finally:
        path.unlink(missing_ok=True)
    names = dict(_data["categories"])  # keep the names already known if the endpoint does not answer
    try:
        for r in sparql(CATEGORY_QUERY % " ".join(f"<{c}>" for c in sorted(concepts))):
            names.setdefault(r["t"]["value"], {})[r["l"].get("xml:lang") or "nl"] = r["l"]["value"]
    except httpx.HTTPError as e:
        print(f"category names not refreshed: {e}", file=sys.stderr)
    place_rows = []
    for r in rows:
        if r["key"]["value"] != "category_concept":
            place_rows.append(r)
            continue
        for lang, name in names.get(r["value"]["value"], {}).items():
            place_rows.append({**r, "key": {"value": "category"}, "value": {"value": name, "xml:lang": lang}})
    return place_rows, texts, {"export": url, "export_modified": modified, "categories": names}


def refresh() -> None:
    """Load the places afresh; on failure the old data stays and the next try is RETRY_S later."""
    place_rows, texts, info = fetch_rows()
    places = build(place_rows, texts)
    loaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _data.update(places=places, loaded_at=loaded_at, next_refresh=time.time() + REFRESH_S, **info)
    save_cache()


def save_cache() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DATA_DIR / "places.json.tmp"
    tmp.write_text(json.dumps({k: _data[k] for k in ("places", "loaded_at", "export", "export_modified", "categories")},
                              ensure_ascii=False, default=sorted), encoding="utf-8")
    tmp.replace(DATA_DIR / "places.json")


def load_cache() -> None:
    """Serve the last saved places at once after a restart; refresh when they are older than REFRESH_S."""
    f = DATA_DIR / "places.json"
    if not f.exists() or _data["places"] is not None:
        return
    saved = json.loads(f.read_text(encoding="utf-8"))
    for p in saved["places"].values():
        p["labels"], p["support"] = set(p["labels"]), set(p["support"])
    age = time.time() - datetime.fromisoformat(saved["loaded_at"]).timestamp()
    _data.update(saved, next_refresh=time.time() + max(0.0, REFRESH_S - age))


def keep_fresh() -> None:
    """Background loop: load from the cache, then refresh daily; requests never wait for a load."""
    try:
        load_cache()
    except (OSError, ValueError, KeyError) as e:
        print(f"cache not used: {e}", file=sys.stderr)
    while True:
        if time.time() >= _data["next_refresh"]:
            try:
                refresh()
            except Exception as e:  # network, parse or query errors: keep the old data, retry later
                print(f"refresh failed: {type(e).__name__}: {e}", file=sys.stderr)
                _data["next_refresh"] = time.time() + RETRY_S
        time.sleep(30)


def places() -> dict[str, dict]:
    if _data["places"] is None:
        raise HTTPException(503, "Toerisme Vlaanderen's places are still loading (a few minutes after the first "
                                 "start, or after a failed download); retry in a minute", headers={"Retry-After": "60"})
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
           "a_label": p["a_label"], "support": sorted(p["support"]), "topics": sorted(p["texts"]),
           "modified": p.get("modified"), "url": p["uri"]}  # the linked-data URI opens as a page about the place
    if distance is not None:
        out["distance_m"] = round(distance)
    return out


def provenance() -> dict:
    return {"source": "Toerisme Vlaanderen, linked open data", "source_url": _data["export"] or SPARQL,
            "publisher": "Toerisme Vlaanderen", "licence": None, "licence_note": LICENCE_NOTE,
            "export_modified": _data["export_modified"], "data_loaded_at": _data["loaded_at"],
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "mode": f"daily export '{DUMP_TITLE}' of the linked data, loaded every {REFRESH_S / 3600:g} hours"}


@asynccontextmanager
async def lifespan(_app):
    threading.Thread(target=keep_fresh, daemon=True).start()
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

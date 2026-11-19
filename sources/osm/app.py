"""OpenStreetMap accessibility, as two read-only APIs for agents: OnWheels features and OSM's native accessibility tags.

Live mode: every search is an Overpass query and every detail a call to the OSM API; nothing is stored beyond a
30-minute in-memory cache. Responses carry the ODbL attribution; this is not a republication of OSM.

The public Overpass server is shared and often full, so searches are deliberately polite (see `overpass`): only
small areas inside the covered region, one query at a time, a free-slot check on /api/status before each query,
exponential back-off after a busy answer, and a daily cap. When in doubt the agent gets "busy, retry in N s"
rather than a query being queued. OVERPASS_URL can point at a private Overpass instance.
- /onwheels: entrances, kerbs, toilets, lifts, reception desks and disabled parking, with the keys the OnWheels
  map (MapComplete theme "onwheels") asks contributors for, and measurements normalised to metres.
- /osm: places (amenity, shop, tourism, leisure, healthcare) with OSM's native accessibility tags.
"""

import math
import os
import re
import threading
import time
from datetime import datetime, timezone
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Path, Query

OVERPASS_URL = os.environ.get("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
OSM_API = os.environ.get("OSM_API", "https://api.openstreetmap.org/api/0.6")
UA = {"user-agent": "accessibility-dataspace-demo/0.1 (open research demonstrator)"}
TIMEOUT_S = 17  # below the connector's 20 s, so the agent gets our explanation instead of a timeout
CACHE_S = 1800
DAILY_QUERIES = int(os.environ.get("OVERPASS_DAILY_QUERIES", "500"))  # Overpass asks for well under 10,000/day
BACKOFF_MAX_S = 900
# Covered region (lat_min, lat_max, lon_min, lon_max): Belgium and Hauts-de-France, the project's area.
# Bounding boxes, so strips of neighbouring regions (e.g. Paris, southern Netherlands) pass too; it limits load, not law.
COVERAGE = {"Belgium": (49.49, 51.51, 2.54, 6.41), "Hauts-de-France": (48.83, 51.09, 1.37, 4.26)}
POI_KEYS = "amenity|shop|tourism|leisure|healthcare"
# Keys (and their sub-keys) that describe accessibility; everything else is dropped from the answers.
A11Y_PREFIXES = ("wheelchair", "toilets", "changing_table", "hearing_loop", "ramp", "step_count", "entrance",
                 "automatic_door", "door", "width", "kerb", "tactile_paving", "tactile_writing", "braille",
                 "blind", "deaf", "capacity:disabled", "parking_space", "desk:height", "speech_output",
                 "operational_status", "handrail", "incline", "length", "diameter", "shape", "level", "access")
LENGTH_KEYS = ["width", "door:width", "kerb:height", "desk:height", "length", "diameter"]
FEATURES = {  # OnWheels layer -> Overpass selectors (MapComplete layer sources)
    "entrance": ['nwr["entrance"]', 'nwr["door"]'],
    "kerb": ['nwr["barrier"="kerb"]'],
    "toilet": ['nwr["amenity"="toilets"]'],
    "elevator": ['nwr["highway"="elevator"]'],
    "reception_desk": ['nwr["amenity"="reception_desk"]'],
    "disabled_parking": ['nwr["amenity"="parking_space"]["parking_space"="disabled"]',
                         'nwr["amenity"="parking"]["capacity:disabled"]'],
}
Feature = Literal[tuple(FEATURES)]
Wheelchair = Literal["yes", "limited", "no", "designated"]
OsmType = Literal["node", "way", "relation"]
LICENCE = "https://opendatacommons.org/licenses/odbl/1-0/"
NOTE = ("Live from OpenStreetMap, not republished. A missing tag means nobody has mapped it: unknown, not absent. "
        "Cite '© OpenStreetMap contributors'.")

_cache: dict[str, tuple[float, object]] = {}
_one_query = threading.Lock()
_state = {"backoff_until": 0.0, "backoff_s": 0, "day": "", "count": 0}


def busy(wait_s: float, why: str = "OpenStreetMap's public Overpass server is busy") -> HTTPException:
    wait = max(5, int(wait_s))
    return HTTPException(503, f"{why}; retry in about {wait} seconds", headers={"Retry-After": str(wait)})


def cache_key(method: str, url: str, data=None) -> str:
    return f"{method} {url} {data}"


def fetch(method: str, url: str, **kw):
    """GET/POST with a cache; a busy or slow OSM server becomes a 503 the agent can read."""
    key = cache_key(method, url, kw.get("data"))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_S:
        return hit[1]
    try:
        r = httpx.request(method, url, headers=UA, timeout=TIMEOUT_S, **kw)
    except httpx.TimeoutException:
        raise busy(60, "OpenStreetMap did not answer in time")
    if r.status_code in (429, 502, 503, 504):
        raise busy(60)
    if r.status_code in (404, 410):
        raise HTTPException(404, "no such OpenStreetMap feature (it may have been deleted)")
    r.raise_for_status()
    data = r.json()
    if len(_cache) > 500:
        _cache.clear()
    _cache[key] = (time.time(), data)
    return data


def slot_wait() -> float:
    """Seconds until Overpass has a free slot for us, from its /api/status (which does not use up a slot)."""
    try:
        s = httpx.request("GET", OVERPASS_URL.replace("/interpreter", "/status"), headers=UA, timeout=5).text
    except httpx.HTTPError:
        return 60
    if re.search(r"[1-9]\d* slots? available now", s):
        return 0
    waits = [int(w) for w in re.findall(r"in (\d+) seconds", s)]
    return min(waits) if waits else (60 if "available now" in s else 0)  # private instances may have no status


def in_coverage(lat: float, lon: float) -> None:
    if not any(a <= lat <= b and c <= lon <= d for a, b, c, d in COVERAGE.values()):
        raise HTTPException(422, f"only points in {' and '.join(COVERAGE)} are searched")


def overpass(statements: list[str], lat: float, lon: float, radius_m: int, limit: int) -> dict:
    """One polite Overpass query; anything that would add load to a busy server is answered with 'busy' instead."""
    lat, lon = round(lat, 4), round(lon, 4)  # about 10 m: nearby repeats of a question hit the cache
    in_coverage(lat, lon)
    around = f"(around:{radius_m},{lat},{lon})"
    q = (f"[out:json][timeout:15][maxsize:16777216];({''.join(s + around + ';' for s in statements)});"
         f"out tags center qt {limit};")
    hit = _cache.get(cache_key("POST", OVERPASS_URL, {"data": q}))
    if hit and time.time() - hit[0] < CACHE_S:
        return hit[1]
    now, today = time.time(), datetime.now(timezone.utc).date().isoformat()
    if now < _state["backoff_until"]:
        raise busy(_state["backoff_until"] - now)
    if _state["day"] != today:
        _state.update(day=today, count=0)
    if _state["count"] >= DAILY_QUERIES:
        raise HTTPException(503, f"the daily limit of {DAILY_QUERIES} OpenStreetMap searches is used up; "
                                 "retry tomorrow")
    if not _one_query.acquire(blocking=False):
        raise busy(10, "another OpenStreetMap search is running")
    try:
        if (wait := slot_wait()) > 0:
            raise busy(wait)
        _state["count"] += 1
        try:
            data = fetch("POST", OVERPASS_URL, data={"data": q})
        except HTTPException as e:
            if e.status_code == 503:  # back off: 30 s, then doubling up to 15 minutes
                _state["backoff_s"] = min(BACKOFF_MAX_S, max(30, _state["backoff_s"] * 2))
                _state["backoff_until"] = time.time() + _state["backoff_s"]
                raise busy(_state["backoff_s"])
            raise
        _state.update(backoff_s=0, backoff_until=0.0)
        return data
    finally:
        _one_query.release()


def name_filter(q: str | None) -> str:
    """Case-insensitive name match; regex characters are escaped, then escaped again for the Overpass string."""
    if not q:
        return ""
    return '["name"~"' + re.escape(q).replace("\\", "\\\\").replace('"', '\\"') + '",i]'


def metres(v: str | None) -> float | None:
    """OSM length values ('0.9', '90 cm', '900 mm', '1,2 m') in metres; None when absent or unreadable."""
    m = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*(m|cm|mm)?\s*", v or "")
    if not m:
        return None
    n = float(m[1].replace(",", "."))
    return round(n / {"cm": 100, "mm": 1000}.get(m[2], 1), 3)


def distance_m(lat1, lon1, lat2, lon2) -> int:
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return round(6371000 * 2 * math.asin(math.sqrt(a)))


def record(el: dict, lat: float | None = None, lon: float | None = None) -> dict:
    """One OSM element, reduced to what an agent needs; no contributor names."""
    t = el.get("tags", {})
    c = el.get("center") or el
    kind = next((f"{k}={t[k]}" for k in POI_KEYS.split("|") + ["entrance", "door", "barrier", "highway"] if k in t), None)
    addr = " ".join(x for x in [t.get("addr:street"), t.get("addr:housenumber"), t.get("addr:postcode"),
                                t.get("addr:city")] if x) or None
    out = {"osm_type": el["type"], "osm_id": el["id"], "name": t.get("name"), "kind": kind, "address": addr,
           "latitude": c.get("lat"), "longitude": c.get("lon"),
           "accessibility": {k: v for k, v in sorted(t.items()) if k.startswith(A11Y_PREFIXES)},
           "measurements_m": {k: metres(t.get(k)) for k in LENGTH_KEYS if metres(t.get(k)) is not None},
           "osm_url": f"https://www.openstreetmap.org/{el['type']}/{el['id']}",
           "onwheels_url": f"https://mapcomplete.org/onwheels?z=20&lat={c.get('lat')}&lon={c.get('lon')}"
                           f"#{el['type']}/{el['id']}"}
    if lat is not None and c.get("lat") is not None:
        out["distance_m"] = distance_m(lat, lon, c["lat"], c["lon"])
    return out


def provenance(data: dict | None = None) -> dict:
    return {"source": "OpenStreetMap", "licence": LICENCE, "attribution": "© OpenStreetMap contributors",
            "data_timestamp": (data or {}).get("osm3s", {}).get("timestamp_osm_base"),
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "mode": "live", "note": NOTE}


def results(data: dict, lat: float, lon: float, keep, limit: int) -> dict:
    recs = sorted((r for r in (record(el, lat, lon) for el in data.get("elements", [])) if keep(r)),
                  key=lambda r: r.get("distance_m", 0))
    return {"total": len(recs), "results": recs[:limit], "provenance": provenance(data)}


def feature(osm_type: str, osm_id: int) -> dict:
    """One element from the OSM API (more reliable than Overpass), with its last edit and the editor used."""
    suffix = "/full" if osm_type != "node" else ""
    els = fetch("GET", f"{OSM_API}/{osm_type}/{osm_id}{suffix}.json")["elements"]
    el = next(e for e in els if e["type"] == osm_type and e["id"] == osm_id)
    nodes = [e for e in els if e["type"] == "node" and "lat" in e]
    if osm_type != "node" and nodes:  # centre of a way or relation: mean of its nodes
        el = {**el, "center": {"lat": round(sum(n["lat"] for n in nodes) / len(nodes), 7),
                               "lon": round(sum(n["lon"] for n in nodes) / len(nodes), 7)}}
    cs = fetch("GET", f"{OSM_API}/changeset/{el['changeset']}.json").get("changeset", {}).get("tags", {})
    rec = record(el)
    rec["other_tags"] = {k: v for k, v in el.get("tags", {}).items()
                         if k not in rec["accessibility"] and k in ("opening_hours", "website", "phone", "level")}
    rec["last_edit"] = {"timestamp": el.get("timestamp"), "version": el.get("version"),
                        "changeset": el.get("changeset"), "editor": cs.get("created_by"),
                        "via_onwheels": cs.get("theme") == "onwheels"}
    return {**rec, "provenance": provenance()}


def onwheels_app() -> FastAPI:
    sub = FastAPI(
        title="OnWheels: accessibility features in OpenStreetMap (adapter)",
        version="0.1.0",
        description=("Entrances, kerbs, toilets, lifts, reception desks and disabled parking from OpenStreetMap, "
                     "with the attributes the OnWheels map asks contributors to measure: entrance width, door type, "
                     "automatic doors, kerb height, tactile paving, toilet door width and changing table, lift size "
                     "and speech output, desk height, disabled parking capacity. Lengths are also given in metres "
                     "in measurements_m. Search around a point (coordinates required) in Belgium or Hauts-de-France, "
                     "within 300 m. Live data; when OpenStreetMap's shared server is busy you get 503 with a "
                     "retry time: retry later, do not repeat at once. ODbL: cite '© OpenStreetMap contributors'. A missing attribute means unknown."),
    )

    @sub.get("/features", operation_id="onwheels_search_features", summary="Accessibility features near a point",
             description="Features of the given types within radius_m of a point, nearest first. min_width_m keeps "
                         "only features whose width (or door width) is known and at least that value; "
                         "max_kerb_height_m keeps only those whose kerb height is known and at most that value.")
    def search(latitude: float = Query(ge=-90, le=90, description="e.g. 51.0543 (Ghent, Korenmarkt)"),
               longitude: float = Query(ge=-180, le=180, description="e.g. 3.7196"),
               types: list[Feature] = Query(["entrance", "toilet", "elevator", "disabled_parking"],
                                            description="Feature types to return"),
               radius_m: int = Query(150, ge=10, le=300),
               min_width_m: float | None = Query(None, gt=0, le=5, description="e.g. 0.9"),
               max_kerb_height_m: float | None = Query(None, ge=0, le=1, description="e.g. 0.02"),
               limit: int = Query(30, ge=1, le=100)):
        def keep(r):
            m = r["measurements_m"]
            w = m.get("width", m.get("door:width"))
            return ((min_width_m is None or (w is not None and w >= min_width_m)) and
                    (max_kerb_height_m is None or m.get("kerb:height", 99) <= max_kerb_height_m))
        data = overpass([s for t in types for s in FEATURES[t]], latitude, longitude, radius_m, 400)
        return results(data, latitude, longitude, keep, limit)

    @sub.get("/features/{osm_type}/{osm_id}", operation_id="onwheels_get_feature", summary="One feature",
             description="All accessibility attributes of one feature, its last edit and whether that edit was "
                         "made with the OnWheels map (via_onwheels).")
    def get(osm_type: OsmType = Path(), osm_id: int = Path(ge=1)):
        return feature(osm_type, osm_id)

    return sub


def osm_app() -> FastAPI:
    sub = FastAPI(
        title="OpenStreetMap places with accessibility tags (adapter)",
        version="0.1.0",
        description=("Places in OpenStreetMap (amenity, shop, tourism, leisure, healthcare) that carry community "
                     "accessibility tags: wheelchair (yes = fully accessible, limited = partly, no = not, "
                     "designated = made for wheelchair users), wheelchair:description, toilets:wheelchair, "
                     "hearing_loop (induction loop), ramp, step_count, entrance width and more. Search around a "
                     "point (coordinates required) in Belgium or Hauts-de-France, within 1 km. Live data; when "
                     "OpenStreetMap's shared server is busy you get 503 with a retry time. ODbL: cite '© OpenStreetMap contributors'. "
                     "Places without a tag are left out; a missing tag means unknown."),
    )

    @sub.get("/places", operation_id="osm_search_places", summary="Places with accessibility tags near a point",
             description="Places within radius_m of a point that have at least one of wheelchair, "
                         "wheelchair:description, toilets:wheelchair or hearing_loop, nearest first; optionally "
                         "filtered by kind, name and tag values.")
    def search(latitude: float = Query(ge=-90, le=90, description="e.g. 50.8467 (Brussels, Grand-Place)"),
               longitude: float = Query(ge=-180, le=180, description="e.g. 4.3525"),
               radius_m: int = Query(500, ge=10, le=1000),
               kind: list[str] = Query([], description="OSM values of amenity, shop, tourism, leisure or healthcare, "
                                                       "e.g. restaurant, cafe, museum, hotel, toilets, pharmacy"),
               name: str | None = Query(None, max_length=60, description="Text in the name, case-insensitive"),
               wheelchair: list[Wheelchair] = Query([], description="Keep places with one of these wheelchair values"),
               toilets_wheelchair: bool = Query(False, description="Only places with toilets:wheelchair=yes"),
               hearing_loop: bool = Query(False, description="Only places with hearing_loop=yes"),
               limit: int = Query(30, ge=1, le=100)):
        if any(not re.fullmatch(r"[a-z_]+", k) for k in kind):
            raise HTTPException(422, "kind values are OSM tag values: lowercase letters and underscores")
        sel = f'nwr[~"^({POI_KEYS})$"~"^({"|".join(kind)})$"]' if kind else f'nwr[~"^({POI_KEYS})$"~"."]'
        sel += '[~"^(wheelchair|wheelchair:description|toilets:wheelchair|hearing_loop)$"~"."]' + name_filter(name)
        if wheelchair:
            sel += f'["wheelchair"~"^({"|".join(wheelchair)})$"]'
        if toilets_wheelchair:
            sel += '["toilets:wheelchair"="yes"]'
        if hearing_loop:
            sel += '["hearing_loop"="yes"]'
        return results(overpass([sel], latitude, longitude, radius_m, 300), latitude, longitude, lambda r: True, limit)

    @sub.get("/places/{osm_type}/{osm_id}", operation_id="osm_get_place", summary="One place",
             description="All accessibility tags of one place, its address, opening hours and website, and its "
                         "last edit (date, version, editor).")
    def get(osm_type: OsmType = Path(), osm_id: int = Path(ge=1)):
        return feature(osm_type, osm_id)

    return sub


app = FastAPI(title="OpenStreetMap accessibility (adapters)")
app.mount("/onwheels", onwheels_app())
app.mount("/osm", osm_app())


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "overpass": OVERPASS_URL, "cached_queries": len(_cache)}

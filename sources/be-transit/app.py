"""Belgian public transport stops and stations with their accessibility, as one read-only API per operator.

Snapshot mode: static GTFS feeds (data.belgianmobility.io, CC BY 4.0) and iRail's station facilities (GitHub)
are downloaded into DATA_DIR, reduced to stops, and refreshed every REFRESH_HOURS in the background.
Each operator is a mounted sub-API with its own OpenAPI at /<operator>/openapi.json, so it is its own catalog entry.
"""

import csv
import io
import json
import logging
import math
import os
import threading
import time
import unicodedata
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path as FsPath
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Path, Query

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("be-transit")
DATA_DIR = FsPath(os.environ.get("BE_TRANSIT_DATA", "/data"))
REFRESH_HOURS = float(os.environ.get("REFRESH_HOURS", "24"))
UA = {"user-agent": "accessibility-dataspace-demo/0.1 (open research demonstrator)"}
FEEDS = "https://api-management-discovery-production.azure-api.net/api/gtfs/feed"
IRAIL = "https://raw.githubusercontent.com/iRail/stations/master"
GTFS = {  # operator -> (feed name, attribution name, region)
    "stib": ("stibmivb", "STIB-MIVB", "Brussels"),
    "tec": ("tec", "TEC (LETEC)", "Wallonia"),
    "delijn": ("delijn", "De Lijn", "Flanders"),
}
WHEELCHAIR = {"1": "accessible", "2": "not_accessible"}  # GTFS: 0 or empty means no information
Wheelchair = Literal["accessible", "not_accessible", "unknown"]
FACILITIES = ["wheelchair_available", "ramp", "elevator_platform", "escalator_up", "escalator_down",
              "audio_induction_loop"]
Facility = Literal[tuple(FACILITIES + ["disabled_parking"])]

store: dict[str, dict] = {}  # operator -> {"dataset_date", "retrieved_at", "records": [...]}


def fold(s) -> str:
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower().strip()


def distance_km(lat1, lon1, lat2, lon2) -> float:
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def gtfs_stops(zip_bytes: bytes) -> tuple[list[dict], str | None]:
    """Boarding stops (location_type 0) with their wheelchair_boarding, and the feed's start date."""
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))

    def table(name):
        n = next((x for x in z.namelist() if x.endswith(name)), None)
        return list(csv.DictReader(io.TextIOWrapper(z.open(n), encoding="utf-8-sig"))) if n else []

    info = table("feed_info.txt")
    date = (info[0].get("feed_start_date") or "").strip() if info else None
    stops = [{"id": r["stop_id"], "name": r["stop_name"], "code": r.get("stop_code") or None,
              "latitude": float(r["stop_lat"]), "longitude": float(r["stop_lon"]),
              "wheelchair": WHEELCHAIR.get((r.get("wheelchair_boarding") or "").strip(), "unknown")}
             for r in table("stops.txt") if (r.get("location_type") or "0").strip() in ("0", "")]
    return stops, date


def irail_stations(stations_csv: str, facilities_csv: str) -> list[dict]:
    """Belgian NMBS/SNCB stations with iRail's facilities; empty fields stay unknown (None)."""
    fac = {r["URI"]: r for r in csv.DictReader(io.StringIO(facilities_csv))}

    def val(r, k):
        v = (r.get(k) or "").strip()
        if v == "":
            return None
        if k == "platform_height_cm":  # several platforms: "28;55;76"
            return [int(x) for x in v.split(";")]
        return int(v) if k == "disabled_parking_spots" else v == "1"

    out = []
    for s in csv.DictReader(io.StringIO(stations_csv)):
        if s["country-code"] != "be":
            continue
        f = fac.get(s["URI"], {})
        out.append({"id": s["URI"].rsplit("/", 1)[-1], "uri": s["URI"], "name": s["name"],
                    "latitude": float(s["latitude"]), "longitude": float(s["longitude"]),
                    "address": " ".join(x for x in [f.get("street"), f.get("zip"), f.get("city")] if x) or None,
                    "facilities": {k: val(f, k) for k in FACILITIES + ["disabled_parking_spots", "platform_height_cm"]}})
    return out


def download(url: str) -> bytes:
    r = httpx.get(url, headers=UA, timeout=600, follow_redirects=True)
    r.raise_for_status()
    return r.content


def refresh() -> None:
    """Download all sources, reduce them, and write one JSON file per operator (atomic replace)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    jobs = {op: lambda feed=feed: gtfs_stops(download(f"{FEEDS}/{feed}/static")) for op, (feed, _, _) in GTFS.items()}
    jobs["irail"] = lambda: (irail_stations(download(f"{IRAIL}/stations.csv").decode(),
                                            download(f"{IRAIL}/facilities.csv").decode()), None)
    for op, job in jobs.items():
        try:
            records, date = job()
        except Exception as e:  # keep the previous snapshot of this operator
            log.warning("refresh of %s failed: %s", op, e)
            continue
        tmp = DATA_DIR / f"{op}.json.tmp"
        tmp.write_text(json.dumps({"dataset_date": date or now[:10], "retrieved_at": now, "records": records}))
        tmp.replace(DATA_DIR / f"{op}.json")
        log.info("refreshed %s: %d records, dataset date %s", op, len(records), date or now[:10])
    load()


def load() -> None:
    for f in DATA_DIR.glob("*.json"):
        store[f.stem] = json.loads(f.read_text())


def stale() -> bool:
    files = list(DATA_DIR.glob("*.json"))
    return len(files) < len(GTFS) + 1 or time.time() - min(f.stat().st_mtime for f in files) > REFRESH_HOURS * 3600


def refresher() -> None:
    while True:
        if stale():
            refresh()
        time.sleep(3600)


@asynccontextmanager
async def lifespan(_app):
    load()
    if REFRESH_HOURS > 0:
        threading.Thread(target=refresher, daemon=True).start()
    yield


def snapshot(op: str) -> dict:
    if op not in store:
        raise HTTPException(503, "the data is still being downloaded; retry in a minute")
    return store[op]


def provenance(op: str, name: str, licence: str | None, note: str) -> dict:
    s = store.get(op, {})
    return {"source": name, "licence": licence, "attribution": note.format(date=s.get("dataset_date")),
            "dataset_date": s.get("dataset_date"), "retrieved_at": s.get("retrieved_at"), "mode": "snapshot"}


def near(records, q, latitude, longitude, radius_km):
    if (latitude is None) != (longitude is None):
        raise HTTPException(422, "give both latitude and longitude, or neither")
    hits = []
    for r in records:
        if q and fold(q) not in fold(r["name"]):
            continue
        d = None if latitude is None else distance_km(latitude, longitude, r["latitude"], r["longitude"])
        if d is not None and d > radius_km:
            continue
        hits.append((d, r))
    return sorted(hits, key=lambda h: (h[0] or 0, fold(h[1]["name"]), h[1]["id"]))


def page(hits, start, limit, prov):
    return {"total": len(hits), "results": [{**r, **({"distance_km": round(d, 3)} if d is not None else {})}
                                            for d, r in hits[start:start + limit]], "provenance": prov}


def gtfs_app(op: str) -> FastAPI:
    feed, name, region = GTFS[op]
    licence, note = "https://creativecommons.org/licenses/by/4.0/", f"Source: {name} – Open Data – {{date}}"
    sub = FastAPI(
        title=f"{name} stops: wheelchair accessibility (adapter)",
        version="0.1.0",
        description=(f"Stops of {name} ({region}) from its static GTFS feed on data.belgianmobility.io, with the "
                     "GTFS wheelchair_boarding value per stop: accessible, not_accessible, or unknown (the operator "
                     "gave no information; this is not the same as inaccessible). Licence CC BY 4.0; cite the "
                     "attribution in provenance. Use the search with a name or a point."),
    )

    @sub.get("/stops", operation_id=f"{op}_search_stops", summary=f"Search {name} stops",
             description="Stops matching a name and/or within radius_km of a point (then sorted by distance), "
                         "optionally only those with the given wheelchair values.")
    def search(q: str | None = Query(None, description="Text in the stop name, e.g. 'Gare', 'Korenmarkt'"),
               latitude: float | None = Query(None, ge=-90, le=90),
               longitude: float | None = Query(None, ge=-180, le=180),
               radius_km: float = Query(0.5, gt=0, le=50),
               wheelchair: list[Wheelchair] = Query([], description="Keep stops with one of these values"),
               offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
        hits = [h for h in near(snapshot(op)["records"], q, latitude, longitude, radius_km)
                if not wheelchair or h[1]["wheelchair"] in wheelchair]
        return page(hits, offset, limit, provenance(op, name, licence, note))

    @sub.get("/stops/{stop_id}", operation_id=f"{op}_get_stop", summary=f"One {name} stop")
    def get(stop_id: str = Path(description="Stop id from the search")):
        r = next((r for r in snapshot(op)["records"] if r["id"] == stop_id), None)
        if r is None:
            raise HTTPException(404, "stop not found")
        return {**r, "provenance": provenance(op, name, licence, note)}

    return sub


def irail_app() -> FastAPI:
    name, note = "iRail stations", "Source: iRail stations (github.com/iRail/stations), retrieved {date}"
    sub = FastAPI(
        title="Belgian railway stations: accessibility facilities (adapter)",
        version="0.1.0",
        description=("NMBS/SNCB stations in Belgium with facilities from the iRail stations repository: "
                     "wheelchair_available, ramp (boarding ramp), elevator_platform, escalators, "
                     "audio_induction_loop, disabled_parking_spots and platform_height_cm (a list: one value per platform height). null means unknown. "
                     "wheelchair_available, ramp and audio_induction_loop were last published by NMBS in June 2023; "
                     "lift and escalator data come from OpenStreetMap (ODbL)."),
    )

    @sub.get("/stations", operation_id="irail_search_stations", summary="Search railway stations",
             description="Stations matching a name and/or near a point, optionally only those with all given "
                         "facilities ('disabled_parking' means at least one reserved space).")
    def search(q: str | None = Query(None, description="Text in the station name, e.g. 'Gent', 'Bruxelles'"),
               latitude: float | None = Query(None, ge=-90, le=90),
               longitude: float | None = Query(None, ge=-180, le=180),
               radius_km: float = Query(5, gt=0, le=100),
               has: list[Facility] = Query([], description="Facilities the station must have"),
               offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
        def ok(f):
            return all((f["disabled_parking_spots"] or 0) > 0 if k == "disabled_parking" else f[k] for k in has)
        hits = [h for h in near(snapshot("irail")["records"], q, latitude, longitude, radius_km) if ok(h[1]["facilities"])]
        return page(hits, offset, limit, provenance("irail", name, None, note))

    @sub.get("/stations/{station_id}", operation_id="irail_get_station", summary="One railway station")
    def get(station_id: str = Path(description="Station id from the search, e.g. '008892007'")):
        r = next((r for r in snapshot("irail")["records"] if r["id"] == station_id), None)
        if r is None:
            raise HTTPException(404, "station not found")
        return {**r, "provenance": provenance("irail", name, None, note)}

    return sub


app = FastAPI(title="Belgian public transport accessibility (adapters)", lifespan=lifespan)
for _op in GTFS:
    app.mount(f"/{_op}", gtfs_app(_op))
app.mount("/irail", irail_app())


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "loaded": {op: len(s["records"]) for op, s in store.items()},
            "dates": {op: s["dataset_date"] for op, s in store.items()}}

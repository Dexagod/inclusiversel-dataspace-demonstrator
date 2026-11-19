"""Offline tests: Overpass and the OSM API are replaced by fictional responses."""

import httpx
import pytest
from fastapi.testclient import TestClient

import app as osm

OVERPASS = {"osm3s": {"timestamp_osm_base": "2026-11-18T10:00:00Z"}, "elements": [
    {"type": "node", "id": 1, "lat": 51.0001, "lon": 3.7001,
     "tags": {"entrance": "main", "width": "90 cm", "automatic_door": "button", "kerb:height": "0"}},
    {"type": "node", "id": 2, "lat": 51.0000, "lon": 3.7000,
     "tags": {"entrance": "yes", "width": "0.7"}},
    {"type": "way", "id": 3, "center": {"lat": 51.002, "lon": 3.702},
     "tags": {"amenity": "toilets", "wheelchair": "yes", "door:width": "1,0 m", "fee": "no"}},
]}
NODE = {"elements": [{"type": "node", "id": 1, "lat": 51.0001, "lon": 3.7001, "version": 4, "changeset": 77,
                      "timestamp": "2026-03-01T09:00:00Z", "user": "someone", "uid": 42,
                      "tags": {"amenity": "cafe", "name": "Café Fictief", "wheelchair": "limited",
                               "toilets:wheelchair": "no", "website": "https://example.org"}}]}
CHANGESET = {"changeset": {"id": 77, "tags": {"created_by": "MapComplete 0.50", "theme": "onwheels"}}}


STATUS_FREE = "Rate limit: 2\n2 slots available now.\nCurrently running queries:\n"
STATUS_FULL = "Rate limit: 2\nSlot available after: 2026-11-18T20:00:40Z, in 40 seconds.\n"


@pytest.fixture
def calls(monkeypatch):
    """Overpass queries sent (status checks excluded); the status answer can be changed via calls.status."""
    seen = []

    def fake(method, url, **kw):
        if url.endswith("/api/status"):
            return httpx.Response(200, text=state["status"], request=httpx.Request(method, url))
        seen.append((method, url, (kw.get("data") or {}).get("data")))
        if url == osm.OVERPASS_URL and state["overpass_code"] != 200:
            return httpx.Response(state["overpass_code"], request=httpx.Request(method, url))
        if url == osm.OVERPASS_URL:
            body = OVERPASS
        elif url.endswith("/node/1.json"):
            body = NODE
        elif url.endswith("/changeset/77.json"):
            body = CHANGESET
        else:
            return httpx.Response(404, request=httpx.Request(method, url))
        return httpx.Response(200, json=body, request=httpx.Request(method, url))

    state = {"status": STATUS_FREE, "overpass_code": 200}
    osm._cache.clear()
    osm._state.update(backoff_until=0.0, backoff_s=0, day="", count=0)
    monkeypatch.setattr(osm.httpx, "request", fake)
    return seen, state


client = TestClient(osm.app)


@pytest.mark.parametrize("raw,m", [("0.9", 0.9), ("90 cm", 0.9), ("900mm", 0.9), ("1,2 m", 1.2),
                                    ("wide", None), (None, None), ("3'", None)])
def test_metres(raw, m):
    assert osm.metres(raw) == m


def test_onwheels_search_filters_on_width_and_sorts_by_distance(calls):
    r = client.get("/onwheels/features", params={"latitude": 51.0, "longitude": 3.7, "min_width_m": 0.8})
    body = r.json()
    assert r.status_code == 200
    assert [x["osm_id"] for x in body["results"]] == [1, 3]  # node 2 is 0.7 m wide
    first = body["results"][0]
    assert first["measurements_m"] == {"width": 0.9, "kerb:height": 0.0}
    assert first["accessibility"]["automatic_door"] == "button"
    assert body["results"][1]["measurements_m"] == {"door:width": 1.0}
    assert "fee" not in body["results"][1]["accessibility"]
    assert body["provenance"]["attribution"] == "© OpenStreetMap contributors"
    assert body["provenance"]["data_timestamp"] == "2026-11-18T10:00:00Z"
    q = calls[0][0][2]
    assert 'nwr["entrance"](around:150,51.0,3.7);' in q and 'nwr["amenity"="toilets"]' in q


def test_osm_search_builds_tag_filters_and_escapes_name(calls):
    client.get("/osm/places", params={"latitude": 51.0, "longitude": 3.7, "kind": ["restaurant", "cafe"],
                                      "wheelchair": ["yes", "limited"], "toilets_wheelchair": True,
                                      "name": 'Chez "Nous" (1)'})
    q = calls[0][0][2]
    assert '~"^(restaurant|cafe)$"' in q
    assert '["wheelchair"~"^(yes|limited)$"]["toilets:wheelchair"="yes"]' in q
    assert '["name"~"Chez\\\\ \\"Nous\\"\\\\ \\\\(1\\\\)",i]' in q


def test_osm_search_rejects_odd_kind(calls):
    r = client.get("/osm/places", params={"latitude": 51.0, "longitude": 3.7, "kind": 'cafe"];out;'})
    assert r.status_code == 422 and not calls[0]


def test_detail_reports_onwheels_edit_without_contributor_names(calls):
    body = client.get("/osm/places/node/1").json()
    assert body["accessibility"] == {"toilets:wheelchair": "no", "wheelchair": "limited"}
    assert body["last_edit"] == {"timestamp": "2026-03-01T09:00:00Z", "version": 4, "changeset": 77,
                                 "editor": "MapComplete 0.50", "via_onwheels": True}
    assert body["other_tags"] == {"website": "https://example.org"}
    assert "someone" not in str(body) and "uid" not in str(body)


def test_cache_spares_the_server(calls):
    for _ in range(2):
        client.get("/onwheels/features", params={"latitude": 51.0, "longitude": 3.7})
    assert len(calls[0]) == 1


GHENT = {"latitude": 51.0, "longitude": 3.7}


def test_busy_server_backs_off_without_asking_again(calls):
    sent, state = calls
    state["overpass_code"] = 504
    r = client.get("/osm/places", params=GHENT)
    assert r.status_code == 503 and r.headers["retry-after"] == "30" and "busy" in r.json()["detail"]
    state["overpass_code"] = 200
    r = client.get("/osm/places", params={**GHENT, "radius_m": 200})  # a different query, still backing off
    assert r.status_code == 503 and len(sent) == 1


def test_no_free_slot_means_no_query(calls):
    sent, state = calls
    state["status"] = STATUS_FULL
    r = client.get("/onwheels/features", params=GHENT)
    assert r.status_code == 503 and r.headers["retry-after"] == "40" and not sent


def test_outside_coverage_is_refused_without_query(calls):
    r = client.get("/osm/places", params={"latitude": 45.764, "longitude": 4.8357})  # Lyon
    assert r.status_code == 422 and "Belgium" in r.json()["detail"] and not calls[0]


def test_daily_limit(calls, monkeypatch):
    monkeypatch.setattr(osm, "DAILY_QUERIES", 1)
    assert client.get("/osm/places", params=GHENT).status_code == 200
    r = client.get("/osm/places", params={**GHENT, "radius_m": 200})
    assert r.status_code == 503 and "daily limit" in r.json()["detail"] and len(calls[0]) == 1


def test_nearby_points_share_the_cache(calls):
    client.get("/osm/places", params={"latitude": 51.00001, "longitude": 3.70001})
    client.get("/osm/places", params={"latitude": 51.00002, "longitude": 3.69999})
    assert len(calls[0]) == 1


def test_unknown_feature_is_404(calls):
    assert client.get("/onwheels/features/node/999").status_code == 404

"""Offline tests on fictional places shaped like the PictoAccess export."""

import json

import pytest
from fastapi.testclient import TestClient


def place(uuid, title, city, lat, lon, cats, brands=(), moteur=-2, country="france", address="1 rue X"):
    return {"uuid": uuid, "published": True, "updated_at": "2025-01-01T00:00:00+01:00",
            "content": {"title": title, "display_title": None, "description": "", "page": True},
            "localisation": {"address": address, "postal_code": "76000", "city": city, "country": country,
                             "latitude": lat, "longitude": lon},
            "accessibility": {"handicaps": {"moteur": moteur}, "readable_handicaps": []},
            "referential": None, "photos": [],
            "categories": [{"id": i, "slug": s, "name": s.title()} for i, s in enumerate(cats)],
            "brands": [{"uuid": b, "name": b.upper(), "slug": b} for b in brands]}


PLACES = [
    place("a", "Bâtiment A", "Évreux", 49.0240, 1.1510, ["enseignement"], ["univ", "campus-1"], moteur=2,
          address="55 boulevard Gambetta"),
    place("b", "Bâtiment B", "evreux", 49.0242, 1.1512, ["enseignement"], ["univ", "campus-1"], moteur=0),
    place("c", "Bibliothèque", "Rouen", 49.4431, 1.0993, ["culture"], ["univ"], moteur=-1, country="FR"),
    place("d", "Arrêt de bus", "Évreux", 49.0242, 1.1512, ["transport", "arret-de-bus"], country=None),
]


@pytest.fixture
def client(tmp_path, monkeypatch):
    for p in PLACES:
        (tmp_path / f"{p['uuid']}.json").write_text(json.dumps(p), encoding="utf-8")
    monkeypatch.setenv("PICTOACCESS_PLACES", str(tmp_path))
    import importlib

    import app as app_module

    importlib.reload(app_module)
    with TestClient(app_module.app) as c:
        yield c


def ids(r):
    assert r.status_code == 200, r.text
    return sorted(p["id"] for p in r.json()["places"])


def test_filters(client):
    assert ids(client.get("/places", params={"city": "EVREUX"})) == ["a", "b", "d"]
    assert ids(client.get("/places", params={"address": "gambetta"})) == ["a"]
    assert ids(client.get("/places", params={"q": "bibliotheque"})) == ["c"]
    assert ids(client.get("/places", params={"category": "Arret-De-Bus"})) == ["d"]
    assert ids(client.get("/places", params={"group": "campus"})) == ["a", "b"]
    assert ids(client.get("/places", params={"country": "fr"})) == ["a", "b", "c"]
    assert ids(client.get("/places", params={"mobility": ["autonomous", "with_help"]})) == ["a"]
    assert ids(client.get("/places", params={"mobility": "unknown"})) == ["d"]
    assert client.get("/places", params={"mobility": "great"}).status_code == 422


def test_location_sorted_by_distance(client):
    r = client.get("/places", params={"latitude": 49.0240, "longitude": 1.1510, "radius_km": 1})
    assert [p["id"] for p in r.json()["places"]] == ["a", "d", "b"]
    assert r.json()["places"][0]["distance_km"] == 0
    assert client.get("/places", params={"latitude": 49}).status_code == 422


def test_full_record_and_related(client):
    full = client.get("/places/c").json()
    assert full["place"] == PLACES[2] and full["provenance"]["source"] == "PictoAccess"
    assert client.get("/places/nope").status_code == 404
    rel = client.get("/places/a/related").json()
    assert {g["group"]: sorted(p["id"] for p in g["places"]) for g in rel["same_group"]} == \
        {"UNIV": ["b", "c"], "CAMPUS-1": ["b"]}
    assert [p["id"] for p in rel["nearby"]] == ["b", "d"]


def test_facets_and_openapi(client):
    f = client.get("/facets").json()
    assert f["groups"][0] == {"name": "UNIV", "places": 3}
    assert f["countries"] == {"FR": 3, "None": 1}
    ops = {o["operationId"] for p in client.get("/openapi.json").json()["paths"].values() for o in p.values()}
    assert ops == {"pictoaccess_search_places", "pictoaccess_get_place", "pictoaccess_related_places",
                   "pictoaccess_facets", "pictoaccess_about"}

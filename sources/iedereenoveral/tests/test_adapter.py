"""Offline tests: trimmed upstream responses recorded on 2026-11-12 stand in for the live API."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as adapter
from transform import Lookups, detail, summary

FIX = Path(__file__).parent / "fixtures"


def fixture(name):
    return json.loads((FIX / f"{name}.json").read_text())


@pytest.fixture
def lk():
    return Lookups(*(fixture(n) for n in ("city", "valuation", "locationtype", "filter", "targetaudience")))


@pytest.fixture
def client(monkeypatch):
    calls = []

    async def fake_upstream(path, params=None):
        calls.append((path, params))
        if path.startswith("location/"):
            if path != "location/00015-t-kroonrad":
                raise adapter.HTTPException(404, "place not found")
            return fixture("detail")
        return fixture(path)

    monkeypatch.setattr(adapter, "upstream", fake_upstream)
    adapter._lookups.clear()
    with TestClient(adapter.app) as c:
        c.calls = calls
        yield c


def test_town_aliases_and_postcodes(lk):
    assert set(lk.city_ids("Ghent")) == set(lk.city_ids("gent")) and lk.city_ids("Gent")
    assert lk.city_ids("3000") and lk.city_ids("Louvain") and lk.city_ids("Tokyo") == []


def test_summary_from_html_card(lk):
    s = summary(fixture("location")["items"][0], lk)
    assert s == {"id": "00015-t-kroonrad", "name": "'t Kroonrad", "category": "food_and_drink",
                 "address": "Dorpsstraat 47, 3294 Molenstede", "location": {"lat": 51.0026872, "lon": 5.0177587},
                 "medal": "gold", "source_url": "https://iedereen.overal.info/locaties/00015-t-kroonrad"}


def test_detail_is_compact_and_keeps_answers(lk):
    raw = fixture("detail")
    d = detail(raw, lk)
    assert d["medal"] == "gold" and d["address"]["town"] == "Molenstede"
    assert [a["area"] for a in d["accessibility"]] == ["Toegang", "Toilet"]
    text = json.dumps(d, ensure_ascii=False)
    assert "created_at" not in text and "requirement_id" not in text and "vault" not in text
    assert len(text) < len(json.dumps(raw)) / 5
    numbers = [s for a in d["accessibility"] for s in a["statements"] if s["value"].endswith(" cm")]
    assert numbers, "numeric answers keep their unit"
    assert [a["area"] for a in detail(raw, lk, area="toilet")["accessibility"]] == ["Toilet"]


def test_search_sends_json_arrays_upstream(client, lk):
    r = client.get("/places", params={"town": "Ghent", "category": "food_and_drink",
                                      "needs": ["Toegankelijk toilet"], "medal": ["gold", "silver"]})
    assert r.status_code == 200 and r.json()["places"][0]["id"] == "00015-t-kroonrad"
    _, params = client.calls[-1]
    assert json.loads(params["city_select"]) == lk.city_ids("gent")
    assert json.loads(params["type_filter"]) == [2]
    assert json.loads(params["valuation_filter"]) == [1, 2]
    assert json.loads(params["filter_id"]) == [1]


def test_search_rejects_unknown_values(client):
    assert "unknown town" in client.get("/places", params={"town": "Tokyo"}).json()["detail"]
    assert "facets" in client.get("/places", params={"needs": "Jacuzzi"}).json()["detail"]
    assert client.get("/places", params={"category": "bar"}).status_code == 422


def test_get_place_and_provenance(client):
    d = client.get("/places/00015-t-kroonrad").json()
    assert d["provenance"]["source"] == "IedereenOveral" and d["provenance"]["licence_note"]
    assert client.get("/places/nope").status_code == 404


def test_openapi_is_agent_ready(client):
    spec = client.get("/openapi.json").json()
    ops = [op for item in spec["paths"].values() for op in item.values()]
    assert {o["operationId"] for o in ops} == {"iedereenoveral_search_places", "iedereenoveral_get_place",
                                              "iedereenoveral_facets", "iedereenoveral_about"}
    assert all(o.get("summary") for o in ops)
    params = [p for o in ops for p in o.get("parameters", [])]
    assert all(p.get("description") for p in params if p["name"] not in {"page"})


def test_category_sub_apis(client, lk):
    r = client.get("/toilets/places", params={"town": "Gent"})
    assert r.status_code == 200
    _, params = client.calls[-1]
    assert sorted(json.loads(params["type_filter"])) == sorted(
        lk.type_ids[n] for n in ("Publiek toilet", "Changing place"))
    assert client.get("/toilets/places", params={"category": "museum"}).status_code == 422
    client.get("/museums/places")
    assert json.loads(client.calls[-1][1]["type_filter"]) == [lk.type_ids["Museum"]]
    spec = client.get("/parking/openapi.json").json()
    assert {op["operationId"] for item in spec["paths"].values() for op in item.values()} == {
        "iedereenoveral_parking_search_places", "iedereenoveral_parking_get_place",
        "iedereenoveral_parking_facets", "iedereenoveral_parking_about"}


def test_search_marks_places_inter_confirmed(client, monkeypatch):
    async def upstream(path, params=None):
        if path == "location" and params.get("confirmed_by_inter_filter"):
            return {"items": [], "itemsTotal": 0}  # none of the hits was checked by Inter
        return fixture(path)

    monkeypatch.setattr(adapter, "upstream", upstream)
    hit = client.get("/places", params={"town": "Ghent"}).json()["places"][0]
    assert hit["confirmed_by_inter"] is False
    monkeypatch.setattr(adapter, "upstream", lambda path, params=None: _same(fixture(path)))
    assert client.get("/places", params={"town": "Ghent"}).json()["places"][0]["confirmed_by_inter"] is True


async def _same(value):
    return value

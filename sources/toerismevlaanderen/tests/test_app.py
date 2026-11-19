"""Offline tests: the SPARQL endpoint is replaced by fictional result rows."""

import httpx
import pytest
from fastapi.testclient import TestClient

import app as tv

ACC = tv.ACC


def lit(v, lang=None):
    return {"type": "literal", "value": v, **({"xml:lang": lang} if lang else {})}


def place(i, **kv):
    rows = []
    for k, vals in kv.items():
        for v in vals if isinstance(vals, list) else [vals]:
            rows.append({"prod": {"value": f"http://lod/{i}"}, "id": lit(i), "key": lit(k),
                         "value": lit(*v) if isinstance(v, tuple) else lit(v)})
    return rows


PLACES = (place("1", name="Museum Fictief", category=[("Museum", "nl"), ("Museum", "en")], lat="51.0543",
                lon="3.7174", street="Kouter", number="1", postcode="9000", post_name="Gent", municipality="Gent",
                label=["Toegankelijkheidslabel A+", "Green Key"], website="https://example.org")
          + place("2", alt_name="Eethuis Verzonnen", category=[("Eetgelegenheid", "nl")], lat="51.0500", lon="3.7300",
                  postcode="9000", post_name="Gent", municipality="Gent")
          + place("3", category=[("Tourist information office", "en")], lat="51.2093", lon="3.2247",
                  postcode="8000", post_name="Brugge", municipality="Brugge", label="Toegankelijkheidslabel A"))
TEXTS = [
    {"id": lit("1"), "p": {"value": ACC + "informationAboutEntrances"}, "o": lit("Level entrance.", "en")},
    {"id": lit("1"), "p": {"value": ACC + "informationAboutEntrances"}, "o": lit("Gelijkvloerse ingang.", "nl")},
    {"id": lit("1"), "p": {"value": ACC + "informationAboutCommonToiletFacilities"}, "o": lit("Aangepast toilet.", "nl")},
    {"id": lit("1"), "p": {"value": ACC + "supportForMotoricalHandicap"}, "o": lit("1")},
    {"id": lit("1"), "p": {"value": ACC + "supportForDeaf"}, "o": lit("1")},
    {"id": lit("2"), "p": {"value": ACC + "supportForMotoricalHandicap"}, "o": lit("1")},
    {"id": lit("2"), "p": {"value": "http://schema.org/accessibilitySummary"}, "o": lit("Step of 3 cm.", "en")},
    {"id": lit("9"), "p": {"value": ACC + "supportForBlind"}, "o": lit("1")},  # a place outside the place query
]


@pytest.fixture
def upstream(monkeypatch):
    state = {"fail": False, "calls": 0}

    def fake(query):
        state["calls"] += 1
        if state["fail"]:
            raise httpx.ConnectError("down")
        return PLACES if "?key" in query else TEXTS

    monkeypatch.setattr(tv, "sparql", fake)
    tv._data.update(places=None, next_refresh=0.0, loaded_at=None)
    return state


client = TestClient(tv.app)


def test_topic_names():
    assert tv.topic(ACC + "informationAboutRouteAndLevels") == "route_and_levels"
    assert tv.topic("http://schema.org/accessibilitySummary") == "summary"


def test_search_near_a_point_sorts_by_distance(upstream):
    body = client.get("/places", params={"latitude": 51.054, "longitude": 3.718, "radius_m": 3000}).json()
    assert [r["id"] for r in body["results"]] == ["1", "2"] and body["count"] == 2
    first = body["results"][0]
    assert first["a_label"] == "A+" and first["support"] == ["deaf", "motor"]
    assert first["topics"] == ["common_toilet_facilities", "entrances"]
    assert first["address"] == "Kouter 1, 9000 Gent" and first["distance_m"] < 100
    assert body["provenance"]["licence"] is None and body["provenance"]["licence_note"]


def test_filters(upstream):
    def ids(**params):
        return [r["id"] for r in client.get("/places", params=params).json()["results"]]
    assert ids(a_label=["A", "A+"]) == ["1", "3"]  # sorted by name: "Museum ..." before "Tourist ..."
    assert ids(municipality="8000") == ["3"]
    assert ids(municipality="gent", support=["motor"]) == ["2", "1"]  # "Eethuis" before "Museum"
    assert ids(support=["motor", "deaf"]) == ["1"]
    assert ids(category="eetgelegenheid") == ["2"]
    assert ids(name="fictief") == ["1"]
    assert client.get("/places", params={"latitude": 51}).status_code == 422


def test_names_fall_back(upstream):
    names = {r["id"]: r["name"] for r in client.get("/places").json()["results"]}
    assert names == {"1": "Museum Fictief", "2": "Eethuis Verzonnen", "3": "Tourist information office, Brugge"}


def test_detail_falls_back_to_the_other_language(upstream):
    body = client.get("/places/1", params={"lang": "en"}).json()
    assert body["texts"] == {"common_toilet_facilities": "Aangepast toilet.", "entrances": "Level entrance."}
    assert body["texts_in_other_language"] == ["common_toilet_facilities"]
    assert body["website"] == "https://example.org" and body["linked_data_uri"] == "http://lod/1"
    assert "one topic too far" in body["topic_note"]
    assert client.get("/places/9").status_code == 404


def test_loaded_once_and_old_data_survives_a_failed_refresh(upstream):
    client.get("/places")
    client.get("/places/1")
    assert upstream["calls"] == 2  # two queries, one load
    tv._data["next_refresh"] = 0.0
    upstream["fail"] = True
    assert client.get("/places/1").status_code == 200  # old data served
    assert tv._data["next_refresh"] > 0


def test_unreachable_without_data_is_503(upstream):
    upstream["fail"] = True
    r = client.get("/places")
    assert r.status_code == 503 and r.headers["retry-after"] == "60"

"""Offline tests on a fictional GTFS feed and fictional iRail CSVs."""

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

STOPS = """stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station,wheelchair_boarding
S1,Gare Centrale A,50.8450,4.3570,0,ST,1
S2,Gare Centrale B,50.8452,4.3572,0,ST,2
S3,Korenmarkt,51.0545,3.7210,,,0
ST,Gare Centrale,50.8451,4.3571,1,,
"""
FEED_INFO = "feed_publisher_name,feed_start_date\nX, 20261114\n"
STATIONS = """URI,name,country-code,longitude,latitude
http://irail.be/stations/NMBS/008892007,Gent-Sint-Pieters,be,3.710675,51.035896
http://irail.be/stations/NMBS/008400319,'s Hertogenbosch,nl,5.29,51.69
http://irail.be/stations/NMBS/008895000,Aalst,be,4.039653,50.942813
"""
FACILITIES = """URI,name,street,zip,city,wheelchair_available,ramp,disabled_parking_spots,platform_height_cm,escalator_up,escalator_down,elevator_platform,audio_induction_loop
http://irail.be/stations/NMBS/008892007,Gent-Sint-Pieters,Koningin Maria Hendrikaplein,9000,Gent,1,1,10,28;55;76,1,1,1,1
http://irail.be/stations/NMBS/008895000,Aalst,,,,0,,0,,0,0,0,
"""


def gtfs_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("stops.txt", STOPS)
        z.writestr("feed_info.txt", FEED_INFO)
    return buf.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BE_TRANSIT_DATA", str(tmp_path))
    monkeypatch.setenv("REFRESH_HOURS", "0")
    import importlib

    import app as app_module

    importlib.reload(app_module)

    def fake_download(url):
        if url.endswith("/static"):
            return gtfs_zip()
        return (STATIONS if url.endswith("stations.csv") else FACILITIES).encode()

    monkeypatch.setattr(app_module, "download", fake_download)
    app_module.refresh()
    with TestClient(app_module.app) as c:
        yield c


def test_gtfs_stops(client):
    r = client.get("/stib/stops", params={"q": "gare centrale"}).json()
    assert [(s["id"], s["wheelchair"]) for s in r["results"]] == [("S1", "accessible"), ("S2", "not_accessible")]
    assert r["provenance"]["attribution"] == "Source: STIB-MIVB – Open Data – 20261114"
    # 0 means no information, not inaccessible; stations (location_type 1) are not stops
    assert client.get("/delijn/stops/S3").json()["wheelchair"] == "unknown"
    assert client.get("/delijn/stops/ST").status_code == 404
    near = client.get("/tec/stops", params={"latitude": 50.8450, "longitude": 4.3570, "radius_km": 0.1,
                                            "wheelchair": "accessible"}).json()
    assert [s["id"] for s in near["results"]] == ["S1"] and near["results"][0]["distance_km"] == 0
    assert client.get("/tec/stops", params={"latitude": 50}).status_code == 422


def test_irail_stations(client):
    r = client.get("/irail/stations", params={"has": ["ramp", "disabled_parking"]}).json()
    assert [s["name"] for s in r["results"]] == ["Gent-Sint-Pieters"]
    assert r["results"][0]["facilities"]["platform_height_cm"] == [28, 55, 76]
    aalst = client.get("/irail/stations/008895000").json()
    assert aalst["facilities"]["ramp"] is None and aalst["facilities"]["elevator_platform"] is False
    assert client.get("/irail/stations/008400319").status_code == 404  # not in Belgium


def test_one_openapi_per_operator(client):
    for op, ops in {"stib": {"stib_search_stops", "stib_get_stop"},
                    "irail": {"irail_search_stations", "irail_get_station"}}.items():
        spec = client.get(f"/{op}/openapi.json").json()
        assert {o["operationId"] for p in spec["paths"].values() for o in p.values()} == ops


def test_not_loaded_yet(tmp_path, monkeypatch):
    monkeypatch.setenv("BE_TRANSIT_DATA", str(tmp_path))
    monkeypatch.setenv("REFRESH_HOURS", "0")
    import importlib

    import app as app_module

    importlib.reload(app_module)
    with TestClient(app_module.app) as c:
        assert c.get("/stib/stops").status_code == 503

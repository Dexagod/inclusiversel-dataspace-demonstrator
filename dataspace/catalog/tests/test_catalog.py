import json

import pytest
from fastapi.testclient import TestClient
from rdflib import Graph

OPENAPI = {"openapi": "3.1.0", "info": {"title": "Test", "version": "1"}, "paths": {}}
REG = {
    "id": "test-places",
    "title": "Example Ghent places",
    "description": "Wheelchair accessibility of venues in Ghent",
    "publisher": {"name": "KNoWS demo"},
    "licence": "https://creativecommons.org/licenses/by/4.0/",
    "endpoint_url": "http://test-source:8000/",
    "openapi_url": "http://test-source:8000/openapi.json",
    "keywords": ["wheelchair", "toilet"],
    "languages": ["nl", "en"],
    "spatial": ["Ghent", "Flanders"],
    "update_frequency": "MONTHLY",
    "conforms_to": [{"url": "https://gtfs.org/documentation/schedule/reference/", "title": "GTFS Schedule"}],
    "distributions": [{"url": "https://example.org/guide.pdf", "media_type": "application/pdf", "title": "Guide"}],
    "assessment": {"methods": ["certified", "crowd_sourced"], "note": "verified=true: checked on site."},
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib

    import app as app_module

    importlib.reload(app_module)

    async def ok(url):
        if "broken" in url:
            raise app_module.HTTPException(422, "openapi_url could not be fetched")
        return OPENAPI

    monkeypatch.setattr(app_module, "fetch_openapi", ok)
    with TestClient(app_module.app) as c:
        yield c


def test_register_search_and_get(client):
    assert client.post("/datasets", json=REG).status_code == 201
    assert client.post("/datasets", json=REG).status_code == 409
    hits = client.get("/datasets", params={"q": "restaurant wheelchair Ghent"}).json()
    assert [h["id"] for h in hits] == ["test-places"]
    assert hits[0]["openapi_url"] == REG["openapi_url"]
    assert hits[0]["assessment"]["methods"] == ["certified", "crowd_sourced"]
    assert client.get("/datasets", params={"q": "tokyo"}).json() == []
    assert client.get("/datasets", params={"language": "fr"}).json() == []
    assert client.get("/datasets", params={"spatial": "flan"}).json()[0]["id"] == "test-places"
    full = client.get("/datasets/test-places").json()
    assert full["registered_at"] and "openapi" not in full  # the copy is served separately


def test_invalid_registration_is_readable(client):
    bad = {**REG, "languages": ["xx"], "licence": "not a url", "assessment": {"methods": ["rumour"], "note": "x"}}
    r = client.post("/datasets", json=bad)
    assert r.status_code == 422
    text = json.dumps(r.json())
    assert "unknown language codes" in text and "licence" in text and "assessment" in text
    assert client.post("/datasets", json={**REG, "openapi_url": "http://broken/openapi.json"}).status_code == 422


def test_dcat_output(client):
    client.put("/datasets/test-places", json=REG)
    ttl = client.get("/catalog").text
    g = Graph().parse(data=ttl, format="turtle")
    q = """PREFIX dcat: <http://www.w3.org/ns/dcat#>
           SELECT ?desc WHERE { ?s a dcat:DataService ; dcat:endpointDescription ?desc }"""
    copy = "http://localhost:8001/services/test-places/openapi.json"
    assert [str(r.desc) for r in g.query(q)] == [copy]
    assert client.get("/services/test-places/openapi.json").json() == OPENAPI
    std = """PREFIX dct: <http://purl.org/dc/terms/>
             SELECT ?src ?title WHERE { <%s> dct:source ?src . ?d dct:conformsTo ?s . ?s a dct:Standard ; dct:title ?title }"""
    assert [(str(r.src), str(r.title)) for r in g.query(std % copy)] == [(REG["openapi_url"], "GTFS Schedule")]
    pdf = """PREFIX dcat: <http://www.w3.org/ns/dcat#>
             SELECT ?file ?type WHERE { ?d dcat:distribution ?x . ?x dcat:downloadURL ?file ; dcat:mediaType ?type }"""
    assert [(str(r.file), str(r.type)) for r in g.query(pdf)] == [
        ("https://example.org/guide.pdf", "https://www.iana.org/assignments/media-types/application/pdf")]
    prov = """PREFIX dct: <http://purl.org/dc/terms/> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
              SELECT ?label WHERE { ?d dct:provenance ?p . ?p a dct:ProvenanceStatement ; rdfs:label ?label }"""
    assert [str(r.label) for r in g.query(prov)] == ["Collection methods: certified, crowd_sourced. verified=true: checked on site."]
    jsonld = client.get("/catalog", params={"format": "jsonld"})
    assert jsonld.headers["content-type"].startswith("application/ld+json")
    Graph().parse(data=jsonld.text, format="json-ld")
    sparql = client.get("/sparql", params={"query": q.replace("?desc WHERE", "(COUNT(*) AS ?n) WHERE")})
    assert sparql.json()["results"]["bindings"][0]["n"]["value"] == "1"


def test_persistence_and_delete(client, tmp_path):
    client.post("/datasets", json=REG)
    assert (tmp_path / "datasets" / "test-places.json").exists()
    assert client.delete("/datasets/test-places").status_code == 204
    assert client.get("/datasets/test-places").status_code == 404


def test_unknown_licence_needs_a_note_in_dcat(client):
    reg = {k: v for k, v in REG.items() if k != "licence"}
    assert "licence_note" in client.post("/datasets", json=reg).text
    reg["licence_note"] = "Terms not yet confirmed"
    assert client.post("/datasets", json=reg).status_code == 201
    assert client.get("/datasets").json()[0]["licence_note"] == "Terms not yet confirmed"
    ttl = client.get("/catalog").text
    assert "dct:rights" in ttl and "Terms not yet confirmed" in ttl and "dct:license" not in ttl


def test_country_sub_catalogs(client):
    client.put("/datasets/test-places", json={**REG, "catalog": "belgium"})
    client.put("/datasets/fr-source", json={**REG, "id": "fr-source", "catalog": "france"})
    assert client.put("/datasets/x-source", json={**REG, "id": "x-source", "catalog": "mars"}).status_code == 422
    assert {c["id"]: c["datasets"] for c in client.get("/catalogs").json()} == \
        {"belgium": ["test-places"], "france": ["fr-source"], "belgium-mobility": [], "france-mobility": []}
    assert [h["id"] for h in client.get("/datasets", params={"catalog": "france"}).json()] == ["fr-source"]
    g = Graph().parse(data=client.get("/catalog").text, format="turtle")
    q = """PREFIX dcat: <http://www.w3.org/ns/dcat#> PREFIX dct: <http://purl.org/dc/terms/>
           SELECT ?cid ?ds WHERE { ?root dcat:catalog ?sub . ?sub dct:identifier ?cid ; dcat:dataset ?d .
                                   ?d dct:identifier ?ds }"""
    assert sorted((str(r.cid), str(r.ds)) for r in g.query(q)) == [("belgium", "test-places"), ("france", "fr-source")]


SOURCE_DCAT = """<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:dcat="http://www.w3.org/ns/dcat#"
         xmlns:dcterms="http://purl.org/dc/terms/">
  <dcat:Catalog rdf:about="https://portal.example/"><dcat:dataset rdf:resource="https://portal.example/ds/lifts/"/></dcat:Catalog>
  <dcat:Dataset rdf:about="https://portal.example/ds/lifts/">
    <dcterms:title>Lift status</dcterms:title>
    <dcterms:publisher rdf:resource="Ville de Liège"/>
    <dcat:distribution><dcat:Distribution rdf:about="https://portal.example/ds/lifts/csv">
      <dcat:accessURL rdf:resource="https://portal.example/ds/lifts/csv"/></dcat:Distribution></dcat:distribution>
  </dcat:Dataset>
</rdf:RDF>"""


def test_source_dcat_is_copied(client, monkeypatch):
    import app as app_module
    from dcat import extract_dataset

    async def fake_fetch(url):
        uri, turtle = extract_dataset(SOURCE_DCAT, "application/rdf+xml")
        return {"uri": uri, "turtle": turtle}

    monkeypatch.setattr(app_module, "fetch_source_dcat", fake_fetch)
    client.put("/datasets/test-places", json={**REG, "source_dcat_url": "https://portal.example/dcat"})
    g = Graph().parse(data=client.get("/catalog").text, format="turtle")
    q = """PREFIX dct: <http://purl.org/dc/terms/> PREFIX dcat: <http://www.w3.org/ns/dcat#>
           SELECT ?title ?url WHERE { ?ours dct:identifier "test-places" ; dct:source ?orig .
                                      ?orig dct:title ?title ; dcat:distribution/dcat:accessURL ?url }"""
    assert [(str(r.title), str(r.url)) for r in g.query(q)] == [("Lift status", "https://portal.example/ds/lifts/csv")]
    assert "https://portal.example/" not in {str(s) for s in g.subjects()}  # the publisher's catalog node is not copied


def test_extract_dataset_needs_exactly_one():
    from dcat import extract_dataset
    with pytest.raises(ValueError, match="exactly one"):
        extract_dataset("<x:a> <x:b> <x:c> .", "text/turtle")


def test_every_catalog_uri_resolves(client):
    client.put("/datasets/test-places", json={**REG, "catalog": "belgium"})
    g = Graph().parse(data=client.get("/catalog").text, format="turtle")
    base = "http://localhost:8001"
    uris = {str(t).split("#")[0] for triple in g for t in triple if str(t).startswith(base + "/")}
    assert {u.split("/")[3] for u in uris} >= {"catalog", "catalogs", "datasets", "services", "themes"}
    for u in sorted(uris):
        assert client.get(u[len(base):]).status_code == 200, u
    assert client.get("/services/nope").status_code == 404

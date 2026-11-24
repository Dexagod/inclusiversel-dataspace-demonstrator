import pytest

import json

from openapi_calls import CallError, build_request, compact, condense, load_credentials, shrink

SPEC = {
    "openapi": "3.1.0",
    "info": {"title": "T"},
    "paths": {
        "/places": {"get": {
            "operationId": "search", "security": [{"key": []}],
            "parameters": [
                {"$ref": "#/components/parameters/q"},
                {"name": "category", "in": "query", "schema": {"type": "string", "enum": ["cafe", "museum"]}},
                {"name": "medal", "in": "query", "schema": {"anyOf": [
                    {"type": "array", "items": {"enum": ["gold", "silver"], "type": "string"}}, {"type": "null"}]}},
            ]}},
        "/places/{id}": {"get": {"operationId": "get", "security": [{"key": []}],
                                 "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}]},
                         "delete": {"operationId": "remove"}},
        "/open": {"get": {"operationId": "open"}},
    },
    "components": {
        "parameters": {"q": {"name": "q", "in": "query", "schema": {"type": "string"}}},
        "securitySchemes": {"key": {"type": "apiKey", "in": "header", "name": "X-API-Key"}},
    },
}
BASE = "http://src:8000/api/"


def test_condense_lists_read_operations_only():
    c = condense(SPEC, credentials_configured=True)
    assert [o["operation_id"] for o in c["operations"]] == ["search", "get", "open"]
    search = c["operations"][0]
    assert search["requires_api_key"] and search["parameters"][1]["enum"] == ["cafe", "museum"]
    assert search["parameters"][2]["enum"] == ["gold", "silver"]


def test_condense_shows_only_the_registered_operations():
    assert [o["operation_id"] for o in condense(SPEC, False, ["get"])["operations"]] == ["get"]


def test_compact_drops_empty_values_but_keeps_false_and_zero():
    assert compact({"a": None, "b": "", "c": [None, {}], "d": {"e": None}, "f": False, "g": 0, "h": [1, ""]}) == \
        {"f": False, "g": 0, "h": [1]}


def test_shrink_drops_whole_records_and_keeps_valid_json():
    body = {"count": 30, "meta": {"q": "x"}, "results": [{"name": f"place {i}", "text": "x" * 100} for i in range(30)]}
    fits = lambda b: len(json.dumps(b)) <= 1000
    small, cut = shrink(body, fits)
    assert fits(small) and small["count"] == 30 and small["results"] == body["results"][:cut["kept"]]
    assert cut["of"] == 30 and 1 <= cut["kept"] < 30
    assert shrink(body, lambda b: True) == (body, None)
    nested, cut = shrink({"data": {"places": body["results"]}}, fits)
    assert len(nested["data"]["places"]) == cut["kept"]


def test_key_injected_from_security_scheme():
    method, url, query, headers = build_request(SPEC, BASE, "get", {"id": "a/b"}, {"api_key": "s3"})
    assert (method, url, headers) == ("GET", "http://src:8000/api/places/a%2Fb", {"X-API-Key": "s3"})


def test_key_override_with_prefix():
    cred = {"api_key": "s3", "in": "header", "name": "Authorization", "prefix": "Api-Key "}
    *_, headers = build_request(SPEC, BASE, "search", {"q": "x"}, cred)
    assert headers == {"Authorization": "Api-Key s3"}


@pytest.mark.parametrize("op,params,cred,msg", [
    ("nope", {}, None, "unknown operation_id"),
    ("remove", {"id": "1"}, None, "only read operations"),
    ("search", {"city": "Gent"}, {"api_key": "k"}, "not in the OpenAPI"),
    ("get", {}, {"api_key": "k"}, "missing required"),
    ("search", {"category": "bar"}, {"api_key": "k"}, "is not one of"),
    ("search", {"medal": ["gold", "tin"]}, {"api_key": "k"}, r"\['tin'\] is not one of"),
    ("open", {}, {"api_key": "k"}, "no apiKey/http security scheme"),
])
def test_rejected_calls(op, params, cred, msg):
    with pytest.raises(CallError, match=msg):
        build_request(SPEC, BASE, op, params, cred)


def test_open_operation_without_key():
    assert build_request(SPEC, BASE, "open", {}, None)[1] == "http://src:8000/api/open"


def test_declared_key_missing_still_calls():
    *_, query, headers = build_request(SPEC, BASE, "search", {}, None)
    assert query == {} and headers == {}


def test_credentials_env_interpolation(tmp_path, monkeypatch):
    f = tmp_path / "c.yaml"
    f.write_text("a:\n  api_key: ${KEY_A}\nb:\n  api_key: ${KEY_UNSET}\n")
    monkeypatch.setenv("KEY_A", "secret")
    monkeypatch.delenv("KEY_UNSET", raising=False)
    assert load_credentials(str(f)) == {"a": {"api_key": "secret"}}
    assert load_credentials(str(tmp_path / "missing.yaml")) == {}


def test_source_url_map():
    from openapi_calls import parse_url_map, reachable
    m = parse_url_map("http://src-a:8000/=http://localhost:8103/, http://src-b:8000/=https://b.example.org/")
    assert reachable("http://src-a:8000/places?q=1", m) == "http://localhost:8103/places?q=1"
    assert reachable("https://acceslibre.beta.gouv.fr/api/erps/", m) == "https://acceslibre.beta.gouv.fr/api/erps/"
    assert parse_url_map("") == []
    with pytest.raises(ValueError):
        parse_url_map("no-equals-sign")

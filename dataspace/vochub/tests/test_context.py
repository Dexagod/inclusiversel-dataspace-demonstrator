from fastapi.testclient import TestClient

import app as vochub

client = TestClient(vochub.app)  # no `with`: the lifespan (embedding model, Qdrant) is not needed here


def test_context_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(vochub, "CONTEXT_FILE", tmp_path / "sub" / "context.md")
    assert client.get("/context").json() == {"text": "", "updated_at": None}
    r = client.put("/context", json={"text": "Prefer recent, audited data."})
    assert r.json()["text"] == "Prefer recent, audited data." and r.json()["updated_at"]
    assert client.get("/context").json()["text"] == "Prefer recent, audited data."
    assert client.put("/context", json={"text": "x" * 20_001}).status_code == 422

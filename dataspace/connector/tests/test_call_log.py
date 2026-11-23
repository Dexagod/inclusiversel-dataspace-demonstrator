import asyncio
import json

import calls
import server


def test_logged_writes_one_line_without_the_data(monkeypatch, capsys):
    monkeypatch.setattr(server, "CALL_LOG", True)

    @server.logged
    async def call_source_operation(dataset_id: str, operation_id: str, params: dict | None = None) -> dict:
        return {"provenance": {"status": 200}, "data": {"places": ["secret-ish place data"]}, "truncated": True}

    result = asyncio.run(call_source_operation(dataset_id="x", operation_id="x_search", params={"town": "Gent"}))
    assert result["truncated"]
    entry = json.loads(capsys.readouterr().out)
    assert entry["tool"] == "call_source_operation" and entry["args"]["params"] == {"town": "Gent"}
    assert entry["status"] == 200 and entry["truncated"] is True and entry["ms"] >= 0
    assert "place data" not in json.dumps(entry)


def test_logged_is_silent_when_off(monkeypatch, capsys):
    monkeypatch.setattr(server, "CALL_LOG", False)

    @server.logged
    async def catalog_search(query: str = "") -> dict:
        return {"results": []}

    asyncio.run(catalog_search(query="museum"))
    assert capsys.readouterr().out == ""


def test_summary_shows_gaps_and_blocks(capsys):
    lines = [
        '{"call_log": 1, "start": "2026-11-23T10:00:00.000+00:00", "tool": "catalog_search", "args": {"query": "Lille"}, "ms": 500, "results": 3}',
        '{"call_log": 1, "start": "2026-11-23T10:00:10.500+00:00", "tool": "call_source_operation", "args": {"dataset_id": "acceslibre", "operation_id": "listErps", "params": {}}, "ms": 1000, "status": 200}',
        '{"call_log": 1, "start": "2026-11-23T11:00:00.000+00:00", "tool": "vochub_search", "args": {"question": "label"}, "ms": 200}',
        "INFO: some other log line",
    ]
    calls.main(lines)
    out = capsys.readouterr().out
    assert "block 1" in out and "block 2" in out  # an hour apart: two questions
    assert "10.0" in out  # the gap between the first two calls
    assert "acceslibre.listErps 1x" in out

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

from types import SimpleNamespace
from starlette.requests import Request
from request_identity import capture_requester, requester


def request_for(body=None):
    raw = json.dumps(body or {}).encode()
    async def receive():
        return {'type': 'http.request', 'body': raw, 'more_body': False}
    return Request({'type': 'http', 'method': 'POST', 'path': '/demo/replay',
                    'headers': [(b'content-type', b'application/json'), (b'user-agent', b'Fictional client'),
                                (b'mcp-session-id', b'fixture-session'), (b'authorization', b'fictional-secret')],
                    'client': ('127.0.0.1', 1234)}, receive)


def test_request_metadata_is_allowlisted_and_scoped():
    async def run():
        async def handle(ctx):
            await asyncio.sleep(0)
            return dict(requester.get())
        def context(identifier):
            return SimpleNamespace(request=request_for(), request_id=identifier, protocol_version='test',
                                   session=SimpleNamespace(client_params=SimpleNamespace(client_info=SimpleNamespace(name='Example', version='1', title=None))))
        first, second = await asyncio.gather(capture_requester(context('one'), handle), capture_requester(context('two'), handle))
        assert first['request_id'] == 'one' and second['request_id'] == 'two'
        assert first['client_name'] == 'Example' and first['session_id'] == 'fixture-session'
        assert 'secret' not in json.dumps(first) and 'authorization' not in first
        assert requester.get() == {}
    asyncio.run(run())


def test_replay_runs_validated_tool_and_logs_as_viewer(monkeypatch, capsys):
    monkeypatch.setattr(server, 'CALL_LOG', True)
    async def get_json(*args, **kwargs):
        return []
    monkeypatch.setattr(server, '_get_json', get_json)
    monkeypatch.setattr(server, 'load_credentials', lambda path: {})
    response = asyncio.run(server.replay_call(request_for({'tool': 'catalog_search', 'args': {'query': 'fictional'}})))
    assert response.status_code == 200
    body = json.loads(response.body)
    assert json.loads(body['result']['content'][0]['text'])['results'] == []
    entry = json.loads(capsys.readouterr().out)
    assert entry['requester']['client_name'] == 'Data space viewer replay'
    assert entry['call_id'] and entry['args']['query'] == 'fictional'
    assert entry['args']['theme'] is None
    assert requester.get() == {}


def test_replay_rejects_unknown_tools_and_invalid_arguments(monkeypatch):
    assert asyncio.run(server.replay_call(request_for({'tool': 'delete', 'args': {}}))).status_code == 400
    assert asyncio.run(server.replay_call(request_for({'tool': [], 'args': {}}))).status_code == 400
    # Required arguments are validated by the same SDK path as MCP requests.
    assert asyncio.run(server.replay_call(request_for({'tool': 'call_source_operation', 'args': {}}))).status_code == 502

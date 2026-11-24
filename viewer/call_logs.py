"""Read bounded connector call-log snapshots; no source response bodies."""
import json
import math
from datetime import datetime

MAX_BYTES = 8 * 1024 * 1024
MAX_CALLS = 1000
FIELDS = {'call_log', 'start', 'tool', 'args', 'ms', 'chars', 'results', 'status',
          'truncated', 'records_cut', 'error', 'exception', 'call_id'}
IDENTITY_FIELDS = {'session_id', 'client_id', 'client_name', 'client_version', 'client_title',
                   'request_id', 'remote_address', 'forwarded_for', 'user_agent', 'protocol_version'}


def parse_logs(text):
    calls, skipped = [], 0
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            # Docker Compose may prefix each JSON line with a container name.
            item = json.loads(line[line.index('{'):])
            if not isinstance(item, dict) or item.get('call_log') != 1:
                raise ValueError()
            if not isinstance(item.get('start'), str):
                raise ValueError()
            stamp = datetime.fromisoformat(item['start'].replace('Z', '+00:00'))
            if stamp.tzinfo is None or not isinstance(item['tool'], str):
                raise ValueError()
            if not isinstance(item['ms'], (int, float)) or not math.isfinite(item['ms']) or item['ms'] < 0:
                raise ValueError()
            if not isinstance(item.get('args', {}), dict):
                raise ValueError()
            clean = {key: value for key, value in item.items() if key in FIELDS}
            identity = item.get('requester')
            if isinstance(identity, dict):
                clean['requester'] = {key: str(value)[:512] for key, value in identity.items()
                                      if key in IDENTITY_FIELDS and isinstance(value, (str, int, float))}
            calls.append(clean)
        except (ValueError, TypeError, KeyError):
            skipped += 1
    calls.sort(key=lambda item: datetime.fromisoformat(item['start'].replace('Z', '+00:00')))
    return {'calls': calls[-MAX_CALLS:], 'skipped': skipped, 'omitted': max(0, len(calls) - MAX_CALLS)}


def read_snapshot(path):
    if not path:
        return {'configured': False, 'calls': [], 'skipped': 0, 'omitted': 0}
    try:
        with open(path, 'rb') as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError('Log snapshot exceeds 8 MiB; restart the collector with a smaller tail.')
        return {'configured': True, **parse_logs(data.decode('utf-8'))}
    except FileNotFoundError:
        return {'configured': True, 'calls': [], 'skipped': 0, 'omitted': 0, 'waiting': True}

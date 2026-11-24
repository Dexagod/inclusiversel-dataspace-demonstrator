import json
import tempfile
import unittest
from pathlib import Path
from call_logs import parse_logs, read_snapshot


class LogTests(unittest.TestCase):
    def test_parse_and_validate(self):
        event = {'call_log': 1, 'start': '2026-11-24T10:00:00Z', 'tool': 'catalog_search', 'args': {}, 'ms': 25, 'data': 'not logged'}
        result = parse_logs('INFO startup\nconnector | ' + json.dumps(event) + '\n' + json.dumps({**event, 'ms': -1}))
        self.assertEqual(len(result['calls']), 1)
        self.assertEqual(result['skipped'], 2)
        self.assertNotIn('data', result['calls'][0])

    def test_disabled_missing_and_snapshot(self):
        self.assertFalse(read_snapshot(None)['configured'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'calls.jsonl'
            self.assertTrue(read_snapshot(path)['waiting'])
            path.write_text('')
            self.assertEqual(read_snapshot(path)['calls'], [])

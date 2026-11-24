import test from 'node:test';
import assert from 'node:assert/strict';
import {parseLogText, summarizeCalls} from '../static/logs.mjs';
const call = (start, ms, extra = {}) => ({call_log: 1, start: `2026-11-24T10:${start}Z`, tool: 'catalog_search', args: {query: 'fictional'}, ms, ...extra});
test('reads JSONL and Compose prefixes, rejects malformed entries and excludes response data', () => {
  const data = parseLogText(['INFO startup', 'broken {', JSON.stringify(call('00:00', 100, {data: 'private response'})), `connector | ${JSON.stringify(call('00:01', 200))}`, JSON.stringify(call('00:02', -1))].join('\n'));
  assert.equal(data.calls.length, 2);
  assert.equal(data.skipped, 3);
  assert.equal('data' in data.calls[0], false);
});
test('overlapping durations do not create negative idle time; long gaps form activity blocks', () => {
  const stats = summarizeCalls([call('00:00', 2000), call('00:01', 2000), call('03:10', 1000, {status: 503})]);
  assert.equal(stats.toolTime, 5000);
  assert.equal(stats.busy, 4000);
  assert.equal(stats.elapsed, 191000);
  assert.equal(stats.blocks, 2);
  assert.equal(stats.failures, 1);
  assert.equal(summarizeCalls([]).elapsed, 0);
});
test('retains only the latest 1000 calls', () => {
  const text = Array.from({length: 1002}, () => JSON.stringify(call('00:00', 1))).join('\n');
  assert.equal(parseLogText(text).calls.length, 1000);
  assert.equal(parseLogText(text).omitted, 2);
});

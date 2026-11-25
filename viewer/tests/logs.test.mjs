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

import {callKey, groupCalls, clientIdentity, reconcileChildren} from '../static/logs.mjs';
test('interleaved clients get separate groups; idle gaps are per client', () => {
  const a = {session_id: 'session-a', client_name: 'Example A'}, b = {session_id: 'session-b', client_name: 'Example B'};
  const groups = groupCalls([call('00:00', 1000, {requester: a}), call('00:10', 100, {requester: b}), call('01:00', 100, {requester: a}), call('04:00', 100, {requester: a})]);
  assert.deepEqual(groups.map(g => g.calls.length), [2, 1, 1]);
  assert.equal(groups[0].identity.name, 'Example A');
  assert.notEqual(groups[0].key, groups[2].key);
});
test('group keys survive appended requests and eviction of the oldest call', () => {
  const events = ['00:00', '00:10', '00:20'].map((time, i) => call(time, 1, {call_id: `call-${i}`, requester: {session_id: 'example'}}));
  const original = groupCalls(events.slice(0, 2));
  assert.equal(groupCalls(events, 120000, original)[0].key, original[0].key);
  assert.equal(groupCalls(events.slice(1), 120000, original)[0].key, original[0].key);
  assert.equal(callKey({...events[0], chars: 50}), callKey(events[0]));
});
test('identity fields are allowlisted; unknown and inferred clients are labelled honestly', () => {
  const parsed = parseLogText(JSON.stringify(call('00:00', 1, {requester: {client_name: 'Example', session_id: 'abc', authorization: 'fictional-secret', request_id: '123'}})));
  assert.equal(parsed.calls[0].requester.authorization, undefined);
  assert.equal(parsed.calls[0].requester.request_id, '123');
  assert.equal(clientIdentity(call('00:00', 1)).name, 'Unknown requester');
  assert.match(clientIdentity({requester: {remote_address: '127.0.0.1', user_agent: 'Example'}}).basis, /Inferred/);
});
test('a hosted client calling from changing addresses stays one group', () => {
  const from = ip => ({user_agent: 'example-mcp/1.0', client_name: 'example-mcp', remote_address: '172.26.0.1', forwarded_for: ip});
  const groups = groupCalls([call('00:00', 10, {requester: from('192.0.2.1')}), call('00:02', 10, {requester: from('192.0.2.2')})]);
  assert.equal(groups.length, 1);
});
test('unchanged keyed nodes are not detached and retain expanded/response state', () => {
  let mutations = 0;
  const parent = {children: [], get firstElementChild() { return this.children[0] || null; }, insertBefore(child, before) {
    mutations++; this.children = this.children.filter(item => item !== child);
    const index = before ? this.children.indexOf(before) : this.children.length;
    this.children.splice(index, 0, child);
  }};
  const make = () => ({open: true, response: 'preserved response', get nextElementSibling() { return parent.children[parent.children.indexOf(this) + 1] || null; }, remove() { mutations++; parent.children = parent.children.filter(item => item !== this); }});
  const a = make(), b = make(), c = make(); parent.children = [a, b];
  reconcileChildren(parent, [a, b]); assert.equal(mutations, 0);
  reconcileChildren(parent, [a, b, c]); assert.equal(mutations, 1);
  assert.equal(parent.children[0], a); assert.equal(a.open, true); assert.equal(a.response, 'preserved response');
});

const fields = ['call_log', 'start', 'tool', 'args', 'ms', 'chars', 'results', 'status', 'truncated', 'records_cut', 'error', 'exception', 'call_id'];
const identityFields = ['session_id', 'client_id', 'client_name', 'client_version', 'client_title', 'request_id', 'remote_address', 'forwarded_for', 'user_agent', 'protocol_version'];
export function cleanIdentity(value) {
  return Object.fromEntries(identityFields.filter(key => ['string', 'number'].includes(typeof value?.[key])).map(key => [key, String(value[key]).slice(0, 512)]));
}
export function parseLogText(text) {
  const calls = [];
  let skipped = 0;
  for (const line of text.split(/\r?\n/).filter(line => line.trim())) {
    try {
      const item = JSON.parse(line.slice(line.indexOf('{')));
      if (item?.call_log !== 1 || typeof item.start !== 'string' || !/(Z|[+-]\d\d:\d\d)$/.test(item.start) || !Number.isFinite(Date.parse(item.start)) || typeof item.tool !== 'string' || !Number.isFinite(item.ms) || item.ms < 0 || (item.args && (typeof item.args !== 'object' || Array.isArray(item.args)))) throw new Error();
      calls.push({...Object.fromEntries(fields.filter(key => key in item).map(key => [key, item[key]])), requester: cleanIdentity(item.requester)});
    } catch { skipped++; }
  }
  calls.sort((a, b) => Date.parse(a.start) - Date.parse(b.start));
  return {calls: calls.slice(-1000), skipped, omitted: Math.max(0, calls.length - 1000)};
}

export function summarizeCalls(calls) {
  if (!calls.length) return {elapsed: 0, busy: 0, toolTime: 0, blocks: 0, failures: 0};
  let first = Infinity, end = -Infinity, busy = 0, toolTime = 0, blocks = 0, failures = 0;
  for (const call of [...calls].sort((a, b) => Date.parse(a.start) - Date.parse(b.start))) {
    const start = Date.parse(call.start), finish = start + call.ms;
    first = Math.min(first, start);
    if (start - end > 120000) blocks++;
    busy += Math.max(0, finish - Math.max(start, end));
    end = Math.max(end, finish);
    toolTime += call.ms;
    if (call.error || call.exception || call.status >= 400) failures++;
  }
  return {elapsed: end - first, busy, toolTime, blocks, failures};
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
  return value;
}
export function callKey(call) {
  return typeof call.call_id === 'string' && call.call_id ? call.call_id : JSON.stringify(canonical([call.start, call.tool, call.args, cleanIdentity(call.requester)]));
}
export function clientIdentity(call) {
  const info = cleanIdentity(call.requester);
  const name = info.client_title || info.client_name || info.user_agent || 'Unknown requester';
  if (info.session_id) return {key: `session:${info.session_id}`, name, basis: 'Reported MCP session'};
  if (info.client_id) return {key: `client:${info.client_id}`, name, basis: 'Declared client ID'};
  if (info.remote_address && (info.user_agent || info.client_name)) return {
    key: JSON.stringify(['inferred', info.remote_address, info.forwarded_for || '', info.user_agent || '', info.client_name || '']),
    name, basis: 'Inferred from address and client information; may combine clients behind a proxy',
  };
  return {key: 'unknown', name: 'Unknown requester', basis: 'No client identity logged; these calls may belong to different clients'};
}
export function groupCalls(calls, idleMs = 120000, previous = []) {
  const oldKeys = new Map(previous.flatMap(group => group.calls.map(call => [callKey(call), group.key])));
  const groups = [], latest = new Map();
  for (const call of [...calls].sort((a, b) => Date.parse(a.start) - Date.parse(b.start))) {
    const identity = clientIdentity(call), start = Date.parse(call.start);
    let group = latest.get(identity.key);
    if (!group || start - group.end > idleMs) {
      group = {key: oldKeys.get(callKey(call)) || `${identity.key}:${callKey(call)}`, identity, start, end: start, calls: []};
      groups.push(group); latest.set(identity.key, group);
    }
    group.calls.push(call);
    group.end = Math.max(group.end, start + call.ms);
  }
  return groups;
}

// Leave existing DOM nodes in place: open details, focus, selection and response text survive polling.
export function reconcileChildren(parent, desired) {
  let cursor = parent.firstElementChild;
  for (const child of desired) {
    if (child === cursor) cursor = cursor.nextElementSibling;
    else parent.insertBefore(child, cursor);
  }
  const keep = new Set(desired);
  for (const child of [...parent.children]) if (!keep.has(child)) child.remove();
}

export function initLogs() {
  const $ = id => document.getElementById(id);
  const node = (tag, text, className = '') => {
    const result = document.createElement(tag);
    if (text !== undefined) result.textContent = text;
    result.className = className;
    return result;
  };
  let data = {calls: []}, imported = false, loading = false, revision = 0;
  const seconds = ms => `${(ms / 1000).toFixed(2)} s`;
  let groups = [];
  const groupNodes = new Map(), callNodes = new Map();
  const newViewerId = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('');
  let viewerId;
  try {
    viewerId = sessionStorage.getItem('viewer-demo-client') || newViewerId();
    sessionStorage.setItem('viewer-demo-client', viewerId);
  } catch { viewerId = newViewerId(); }
  function makeCall(call, key) {
    let row = callNodes.get(key);
    if (!row) {
      const details = node('details', undefined, 'log-call'), head = node('summary');
      const body = node('div', undefined, 'log-call-body');
      const info = node('div'), args = node('pre');
      const requesterDetails = node('details'), requesterText = node('pre');
      requesterDetails.append(node('summary', 'Request identity'), requesterText);
      const button = node('button', 'Show request response', 'button secondary');
      button.type = 'button';
      const responseStatus = node('p', 'Repeats this read-only call now; the original response was not stored.', 'muted small');
      responseStatus.setAttribute('role', 'status');
      const response = node('textarea');
      response.readOnly = true; response.rows = 14; response.hidden = true;
      response.setAttribute('aria-label', 'Fresh response for ' + call.tool);
      row = {details, head, info, args, requesterText, button, responseStatus, response, call};
      callNodes.set(key, row);
      button.addEventListener('click', async () => {
        button.disabled = true;
        responseStatus.textContent = 'Repeating the call through the connector…';
        try {
          const result = await fetch('api/logs/replay', {method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({tool: row.call.tool, args: row.call.args || {}, viewer_id: viewerId}), signal: AbortSignal.timeout(90000)});
          const payload = await result.json();
          if (!result.ok) throw new Error(payload.error || `Replay failed (HTTP ${result.status})`);
          let value = payload.result;
          if (value?.content?.length === 1 && value.content[0].type === 'text') {
            try { value = JSON.parse(value.content[0].text); } catch { value = value.content[0].text; }
          }
          response.value = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
          response.hidden = false;
          responseStatus.textContent = `Fresh response retrieved ${new Date(payload.replayed_at).toLocaleString()}${payload.result?.isError ? ' · Tool reported an error' : ''}. This may differ from the original response.`;
          button.textContent = 'Repeat request again';
        } catch (error) { responseStatus.textContent = error.message + (response.hidden ? '' : ' Previous response retained below.'); }
        finally { button.disabled = false; }
      });
      body.append(info, requesterDetails, node('h4', 'Arguments'), args, button, responseStatus, response);
      details.append(head, body);
    }
    row.call = call;
    const signature = JSON.stringify(call);
    if (row.signature !== signature) {
      row.signature = signature;
      const failed = call.error || call.exception || call.status >= 400;
      row.head.replaceChildren(node('time', new Date(call.start).toLocaleTimeString()), node('strong', call.tool), node('span', seconds(call.ms)), node('span', failed ? 'Failed' : call.status ? `HTTP ${call.status}` : 'Completed', `pill ${failed ? 'amber' : 'green'}`));
      row.info.replaceChildren(node('p', [call.args?.dataset_id, call.args?.operation_id].filter(Boolean).join(' · ')),
        node('p', `Started ${new Date(call.start).toLocaleString()} · Answer ${call.chars ?? 'unknown'} characters${call.results !== undefined ? ` · ${call.results} results` : ''}`));
      if (call.truncated || call.records_cut) row.info.append(node('p', `Answer truncated · ${JSON.stringify(call.records_cut || '')}`, 'notice'));
      if (failed) row.info.append(node('p', String(call.error || call.exception || `HTTP ${call.status}`), 'notice error'));
      const identity = cleanIdentity(call.requester);
      row.requesterText.textContent = Object.keys(identity).length ? JSON.stringify(identity, null, 2) : 'No request identity was recorded for this call.';
      row.args.textContent = JSON.stringify(call.args || {}, null, 2);
    }
    return row.details;
  }
  function render() {
    const scrollTop = $('log-list').scrollTop;
    groups = groupCalls(data.calls, Number($('log-idle').value) * 60000, groups);
    const query = $('log-search').value.toLocaleLowerCase();
    const match = call => (!$('log-errors').checked || call.error || call.exception || call.status >= 400) && JSON.stringify(call).toLocaleLowerCase().includes(query);
    const calls = data.calls.filter(match), summary = summarizeCalls(calls);
    const visible = groups.filter(group => group.calls.some(match));
    $('log-count').textContent = `${visible.length} groups · ${calls.length} / ${data.calls.length} calls`;
    $('log-metrics').replaceChildren(...[[calls.length, 'Tool calls'], [seconds(summary.toolTime), 'Total tool duration'], [summary.failures, 'Failed calls'], [visible.length, 'Request groups']].map(([value, label]) => {
      const card = node('div', undefined, 'metric'); card.append(node('span', label, 'muted'), node('strong', value)); return card;
    }));
    $('log-timing').textContent = calls.length ? `Selected span: ${seconds(summary.elapsed)} · Tools active: ${seconds(summary.busy)}. Groups use reported session/client IDs where available, then inferred address and client information. Unknown callers cannot be reliably separated. Identity is reported metadata, not verified authentication.` : '';
    const keepCalls = new Set(), keepGroups = new Set(), desired = [];
    for (const group of groups) {
      keepGroups.add(group.key);
      let view = groupNodes.get(group.key);
      if (!view) {
        const details = node('details', undefined, 'log-group'), head = node('summary'), description = node('p', undefined, 'log-group-description muted small'), list = node('div');
        details.append(head, description, list);
        view = {details, head, description, list}; groupNodes.set(group.key, view);
      }
      const filtered = group.calls.filter(match), stats = summarizeCalls(group.calls);
      const caption = `${group.identity.name} · ${filtered.length}/${group.calls.length} calls · ${seconds(stats.toolTime)} in tools · ${new Date(group.start).toLocaleString()} – ${new Date(group.end).toLocaleTimeString()}`;
      if (view.caption !== caption) { view.head.textContent = caption; view.caption = caption; }
      const identity = cleanIdentity(group.calls[0].requester);
      const description = `${group.identity.basis}${identity.session_id ? ` · Session ${identity.session_id}` : identity.client_id ? ` · Client ${identity.client_id}` : ''}. Expand individual calls for request IDs and all recorded identity fields.`;
      if (view.description.textContent !== description) view.description.textContent = description;
      const occurrences = new Map(), rows = [];
      for (const call of group.calls) {
        const base = callKey(call), count = occurrences.get(base) || 0;
        occurrences.set(base, count + 1);
        const key = `${base}:${count}`; keepCalls.add(key);
        if (match(call)) rows.push(makeCall(call, key));
      }
      reconcileChildren(view.list, rows);
      if (filtered.length) desired.push(view.details);
    }
    reconcileChildren($('log-list'), desired);
    for (const key of callNodes.keys()) if (!keepCalls.has(key)) callNodes.delete(key);
    for (const key of groupNodes.keys()) if (!keepGroups.has(key)) groupNodes.delete(key);
    $('log-list').scrollTop = scrollTop;
    $('log-empty').hidden = calls.length > 0;
    $('log-empty').textContent = data.calls.length ? 'No calls match these filters.' : 'No call entries yet. Import a connector log, or start the optional live collector with CALL_LOG enabled on the connector.';
  }
  async function refresh() {
    if (loading || imported) return;
    const current = revision;
    loading = true; $('refresh-logs').disabled = true;
    try {
      const response = await fetch('api/logs', {signal: AbortSignal.timeout(10000)});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Log feed unavailable');
      if (current !== revision) return;
      data = result;
      $('log-message').textContent = !result.configured ? 'Live feed is not configured. Import a saved log below, or follow the live-demo setup in viewer/README.md.' : result.waiting ? 'Waiting for the collector to create its snapshot.' : `Live snapshot · checked ${new Date().toLocaleTimeString()} · ${result.skipped} non-call or invalid lines skipped · ${result.omitted} older calls omitted`;
      render();
    } catch (error) { if (current === revision) $('log-message').textContent = `${error.message}. Previously loaded calls are retained.`; }
    finally { loading = false; $('refresh-logs').disabled = false; }
  }
  $('log-file').addEventListener('change', async event => {
    const file = event.target.files[0];
    if (!file) return;
    if (file.size > 8 * 1024 * 1024) { $('log-message').textContent = 'Choose a log file smaller than 8 MiB.'; return; }
    const current = ++revision;
    imported = true;
    try {
      const text = await file.text();
      if (current !== revision) return;
      data = parseLogText(text);
      $('log-live').checked = false;
      $('log-message').textContent = `Imported ${file.name} locally · ${data.skipped} non-call or invalid lines skipped · ${data.omitted} older calls omitted. The file is not uploaded.`;
      render();
    } catch { $('log-message').textContent = 'Could not read this file. Try importing it again.'; }
  });
  $('refresh-logs').addEventListener('click', () => { revision++; imported = false; refresh(); });
  $('log-live').addEventListener('change', () => { if ($('log-live').checked) { revision++; imported = false; refresh(); } });
  $('log-idle').addEventListener('change', () => { groups = []; render(); });
  $('log-search').addEventListener('input', render);
  $('log-errors').addEventListener('change', render);
  window.addEventListener('hashchange', () => { if (location.hash === '#logs' && !imported) refresh(); });
  setInterval(() => { if (location.hash === '#logs' && !document.hidden && $('log-live').checked) refresh(); }, 3000);
  render();
  if (location.hash === '#logs') refresh();
}

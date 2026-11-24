const fields = ['call_log', 'start', 'tool', 'args', 'ms', 'chars', 'results', 'status', 'truncated', 'records_cut', 'error', 'exception'];
export function parseLogText(text) {
  const calls = [];
  let skipped = 0;
  for (const line of text.split(/\r?\n/).filter(line => line.trim())) {
    try {
      const item = JSON.parse(line.slice(line.indexOf('{')));
      if (item?.call_log !== 1 || typeof item.start !== 'string' || !/(Z|[+-]\d\d:\d\d)$/.test(item.start) || !Number.isFinite(Date.parse(item.start)) || typeof item.tool !== 'string' || !Number.isFinite(item.ms) || item.ms < 0 || (item.args && (typeof item.args !== 'object' || Array.isArray(item.args)))) throw new Error();
      calls.push(Object.fromEntries(fields.filter(key => key in item).map(key => [key, item[key]])));
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
  function render() {
    const query = $('log-search').value.toLocaleLowerCase();
    const calls = data.calls.filter(call => (!$('log-errors').checked || call.error || call.exception || call.status >= 400) && JSON.stringify(call).toLocaleLowerCase().includes(query));
    const summary = summarizeCalls(calls);
    $('log-count').textContent = `${calls.length} / ${data.calls.length}`;
    $('log-metrics').replaceChildren(...[
      [calls.length, 'Tool calls'], [seconds(summary.toolTime), 'Total tool duration'],
      [summary.failures, 'Failed calls'], [summary.blocks, 'Activity blocks'],
    ].map(([value, label]) => {
      const card = node('div', undefined, 'metric');
      card.append(node('span', label, 'muted'), node('strong', value));
      return card;
    }));
    $('log-timing').textContent = calls.length ? `Selected span: ${seconds(summary.elapsed)} · Tools active: ${seconds(summary.busy)} · No tools active: ${seconds(summary.elapsed - summary.busy)}. Overlapping calls are counted once in active time. Blocks split after two idle minutes; they are not session or question IDs.` : '';
    let previousEnd = -Infinity, block = 0;
    $('log-list').replaceChildren(...calls.map(call => {
      const start = Date.parse(call.start), gap = Number.isFinite(previousEnd) ? Math.max(0, start - previousEnd) : 0;
      const newBlock = start - previousEnd > 120000;
      if (newBlock) block++;
      previousEnd = Math.max(previousEnd, start + call.ms);
      const wrapper = node('div');
      if (newBlock) wrapper.append(node('h3', `Activity block ${block}`, 'log-block'));
      const details = node('details', undefined, 'log-call');
      const head = node('summary');
      const failed = call.error || call.exception || call.status >= 400;
      head.append(node('time', new Date(call.start).toLocaleTimeString()), node('strong', call.tool), node('span', seconds(call.ms)), node('span', failed ? 'Failed' : call.status ? `HTTP ${call.status}` : 'Completed', `pill ${failed ? 'amber' : 'green'}`));
      const body = node('div', undefined, 'log-call-body');
      const args = call.args || {};
      if (args.dataset_id || args.operation_id) body.append(node('p', [args.dataset_id, args.operation_id].filter(Boolean).join(' · ')));
      body.append(node('p', `Started ${new Date(call.start).toLocaleString()} · Gap ${seconds(gap)} · Answer ${call.chars ?? 'unknown'} characters${call.results !== undefined ? ` · ${call.results} results` : ''}`));
      if (call.truncated || call.records_cut) body.append(node('p', `Answer truncated${call.records_cut ? ` · ${call.records_cut} records cut` : ''}`, 'notice'));
      if (failed) body.append(node('p', String(call.error || call.exception || `HTTP ${call.status}`), 'notice error'));
      body.append(node('h4', 'Arguments'), node('pre', JSON.stringify(args, null, 2)));
      details.append(head, body); wrapper.append(details); return wrapper;
    }));
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
  $('log-search').addEventListener('input', render);
  $('log-errors').addEventListener('change', render);
  window.addEventListener('hashchange', () => { if (location.hash === '#logs' && !imported) refresh(); });
  setInterval(() => { if (location.hash === '#logs' && !document.hidden && $('log-live').checked) refresh(); }, 3000);
  render();
  if (location.hash === '#logs') refresh();
}

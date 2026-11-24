import {initLogs} from './logs.mjs';
import {list, safeURL, filterDatasets, filterDocuments, searchParams} from './model.mjs';
import {renderMarkdown} from './markdown.mjs';

const $ = id => document.getElementById(id);
const state = {catalogs: [], datasets: [], documents: [], selected: '', catalogReady: false, datasetsReady: false, documentsReady: false, detailRequest: 0};
const languageNames = new Intl.DisplayNames(['en'], {type: 'language'});
const countryNames = {BEL: 'Belgium', FRA: 'France'};

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else node.setAttribute(key, value);
  }
  for (const child of children.flat(Infinity)) {
    if (child !== null && child !== undefined) node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function language(code) {
  try { return languageNames.of(code) || code; } catch { return code; }
}
function date(value) {
  if (!value) return 'Not provided';
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? String(value) : parsed.toLocaleString([], {dateStyle: 'medium', timeStyle: 'short'});
}
function externalLink(url, label) {
  const safe = safeURL(url);
  return safe ? el('a', {href: safe, target: '_blank', rel: 'noopener noreferrer', text: label || safe}) : el('span', {text: label || url || 'Not provided'});
}
function tags(values) { return list(values).map(value => el('span', {class: 'tag', text: value})); }
function pill(text, type = '') { return el('span', {class: `pill ${type}`, text}); }
function message(id, text = '', type = '') {
  $(id).replaceChildren(...(text ? [el('div', {class: `notice ${type}`, text})] : []));
}
function status(id, ok, label) {
  $(id).textContent = label || (ok ? 'Connected' : 'Unavailable');
  $(id).className = `status ${ok ? 'online' : 'offline'}`;
}
function setOptions(id, values, first, formatter = value => value) {
  const select = $(id);
  const previous = select.value;
  select.replaceChildren(el('option', {value: '', text: first}), ...[...new Set(values)].filter(Boolean).sort().map(value => el('option', {value, text: formatter(value)})));
  if ([...select.options].some(option => option.value === previous)) select.value = previous;
}
async function api(path, expectList = false) {
  const response = await fetch(path, {signal: AbortSignal.timeout(55000)});
  let data;
  try { data = await response.json(); } catch { throw new Error('The service returned an unreadable response.'); }
  if (!response.ok) throw new Error(data.error || `Request failed (HTTP ${response.status}).`);
  if (expectList && !Array.isArray(data)) throw new Error('The service returned an unexpected response shape.');
  return data;
}
function errorText(error) {
  return error?.name === 'TimeoutError' ? 'The request timed out. Please try again.' : error?.message || 'The service could not be reached.';
}

function renderMetrics() {
  const publishers = new Set(state.datasets.map(d => d.publisher?.name).filter(Boolean)).size;
  const licensed = state.datasets.filter(d => d.licence).length;
  const items = [
    [state.catalogReady ? state.catalogs.length : '—', 'DCAT catalogs', 'Linked from the root catalog'],
    [state.datasetsReady ? state.datasets.length : '—', 'Registered datasets', 'Discoverable APIs and sources'],
    [state.datasetsReady ? publishers : '—', 'Publishers', 'Distinct registered names'],
    [state.datasetsReady ? licensed : '—', 'Licence URLs', 'Other records retain their notes'],
  ];
  $('catalog-metrics').replaceChildren(...items.map(([number, label, note], i) => el('div', {class: 'metric'}, el('div', {class: 'metric-top'}, el('span', {text: label}), el('span', {class: 'metric-symbol', 'aria-hidden': 'true', text: ['▦', '▤', '◎', '↗'][i]})), el('strong', {text: number}), el('span', {class: 'muted small', text: note}))));
}

function catalogName(id) {
  if (!id) return 'Root catalog';
  const catalog = state.catalogs.find(c => c.id === id);
  return catalog ? catalog.title.replace(/^Accessibility data space catalog:\s*/i, '') : id;
}
function selectCatalog(id) {
  state.selected = state.selected === id ? '' : id;
  renderCatalogs();
  renderDatasets();
}
function renderCatalogs() {
  const cards = state.catalogs.map(c => {
    const button = el('button', {type: 'button', class: `catalog-card ${state.selected === c.id ? 'selected' : ''}`, 'aria-pressed': String(state.selected === c.id)},
      el('span', {class: 'catalog-card-top'}, el('span', {class: 'country-code', text: c.country || 'DCAT'}), el('span', {class: 'card-arrow', 'aria-hidden': 'true', text: '↗'})),
      el('strong', {text: catalogName(c.id)}),
      el('span', {class: 'muted small', text: `${countryNames[c.country] || c.country || 'Coverage not specified'} · DCAT sub-catalog`}),
      el('span', {class: 'catalog-card-bottom'}, el('span', {text: `${list(c.datasets).length} datasets`}), el('span', {text: state.selected === c.id ? 'Selected' : 'Explore'})));
    button.addEventListener('click', () => selectCatalog(c.id));
    return button;
  });
  if (state.datasets.some(d => !d.catalog)) {
    const root = el('button', {class: `catalog-card ${state.selected === '__root__' ? 'selected' : ''}`, 'aria-pressed': String(state.selected === '__root__')}, el('span', {class: 'country-code', text: 'ROOT'}), el('strong', {text: 'Root catalog'}), el('span', {class: 'muted small', text: `${state.datasets.filter(d => !d.catalog).length} datasets without a sub-catalog`}));
    root.addEventListener('click', () => selectCatalog('__root__'));
    cards.push(root);
  }
  $('catalog-cards').replaceChildren(...cards);
}

function renderDatasets() {
  const filtered = filterDatasets(state.datasets, {catalog: state.selected, query: $('dataset-search').value, language: $('dataset-language').value, licence: $('dataset-licence').value});
  $('dataset-count').textContent = state.datasetsReady ? `${filtered.length} / ${state.datasets.length}` : '—';
  $('catalog-selection').textContent = state.selected ? `Showing ${state.selected === '__root__' ? 'Root catalog' : catalogName(state.selected)}` : 'Across all catalogs';
  $('dataset-rows').replaceChildren(...filtered.map(d => {
    const title = el('button', {class: 'dataset-title', text: d.title || d.id});
    const detail = el('button', {class: 'row-arrow', 'aria-label': `Inspect ${d.title || d.id}`, text: '↗'});
    [title, detail].forEach(button => button.addEventListener('click', () => openDataset(d.id)));
    return el('tr', {},
      el('td', {}, title, el('div', {class: 'muted small', text: d.publisher?.name || 'Publisher not provided'})),
      el('td', {}, el('span', {class: 'catalog-label', text: catalogName(d.catalog)})),
      el('td', {class: 'coverage', text: list(d.spatial).join(', ') || 'Not specified'}),
      el('td', {}, pill(d.licence ? 'URL provided' : d.licence_note ? 'See terms' : 'Not stated', d.licence ? 'green' : 'amber')),
      el('td', {}, detail));
  }));
  $('dataset-empty').hidden = filtered.length > 0;
  $('dataset-empty').textContent = !state.datasetsReady ? 'Dataset metadata is not available. Check the service connection and refresh.' : !state.datasets.length ? 'The broker has no registered datasets. Run make -C sources register after starting the data space.' : 'No datasets match these filters. Try another term or reset the filters.';
}

async function loadCatalog() {
  $('refresh-catalog').disabled = true;
  message('catalog-message', 'Loading catalog metadata…');
  const results = await Promise.allSettled([api('api/catalog/catalogs', true), api('api/catalog/datasets', true), api('api/catalog/health')]);
  state.catalogReady = results[0].status === 'fulfilled';
  state.datasetsReady = results[1].status === 'fulfilled';
  state.catalogs = state.catalogReady ? results[0].value : [];
  state.datasets = state.datasetsReady ? results[1].value : [];
  if (state.selected && state.selected !== '__root__' && !state.catalogs.some(c => c.id === state.selected)) state.selected = '';
  const errors = results.filter(r => r.status === 'rejected').map(r => errorText(r.reason));
  message('catalog-message', [...new Set(errors)].join(' '), 'error');
  status('catalog-status', errors.length === 0, errors.length && (state.catalogReady || state.datasetsReady) ? 'Partial' : undefined);
  $('nav-datasets').textContent = state.datasetsReady ? state.datasets.length : '—';
  setOptions('dataset-language', state.datasets.flatMap(d => list(d.languages)), 'All languages', language);
  renderMetrics(); renderCatalogs(); renderDatasets();
  $('catalog-updated').textContent = state.datasetsReady ? `Retrieved ${date(new Date().toISOString())}` : 'Broker unavailable';
  $('refresh-catalog').disabled = false;
}

function detailField(label, value) { return el('div', {class: 'detail-field'}, el('dt', {text: label}), el('dd', {}, value)); }
async function openDataset(id) {
  const request = ++state.detailRequest;
  const dialog = $('dataset-dialog');
  $('dataset-detail').replaceChildren(el('h2', {id: 'detail-title', text: 'Loading registration…'}));
  if (!dialog.open) dialog.showModal();
  try {
    const d = await api(`api/catalog/datasets/${encodeURIComponent(id)}`);
    if (request !== state.detailRequest) return;
    const raw = el('details', {}, el('summary', {text: 'Full registration JSON'}), el('pre', {text: JSON.stringify(d, null, 2)}));
    const dcat = d.source_dcat?.turtle ? el('details', {}, el('summary', {text: 'Imported publisher DCAT (Turtle)'}), el('pre', {text: d.source_dcat.turtle})) : null;
    $('dataset-detail').replaceChildren(
      el('h2', {id: 'detail-title', text: d.title || d.id}), el('p', {class: 'dataset-id', text: d.id}),
      el('p', {class: 'detail-description', text: d.description || 'No description provided.'}),
      el('div', {class: 'tags'}, ...tags(d.themes), ...tags(d.keywords)),
      el('dl', {class: 'detail-grid'},
        detailField('Publisher', externalLink(d.publisher?.url, d.publisher?.name || 'Not provided')),
        detailField('Catalog', catalogName(d.catalog)),
        detailField('Coverage', list(d.spatial).join(', ') || 'Not specified'),
        detailField('Languages', list(d.languages).map(language).join(', ') || 'Not specified'),
        detailField('Licence', d.licence ? externalLink(d.licence) : 'No licence URL provided'),
        detailField('Licence note', d.licence_note || 'Not provided'),
        detailField('API endpoint', externalLink(d.endpoint_url)),
        detailField('OpenAPI description', externalLink(d.openapi_url)),
        detailField('Access conditions', d.access_note || 'Not provided'),
        detailField('Update frequency', d.update_frequency || 'Not provided'),
        detailField('Publisher page', externalLink(d.landing_page)),
        detailField('Publisher DCAT', externalLink(d.source_dcat_url)),
        detailField('Original dataset URI', externalLink(d.source_dcat?.uri)),
        detailField('Contact', d.contact_email || 'Not provided'),
        detailField('Registered', date(d.registered_at)),
        detailField('Metadata modified', date(d.modified))),
      dcat, raw,
      el('p', {class: 'muted small', text: `Registration retrieved ${date(new Date().toISOString())}. API links may use addresses on the Docker network. No place records are queried by this viewer.`}));
  } catch (error) {
    if (request !== state.detailRequest) return;
    const retry = el('button', {class: 'button secondary', text: 'Retry'});
    retry.addEventListener('click', () => openDataset(id));
    $('dataset-detail').replaceChildren(el('h2', {id: 'detail-title', text: 'Registration unavailable'}), el('p', {class: 'notice error', text: errorText(error)}), retry);
  }
}

function renderDocuments() {
  const filtered = filterDocuments(state.documents, $('document-search').value);
  $('document-count').textContent = state.documentsReady ? `${filtered.length} / ${state.documents.length}` : '—';
  $('document-list').replaceChildren(...filtered.map(d => {
    const useTopic = list(d.tags)[0];
    const topicButton = useTopic ? el('button', {class: 'text-button', text: 'Search this topic ↗'}) : null;
    if (topicButton) topicButton.addEventListener('click', () => {
      $('search-tag').value = useTopic;
      $('question').focus();
      $('question-form').scrollIntoView({behavior: 'smooth', block: 'center'});
    });
    return el('article', {class: 'document-row'},
      el('span', {class: 'document-icon', 'aria-hidden': 'true', text: '▤'}),
      el('div', {class: 'document-content'}, el('h3', {}, externalLink(d.url, d.title || 'Untitled document')),
        el('p', {class: 'muted small', text: `${d.kind || 'Document'} · ${d.language ? language(d.language) : 'Language not specified'} · ${d.chunks ?? 'Unknown'} passages · Ingested ${date(d.ingested_at)}`}),
        el('div', {class: 'tags'}, ...tags(d.tags)),
        el('p', {class: 'document-licence small'}, 'Licence: ', d.licence ? externalLink(d.licence) : 'Not provided')),
      topicButton);
  }));
  $('document-empty').hidden = filtered.length > 0;
  $('document-empty').textContent = !state.documentsReady ? 'Document metadata is not available. Check the service connection and refresh.' : !state.documents.length ? 'No documents have been ingested yet. Run make -C sources knowledge to load the public knowledge collection.' : 'No documents match this search.';
}

async function loadVocabulary() {
  $('refresh-vocabulary').disabled = true;
  message('vocabulary-message', 'Loading knowledge collection…');
  const [docs, health, context] = await Promise.allSettled([api('api/vochub/documents', true), api('api/vochub/health'), api('api/vochub/context')]);
  state.documentsReady = docs.status === 'fulfilled';
  state.documents = state.documentsReady ? docs.value : [];
  const text = context.status === 'fulfilled' ? String(context.value.text || '') : '';
  $('context-summary').textContent = context.status !== 'fulfilled' ? 'Permanent context unavailable' : text ? `The agent receives this text with every vocabulary search · Updated ${date(context.value.updated_at)}` : 'No permanent context set. Run make -C sources knowledge to load it.';
  $('context-text').innerHTML = renderMarkdown(text);
  const errors = [docs, health, context].filter(r => r.status === 'rejected').map(r => errorText(r.reason));
  message('vocabulary-message', [...new Set(errors)].join(' '), 'error');
  status('vochub-status', errors.length === 0, errors.length && state.documentsReady ? 'Partial' : undefined);
  $('nav-documents').textContent = state.documentsReady ? state.documents.length : '—';
  setOptions('search-language', state.documents.map(d => d.language), 'All languages', language);
  setOptions('search-tag', state.documents.flatMap(d => list(d.tags)), 'All topics');
  const chunks = state.documents.reduce((sum, d) => sum + (Number(d.chunks) || 0), 0);
  const languages = new Set(state.documents.map(d => d.language).filter(Boolean)).size;
  $('document-summary').textContent = state.documentsReady ? `${chunks} indexed passages · ${languages} document languages` : 'Document metadata unavailable';
  $('vocabulary-updated').textContent = state.documentsReady ? `Retrieved ${date(new Date().toISOString())}` : '';
  renderDocuments();
  $('refresh-vocabulary').disabled = false;
}

async function search(event) {
  event.preventDefault();
  if ($('search-button').disabled) return;
  let params;
  try { params = searchParams($('question').value, $('result-limit').value, $('search-language').value, $('search-tag').value); }
  catch (error) { $('question').setCustomValidity(error.message); $('question').reportValidity(); return; }
  $('search-button').disabled = true;
  $('search-button').textContent = 'Finding passages…';
  $('results-section').hidden = false;
  $('results-section').setAttribute('aria-busy', 'true');
  $('results-meta').textContent = '';
  $('results-query').textContent = `Question: “${params.get('q')}”${params.get('language') ? ` · Language: ${language(params.get('language'))}` : ''}${params.get('tag') ? ` · Topic: ${params.get('tag')}` : ''}`;
  $('search-results').replaceChildren();
  message('search-message', 'Searching the vocabulary hub…');
  try {
    const hits = await api(`api/vochub/search?${params}`, true);
    const retrieved = date(new Date().toISOString());
    $('results-meta').textContent = `${hits.length} passages · Retrieved ${retrieved}`;
    message('search-message', hits.length ? 'Passages are ranked by meaning and keywords combined, at most two per document; the number is the rank, not a confidence rating. Check the cited context.' : 'No passages were returned. Try a broader question, remove a language or topic filter, or check that documents have been ingested.');
    $('search-results').replaceChildren(...hits.map((hit, index) => {
      const doc = state.documents.find(d => d.doc_id === hit.doc_id);
      const location = [hit.page !== null && hit.page !== undefined ? `Page ${hit.page}` : null, hit.heading, hit.language ? language(hit.language) : null].filter(Boolean).join(' · ');
      return el('article', {class: 'result-card'},
        el('div', {class: 'result-card-heading'}, el('span', {class: 'citation-number', text: String(index + 1).padStart(2, '0')}), el('div', {class: 'result-title'}, el('h3', {}, externalLink(hit.url, hit.title || 'Untitled source')), el('p', {class: 'muted small', text: location || 'No page or section metadata'}))),
        el('blockquote', {class: 'passage', text: hit.text || 'No passage text returned.'}),
        el('div', {class: 'tags'}, ...tags(hit.tags)),
        el('div', {class: 'citation-details'},
          el('div', {}, el('strong', {text: 'Source: '}), hit.url ? externalLink(hit.url) : 'URL not provided'),
          el('div', {}, el('strong', {text: 'Licence: '}), hit.licence ? externalLink(hit.licence) : 'Not provided'),
          el('div', {}, el('strong', {text: 'Ingested: '}), date(doc?.ingested_at)),
          el('div', {}, el('strong', {text: 'Document: '}), hit.doc_id || 'Not provided')));
    }));
  } catch (error) { message('search-message', errorText(error), 'error'); }
  finally {
    $('results-section').removeAttribute('aria-busy');
    $('search-button').disabled = false;
    $('search-button').textContent = 'Find relevant passages ↗';
  }
}

function navigate() {
  const selected = ['#vocabulary', '#logs'].includes(location.hash) ? location.hash.slice(1) : 'catalog';
  for (const name of ['catalog', 'vocabulary', 'logs']) {
    const active = selected === name;
    $(name + '-view').hidden = !active;
    $('nav-' + name).classList.toggle('active', active);
    if (active) $('nav-' + name).setAttribute('aria-current', 'page'); else $('nav-' + name).removeAttribute('aria-current');
  }
  document.title = `${{catalog: 'Metadata broker', vocabulary: 'Vocabulary hub', logs: 'Connector logs'}[selected]} · Accessibility data space`;
}
$('refresh-catalog').addEventListener('click', loadCatalog);
$('refresh-vocabulary').addEventListener('click', loadVocabulary);
for (const id of ['dataset-search', 'dataset-language', 'dataset-licence']) $(id).addEventListener('input', renderDatasets);
$('clear-filters').addEventListener('click', () => {
  state.selected = '';
  for (const id of ['dataset-search', 'dataset-language', 'dataset-licence']) $(id).value = '';
  renderCatalogs(); renderDatasets();
});
$('document-search').addEventListener('input', renderDocuments);
$('question-form').addEventListener('submit', search);
$('question').addEventListener('input', () => $('question').setCustomValidity(''));
document.querySelectorAll('[data-question]').forEach(button => button.addEventListener('click', () => {
  $('question').value = button.dataset.question;
  $('question').setCustomValidity('');
  $('question').focus();
}));
$('close-dialog').addEventListener('click', () => $('dataset-dialog').close());
$('dataset-dialog').addEventListener('close', () => { state.detailRequest++; });
window.addEventListener('hashchange', navigate);
navigate(); renderMetrics(); initLogs();
await Promise.allSettled([loadCatalog(), loadVocabulary()]);

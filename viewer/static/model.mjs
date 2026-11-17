export const list = value => Array.isArray(value) ? value : [];

export function safeURL(value) {
  if (typeof value !== 'string') return null;
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

export function filterDatasets(datasets, {catalog = '', query = '', language = '', licence = ''} = {}) {
  const terms = query.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  return list(datasets).filter(d => {
    const text = [d.id, d.title, d.description, d.publisher?.name, ...list(d.spatial), ...list(d.themes), ...list(d.keywords)].join(' ').toLocaleLowerCase();
    return (!catalog || (catalog === '__root__' ? !d.catalog : d.catalog === catalog))
      && (!language || list(d.languages).includes(language))
      && (!licence || (licence === 'url' ? Boolean(d.licence) : !d.licence))
      && terms.every(term => text.includes(term));
  });
}

export function filterDocuments(documents, query = '') {
  const terms = query.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  return list(documents).filter(d => {
    const text = [d.title, d.language, ...list(d.tags)].join(' ').toLocaleLowerCase();
    return terms.every(term => text.includes(term));
  });
}

export function searchParams(question, k, language, tag) {
  const q = question.trim();
  if (q.length < 2 || q.length > 2000) throw new Error('Enter a question between 2 and 2000 characters.');
  const params = new URLSearchParams({q, k: String(k)});
  if (language) params.set('language', language);
  if (tag) params.set('tag', tag);
  return params;
}

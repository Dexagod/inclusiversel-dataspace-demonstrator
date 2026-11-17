import test from 'node:test';
import assert from 'node:assert/strict';
import {filterDatasets, filterDocuments, safeURL, searchParams} from '../static/model.mjs';

const datasets = [
  {id: 'fictional-museum', title: 'Fictional museum API', publisher: {name: 'Example publisher'}, catalog: 'france', spatial: ['Example town'], languages: ['fr'], licence: 'https://example.org/licence'},
  {id: 'fictional-stops', title: 'Fictional transport stops', catalog: 'belgium-mobility', themes: ['mobility'], languages: ['nl'], licence_note: 'Unconfirmed'},
  {id: 'fictional-root', title: 'Unassigned fixture'},
];
test('catalog, language, licence and text filters compose without losing root records', () => {
  assert.equal(filterDatasets(datasets).length, 3);
  assert.deepEqual(filterDatasets(datasets, {query: 'MUSEUM publisher', catalog: 'france', language: 'fr', licence: 'url'}).map(d => d.id), ['fictional-museum']);
  assert.equal(filterDatasets(datasets, {query: 'museum', language: 'nl'}).length, 0);
  assert.equal(filterDatasets(datasets, {licence: 'note'}).length, 2);
  assert.equal(filterDatasets(datasets, {catalog: '__root__'})[0].id, 'fictional-root');
  assert.equal(filterDatasets(datasets, {catalog: 'belgium-mobility'})[0].id, 'fictional-stops');
});
test('document search includes topics and languages, with missing metadata', () => {
  const docs = [{title: 'Fictional guidance', tags: ['criteria'], language: 'fr'}, {title: 'Another document'}];
  assert.equal(filterDocuments(docs, 'criteria fr').length, 1);
  assert.equal(filterDocuments(docs, 'unknown').length, 0);
  assert.equal(filterDocuments(docs, '').length, 2);
});
test('only safe HTTP(S) links are rendered as links', () => {
  for (const url of ['javascript:alert(1)', 'data:text/html,test', '//example.org', 'https://user:secret@example.org', null]) assert.equal(safeURL(url), null);
  assert.equal(safeURL('https://example.org/a?q=x&b=y'), 'https://example.org/a?q=x&b=y');
  assert.equal(safeURL('http://src-example:8000/'), 'http://src-example:8000/');
});
test('RAG filters round-trip multilingual questions and special characters exactly', () => {
  const params = searchParams('  Où trouver A+ & B ?  ', 5, 'fr', 'criteria & labels');
  const parsed = new URLSearchParams(params.toString());
  assert.equal(parsed.get('q'), 'Où trouver A+ & B ?');
  assert.equal(parsed.get('tag'), 'criteria & labels');
  assert.equal(parsed.get('language'), 'fr');
  assert.equal(parsed.get('k'), '5');
  assert.equal(searchParams('Question', 3, '', '').has('language'), false);
  assert.throws(() => searchParams(' ', 5));
});

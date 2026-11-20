import test from 'node:test';
import assert from 'node:assert/strict';
import {renderMarkdown} from '../static/markdown.mjs';

test('renders headings, paragraphs, emphasis, nested lists, quotes and code', () => {
  const html = renderMarkdown('# Guide\n\nA **strong** and *emphasized* rule.\n\n## Steps\n\n1. Read `width`\n   - Keep unknown values\n2. Cite the source\n\n> An example\n\n```html\n<b>literal code</b>\n```');
  for (const fragment of ['<h1>Guide</h1>', '<h2>Steps</h2>', '<strong>strong</strong>', '<em>emphasized</em>', '<ol>', '<ul>', '<code>width</code>', '<blockquote>', '<pre><code class="language-html">&lt;b&gt;literal code&lt;/b&gt;']) assert.ok(html.includes(fragment), fragment);
  assert.equal(renderMarkdown('one\ntwo\n\nthree'), '<p>one\ntwo</p>\n<p>three</p>\n');
  assert.match(renderMarkdown('one  \ntwo'), /one<br>\ntwo/);
  assert.equal(renderMarkdown(''), '');
});

test('tables keep alignment without inline styles and scroll within the context', () => {
  const html = renderMarkdown('| Field | Value |\n| :--- | ---: |\n| **Width** | `90` |');
  assert.match(html, /<div class="markdown-table"><table>/);
  assert.match(html, /<th class="align-left">Field<\/th>/);
  assert.match(html, /<td class="align-right"><code>90<\/code><\/td>/);
  assert.doesNotMatch(html, /style=/);
});

test('reference links and autolinks remain clickable with safe external attributes', () => {
  const html = renderMarkdown('[**Guide**][guide]\n\n[guide]: https://example.org/guide "Source"\n\n<https://example.org/more>');
  assert.match(html, /href="https:\/\/example.org\/guide" title="Source" target="_blank" rel="noopener noreferrer"><strong>Guide<\/strong>/);
  assert.match(html, /href="https:\/\/example.org\/more"/);
});

test('raw HTML and unsafe URLs cannot inject active content', () => {
  for (const source of [
    '<script>alert(1)</script>',
    '<img src=x onerror=alert(1)>',
    '<svg onload=alert(1)>',
    '[bad](javascript:alert%281%29)',
    '[bad](jav&#x61;script:alert%281%29)',
    '[bad](data:text/html,unsafe)',
    '[bad](https://user:secret@example.org)',
    '[bad](//example.org)',
    '&lt;img src=x onerror=alert(1)&gt;',
  ]) {
    const html = renderMarkdown(source);
    assert.doesNotMatch(html, /<(?:script|img|svg)\b/i, source);
    assert.doesNotMatch(html, /<a\b/, source);
  }
  assert.match(renderMarkdown('<script>alert(1)</script>'), /&lt;script&gt;/);
  assert.doesNotMatch(renderMarkdown('![Example image](https://example.org/image.png)'), /<img\b/);
  assert.match(renderMarkdown('![Example image](https://example.org/image.png)'), /Example image/);
  assert.match(renderMarkdown('[Guide](https://example.org "&quot; onmouseover=&quot;bad")'), /title="&quot; onmouseover=&quot;bad"/);
});

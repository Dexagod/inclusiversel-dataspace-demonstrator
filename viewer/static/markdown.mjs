import MarkdownIt from './vendor/markdown-it.mjs';
import {safeURL} from './model.mjs';

// Raw HTML stays literal. Only validated links become active; images stay text.
const markdown = new MarkdownIt({html: false, breaks: false, linkify: false});
markdown.validateLink = url => Boolean(safeURL(url));
markdown.renderer.rules.link_open = (tokens, index, options, env, renderer) => {
  tokens[index].attrSet('target', '_blank');
  tokens[index].attrSet('rel', 'noopener noreferrer');
  return renderer.renderToken(tokens, index, options);
};
markdown.renderer.rules.image = (tokens, index) => markdown.utils.escapeHtml(tokens[index].content);

// Keep table alignment compatible with the viewer's no-inline-style CSP.
for (const type of ['th_open', 'td_open']) {
  markdown.renderer.rules[type] = (tokens, index, options, env, renderer) => {
    const token = tokens[index];
    const alignment = /^text-align:(left|center|right)$/.exec(token.attrGet('style') || '');
    if (alignment) {
      token.attrs = token.attrs.filter(([name]) => name !== 'style');
      token.attrSet('class', `align-${alignment[1]}`);
    }
    return renderer.renderToken(tokens, index, options);
  };
}
markdown.renderer.rules.table_open = () => '<div class="markdown-table"><table>\n';
markdown.renderer.rules.table_close = () => '</table></div>\n';

export function renderMarkdown(source) {
  return markdown.render(String(source ?? ''));
}

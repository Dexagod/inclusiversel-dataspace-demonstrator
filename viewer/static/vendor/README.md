# Bundled Markdown parser

`markdown-it.mjs` is the unmodified, self-contained browser ESM bundle from
`markdown-it` **15.0.3**, distributed under the MIT licence in
`markdown-it.LICENSE`. No CDN or package install is needed at runtime or for tests.

- Upstream: https://github.com/markdown-it/markdown-it
- Archive: https://registry.npmjs.org/markdown-it/-/markdown-it-15.0.3.tgz
- Archive entry: `package/dist/browser/markdown-it.esm.min.mjs`
- Verified npm SHA-512 integrity:
  `+Az7Ojz3iRGu8KYMvJ6xVhvrxP3eE+vEtJX75Ow88XBpcQNV/0lGX5ZynIIBftREo4DC2jsveAMDaeltmm8QvQ==`

The viewer's renderer configuration lives in `../markdown.mjs`: raw HTML is
disabled, links use the existing HTTP(S) allowlist, and images render as alt text.
When updating the bundle, retain its licence and rerun `make -C viewer check`.

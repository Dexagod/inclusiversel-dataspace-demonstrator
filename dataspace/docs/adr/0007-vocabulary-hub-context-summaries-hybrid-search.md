# 7. Vocabulary hub: permanent context, summaries and hybrid search

Date: 2026-11-23 (permanent context: 2026-11-19)

The hub returns cited passages, without a language model. Three changes make those passages more useful to an agent.

**Permanent context.** `GET /context` and `PUT /context` read and replace one Markdown text (at most 20,000 characters, stored in the `vochub-data` volume). The connector's `vochub_search` now returns `{context, results}` instead of a bare list, so the agent gets the rules with every search: which sources to trust first (by `assessment`, [ADR 0006](0006-assessment-methods.md)), how to compare them, to search the catalog in Dutch, French and English, to decide itself which datasets cover a town, to ask the hub again about labels it does not know (the hub has no graph of related topics), when to search the web, and how to lay out the answer. The demo text is [`sources/permanent-context.md`](../../../sources/permanent-context.md). Keep it short: it travels with every search.

**Summary per document.** Uploads take an optional `summary` (a few sentences: what the document is, which label or standard, for whom, where). It is stored with the document and indexed as a passage of its own, so broad questions ("which labels exist?") find documents and not only fragments. Without one, the hub falls back to the document's own description (HTML meta description, PDF subject). Generating summaries would need a language model, which the hub does not have.

**Search: meaning and keywords, at most two passages per document.** Every chunk now has a dense vector (the multilingual embedding model) and a BM25 keyword vector (no stemming, so names and codes such as "A+" match as written, in any language). `GET /search` takes candidates from both, merges them with reciprocal rank fusion over all candidates, and only then keeps at most 2 passages per document (a first version used Qdrant's grouped query, which ranks within each document and so ordered documents almost arbitrarily). Before this, a one-word question such as "label" returned 18 passages of one page, and a 700-chunk report crowded out everything else. The `score` now only orders the hits; it is not a similarity.

**Chunking.** PDF pages get their heading path from the PDF's table of contents, and chunks with fewer than 5 real words (page numbers, empty table rows) are dropped: they matched on their document title alone.

**Migration.** The vectors moved to a new Qdrant collection, `passages`; the old `chunks` collection is no longer read. After deploying, run `make knowledge` in `sources/`.

**Not done, for later:** a reranker on the top hits and a stronger model with longer chunks (open work in [AGENTS.md](../../../AGENTS.md)).

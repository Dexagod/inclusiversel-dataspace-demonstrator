# 5. Web pages and PDFs as datasets

Date: 2026-11-19

Some accessibility information is published only as a web page or PDF: Zon, Zee … Zorgeloos (beach services per coastal town, every summer), event programmes, parking guides. It changes, so it is data, not domain knowledge for the vocabulary hub. Agents should find it in the catalog and query it like any other source, without the connector learning a new kind of source.

**A document is registered as a dataset with an API.** `../sources/documents/` reads each `documents/<id>/registration.json` and serves the page or PDF named in its first `distributions` entry as a sub-API with its own OpenAPI, so the five MCP tools work unchanged. Three operations per document:

| Operation | Returns |
| --- | --- |
| `<id>_get_outline` | title, dates, and every section: id, heading path, page |
| `<id>_search` | sections containing the given words (case and accents ignored, also inside longer words), best first |
| `<id>_get_section` | the full text of one section |

**Sections follow the document's own structure,** because an agent needs to know which town, event or page a sentence belongs to. Web pages: the main content becomes Markdown. Accordion and disclosure titles (`<summary>`, `button[aria-expanded]`) are turned into headings first, with the panel's headings placed below them. Generic extractors such as trafilatura dropped every town name on the Zon, Zee … Zorgeloos page. PDFs: one section per page, with the heading path from the PDF's table of contents when it has one.

**Freshness is explicit.** Every answer carries `document_date` (PDF metadata), `last_modified` (HTTP header), `retrieved_at` and `content_changed_at`. The adapter fetches at most every `REFRESH_HOURS` (default 24), honours robots.txt, sends an identifying user agent, keeps the last good copy during an outage, and never changes the text. PDFs are downloaded, as a browser would.

**Catalog: `distributions`.** A registration may list further distributions besides the API (`url`, `media_type`, `title`). The DCAT export adds each one as a `dcat:Distribution` with `dcat:accessURL`, `dcat:mediaType` (IANA) and, for files, `dcat:downloadURL`. A document dataset therefore shows both the original page or PDF and the API that reads it. Other sources can use the field for their own downloads.

**Search is by words, not meaning.** Agents search in the document's language, which the API description states. Semantic search would mean an embedding model in the adapter, or the vocabulary hub holding the data again. `shortcut: keyword search; add embeddings if agents miss sections they should find.`

**Licence.** A document dataset is a data source: the licence exception for vocabulary-hub documents does not apply. Register only documents whose terms allow reuse, or whose terms are not stated (with a `licence_note`). Example: Tourisme & Handicaps' Dunkerque programme forbids reproduction without written permission, so it is not registered.

# Accessibility data space viewer

A separate, read-only web interface for the metadata broker and vocabulary hub.
It discovers all registered sources through the existing HTTP APIs; no catalog,
source list, document corpus, credentials or place records are copied into it.

## Run locally

Requires Python 3.10+; there are no runtime packages to install or frontend build steps.

```sh
make -C viewer run
```

Open **http://localhost:8090**. Start the existing data space separately if needed:

```sh
make -C dataspace up
make -C sources up
make -C sources register
make -C sources knowledge  # optional public document ingestion, needs internet
```

The viewer works without the source proxies running: it reads registration and
document metadata, not source place APIs. An empty catalog or hub remains empty
until seeded. It never substitutes demo records for missing live data.

Configuration is via process environment; the viewer does **not** read `.env`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `CATALOG_URL` | `http://localhost:8001` | Metadata broker base URL |
| `VOCHUB_URL` | `http://localhost:8002` | Vocabulary hub base URL |
| `VIEWER_HOST` | `127.0.0.1` | Listener address |
| `VIEWER_PORT` | `8090` | Listener port |

`python3 viewer/server.py --host 127.0.0.1 --port 8091` also selects the listener.
Use a modern browser with JavaScript enabled. Node.js 18+ is needed only for tests.

## Run in Docker

With the data space's `accessibility-dataspace_default` network already present:

```sh
make -C viewer up
make -C viewer down
```

This is an independent Compose project and container on port 8090. It does not
modify or restart the data space or source services. The port is bound to loopback.
To publish it on a server (during presentations only; it has no authentication), put
it behind Caddy or nginx under `/viewer/` (its paths are relative, so the root works too): see "Reverse proxy: Caddy or nginx" in
[`../dataspace/README.md`](../dataspace/README.md#reverse-proxy-caddy-or-nginx).

## What the interface shows

- **Metadata broker:** actual DCAT sub-catalogs and memberships, dataset and publisher
  counts, searchable datasets, catalog/language/licence filters, full registrations,
  source DCAT, endpoints, access conditions, dates, licence notes, and root DCAT
  downloads in Turtle and JSON-LD. Datasets without a sub-catalog appear under Root.
- **Vocabulary hub:** all ingested documents, their tags, language, chunk count,
  source URL, ingestion date and licence. Ask a question in any supported embedding
  language; choose the result count and optional document-language/topic filters.
  Results retain the exact returned excerpts, rank, score, page/heading,
  source URL and licence. Ingestion dates are joined from the document list by ID;
  retrieval time is recorded in the interface. Missing metadata stays explicit.

Search calls the hub's existing `/search` endpoint. This is the retrieval stage of
RAG, **not an LLM-generated answer**. The score only orders the passages; it is not a confidence percentage.
Search does not query source place APIs, resolve a journey, or verify current
accessibility. A knowledge document about Access-i, for example, does not mean an
Access-i place source has been integrated. Existing and newly registered datasets
(including mobility datasets) appear automatically after Refresh.

Root DCAT links export the complete graph. There is no per-sub-catalog export
endpoint in the current broker; selecting a catalog filters the dataset list.
API/OpenAPI links preserve registered addresses, including Docker service names
that may not resolve from the host browser. No addresses are guessed or rewritten.

## Boundaries and HTTP access

All implementation and tests live in `viewer/`. The root `AGENTS.md` documents the
component; `dataspace/` and `sources/` remain owned by their respective workstreams.
The viewer talks only to existing broker/hub read endpoints. It neither uses the
agent MCP connector nor changes its agent-only workflow.

The standard-library Python server serves static files and proxies an explicit
GET/HEAD allowlist to the two configured services. It rejects mutation methods,
unknown paths, unsupported query parameters, arbitrary target URLs and upstream
redirects. Responses are bounded at 16 MiB with a 45-second upstream timeout.
Errors are isolated per service, and questions are not written to request logs.
The same-origin proxy removes any need to add CORS to the existing services.
Metadata and retrieved passages are rendered as text. The collapsed Permanent
context section renders Markdown headings, lists, links, tables, quotes and code
using a locally bundled MIT-licensed markdown-it parser. Raw HTML stays literal,
images display their alt text, and outgoing links accept only credential-free
HTTP(S) URLs. No authentication keys or private exports are used.

## Verification

```sh
make -C viewer check
```

Tests use local HTTP stubs and fictional records only. They cover the proxy
allowlist, forbidden writes, path/URL injection, error/timeout/redirect handling,
DCAT media types, question forwarding, filtering, Markdown formatting and safe links. They do not
contact public sites or require a running data space.

For browser QA against the same fictional data, run
`python3 viewer/tests/preview.py` and open **http://localhost:8091**. This explicit
test server is separate from the live viewer; all its records are marked fictional.

Project-wide checks remain `make -C dataspace check` and `make -C sources test`.
The viewer changes no backend contracts. For a live smoke check, verify catalog
counts against `/catalogs` and `/datasets`, open a registration, and run a hub
question against `/search`; a successfully retrieved passage should retain its URL,
licence and page/heading. Source/connector end-to-end tests are separate from the
viewer and may require credentials and live internet access.

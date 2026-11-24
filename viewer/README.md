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

Catalog and vocabulary browsing work without the source proxies running.
Replaying source calls requires the connector and the relevant source API. An empty catalog or hub remains empty
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

On a server the viewer is published under `/viewer/`, e.g. https://dataspace.example.org/viewer/.

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
  Results retain the exact returned excerpts, rank, page/heading,
  source URL and licence. Ingestion dates are joined from the document list by ID;
  retrieval time is recorded in the interface. Missing metadata stays explicit.

Search calls the hub's existing `/search` endpoint, which combines meaning and
keyword search and returns at most two passages per document ([ADR 0007](../dataspace/docs/adr/0007-vocabulary-hub-context-summaries-hybrid-search.md)).
A document's summary appears as a passage with the heading "Summary". This is the retrieval stage of
RAG, **not an LLM-generated answer**. The viewer shows the rank only: the hub's fused score orders the passages but says nothing about confidence.
Search does not query source place APIs, resolve a journey, or verify current
accessibility. A knowledge document about Access-i, for example, does not mean an
Access-i place source has been integrated. Existing and newly registered datasets
(including mobility datasets) appear automatically after Refresh.

Root DCAT links export the complete graph. There is no per-sub-catalog export
endpoint in the current broker; selecting a catalog filters the dataset list.
API/OpenAPI links preserve registered addresses, including Docker service names
such as `http://src-iedereenoveral:8000/food-and-drink/` that do not open from a
browser. That is by design: the source proxies are not published, and agents reach
them only through the connector, which runs on the same Docker network (see the
note under "Settings" in [`../dataspace/README.md`](../dataspace/README.md#settings)).
No addresses are guessed or rewritten.

## Boundaries and HTTP access

All implementation and tests live in `viewer/`. The root `AGENTS.md` documents the
component; `dataspace/` and `sources/` remain owned by their respective workstreams.
The viewer talks to existing broker/hub read endpoints and optionally reads a local
connector log snapshot for demonstrations. Explicit replay requests use the
connector’s validated read-only tools through its demo endpoint.

The standard-library Python server serves static files and proxies an explicit
GET/HEAD allowlist to the two configured services. A single same-origin POST endpoint
repeats read-only tools through the connector. It rejects other mutation methods,
unknown paths, unsupported query parameters, arbitrary target URLs and upstream
redirects. Responses are bounded at 16 MiB with a 45-second upstream timeout (75 seconds
for replay).
Errors are isolated per service, and questions are not written to request logs.
The same-origin proxy removes any need to add CORS to the existing services.
Metadata and retrieved passages are rendered as text. The collapsed Permanent
context section renders Markdown headings, lists, links, tables, quotes and code
using a locally bundled MIT-licensed markdown-it parser. Raw HTML stays literal,
images display their alt text, and outgoing links accept only credential-free
HTTP(S) URLs. The viewer never reads credential files or private export files;
replay responses can contain source records returned by the connector.

## Demonstrating connector logs

The **Logs** tab reads the connector's existing `call_log: 1` JSON lines. It
shows expandable calls with arguments, timestamps, duration, answer size, source
operation, errors and truncation. Search and failure filters apply to the timeline
and its totals. The scrollable timeline groups calls by reported MCP session ID,
then declared client ID, then an explicitly labelled address/client heuristic.
A new group starts after 2, 5 or 15 idle minutes for that client. Old entries with
no identity appear as Unknown requester and may contain several clients. The
connector remains stateless, so initialized client names/session IDs may not be
available; inferred groups can combine clients behind a proxy. Metadata is not
verified identity. Filtering does not change the original grouping. Expanded
groups, calls, request identity and responses remain open during refresh, and the
list retains its scroll position. Parallel calls count once in active time.

**Show request response** repeats the selected read-only tool through the
connector and displays the fresh result in a read-only text field. This is not
recovery of the original response; source data may have changed. Replays retain
SDK argument validation, source OpenAPI validation and connector credential
handling, and are logged as new viewer requests when logging is enabled.
`CONNECTOR_URL` defaults to `http://localhost:8800` for a Python-hosted viewer and
`http://connector:8800` in Compose. A random per-tab ID in session storage groups
viewer replays without impersonating the original requester. Response bodies stay
in the page and are neither written to the log snapshot nor browser storage.

After upgrading, rebuild the connector to enable metadata and the replay endpoint:
`docker compose -f dataspace/docker-compose.yml up --build -d --no-deps connector`.
Re-run the collector as described below. Metadata cannot be added retroactively
to historical call entries.

For a recorded demo, export from the machine running the connector:

```sh
mkdir -p viewer/.logs
docker compose -f dataspace/docker-compose.yml logs --no-log-prefix connector > viewer/.logs/demo.log
```

Then choose **Import log file** in the tab. Files are parsed in the browser and
are not uploaded or saved in browser storage. JSONL, plain Docker logs and Compose
prefixes are accepted; non-call lines are skipped. Imports are limited to 8 MiB
and the latest 1,000 calls. Arguments are shown only when a call is expanded.

For a live, closed demonstration, with `CALL_LOG=1` already enabled on the
connector, run these in separate terminals from the repository root:

```sh
make -C viewer logs       # follows Docker stdout; Ctrl+C stops collection
make -C viewer demo-up    # starts only the viewer, with the snapshot mounted read-only
```

Open the Logs tab and select **Refresh live every 3 seconds**. Polling pauses when
the tab or browser document is hidden. `python3 viewer/collect_logs.py --container
NAME` selects a differently named connector. Re-run the collector after recreating
the connector container. For a Python-hosted viewer, set
`VIEWER_LOG_FILE=/absolute/path/to/viewer/.logs/calls.jsonl` before `make -C viewer run`.

The collector runs on the Docker host; the viewer never gets the Docker socket.
Snapshots contain only call-log fields, not source response bodies, and `.logs/`
is excluded from Git and Docker builds. Logs include user questions: the normal
Compose configuration leaves the live endpoint disabled. Enable the demo override
only for an audience allowed to see those questions. Stop the collector and run
`make -C viewer up` to remove the live feed afterward; the last local snapshot is
retained until you remove it. Imported files remain local to that browser tab.

## Verification commands

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

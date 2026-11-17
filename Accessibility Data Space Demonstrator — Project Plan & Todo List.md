# Accessibility Data Space Demonstrator — Project Plan & Todo List

Nov 12, 2026 · @Ruben

## Goal, scope and definition of done

The goal is a single `docker compose up` that starts a small accessibility data space: four source adapters with OpenAPI definitions, a DCAT catalog, a vocabulary hub for domain knowledge, and an MCP connector that lets a user agent answer a question end to end. No authentication or authorization in v1.

**Working rule (organization instruction):** Claude is only to be used for public research and open-source projects. Keep every dataset, document and line of code in this repo public or open-source, and do not paste non-public material into agent sessions.

**Definition of done for the demonstrator**

- [ ] A clean checkout runs with one `docker compose up` (plus an `.env` file) and reaches a healthy state.
- [ ] The catalog lists at least four datasets, one per source, each linking to a valid OpenAPI document.
- [ ] Each adapter answers a place search and a place detail call with data that is traceable to the original source.
- [ ] The vocabulary hub ingests a PDF and a web page and returns cited chunks for a question.
- [ ] A user agent answers the golden questions in the demo section with the right sources, provenance and an honest "no coverage" when applicable.
- [ ] A fifth source can be added by following a documented recipe (target: under one working day, mostly adapter code).

**Out of scope for v1:** authentication, usage policies and contracts, Dataspace Protocol or Eclipse Dataspace Components connectors, write access to sources, full mirrors of the sources, and production hosting.

## Decisions and status (updated Nov 12, 2026)

The core infrastructure is built in `dataspace/`; the source adapters follow in a later round.

| Topic | Decision | Rejected alternative and why |
| --- | --- | --- |
| Stack | Python 3.12 and FastAPI for every service | Reusing the Node/Express prototype: document extraction and embedding libraries are much stronger in Python. The prototype is kept in `dataspace/legacy/` |
| Publishing | Publishers register a dataset through `POST` or `PUT /datasets/{id}` with DCAT metadata, `endpoint_url` and `openapi_url`; the catalog checks that the OpenAPI document is OpenAPI 3.x | A `source.yaml` built at deploy time only: a registration API lets external publishers join without a rebuild. Seed registrations are JSON files in `seed/registrations/` |
| Catalog store | Registration records as JSON files on a volume; the DCAT graph (rdflib) is derived on request, with Turtle, JSON-LD and SPARQL | A separate triple store (Oxigraph, Fuseki): one fewer container, and a demo-sized catalog fits in memory. Revisit when the catalog grows or needs federation |
| Vocabulary hub | PyMuPDF for PDF (keeps page numbers), trafilatura for web pages, markitdown for DOCX, PPTX, XLSX, CSV and other formats; heading-aware chunks of up to 250 words; fastembed inside the hub container; Qdrant v1.20 | A separate embedding container: fastembed runs on CPU with ONNX, and the model is baked into the image. The default model is `paraphrase-multilingual-MiniLM-L12-v2` (about 220 MB); `multilingual-e5-large` is an option via a build argument |
| Source API keys | The connector reads `config/credentials.yaml` (dataset id to `${ENV_VAR}`), with values in `.env`. Where the key goes comes from the source's OpenAPI `securitySchemes`, with an optional `in`, `name` and `prefix` override. Keys never reach the agent | Keys in the catalog: they would be shared with every consumer |
| Consumer authentication | Removed (the prototype had JWT login and purpose checks) | Keeping it: v1 has no auth, and it can come back later in front of the connector without changing the tools |
| MCP SDK | Python `mcp` 2.x (`MCPServer`), stateless streamable HTTP on port 8800 | |
| Gateway | Not yet; each service has its own port (catalog 8001, vochub 8002, connector 8800) | Add one when the adapters arrive and need stable `/sources/<id>/` URLs |
| Example source | `sources/example`: a small Ghent API that needs an `X-API-Key`, to show the registration and key flow offline | Acceslibre as the first live source: its OpenAPI location and key header are not yet confirmed (Phase 1.1) |
| First provider: IedereenOveral | Live proxy adapter `sources/iedereenoveral` in front of Inter's Xano API, registered in the catalog instead of the raw API. It shrinks responses (a 130 KB place detail becomes about 8 KB; list items lose their HTML), resolves town names to Xano's numeric city ids, sends multi-value filters as JSON arrays (the only form Xano reads correctly) and exposes four described read operations | Registering the raw API: responses overwhelm agents with database internals, filters need numeric ids, there are no parameter descriptions, and repeated array parameters silently drop values |
| Licence unknown | `licence` is optional in a registration when `licence_note` explains why; the DCAT output then has a `dct:rights` statement instead of `dct:license` | Inventing a licence or citing the website as one |

**Done:** catalog with registration, search, DCAT and SPARQL (tasks 2.8 to 2.10, without SHACL); vocabulary hub ingestion, embeddings, search and seed (2.12 to 2.16); MCP connector with the five tools, OpenAPI parameter validation, read-only calls, host check, timeouts and truncation (3.1, 3.2, most of 3.3); compose, `make up`, `check`, `e2e` and `seed`; IedereenOveral adapter (1.3 and 2.6, apart from the reuse terms).
**Open:** the call budget per question (3.3), SHACL validation (2.11), the skill document and demo agent (3.4 to 3.6), the Acceslibre, Access-i and Picto Access adapters, the reuse terms for IedereenOveral, the gateway, and the golden-question harness.

## Target architecture

Every question flows through one MCP connector: it asks the vocabulary hub for terms, the catalog for sources, and the gateway for each source's OpenAPI and data.

&#91;embedded content: architecture · agent, connector, hub, catalog, gateway, 4 adapters\]

The numbers show the order of tool calls in the skill workflow. Adding a source adds one adapter container and one `source.yaml`; nothing else changes.

**Compose services** (names are suggestions)

| Service | Profile | Role |
| --- | --- | --- |
| `gateway` | core | (later) Single entry point on port 8080; routes `/sources/<id>/` to each adapter |
| `catalog` | core | Registration API, search, DCAT export and SPARQL (port 8001); registrations on a volume |
| `vochub`, `vochub-vectors` | core | Hub API with built-in embedding model (port 8002), Qdrant vector database |
| `example-source` | core | Demo API that needs an API key (port 8101) |
| `src-iedereenoveral` | core | Live adapter for IedereenOveral (port 8102) |
| `src-acceslibre`, `src-access-i`, `src-pictoaccess` | core | (later) One adapter per source, each serving its own OpenAPI |
| `crawler` | crawl | (later) One-shot refresh jobs that rebuild snapshots |
| `connector` | demo | MCP server for the user agent on port 8800; holds source API keys |
| `agent` | demo | (later) Demo CLI agent, started on demand with `docker compose run` |

## Source landscape

Only Acceslibre documents a public API; the other three look like websites without a published data interface, so each adapter will be a different mix of live proxy, snapshot and crawler. These findings come from public web pages and must be confirmed in the Phase 1 spike. The platform you listed as iedereenoveral.info is also published as iedereenoveral.be.

| Source | Coverage and content | Access path found | Adapter mode (proposed) | To verify |
| --- | --- | --- | --- | --- |
| [Acceslibre](https://acceslibre.beta.gouv.fr/contact/questions-frequentes/) | France; public buildings (ERP), crowd and manager contributed | REST API with [docs](https://acceslibre.beta.gouv.fr/api/docs/), keys on request; open CSV dumps on [data.gouv.fr](https://www.data.gouv.fr/datasets/acceslibre) (two files, about 518 MB and 195 MB); data schema published; [Licence Ouverte 2.0](https://acceslibre.beta.gouv.fr/cgu), code under MIT | Live proxy to the API, with a regional CSV snapshot as fallback | Request an API key; rate limits; field names for the schema |
| [Access-i](https://access-i.be/en/?p=1453) | Wallonia and Brussels; sites audited by accredited experts, rated per disability type; [500+ locations](https://www.visit.brussels/es/profesionales/partners/labels-awards/access-i-certification) | WordPress site; WP REST API visible at [wp-json](https://access-i.be/en/wp-json/wp/v2/posts/23781); one information sheet per place; no data API documented | Crawl or WP REST read into a local snapshot, served by a search API | Which WP post type holds place sheets; terms of use; robots.txt |
| [IedereenOveral](https://iedereen.overal.info) | Flanders and Brussels; cafes and restaurants, public toilets, Changing Places, museums, parking; about 7,700 places with a medal and questionnaire answers; successor of [Toevla](https://www.vlaanderen.be/inter/toolbox-toegankelijke-steden-en-gemeenten/ondernemen-en-werken/website-toevla-stopt) | Xano REST API `https://xcli-wrwg-eljt.f2.xano.io/api:SuAo_4fA` with an OpenAPI 3.0 spec; public reads need no key | **Built:** live proxy adapter `src-iedereenoveral` that returns compact records (see `dataspace/docs/sources/iedereenoveral.md`) | Reuse terms with Inter; unauthenticated write routes in their spec (`/province`) |
| [Picto Access](https://trappes.fr/print/pdf/node/4034) | France; municipal and campus buildings rated with 8 pictograms in 3 levels (A green, B yellow, C red), see the [Limoges release](https://limoges.fr/sites/default/files/espace_presse/2025/CP%20Picto%20Access%2003%202025-1.pdf) | Public pages such as `/cards/<slug>` and `/brands/<slug>`; no public API found | Crawl a chosen set of brands into a snapshot, served by a search API | Terms of use; permission from the vendor; robots.txt |

A good fifth source to prove the "add a source" recipe is the Toerisme Vlaanderen accessibility open data, for example [accessible monuments](https://metadata.omgeving.vlaanderen.be/srv/api/records/6024b7e8-e293-3d1f-b936-0343a3c6ec95), which is already described in DCAT-style metadata.

## Repo layout and AI-driven workflow

Work spec-first: contracts (OpenAPI files, DCAT shapes, MCP tool schemas) are committed before the code behind them, and every agent task is small, testable and ends in a green `make check`. One monorepo keeps the compose file, contracts and tests visible to every agent session.

```text
dataspace/
  AGENTS.md              rules for coding agents (CLAUDE.md points here)
  docker-compose.yml
  .env.example           secrets (source API keys) go in .env, never in git
  Makefile               up, down, check, test, e2e, seed, clean
  config/credentials.yaml  dataset id -> ${ENV_VAR} API key for the connector
  seed/
    registrations/       dataset registrations loaded at start-up
    domain-knowledge.yaml  public documents for `make seed`
  catalog/               registration API, DCAT builder, search, SPARQL
  vochub/                extraction, chunking, embeddings, search API
  connector/             MCP server the agent talks to
  sources/
    example/             demo API with an API key
    _template/  acceslibre/  access-i/  iedereenoveral/  pictoaccess/   (later)
      registration.json  catalog registration for the source
      app/ tests/ Dockerfile
  packages/adapter-kit/  (later) shared FastAPI library: models, paging, errors, provenance
  docs/adr/              (later) decision records
  agent/                 (later) skill document, demo CLI agent, evaluation harness
  tests/e2e/             compose-level smoke test (golden questions later)
  legacy/                previous Node.js prototype
```

Contracts are the OpenAPI documents that each FastAPI service generates (`/openapi.json`) and the MCP tool schemas the connector publishes; exporting them to a `contracts/` folder for review is still open.

**Working rules for the AI agents**

1. Each task names one component, its inputs (files to read), its acceptance command, and its limits. Use the task template below.
2. Tests come first. Every adapter gets contract tests (for example Schemathesis against its own OpenAPI) and recorded fixtures of the live source, so tests run offline and never hammer a public site.
3. `make check` is the only gate: lint, unit tests, contract tests, and `docker compose build`. A task is not done until it passes.
4. Agents log non-obvious decisions as short ADRs in `docs/adr/`, so a human can review choices rather than diffs.
5. `AGENTS.md` fixes the guardrails: public data and open-source code only, crawlers honour robots.txt and rate limits, no secrets in the repo, no scope creep beyond the task.
6. A human reviews at the end of each phase gate, not at each commit.
7. After Phase 1, the component tasks in Phase 2 are independent and can run as parallel agent sessions in separate git worktrees.

```text
Task: <id> <title>
Read first: AGENTS.md, docs/architecture.md, contracts/<file>
Goal: <one sentence>
Acceptance: <commands that must pass, expected output>
Constraints: <ports, libraries, files you may not touch>
Deliver: small change set, updated docs, passing `make check`
```

## Phased todo list

The build is five phases, roughly 8 to 13 working days for one person steering AI agents (my estimate, not sourced), and each phase ends at a gate that a human signs off. Task numbers match the component specs further down.

&#91;embedded content: roadmap · 5 phases, 5 gates\]

Gates are review points, not calendar dates; the task lists below follow the same five phases.

### Phase 0: Foundations (0.5 to 1 day)

- [ ] **0.1 Repo and guardrails.** Create the monorepo with `AGENTS.md`, `Makefile` and a CI job that runs `make check`. Done when CI is green on an empty skeleton.
- [ ] **0.2 Architecture decisions.** Write `docs/architecture.md` and ADRs for the catalog store, vector store, embedding model, MCP SDK and gateway. Done when each choice lists the alternative that was rejected and why.
- [ ] **0.3 Draft the contracts.** Commit the shared place-search model, the catalog API, the vochub API and the MCP tool schemas under `contracts/`. Done when each file lints (Spectral or equivalent).
- [ ] **0.4 Compose skeleton.** One gateway, one Docker network, healthchecks, `.env.example`, and stable URLs of the form `http://localhost:8080/sources/<id>/openapi.json`. Done when `docker compose up` starts placeholder containers that report healthy.
- [ ] **0.5 Golden questions.** Write at least eight questions with the expected sources and expected facts (see the demo section) and a stub evaluation harness. Done when the harness runs and reports all as failing.

**Gate G0:** contracts and golden questions reviewed by a human.

### Phase 1: Source spikes (1 to 2 days)

- [ ] **1.1 Acceslibre.** Request an API key, read the API docs, list searchable fields and filters, choose demo regions. Done when `docs/sources/acceslibre.md` shows one working call with a saved response.
- [ ] **1.2 Access-i.** Probe the WordPress REST routes for the place post type and taxonomies; read robots.txt and terms of use. Done when the note says how to list all sheets and which fields describe accessibility per disability type.
- [ ] **1.3 IedereenOveral.** Contact Inter about a data feed and inspect what the web app itself calls. Done when the note records the answer or the observed endpoints and the reuse terms.
- [ ] **1.4 Picto Access.** Check terms and robots.txt, map the page structure of `/cards` and `/brands`, choose a small set of brands. Done when the note lists the 8 pictograms with their levels and the fields to extract.
- [ ] **1.5 Mapping to a common model.** For each source, map native fields to the shared model and keep the native payload under `raw`. Done when a table of field mappings is committed for all four.

**Gate G1:** each source has an approved access decision (live proxy, snapshot or crawl) and a licence note. A source that cannot be reused legitimately is swapped for a fallback such as Toerisme Vlaanderen open data.

### Phase 2: Core components (3 to 5 days, three parallel tracks)

**Track A: source adapters**

- [ ] **2.1 `adapter-kit`.** Shared FastAPI library with the place model, paging, error format, `/health`, provenance fields and an OpenAPI quality check. Done when a toy adapter passes the check: every operation has an `operationId`, a plain-language description and an example.
- [ ] **2.2 Snapshot store and refresh job.** SQLite with full-text search (or DuckDB) plus `make refresh SOURCE=<id>`. Done when a CSV fixture is loaded and searched by text, bounding box and category.
- [ ] **2.3 Source template.** `sources/_template` and `make new-source ID=<id>` that scaffolds `source.yaml`, app, tests and Dockerfile. Done when a generated adapter builds and passes its contract tests untouched.
- [ ] **2.4 Acceslibre adapter.** Live proxy to the API with a regional CSV snapshot fallback. Done when search by place name and by location returns places with accessibility fields and a source URL.
- [ ] **2.5 Access-i adapter.** Crawl or WP REST read into a snapshot, rate limited and resumable. Done when the snapshot holds all audited places and the search returns disability-specific ratings.
- [ ] **2.6 IedereenOveral adapter.** Built on the path chosen at G1. Done when search for cafes, restaurants and public toilets in a Flemish town returns accessibility answers.
- [ ] **2.7 Picto Access adapter.** Crawler for the chosen brands into a snapshot. Done when a place returns its 8 pictogram levels (A, B, C).

**Track B: DCAT catalog**

- [ ] **2.8 `source.yaml` schema and validator.** Title, description, publisher, licence, languages, spatial coverage, themes, update frequency, endpoint paths. Done when an invalid file fails with a readable message.
- [ ] **2.9 DCAT builder.** Generates `dcat:Catalog`, `dcat:Dataset`, `dcat:Distribution` and a `dcat:DataService` per source, where `dcat:endpointURL` is the live API and `dcat:endpointDescription` is the OpenAPI document. Done when output parses as Turtle and JSON-LD.
- [ ] **2.10 Catalog store and API.** Triple store loaded at start-up, `GET /catalog` (Turtle or JSON-LD), `GET /datasets` with text, theme, spatial and language filters, `GET /datasets/{id}`, and a SPARQL endpoint. Done when all four datasets are found by a relevant keyword.
- [ ] **2.11 SHACL validation.** Check the generated catalog against DCAT-AP shapes in CI. Done when CI fails on a dataset without a licence or without a distribution.

**Track C: vocabulary hub**

- [ ] **2.12 Service and vector store.** FastAPI service plus a vector database container with a persistent volume. Done when the service reports healthy and survives a restart with data intact.
- [ ] **2.13 Ingestion.** `POST /documents` for PDFs and `POST /documents/url` for web pages, with page numbers, headings and a content hash to skip duplicates. Done when a PDF and a web page are chunked with their source metadata.
- [ ] **2.14 Embeddings.** A multilingual open model (Dutch, French, English) running locally in its own container, configurable by env var. Done when a Dutch query finds a French passage on the same concept.
- [ ] **2.15 Search API.** `GET /search?q=&k=&language=&tag=` returns chunks with score, source URL, page and document title; retrieval only, no text generation. Done when the OpenAPI is valid and a seed question returns a cited chunk.
- [ ] **2.16 Seed set.** `seed/domain-knowledge.yaml` lists the initial public documents and pages, and `make seed` ingests them. Done when a fresh stack is seeded with one command.
- [ ] **2.17 Stretch: term mappings.** A small SKOS file that links equivalent terms across sources and languages (for example wheelchair user, rolstoelgebruiker, personne en fauteuil roulant). Done when search results can be expanded with mapped terms.

**Gate G2:** every component passes its contract tests and runs on its own in compose; the catalog lists four datasets; the vochub returns a cited chunk for a seed question.

### Phase 3: Connector, skill and user agent (2 to 3 days)

- [ ] **3.1 MCP connector skeleton.** An MCP server in its own container with streamable HTTP, a health endpoint and the tool schemas from `contracts/`. Done when an MCP inspector lists the tools.
- [ ] **3.2 Tool implementations.** `vochub_search`, `catalog_search`, `catalog_get_dataset`, `get_openapi` and `call_source_operation`. Done when each tool works against the running stack.
- [ ] **3.3 Guardrails.** Only hosts that appear in the catalog may be called, requests are validated against the OpenAPI, and each question has a call budget, timeouts and truncated responses. Done when a call to an unlisted host is refused in a test.
- [ ] **3.4 Skill document.** `agent/skills/accessibility-dataspace/SKILL.md` describing the workflow and the answer format (see the specs below). Done when a fresh agent session follows it without extra instructions.
- [ ] **3.5 Demo CLI agent.** A container that runs the agent loop against the connector, using a model API key from `.env` (or a local model profile). Done when `docker compose run agent "<question>"` prints an answer with sources.
- [ ] **3.6 Client configuration.** Ready-made MCP configuration snippets for Claude Desktop, Claude Code and a generic MCP client. Done when each client lists the tools.

**Gate G3:** the agent answers golden question 1 end to end, with the vochub call, the catalog call, an OpenAPI read and a source lookup visible in its trace.

### Phase 4: Integration, evaluation and packaging (1 to 2 days)

- [ ] **4.1 Compose profiles.** `core` (catalog, vochub, adapters, gateway), `demo` (connector, agent) and `crawl` (refresh jobs). Done when `docker compose --profile demo up` starts the whole demo.
- [ ] **4.2 End-to-end tests.** Start the stack and assert: four datasets in the catalog, every OpenAPI valid, every adapter returns at least one place, vochub returns a cited chunk. Done when `make e2e` is green from a clean volume.
- [ ] **4.3 Evaluation run.** Run all golden questions, store the traces and a score sheet. Done when results are committed and failures are explained.
- [ ] **4.4 Prove the recipe.** A fresh agent session adds a fifth source (for example Toerisme Vlaanderen accessible monuments) using only `docs/add-a-source.md`. Done when the catalog and the agent pick it up without changes to other components.
- [ ] **4.5 Quickstart and demo script.** README with prerequisites, commands, ports and troubleshooting, plus a scripted demo walk-through. Done when someone else runs it from the README alone.

**Gate G4:** demonstrator accepted; known limits and next steps are written down.

## Component specs

Each component has one contract that the agent tasks above implement and test. Details marked "suggested" are decided in the Phase 0 ADRs.

### Source adapters (tasks 2.1 to 2.7)

Every adapter is one container with the same core operations, so the agent can learn one pattern and still read each OpenAPI for source-specific filters. The OpenAPI text is written for a language model reader: unambiguous descriptions, allowed values, examples, and `operationId`s such as `acceslibre_search_places`.

| Operation | Purpose | Key parameters |
| --- | --- | --- |
| `GET /places` | Search places | `q`, `near` (lat,lon) with `radius_km`, `bbox`, `category`, `needs` (source-specific accessibility filters), `limit`, `cursor` |
| `GET /places/{id}` | One place with full accessibility detail | `id` |
| `GET /facets` | Which categories, needs and regions this source supports | none |
| `GET /about` | Source metadata, same content as `source.yaml` | none |
| `GET /health` | Liveness and snapshot date | none |

A place in the shared model carries: `id`, `name`, `category`, `address`, `location`, a list of accessibility statements (`criterion`, `value`, optional `level` and `disability_type`, free-text `detail`), `source_url`, `retrieved_at`, `licence`, `mode` (`live` or `snapshot`) and the untouched native payload under `raw`. Provenance is mandatory because the agent must cite it.

### DCAT catalog (tasks 2.8 to 2.11)

A source is added by one registration: a publisher calls `POST /datasets` (or `PUT /datasets/{id}`) with title, description, publisher, licence, keywords, themes, languages, spatial coverage, update frequency, an optional access note, the API's `endpoint_url` and its `openapi_url`; a file in `seed/registrations/` does the same at start-up. The catalog rejects a registration whose OpenAPI document cannot be fetched or is not OpenAPI 3.x. The builder turns registrations into DCAT, where the link the agent follows is `dcat:endpointDescription` on the `dcat:DataService`, pointing at the adapter's OpenAPI document. The example below is illustrative.

```turtle
<https://demo.local/datasets/access-i> a dcat:Dataset ;
    dct:title "Access-i accessibility sheets"@en ;
    dct:spatial [ a dct:Location ; rdfs:label "Wallonia and Brussels" ] ;
    dct:language <http://publications.europa.eu/resource/authority/language/FRA> ;
    dcat:theme <https://demo.local/themes/accessibility> ;
    dcat:distribution [ a dcat:Distribution ;
        dcat:accessService <https://demo.local/services/access-i> ] .

<https://demo.local/services/access-i> a dcat:DataService ;
    dcat:endpointURL <http://localhost:8080/sources/access-i/> ;
    dcat:endpointDescription <http://localhost:8080/sources/access-i/openapi.json> ;
    dcat:servesDataset <https://demo.local/datasets/access-i> .
```

The catalog keeps RDF as the source of truth (Turtle and JSON-LD at `/catalog`, SPARQL for power users) and also offers a flat JSON search so that the agent does not have to parse RDF. Each search hit returns `id`, `title`, `description`, `publisher`, `themes`, `spatial`, `languages`, `licence`, `endpoint_url`, `openapi_url` and `access_note`. Registration records are stored as JSON on a volume and the DCAT graph is derived from them with rdflib (see Decisions); Oxigraph or Fuseki remain the upgrade path, and CKAN with its DCAT extension is the heavier alternative if you want a ready-made portal UI.

### Vocabulary hub (tasks 2.12 to 2.17)

The hub is retrieval only: it stores domain knowledge and returns cited passages, and the user agent does the reasoning. That keeps the container free of any language model API.

- **Ingest:** PDFs (text per page, with page numbers), web pages and HTML (main content only), and office and text formats (DOCX, PPTX, XLSX, CSV, Markdown, plain text, through markitdown). Upload a file with `POST /documents` or fetch a URL with `POST /documents/url`. Every document carries title, URL, language, tags and a licence or permission note; identical content is stored once.
- **Chunk:** up to 250 words per chunk, split on headings, with the heading path stored as metadata.
- **Embed and store:** a multilingual open embedding model running locally (fastembed, in the hub container) and Qdrant with a persistent volume. Default model `paraphrase-multilingual-MiniLM-L12-v2`; `multilingual-e5-large` is the more accurate option.
- **Search:** `GET /search?q=&k=` with filters on language and tag; hybrid keyword plus vector search and re-ranking are later upgrades. Each hit returns text, score, document title, URL and page.
- **Stretch (2.17):** a SKOS file for term equivalence across Dutch, French and English and across source vocabularies, because matching what a user asks for to each source's own criteria is the main reason this hub exists.

**Initial seed set** (all public; add your own PDFs next to these):

- Acceslibre [field documentation](https://acceslibre.beta.gouv.fr/contrib/documentation/) and [data schema](https://schema.data.gouv.fr/MTES-MCT/acceslibre-schema/latest.html)
- [IedereenOveral for governments and professionals](https://www.vlaanderen.be/inter/overheden-en-professionelen/iedereenoveral), explaining its categories and location types
- [Access-i: what it is and how places are audited](https://access-i.be/en/?p=1453)
- The Picto Access pictogram scheme, for example the [Limoges press release](https://limoges.fr/sites/default/files/espace_presse/2025/CP%20Picto%20Access%2003%202025-1.pdf)

### MCP connector (tasks 3.1 to 3.3)

The connector is the single door between the user agent and the data space. It is read-only and exposes five tools, and each tool description states when to use it.

| Tool | Input | Returns | Use it to |
| --- | --- | --- | --- |
| `vochub_search` | `question`, optional `k`, `language` | Cited chunks | Learn the terms and criteria before looking for data |
| `catalog_search` | `query`, optional `theme`, `spatial`, `language` | Dataset summaries with `openapi_url` | Find sources that can answer the question |
| `catalog_get_dataset` | `id` | Full dataset record | Check licence, coverage and update frequency |
| `get_openapi` | `dataset_id` | Condensed list of operations, parameters and descriptions (full spec on request) | Learn how to query one source |
| `call_source_operation` | `dataset_id`, `operation_id`, `params` | Source JSON plus provenance | Run the lookup |

Guardrails sit in this one place: only the registered endpoint host is called, only read operations, parameters validated against the OpenAPI (unknown, missing and out-of-enum values are refused), a call budget per question (not built yet), timeouts, and response truncation with a continuation hint. A geocoding tool for place names is an optional addition (open question below).

**Source credentials.** The connector holds API keys for sources that need them; the agent never sees them. `config/credentials.yaml` maps a dataset id to `api_key: ${ENV_VAR}`, and the value lives in `.env`. The connector reads where to put the key from the source's OpenAPI `securitySchemes` (an `apiKey` in a header or query, or an HTTP bearer token), and an entry may override this with `in`, `name` and `prefix` (for example `Authorization: Api-Key <key>`). `catalog_search` and `get_openapi` report `credentials_configured`, so the agent can tell the user when a source needs a key that is missing. Keys are masked in all tool output.

### Skill document (task 3.4)

The skill is a `SKILL.md` (with `name` and `description` front matter) plus an `AGENTS.md` pointer, so that Claude Code, Claude Desktop or any MCP-capable agent can follow the same procedure. It tells the agent to:

1. Restate the question as place type, location, accessibility need and answer language.
2. Call `vochub_search` first and note the terminology, criteria and how each source rates them.
3. Call `catalog_search` with those terms, then shortlist by spatial coverage, language and theme; say which sources were left out and why.
4. Call `get_openapi` for each shortlisted source and choose operations from their descriptions; never guess parameters.
5. Call `call_source_operation`, starting broad and narrowing, staying within the call budget.
6. If no source in the data space covers the question, or the results are insufficient (the needed facts are missing, outdated, or only a summary label), search external sources with the agent's own web tools. Start from the websites, labels and verification pages named in the step 2 passages, and interpret external findings with the same domain knowledge (what a label certifies, who assessed it, what it leaves out). Missing data means unknown, not absent.
7. Reconcile results: map each source's criteria to the user's need using step 2, and treat places with similar names and close coordinates as one place.
8. Answer in the user's language: the result first, then per place what each source says, with source name, URL, snapshot or retrieval date and licence. Mark which facts come from the data space and which from external sources. Flag conflicts, gaps, crowd-sourced or old data, and sources that do not cover the area. Never present an accessibility claim as certain beyond what the source states.

## Demo scenarios and acceptance tests

Nine golden questions cover every source, three languages, a cross-source comparison, and two cases where the right behaviour is to not query or not answer. Expected facts are checked against pinned snapshot fixtures, so scoring is repeatable even when live sources change.

| # | Question (language) | Expected behaviour |
| --- | --- | --- |
| 1 | Is there a restaurant in Ghent with a wheelchair-accessible toilet? (EN) | Queries IedereenOveral only; lists places with toilet details and provenance |
| 2 | Welke cafés in Leuven zijn rolstoeltoegankelijk? (NL) | Vochub maps the Dutch term to the source's criteria; queries IedereenOveral |
| 3 | Quels musées à Lille sont accessibles en fauteuil roulant ? (FR) | Queries Acceslibre (and Picto Access if it covers Lille); answers in French |
| 4 | Which tourist sites in Namur suit blind visitors? (EN) | Queries Access-i; reports the rating for visual impairment, not a general score |
| 5 | How do Acceslibre and Picto Access describe the same municipal building in Limoges? (EN) | Queries both; matches the place across sources; flags differences in scale and wording |
| 6 | Where can I find accessible hotels in Brussels? (EN) | Uses Access-i; says which other sources do not cover Brussels |
| 7 | Is there an accessible restaurant in Tokyo? (EN) | Finds no covering source in the data space and says so; may search externally, labelled as such; invents nothing |
| 8 | What does a green A pictogram mean in Picto Access? (EN) | Answers from the vochub with a citation; makes no source call |
| 9 | Which sources in this data space cover Belgium? (EN) | Uses the catalog only, no source calls |

**Scoring per question** (pass or fail on each):

- the right sources were chosen and the wrong ones were not called
- every call used parameters that exist in the OpenAPI
- facts in the answer match the fixture
- each claim carries source, URL, date and licence
- gaps and conflicts are stated
- the call budget was respected

**Test layers.** Unit and contract tests run inside each component on `make check`; `make e2e` starts the stack and asserts the catalog, OpenAPI validity and adapter responses; `make eval` runs the nine questions through the agent and writes traces and a score sheet.

**Demo walk-through (about ten minutes).** Show the catalog and one OpenAPI; ingest a new PDF into the hub; ask question 2 and show the trace; add the fifth source with the recipe and ask a question that only it can answer.

## Risks, open questions and later extensions

The biggest risk is access rights: three of the four sources show no public API, so reuse terms decide what the adapters may do, and that is settled at Gate G1.

| Risk | Mitigation |
| --- | --- |
| Reuse terms unclear for Access-i, IedereenOveral and Picto Access | Ask the operators in Phase 1; crawl politely (robots.txt, rate limits, identifying user agent); swap in a fallback source if refused |
| Snapshots of non-open data end up in a public repo | Keep snapshots out of git and generate them locally with `make refresh`; commit only tiny fixtures that the terms allow |
| A website changes and a crawler breaks | Fixture-based contract tests plus a scheduled canary job that flags structure changes |
| Acceslibre files are very large | Prefer the live API; load the CSV for one region only, streamed |
| The agent picks the wrong source or invents parameters | OpenAPI quality gate (2.1), connector guardrails (3.3), golden questions (4.3) |
| Weak Dutch to French retrieval | Multilingual embeddings tested in 2.14; SKOS term mappings (2.17) |
| Demo depends on an external model API | Local model profile for the CLI agent; recorded traces as a fallback |
| Heavy stack on a laptop (embedding model, vector store, triple store, adapters) | Compose profiles; CPU-friendly default model; measure and document real memory use in Phase 4 |

**Open questions for you**

- [ ] Who at Inter, Access-i and Picto Access can KNoWS approach, and is there an existing relationship?
- [ ] Is the repo public from day one, and may snapshots be redistributed?
- [ ] Plain DCAT-AP, or the Flemish DCAT-AP profile, as the target for catalog shapes?
- [ ] Which agent runtime must the demo support: Claude Desktop and Claude Code only, a headless CLI with an API key, or a local model as well?
- [ ] Geocoding for place names: allow a public geocoder (with its usage limits), run a local one, or require coordinates?
- [ ] Which languages must the domain documents cover: Dutch, French, English, all three?
- [ ] Is a post-demo hosting target expected?

**Later extensions** (kept out of v1 on purpose): OAuth2/OIDC with a Keycloak container; usage policies in ODRL; a Dataspace Protocol catalog and an EDC-style connector in front of the adapters; a federated catalog across several brokers; publishing sources as linked data; and more sources such as OpenStreetMap wheelchair tags or the Toerisme Vlaanderen datasets.

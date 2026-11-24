# Accessibility data space demonstrator: guide for coding agents

A small, runnable data space for accessibility information. Publishers register their APIs in a DCAT catalog, a vocabulary hub holds domain knowledge, and an MCP connector lets a user agent find a source, read its OpenAPI and query it. Research demonstrator of the KNoWS team (Ghent University). No authentication between components in v1.

This file is the working version of `Accessibility Data Space Demonstrator — Project Plan & Todo List.md` (Nov 12, 2026), updated with the work done since (status as of Nov 23, 2026). The plan keeps the full rationale, the source landscape and the risk table. Where the two disagree, this file wins.

## Rules

- **Public research and open-source only** (organization rule). Never paste non-public material into an agent session; commit only public data and code.
- **No secrets in the repo or in agent context.** API keys go in `dataspace/.env`; `dataspace/config/credentials.yaml` holds only `${VAR}` references. Do not read `.env` files; the user's permission settings block it.
- **Non-public data stays out of git.** The PictoAccess export (`sources/pictoaccess/pictoaccess_dump/`) came from a token-protected API and is git-ignored. Tests use fictional fixtures, not records copied from a dump.
- **The data space knows no sources.** Nothing source-specific goes in `dataspace/`. Proxies, registrations, source notes and seed content live in `sources/` and reach the data space only through its HTTP APIs ([ADR 0002](dataspace/docs/adr/0002-sources-outside-the-data-space.md)).
- **One task, one component.** Changing a component's contract (API, registration fields, MCP tools) needs a short ADR in `dataspace/docs/adr/`.
- **Tests run offline**, on fixtures. Never hit live public sites from unit tests. Crawlers and fetchers honour robots.txt and rate limits and send the user agent `accessibility-dataspace-demo/0.1 (open research demonstrator)`.
- **Unknown licences are written down, not guessed.** If reuse terms are unconfirmed, a registration leaves `licence` empty and explains the situation in `licence_note`.
- **Keep the inventories current.** [`sources/source-inventory.md`](sources/source-inventory.md) and [`sources/domain-knowledge-inventory.md`](sources/domain-knowledge-inventory.md) are the source of truth for the following:
  - which sources and documents are added, candidates, blocked or skipped, and why;
  - their licences and terms of use;
  - where the literature study is wrong or out of date.

  Read them before you pick or add a source or document. When you add, block or skip one, update its row and the "Last checked" date in the same change.
- **Vocabulary-hub documents may disregard their site's licence, visibly.** The hub is used only locally and in closed demos.
  - A document whose terms restrict reproduction gets the tag `licence-restricted` in `sources/domain-knowledge.yaml` and is marked **Restricted** in the inventory.
  - A public deployment leaves all tagged documents out; set-up B counts, because `vochub_search` makes every passage readable. `make -C sources public` does this (and leaves out data sources marked `"visibility": "private"`: `toevla`, `toerismevlaanderen`); `make -C sources full` loads everything.
  - This exception covers hub documents only, never data sources.
- **Done means green.** A task is done when `make check` passes in `dataspace/`, `make test` passes in `sources/`, and, for changes that cross components, `make e2e` passes in `sources/`.

## Layout

One git repository at this root (it may be split into `dataspace/` and `sources/` later; keep the two independent). `.env` files and `sources/pictoaccess/pictoaccess_dump/` are git-ignored.

```text
dataspace/                  generic data space (CLAUDE.md -> AGENTS.md there)
  catalog/                  registration API, search, DCAT (rdflib), SPARQL, country sub-catalogs   :8001
  vochub/                   document ingestion, chunking, multilingual embeddings (fastembed), Qdrant :8002
  connector/                MCP server, five read-only tools; openapi_calls.py validates and adds keys :8800/mcp
  config/credentials.yaml   connector's API keys per dataset id (env var references only)
  docs/adr/                 decision records: 0001 sub-catalogs, 0002 sources outside, 0003 mobility catalogs and source DCAT,
                            0004 schemas in DCAT, 0005 documents as datasets, 0006 assessment, 0007 vocabulary hub,
                            0008 evidence per record
sources/                    everything source-specific
  docker-compose.yml        proxies; join the external network accessibility-dataspace_default
  seed.py                   `register`: PUT */registration.json to the catalog; `knowledge`: ingest domain-knowledge.yaml and PUT permanent-context.md
  permanent-context.md      the vochub's permanent context: returned with every vochub_search (compare sources, ask again, web search, answer layout); keep it short
  domain-knowledge.yaml     documents for the vocabulary hub (`url:` or `file:`, each with a `summary`), incl. literatuurstudie.pdf
  source-inventory.md       every source from the literature study: status, access, proxy, licence, study errors
  domain-knowledge-inventory.md  the same for vocabulary-hub documents, with each site's reuse terms
  tests/e2e.py              end-to-end test of data space + sources
  iedereenoveral/           live proxy in front of IedereenOveral's Xano API                         :8102
  pictoaccess/              snapshot API over the local PictoAccess export (+ pictoaccess_export.py)  :8103
  acceslibre/               registration only: Acceslibre's own API is used directly
  be-transit/               Belgian stops: daily snapshot of STIB, TEC and De Lijn GTFS + iRail station facilities :8104
  toerismevlaanderen/       Toerisme Vlaanderen linked open data: daily export, queried locally (pyoxigraph), A-labels :8106
  documents/                web pages and PDFs as datasets: one documents/<id>/registration.json each, outline/search/section :8107
  osm/                      OpenStreetMap live (OnWheels features + native accessibility tags), polite Overpass use :8105
                            (parked: registrations renamed registration.parked.json, see "Catalog and sources")
  toevla/                   registration only: the archived ToeVla API, hosted by the project owner (bearer token)
  opendatasoft/             11 open datasets forwarded live from Opendatasoft portals; registrations generated
                            from the portals' metadata by make_registrations.py (datasets.yaml lists them)
viewer/                     read-only web interface over catalog and vochub, for people (:8090, published under /viewer/)
user-profiles.md            analysis of personal needs and preferences (not built)
literatuurstudie.pdf        the project's literature study (Dutch); loaded into the vochub by `make knowledge`
```

## Commands

```bash
make start-public | start-full | public | full | restart | stop | update | reset[-knowledge|-catalog] | status
                            # root Makefile: everyday commands for everything; `make help` explains them
make -C dataspace up        # data space (catalog, vochub, connector); starts empty
make -C sources up          # source proxies (needs the data space network)
make -C sources full        # register all sources and load all documents (local, closed demos)
make -C sources public      # the same without private sources and licence-restricted documents (published server)
make -C sources register    # only: register all sources in the catalog over HTTP
make -C sources knowledge   # only: ingest domain knowledge and the permanent context (needs internet)
make -C dataspace check     # offline tests of catalog, connector, vochub + compose build
make -C dataspace calls     # summary of the connector's tool calls (needs CALL_LOG=1 in dataspace/.env)
make -C sources test        # offline tests of the proxies
make -C sources e2e         # end to end (live IedereenOveral call, needs internet)
```

Agents connect to `http://localhost:8800/mcp` only. The proxies and the catalog are REST APIs, not MCP servers.

### Running components separately

`make up-catalog`, `make up-vochub` and `make up-connector` in `dataspace/` start one component each. A connector elsewhere is pointed at its catalog and vochub with `CATALOG_URL` and `VOCHUB_URL`, and at the source proxies with `SOURCE_URL_MAP` (registered proxy URLs are Docker names that only resolve on the server). The usual split: catalog, vochub and proxies on a server, connector (with the API keys) locally over an SSH tunnel; see "Running components separately" in `dataspace/README.md`.

### Deployment on a server

The repository `README.md` compares the two set-ups (A: catalog, vochub and proxies on the server, connector local over SSH; B: everything on the server, connector open over HTTPS, online only during presentations) and gives the clone + `rsync` steps. Details in "Running on a remote server" in `dataspace/README.md`. In short:
- **Getting it there:** `git clone`, then `rsync` the git-ignored `sources/pictoaccess/pictoaccess_dump/places/` (33 MB; the images are not used). Update with `git pull`, `make -C dataspace up`, `make -C sources up public` (set-up B) or `up full`.
- **Restarts:** every service has `restart: unless-stopped`; state lives on volumes (`catalog-data`, `vochub-vectors`, `be-transit-cache`).
- **Ports:** all published ports bind to `127.0.0.1` by default (`CONNECTOR_BIND`, `CATALOG_BIND`, `VOCHUB_BIND` in `dataspace/.env`; `SOURCES_BIND` in `sources/.env`). Only port 8800 (MCP) needs to reach agents; 8001 (catalog) only for publishing DCAT, and then read-only. 8002 and 8102 to 8107 stay private.
- **Base URL:** `CATALOG_BASE_URL` in `dataspace/.env` is the public base of every URI in the DCAT export; each URI resolves (`/catalog`, `/catalogs/{id}`, `/datasets/{id}`, `/services/{id}`, `/themes/{slug}`).
- **Security:** no component of the data space authenticates, on purpose (user decision 2026-11-19): the server is online only during public presentations. No secret paths, bearer tokens or basic auth on the data space's endpoints (a source's own API may still need a key or token, which the connector adds, e.g. ToeVla). Production needs OAuth, the only option ChatGPT accepts (MCP SDK hook `auth_server_provider` / `token_verifier`). Put HTTPS in front with a reverse proxy (Caddy and nginx configurations in "Reverse proxy: Caddy or nginx" in `dataspace/README.md`), or the connector exposes your API keys' quota and the PictoAccess snapshot to anyone.
- **Registrations** keep Docker-internal proxy URLs (`http://src-…:8000/`); that is correct on a server too. The viewer and the DCAT export show them, and they do not open from a browser, by design: the connector is the only way in, so every call is validated and gets its key in one place.
- **A source on the same server** under a public name (ToeVla) is unreachable from the containers without hairpin NAT; registering fails with an empty `422`. Fix with a server-only `docker-compose.override.yml` (`extra_hosts`), described in "Sources on the same server" in `dataspace/README.md`. `SOURCE_URL_MAP` does not help: the catalog does not read it.
- **Viewer:** published under `/viewer/` (relative paths; the reverse proxy strips the prefix).
- **Vochub after an update:** a change to chunking or search needs `make -C sources knowledge` again (collection `passages`, [ADR 0007](dataspace/docs/adr/0007-vocabulary-hub-context-summaries-hybrid-search.md)).
- **ChatGPT and other web-hosted agents** reach the connector at `https://<host>/mcp` through Caddy or nginx (only ports 443 and 80 open) without authentication. Steps in "Connecting ChatGPT or another web-hosted agent" in `dataspace/README.md`.

## Current state

### Catalog and sources

| Dataset id | Sub-catalog | Served by | Mode | Licence |
| --- | --- | --- | --- | --- |
| `iedereenoveral-food-and-drink`, `-toilets`, `-museums`, `-parking` | belgium | `src-iedereenoveral` (one sub-API per kind) | live proxy (compact records, town names resolved to Xano ids, JSON-array filters) | unconfirmed with Inter |
| `pictoaccess` | france | `src-pictoaccess` | snapshot of 1,720 places, loaded in memory at start-up; full export provided by PictoAccess, used until their API is back | demonstrator use agreed; wider reuse unconfirmed (open subset on data.gouv.fr is ODbL) |
| `acceslibre` | france | Acceslibre API directly | live; `Authorization: Api-Key` from `ACCESLIBRE_API_KEY` | open data, licence URL not yet confirmed |
| `tourisme-handicap` | france | data.economie.gouv.fr Explore API directly | live; 3,682 labelled establishments | none stated by the publisher |
| `liege-pmr-toilets` | belgium | ODWB Explore API directly | live | CC BY |
| `sncf-stations`, `sncf-lift-status`, `sncf-station-equipment`, `sncf-assistance` | france-mobility | SNCF Explore API directly | live; lift status is real time | ODbL (SNCF licence page) |
| `stib-stops`, `tec-stops`, `delijn-stops` | belgium-mobility | `src-be-transit` | daily snapshot of the operators' static GTFS: wheelchair value per stop | CC BY 4.0, attribution "Source: <operator> – Open Data – <date>" |
| `irail-stations` | belgium-mobility | `src-be-transit` | daily snapshot of iRail's station facilities (ramp, lift, induction loop, platform height) | repository CC0, but lift/escalator data from OSM (ODbL); some fields date from June 2023 |
| `zon-zee-zorgeloos` | belgium | `src-documents` | Inter's web page on accessible beaches per coastal town, served as sections (outline, word search, full section) that keep the town as heading; refetched daily, with document dates | vlaanderen.be disclaimer: free reuse |
| `toerismevlaanderen` | belgium | `src-toerismevlaanderen` | 1,039 tourist places with accessibility information from Toerisme Vlaanderen's daily export (not its SPARQL endpoint, which times out on big queries since Nov 2026), loaded daily and kept on a volume; A / A+ labels, groups catered for, texts per topic (nl, en); topics often misfiled in the source, the API says so | no licence published; Toerisme Vlaanderen asked for the integration; licence being discussed |
| `toevla` | belgium | external: https://toevla-api.rubendedecker.be (registration only, `sources/toevla/`) | archived ToeVla database, ~7,600 places screened on site, mostly 2010-2015; bearer token (`TOEVLA_API_TOKEN`), photos as open URLs; detailed screening per section via `getInrichtingAccessibility` (outline, then `?section=`), for about half of the dossiers; personal data and unrelated tables removed 2026-11-23 (no phone or email) | no licence; Toerisme Vlaanderen asked for the integration |
| `onwheels`, `osm-accessibility` | root catalog (no sub-catalog; Belgium and Hauts-de-France) | `src-osm` | **not registered** (removed 2026-11-19; registrations parked as `registration.parked.json`, code and tests kept): the public Overpass server was full for a whole night of polite retries, so searches returned 503. Rename the files back and `make register` once a private Overpass instance (`OVERPASS_URL`) or access to the OnWheels API is arranged | ODbL, "© OpenStreetMap contributors"; not republished |
| `liege-`, `brabant-wallon-`, `marche-en-famenne-`, `la-louviere-`, `databusters-pmr-parking` | belgium-mobility | ODWB Explore API directly | live; disabled parking spaces | CC BY, except Marche (publisher metadata conflicts) and La Louvière (not specified) |

The catalog has four DCAT sub-catalogs, linked from the root with `dcat:catalog`: `belgium`, `france`, and, for transport and parking, `belgium-mobility` and `france-mobility` ([ADR 0001](dataspace/docs/adr/0001-country-sub-catalogs.md), [ADR 0003](dataspace/docs/adr/0003-mobility-catalogs-source-dcat-optional-keys.md)). Datasets forwarded from open data portals carry the publisher's original DCAT, copied in through `source_dcat_url` and linked with `dct:source`. You can list them with `GET /catalogs` and filter search with `GET /datasets?catalog=`. Adding a country means adding one entry to `CATALOGS` in `dataspace/catalog/dcat.py`.

### Vocabulary hub and catalog search

- **Hub contents** (Nov 23, 2026): 35 documents, about 2,100 passages, listed in `sources/domain-knowledge.yaml` and `sources/domain-knowledge-inventory.md`: labels and certification schemes, data standards (Acceslibre, A11yJSON, OSM, GTFS, NeTEx incl. the French accessibility profile v2.4), services, and the literature study (393 passages, headings from its table of contents). Every document has a `summary`, indexed as its own passage.
- **Search** combines meaning (multilingual MiniLM, 128 tokens, so chunks of at most 60 words with title and heading in front) and keywords (BM25 without stemming), fused with reciprocal rank fusion, at most 2 passages per document ([ADR 0007](dataspace/docs/adr/0007-vocabulary-hub-context-summaries-hybrid-search.md)). Before, "label" returned 18 passages of one page and a 700-passage report crowded out the rest. Still weak: abstract questions such as "how do certification methods work?" miss the literature study's section 3.2; see open work 12.
- **Permanent context:** `sources/permanent-context.md`, returned with every `vochub_search` (trust order by `assessment`, multilingual catalog search, regions left to the agent, ask the hub again, web search, answer layout). Shown in the viewer.
- **Decided: dataset metadata stays out of the hub.** Agents find datasets with `catalog_search`; ingesting registrations into the hub would duplicate the catalog and need re-ingesting after every registration. Left out for now.
- **Catalog search** is a linear scan over the registrations: one point per query word (longer than two letters) found in title, description, keywords, themes, spatial or publisher; no stemming or accent folding. Hence keywords in three languages, and the permanent context's rule to search in Dutch, French and English and to filter on the country at most. Which dataset covers which town is left to the agent, which knows that Flanders covers Gent.

### Facts learned about the sources

- **PictoAccess** has no letter grades (A, B, C) in its export, although the plan and press material use them. Each place instead has a numeric level per disability type: `2` autonomous, `1` with_help, `-1` autonomous_or_with_help, `0` inaccessible, `-2` unknown. These codes were verified against `readable_handicaps` for every place. The proxy maps the 8 types to English parameter names (`mobility`, `walking_difficulty`, `cognitive`, `blind`, `low_vision`, `deaf`, `hard_of_hearing`, `temporary_mobility`).
- **PictoAccess groups places** through `brands`: a university, a campus, a transport network. About 44% of places have one. `pictoaccess_related_places` returns same-group places and places nearby. Per-campus groups often hold a single building, so the university-level group is usually the useful one.
- **PictoAccess country is free text.** 627 places have no country; the proxy returns `null` rather than assuming France.
- **PictoAccess coverage of the golden-question cities:** Lille has 65 places and Limoges 12. Most places are in Normandy and La Rochelle.
- **Acceslibre** needs an API key for reads (403 without one). Its OpenAPI 3.0.2 declares no `securitySchemes`, so the key location is set in `credentials.yaml`, and `get_openapi` shows `requires_api_key: false` even though the key is sent.
- **Acceslibre `zone`** is declared as an array, but the API expects one comma-separated value (`zone=lon1,lat1,lon2,lat2`). Pass it as a string; the connector sends lists as repeated parameters.
- **Acceslibre `commune`** matches by name, so `commune=Limoges` also returns Limoges-Fourches (Seine-et-Marne). Use `code_postal` or `code_insee` (Limoges: 87085) for an exact town.
- **Acceslibre has duplicates**: the same place can appear as several records, e.g. two for the Musée de la Résistance in Limoges. Merge records with the same address or `ban_id`. Without `clean=true`, unfilled fields come back as `null`, which means unknown.
- **Access-i is not connected** (checked Nov 16, 2026). It has no public API or OpenAPI: the WordPress REST API only holds news and pages, and the place sheets come from a private backend and are rendered as HTML at `access-i.be/<lang>/je-recherche/<slug>`. Its licence forbids reuse without approval, so no adapter, crawler or snapshot may be built until Access-i approves. Approval has been requested by e-mail. Each sheet gives a verdict for 7 disability groups (wheelchair users, walking difficulties, blind, visually impaired, deaf, hard of hearing, comprehension difficulties), which is what an adapter would expose.
- **Opendatasoft portals** (SNCF, ODWB, data.economie.gouv.fr) all serve the same Explore API with an OpenAPI at `/api/explore/v2.1/swagger.json` and a per-dataset DCAT export (`/catalog/exports/dcat?where=dataset_id="…"`). Their OpenAPI declares an API key on every operation, but reads work without one; the connector therefore calls even when no key is configured (ADR 0003).
- **SNCF lift status** has no station names: `gareid` is the `id` in `sncf-stations` (gares-de-voyageurs). The station reference id named in SNCF's own description (`referentiel-gares-voyageurs`) no longer exists.
- **Publisher metadata is not always clean**: Liège's DCAT export uses "Ville de Liège" as an IRI (those triples are skipped when copying), and Marche-en-Famenne names CC0 but links to CC BY (recorded as a licence note).
- **Belgian public transport**: the static GTFS of STIB, TEC, De Lijn and SNCB downloads from data.belgianmobility.io without a key (CC BY 4.0, operator is the licensor). STIB and TEC fill `wheelchair_boarding` well; De Lijn only marks accessible stops (`0` = no information); SNCB fills none, hence iRail's `facilities.csv` for stations. The feeds are 12 to 184 MB zips and the server ignores range requests, so they are cached, not forwarded.
- **OpenStreetMap's public Overpass server is often full** (checked Nov 18, 2026):
  - overpass-api.de answered 502 "at capacity" or took 28 to 41 s even for a trivial query;
  - private.coffee and kumi.systems were also full, and openstreetmap.fr and mail.ru are whitelist-only;
  - the OSM API (`api.openstreetmap.org`) answers single features in well under a second.

  Hence the `osm/` adapter's politeness guards, and the advice to set `OVERPASS_URL` to a private instance if searches must be reliable. Overpass metadata includes contributor user names; never pass them on.
- **Labels and verification per source** (checked Nov 20, 2026; recorded as `assessment` in each registration):
  - IedereenOveral: `confirmed_by_inter` (Inter advisor checked it; the "Inter" icon on the site): 26 of 51 places in Gent. Only in place details, not in search hits; search with `confirmed_by_inter=true` to get the set. Other places are added by visitors or venues.
  - Toerisme Vlaanderen: `a_label` A/A+ on 395 places.
  - Tourisme & Handicap: every record is labelled; `droit_d_utilisation_du_label` 'actif' = valid; flags per disability family.
  - Acceslibre: `user_type` public / gestionnaire / system; `accessibilite.commentaire.labels` are claimed, not verified.
  - PictoAccess: self-diagnosis tool, no label field; assessment date `accessibility.updated_at` (some from 2017).
  - Databusters PMR parking is crowd-sourced (2022 challenge). Transit, SNCF and municipal datasets are operator or municipal data, no labels.
- **IedereenOveral's raw API** is unsuitable for agents (130 KB details, numeric ids, silently dropped array values); see `sources/iedereenoveral/README.md`.

### Status against the plan

Done:
- Catalog: registration, search, DCAT/SPARQL, country sub-catalogs (2.8 to 2.10, without SHACL).
- Vocabulary hub: ingestion, embeddings, search and seed (2.12 to 2.16).
- Connector: five tools, OpenAPI validation, read-only, host check, timeouts, truncation (3.1, 3.2, most of 3.3).
- IedereenOveral proxy (1.3, 2.6).
- PictoAccess proxy over a token-based export rather than a crawler (1.4, 2.7).
- Acceslibre connected directly through its own API, with no CSV fallback (1.1, 2.4).
- Sources split out of the data space, with seeding over HTTP.
- Source assessment (`certified`, `official`, `self_declared`, `crowd_sourced`) in every registration ([ADR 0006](dataspace/docs/adr/0006-assessment-methods.md)); permanent context; hybrid hub search with summaries ([ADR 0007](dataspace/docs/adr/0007-vocabulary-hub-context-summaries-hybrid-search.md)).
- IedereenOveral split into four datasets (food and drink, toilets incl. Changing Places, museums, parking), as on its website; the combined dataset was removed from the catalog.
- ToeVla archive connected (2026-11-23), with personal data removed from its database first.
- Evidence per record ([ADR 0008](dataspace/docs/adr/0008-evidence-per-record.md)): `records` blocks in the registrations of Acceslibre, IedereenOveral (4), PictoAccess, Tourisme & Handicap, Toerisme Vlaanderen and ToeVla; the connector returns a link, basis, by whom and date per record. IedereenOveral search hits now carry `confirmed_by_inter`.
- Connector call log (`CALL_LOG=1`, `make -C dataspace calls`).
- Lean answers ([ADR 0009](dataspace/docs/adr/0009-lean-answers.md)): source answers without empty fields and cut by whole records, compact JSON, short catalog hits, `operations` in the Opendatasoft registrations, cached OpenAPI documents; a replayed Lille question went from about 270 KB to 142 KB.
- Viewer, published under `/viewer/`.
- `make e2e`.
- MCP client snippets for Claude Code and VS Code in the data space README (part of 3.6).

Changed from the plan:
- **No `source.yaml`.** A source is one `registration.json` PUT to the catalog.
- **No catalog seeding at start-up.** The data space starts empty.
- **The gateway may be unnecessary.** Proxies reach the data space over the shared Docker network, so a gateway is only needed for public URLs.
- **Access-i is on hold.** There is no public API, and reuse needs Access-i's approval, which has been requested.
- **No shared place model (1.5, 2.1).** Each proxy has its own response shape, and agents adapt by reading each OpenAPI. Considered and left out in [ADR 0009](dataspace/docs/adr/0009-lean-answers.md); the `records` block is the small shared part.

## Open work

Pick one task, stay in one component, and meet its acceptance criteria.

| # | Task | Component | Acceptance |
| --- | --- | --- | --- |
| 1 | **Blocked: Access-i adapter** (plan 1.2, 2.5). Do not start until Access-i has approved reuse in writing; the spike is done (see "Facts learned"). Then use their API if they offer one, otherwise a polite crawl of the public sheets into a git-ignored snapshot | `sources/access-i/` | `registration.json` in the `belgium` catalog; search returns the verdict per disability group; offline tests on fictional fixtures |
| 2 | Confirm reuse terms: Access-i (approval requested by e-mail), Inter (IedereenOveral), PictoAccess, the Acceslibre licence URL | human task; then registrations | `licence` set or `licence_note` updated in each `registration.json` |
| 3 | Call budget per question (3.3) | `dataspace/connector/` | a test shows calls beyond the budget are refused with a readable error |
| 4 | Golden-question harness (0.5, 4.3) | `sources/tests/` or a new `agent/` | runs the golden questions below on pinned fixtures, stores traces and a score sheet |
| 5 | Skill document (3.4): workflow steps 1 to 8 in the plan, "Skill document" | new `agent/skills/accessibility-dataspace/SKILL.md` | a fresh agent session follows it without extra instructions |
| 6 | Demo CLI agent (3.5) | new `agent/` | `docker compose run agent "<question>"` prints an answer with sources |
| 7 | SHACL validation against DCAT-AP (2.11) | `dataspace/catalog/` | `make check` fails for a dataset without licence information or distribution |
| 8 | ~~Prove the recipe with a fifth source (4.4)~~ done: `toerismevlaanderen` (2026-11-19) | `sources/` | added by following `sources/README.md` alone, with no change in `dataspace/` |
| 9 | Fix the Acceslibre `zone` mismatch: comma-join array parameters whose OpenAPI `style`/`explode` asks for it | `dataspace/connector/openapi_calls.py` | unit test: `zone=[a,b,c,d]` becomes `zone=a,b,c,d` |
| 10 | CI running `make check` and `make -C sources test` (0.1) | repo root | green on push |
| 11 | More sources from the literature study: take the next one from "Candidates, in suggested order" in [`sources/source-inventory.md`](sources/source-inventory.md) (DATAtourisme, Accessibility.Cloud and so on) | `sources/` | one registration each, tested through the connector; its row in the inventory updated |
| 12 | Better retrieval in the vocabulary hub, once a demo needs it: a golden question set for search (expected document in the top 5), then a reranker on the top 30 to 50 hits (e.g. `bge-reranker-v2-m3`) and a stronger multilingual model (e.g. `bge-m3`, longer chunks) | `dataspace/vochub/` | the question set scores higher than with the current hybrid search |
| 13 | Fewer turns and tokens, after measuring a real client with `make calls` ([ADR 0009](dataspace/docs/adr/0009-lean-answers.md), "Not done"): the permanent context in the MCP server instructions (check first that the client shows them to the model), and a batch tool for clients without parallel tool calls | `dataspace/connector/` | a logged session of a golden question needs fewer KB or turns than before |

User profiles (personal needs and preferences) are analysed in [`user-profiles.md`](user-profiles.md): not implemented; read it before adding anything profile-related to the connector or skill.

Open questions for the project lead (from the plan, still open): contacts at Inter, Access-i and PictoAccess; whether snapshots may be redistributed; plain DCAT-AP or the Flemish profile; supported agent runtimes; geocoding of place names; post-demo hosting.

## Golden questions

| # | Question | Expected behaviour with the current sources |
| --- | --- | --- |
| 1 | Is there a restaurant in Ghent with a wheelchair-accessible toilet? (EN) | `iedereenoveral-food-and-drink`, toilet details with provenance, Inter-confirmed places first; `toevla` may add older screenings, which the answer dates |
| 2 | Welke cafés in Leuven zijn rolstoeltoegankelijk? (NL) | vochub maps the term; IedereenOveral |
| 3 | Quels musées à Lille sont accessibles en fauteuil roulant ? (FR) | Acceslibre (`commune=Lille&activite=musee`: 8 museums, e.g. Maison natale Charles de Gaulle with a separate accessible entrance); PictoAccess has 65 places in Lille but no museum, which the answer says; answer in French |
| 4 | Which tourist sites in Namur suit blind visitors? (EN) | needs Access-i (not connected, awaiting approval): until then, say no source in the data space covers Wallonia; an external search is labelled as such |
| 5 | How do Acceslibre and PictoAccess describe the Musée de la Résistance in Limoges? (EN) | both sources, plus `tourisme-handicap`, which lists the museum as labelled. PictoAccess: all 8 disability types `autonomous`. Acceslibre: two records at 7 rue Neuve Saint-Étienne, a full one (Tourisme & Handicap label for 4 disability families, induction loop, trained staff, step-free entrance) and a sparse duplicate; the agent merges the two, matches them to PictoAccess by address and coordinates, and contrasts per-disability levels with a list of facilities |
| 6 | Where can I find accessible hotels in Brussels? (EN) | Access-i once approved; until then, say that IedereenOveral covers Brussels for food and drink only and that no source in the data space covers hotels there |
| 7 | Is there an accessible restaurant in Tokyo? (EN) | no covering source; anything found externally is labelled as such; nothing invented |
| 8 | What does a green A pictogram mean in Picto Access? (EN) | vochub only, with citation; no source call (the PictoAccess data itself has no letters, see above) |
| 9 | Which sources in this data space cover Belgium, and which cover France? (EN) | catalog only (`GET /catalogs`): accessibility and mobility sub-catalogs per country, as in "Catalog and sources"; no source calls |
| 10 | Quels hôtels à Rouen ont une chambre accessible et un parking adapté ? (FR) | Acceslibre only (`commune=Rouen&activite=hotel&equipments=having_adapted_parking`: 18 hotels), then per hotel `accueil_chambre_nombre_accessibles` (e.g. Hôtel Centre Rouen Vieille Tour: 1 accessible room, no step-free shower); PictoAccess has no accommodation in Rouen; empty fields reported as unknown |
| 11 | Is the lift at Lille Flandres station working right now? (EN) | `sncf-stations` to find the station id, then `sncf-lift-status` with `gareid`; answer with the live state and its retrieval time |
| 12 | Welke haltes bij de Grote Markt in Brussel zijn rolstoeltoegankelijk, en heeft Gent-Sint-Pieters een lift naar de perrons? (NL) | `stib-stops` near the Grand-Place with `wheelchair=accessible`, and `irail-stations`; mentions that iRail's ramp data dates from 2023 |

Facts above were checked against the live sources and the PictoAccess snapshot on Nov 16, 2026. Acceslibre is live, so the harness pins its responses as fixtures before scoring.

Score each answer pass or fail on: right sources chosen, parameters exist in the OpenAPI, facts match, each claim has source, URL, date and licence, gaps and conflicts stated, call budget respected.

## Adding a source

Follow `sources/README.md`, "Adding a source":
1. Choose between an adapter and registering the provider's API directly.
2. Write `registration.json`, including a `catalog` (`belgium` or `france`).
3. Add a credentials entry if the source needs a key.
4. Run `make up register`.

An adapter's OpenAPI is written for a language-model reader:
- an `operationId` prefixed with the source id, e.g. `pictoaccess_search_places`;
- a plain-language description per operation and parameter;
- allowed values listed as enums;
- provenance in every response.

## Data space viewer

`viewer/` is a separate, read-only web interface for the metadata broker and
vocabulary hub, published on a server under `/viewer/` (its paths are relative). It has a standard-library Python server, buildless HTML/CSS/JS,
its own Compose project and offline tests. See [viewer/README.md](viewer/README.md).

```bash
make -C viewer run          # http://localhost:8090; Python 3.10+, no packages to install
make -C viewer up           # alternative: standalone Docker service on the data space network
make -C viewer down         # stops only the viewer Compose project
make -C viewer check        # offline fictional fixtures; Python and Node.js 18+
```

- **Ownership boundary:** viewer work stays in `viewer/`, with narrowly scoped
  updates to this root `AGENTS.md`. Do not edit `dataspace/` or `sources/` as part
  of viewer work, particularly while another agent is working there. Preserve
  concurrent edits to this file; do not replace it with an earlier copy.
- **Discovery:** the metadata tab reads `/catalogs`, `/datasets` and individual
  registrations; it shows all integrated DCAT sub-catalogs and current datasets,
  including mobility sources, without maintaining a source-specific list. It
  exposes licence notes, access conditions, source DCAT and root graph exports.
- **Vocabulary and questions:** the vocabulary tab lists `/documents` and calls
  `/search` with `q`, `k`, optional `language` and `tag`. Show retrieved passages
  with source URL, page/heading, licence, rank and retrieval time; join
  ingestion dates from document metadata. This is RAG retrieval, not generated
  answers or live place searches. Missing metadata stays unknown. Inclusion of a
  provider's knowledge document does not imply its place API is connected.
- **Connections:** the viewer's allowlisted GET/HEAD proxy uses `CATALOG_URL`
  (default `http://localhost:8001`) and `VOCHUB_URL` (default
  `http://localhost:8002`). This administrative viewing interface reads the REST
  services; the agent workflow still uses `http://localhost:8800/mcp`. No existing
  service contract, CORS configuration, source registration or credential changes
  are needed. The viewer does not read `.env` files or private source exports.
- **Verification:** `make -C viewer check` adds offline proxy and frontend logic
  checks to the existing project gates. `python3 viewer/tests/preview.py` serves
  explicitly fictional browser fixtures on port 8091; normal operation always
  uses the live service APIs and reports unavailable or empty services explicitly.

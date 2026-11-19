# Data sources for the accessibility data space

Everything that is specific to a data source: proxies (adapters) in front of providers' APIs, their catalog registrations, per-source notes, and the domain knowledge loaded into the vocabulary hub. The data space in [../dataspace](../dataspace/README.md) knows nothing about them; they reach it only through its HTTP APIs (catalog `PUT /datasets/{id}`, vocabulary hub `POST /documents/url`).

| Source | Catalog | How it is served | Notes |
| --- | --- | --- | --- |
| `iedereenoveral` | belgium | `src-iedereenoveral`, port 8102: live adapter in front of the IedereenOveral (Xano) API | [README](iedereenoveral/README.md) |
| `pictoaccess` | france | `src-pictoaccess`, port 8103: snapshot API over a local PictoAccess export | [README](pictoaccess/README.md) |
| `acceslibre` | france | no proxy: registered with its own OpenAPI (https://acceslibre.beta.gouv.fr/api/openapi), called directly by the connector | needs an API key, see below |
| `be-transit/*`: `stib-stops`, `tec-stops`, `delijn-stops`, `irail-stations` | belgium-mobility | `src-be-transit`, port 8104: daily snapshot of the static GTFS feeds on data.belgianmobility.io (CC BY 4.0, no key) and iRail's station facilities (GitHub); one sub-API with its own OpenAPI per operator | see below |
| `opendatasoft/*` (11 datasets) | all four | no proxy: live Explore API of Opendatasoft portals (SNCF, ODWB, data.economie.gouv.fr); registrations generated from the portals' own metadata, with their DCAT copied in | see below |
| `toerismevlaanderen` | belgium | `src-toerismevlaanderen`, port 8106: Toerisme Vlaanderen's linked open data (SPARQL), loaded into memory every 6 hours | see below |
| `documents/*`: `zon-zee-zorgeloos` | belgium | `src-documents`, port 8107: published web pages and PDFs served as sections | see below |
| `osm/*`: `onwheels`, `osm-accessibility` | root catalog (no sub-catalog: covers Belgium and Hauts-de-France) | `src-osm`, port 8105: live adapter over OpenStreetMap's public Overpass and OSM APIs | see below |
| Access-i | (belgium) | **not connected**: no public API, and reuse needs Access-i's approval (requested) | do not crawl or snapshot before approval |

Each source directory holds a `registration.json`: the record PUT to the catalog.

Two inventories track the work against the literature study:
- [source-inventory.md](source-inventory.md) lists every source: added, candidate, blocked or skipped, with how it is reached, its licence and the study's errors.
- [domain-knowledge-inventory.md](domain-knowledge-inventory.md) does the same for the vocabulary hub's documents.

Update them when a source or document changes status.

### Belgian public transport stops (`be-transit`)

`src-be-transit` downloads the static GTFS of STIB-MIVB, TEC and De Lijn from data.belgianmobility.io, and `stations.csv` + `facilities.csv` from github.com/iRail/stations. It keeps only boarding stops (railway stations for iRail) and stores them on the `be-transit-cache` volume. The data is refreshed every `REFRESH_HOURS` (default 24) in the background; the first start takes a minute or two, during which calls return 503. Each operator is a mounted sub-API (`/stib/`, `/tec/`, `/delijn/`, `/irail/`) with its own OpenAPI, so each is a separate catalog entry with its own licence and attribution.

- **Wheelchair values:** GTFS `wheelchair_boarding` becomes `accessible`, `not_accessible` or `unknown`. `0` or empty means the operator gave no information, not that the stop is inaccessible. De Lijn marks about 5,500 stops accessible and gives no information for the other 25,000; its finer classification is not in the feed.
- **SNCB:** its GTFS has no wheelchair data, so train stations come from iRail. There, `wheelchair_available`, `ramp` and `audio_induction_loop` date from June 2023; lift and escalator fields derive from OpenStreetMap (ODbL) although the repository is CC0.
- **Attribution:** each response's `provenance.attribution` gives the line the licence requires, e.g. "Source: STIB-MIVB – Open Data – 20261109".

### Toerisme Vlaanderen (`toerismevlaanderen`)

`src-toerismevlaanderen` reads the accessibility information in Toerisme Vlaanderen's linked open data (https://linked.toerismevlaanderen.be/sparql). Of 57,000 accessibility records only about 1,000 hold anything, so it loads those places with two SPARQL queries at start-up and every `REFRESH_HOURS` (default 6), keeps them in memory, and searches locally. If a refresh fails it keeps serving the previous load. Per place: the A or A+ label, flags for the groups it caters for, texts per topic in Dutch and English, coordinates and address.

- **Topics are often misfiled in the source:** compared with Toerisme Vlaanderen's own search site for 15 places, about 4 in 10 texts on entrances, routes and toilets were under another topic. The API description and every detail say so; the adapter does not move texts.
- **Query speed:** a filter on "any accessibility property", or a `VALUES` list of ids, takes the endpoint over a minute. The place query therefore names the properties the text query returned.
- **Licence:** none published; Toerisme Vlaanderen asked for this integration, and the licence is being discussed with them.

### Web pages and PDFs as datasets (`documents`)

Information that is only published as a web page or PDF, and changes (seasonal services, event programmes, parking guides), is data, not domain knowledge. `src-documents` serves each `documents/<id>/registration.json` as its own dataset with three operations: `<id>_get_outline` (sections with heading path and page), `<id>_search` (sections containing words, ignoring case and accents) and `<id>_get_section` (full text). Sections follow the document's structure: headings, accordion titles, PDF pages and table of contents. Every answer gives `document_date`, `last_modified`, `retrieved_at` and `content_changed_at`, so an agent can tell last year's programme from this year's ([ADR 0005](../dataspace/docs/adr/0005-documents-as-datasets.md)).

To add a document:
1. Copy `documents/zon-zee-zorgeloos/registration.json` to `documents/<id>/`.
2. Set `distributions[0]` to the page or PDF (`media_type` `text/html` or `application/pdf`), and `endpoint_url` and `openapi_url` to `http://src-documents:8000/<id>/`.
3. Write the description for an agent: what the document lists, per what (town, event, page), its language, and how often it changes.
4. Check the terms first. The hub's licence exception does not apply to data sources.
5. `docker compose up -d --build src-documents && make register`.

The adapter fetches at most every `REFRESH_HOURS` (default 24), honours robots.txt and keeps the last good copy during an outage. Search is by words in the document's language (`shortcut:` no semantic search).

### OpenStreetMap: OnWheels and native accessibility tags (`osm`)

`src-osm` answers each search with one Overpass query and each detail with one call to the OSM API. It keeps nothing beyond a 30-minute in-memory cache and adds the ODbL attribution to every response, so OSM is queried live, not republished. Two sub-APIs, two catalog entries:
- **`onwheels`** (`/onwheels/`) returns the features the [OnWheels map](https://mapcomplete.org/onwheels) asks contributors to measure (entrances, kerbs, toilets, lifts, reception desks, disabled parking), with lengths in metres. Its detail says whether the last edit was made with OnWheels: the OSM changeset carries `theme=onwheels`.
- **`osm-accessibility`** (`/osm/`) returns places with OSM's own accessibility tags (`wheelchair`, `toilets:wheelchair`, `hearing_loop` and more). This also covers what Wheelmap and Toilettes Publiques show.

**Polite towards the public Overpass server**, which is shared and often full:
- searches only around a point in Belgium or Hauts-de-France (bounding boxes), within 300 m (features) or 1 km (places);
- coordinates are rounded to about 10 m, so repeats hit the cache;
- one query at a time;
- a free-slot check on `/api/status` before each query;
- back-off of 30 s, doubling up to 15 minutes, after a busy answer;
- at most `OVERPASS_DAILY_QUERIES` (default 500) queries a day.

When in doubt, the agent gets a 503 with `Retry-After` instead of a query being queued. Contributor names from OSM metadata are never returned. To use a private Overpass instance, set `OVERPASS_URL` in `sources/.env`.

### Datasets forwarded from open data portals

`opendatasoft/datasets.yaml` lists open datasets that the connector queries live on their portal, with no proxy and no key. `python opendatasoft/make_registrations.py` (with httpx and pyyaml) regenerates every `opendatasoft/<id>/registration.json` from the portal's metadata: title, description, publisher, licence, keywords and the dataset's field list. It also sets `source_dcat_url` to the portal's DCAT export of the dataset, so the catalog copies the original DCAT. Add a dataset by adding an entry and rerunning the script, then `make register`.

| Catalog | Datasets |
| --- | --- |
| france | `tourisme-handicap` (labelled establishments, DGE) |
| belgium | `liege-pmr-toilets` |
| france-mobility | `sncf-stations` (reference list), `sncf-lift-status` (live state of lifts and escalators; `gareid` = `id` in `sncf-stations`), `sncf-station-equipment`, `sncf-assistance` |
| belgium-mobility | disabled parking: `liege-pmr-parking`, `brabant-wallon-pmr-parking`, `marche-en-famenne-pmr-parking`, `la-louviere-pmr-parking`, `databusters-pmr-parking` |

Agents call them with operation `getRecords`, the portal's `dataset_id` (given in the description), and an ODSQL `where`.

## Run

```bash
make -C ../dataspace up   # the data space first: the proxies join its Docker network
make up                   # build and start the proxies
make register             # PUT every */registration.json to the catalog (http://localhost:8001)
make knowledge            # optional: ingest domain-knowledge.yaml into the vocabulary hub (needs internet)
make test                 # offline unit tests of the proxies
make e2e                  # data space + sources end to end (needs internet for IedereenOveral)
```

On a server, the PictoAccess export is not in git: copy `pictoaccess_dump/places/` there first (command in the [repository README](../README.md#deploy-to-a-server)), or the PictoAccess proxy starts with no places. The transit proxy fills its `be-transit-cache` volume on first start and refreshes it daily; the volume survives restarts and redeploys.

`CATALOG_URL` and `VOCHUB_URL` point `seed.py` at another data space; for a data space on a remote server, run these commands on the server or through an SSH tunnel (see "Running on a remote server" in the data space README). Registering checks that each source's OpenAPI is reachable from the catalog, so start the proxies first. The registrations use Docker-internal addresses (`http://src-iedereenoveral:8000/`) because the catalog and connector call the proxies from inside Docker; `localhost:8102` inside a container is that container itself. A source hosted elsewhere registers its public URL instead.

Settings for the proxies go in `sources/.env` (read by Compose): `SOURCES_BIND` (address the proxy ports 8102 to 8107 are published on, default `127.0.0.1`; keep it on a server, the catalog and connector use the Docker network), `IEDEREENOVERAL_API` (upstream base URL), and `PICTOACCESS_PLACES_DIR` (location of the export, default `./pictoaccess/pictoaccess_dump/places`).

## API keys

Keys are held by the data space's connector, not by the sources: entries in `../dataspace/config/credentials.yaml` refer to variables in `../dataspace/.env`. For Acceslibre, set `ACCESLIBRE_API_KEY` there (request a key at https://acceslibre.beta.gouv.fr/contact/api_key) and run `docker compose up -d connector` in `../dataspace`.

## Checking with an agent

Connect the agent to the data space's MCP connector (see the data space README), then ask, for example:

> Use the accessibility-dataspace MCP tools to find places in Gent with accessibility information from IedereenOveral. Look up relevant domain knowledge, inspect the source metadata and OpenAPI, then search and retrieve details. Cite the source and distinguish missing information from explicitly absent facilities.

The agent should find `iedereenoveral` through `catalog_search`, inspect it with `catalog_get_dataset` and `get_openapi`, then use `call_source_operation`. Registering or updating a source needs no change to the agent or the connector.

## Adding a source

1. If the provider's API is hard for an agent to use (huge responses, numeric ids, no descriptions), write an adapter in `<id>/` with its own OpenAPI, and add it to `docker-compose.yml`. Otherwise register the provider's API directly, as for Acceslibre.
2. Write `<id>/registration.json` (fields: see "Publishing a dataset" in the data space README). If the data follows a published schema, data model or vocabulary (GTFS, an OSLO model, the publisher's own vocabulary), list it in `conforms_to`: the DCAT export links it with `dct:conformsTo`, next to the API's OpenAPI document ([ADR 0004](../dataspace/docs/adr/0004-schemas-in-dcat.md)). Link only URLs you have opened.
3. If it needs a key, add an entry to `../dataspace/config/credentials.yaml`.
4. `make up register`.
5. Update its row in [source-inventory.md](source-inventory.md).

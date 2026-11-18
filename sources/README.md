# Data sources for the accessibility data space

Everything that is specific to a data source: proxies (adapters) in front of providers' APIs, their catalog registrations, per-source notes, and the domain knowledge loaded into the vocabulary hub. The data space in [../dataspace](../dataspace/README.md) knows nothing about them; they reach it only through its HTTP APIs (catalog `PUT /datasets/{id}`, vocabulary hub `POST /documents/url`).

| Source | Catalog | How it is served | Notes |
| --- | --- | --- | --- |
| `iedereenoveral` | belgium | `src-iedereenoveral`, port 8102: live adapter in front of the IedereenOveral (Xano) API | [README](iedereenoveral/README.md) |
| `pictoaccess` | france | `src-pictoaccess`, port 8103: snapshot API over a local PictoAccess export | [README](pictoaccess/README.md) |
| `acceslibre` | france | no proxy: registered with its own OpenAPI (https://acceslibre.beta.gouv.fr/api/openapi), called directly by the connector | needs an API key, see below |
| `be-transit/*`: `stib-stops`, `tec-stops`, `delijn-stops`, `irail-stations` | belgium-mobility | `src-be-transit`, port 8104: daily snapshot of the static GTFS feeds on data.belgianmobility.io (CC BY 4.0, no key) and iRail's station facilities (GitHub); one sub-API with its own OpenAPI per operator | see below |
| `opendatasoft/*` (11 datasets) | all four | no proxy: live Explore API of Opendatasoft portals (SNCF, ODWB, data.economie.gouv.fr); registrations generated from the portals' own metadata, with their DCAT copied in | see below |
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

Settings for the proxies go in `sources/.env` (read by Compose): `SOURCES_BIND` (address the proxy ports 8102 to 8104 are published on, default `127.0.0.1`; keep it on a server, the catalog and connector use the Docker network), `IEDEREENOVERAL_API` (upstream base URL), and `PICTOACCESS_PLACES_DIR` (location of the export, default `./pictoaccess/pictoaccess_dump/places`).

## API keys

Keys are held by the data space's connector, not by the sources: entries in `../dataspace/config/credentials.yaml` refer to variables in `../dataspace/.env`. For Acceslibre, set `ACCESLIBRE_API_KEY` there (request a key at https://acceslibre.beta.gouv.fr/contact/api_key) and run `docker compose up -d connector` in `../dataspace`.

## Checking with an agent

Connect the agent to the data space's MCP connector (see the data space README), then ask, for example:

> Use the accessibility-dataspace MCP tools to find places in Gent with accessibility information from IedereenOveral. Look up relevant domain knowledge, inspect the source metadata and OpenAPI, then search and retrieve details. Cite the source and distinguish missing information from explicitly absent facilities.

The agent should find `iedereenoveral` through `catalog_search`, inspect it with `catalog_get_dataset` and `get_openapi`, then use `call_source_operation`. Registering or updating a source needs no change to the agent or the connector.

## Adding a source

1. If the provider's API is hard for an agent to use (huge responses, numeric ids, no descriptions), write an adapter in `<id>/` with its own OpenAPI, and add it to `docker-compose.yml`. Otherwise register the provider's API directly, as for Acceslibre.
2. Write `<id>/registration.json` (fields: see "Publishing a dataset" in the data space README).
3. If it needs a key, add an entry to `../dataspace/config/credentials.yaml`.
4. `make up register`.
5. Update its row in [source-inventory.md](source-inventory.md).

# Accessibility data space demonstrator

A small, runnable data space for accessibility information: publishers register their APIs in a DCAT catalog, a vocabulary hub holds domain knowledge, and an MCP connector lets an AI agent find a source, read its OpenAPI and query it, with per-source API keys handled by the connector.

Research demonstrator of the [KNoWS team](https://knows.idlab.ugent.be) (Ghent University). Open source, public data only. No authentication between components in this version.

## Components

| Service | Port | What it does |
| --- | --- | --- |
| `catalog` | 8001 | Dataset registration API, search, DCAT export (Turtle, JSON-LD) and SPARQL. Docs at http://localhost:8001/docs |
| `vochub` + `vochub-vectors` | 8002 | Ingests PDFs, office files, HTML and web pages; returns cited passages (multilingual embeddings, Qdrant). Docs at http://localhost:8002/docs |
| `connector` | 8800 | MCP server (`/mcp`, streamable HTTP) with five read-only tools; injects source API keys |
Data sources (proxies, registrations, source notes, domain-knowledge seed) live outside the data space in [../sources](../sources/README.md); they talk to it only through its HTTP APIs.

```text
agent ──MCP──▶ connector ──▶ vochub        (terms, criteria, cited passages)
                         ──▶ catalog       (which sources, their API + OpenAPI)
                         ──▶ source APIs   (OpenAPI-validated GETs, API key added from config/credentials.yaml)
publisher ──POST /datasets──▶ catalog
```

## Run

Requirements: Docker with Compose, and [uv](https://docs.astral.sh/uv/) for tests.

```bash
make up        # copies .env.example to .env on first run, builds, waits until healthy
make check     # offline unit tests + compose build
make clean     # stop and delete volumes
```

The first build downloads the embedding model (about 220 MB) into the vochub image. The data space starts empty; to add the demo sources and domain knowledge, see [../sources](../sources/README.md).

## Running on a remote server

The stack runs the same way on a server: copy both `dataspace/` and `../sources/` (including `sources/pictoaccess/pictoaccess_dump/`, which is not in git), then run `make up` in `dataspace/` and `make up register` in `sources/`. **By default every port is bound to `127.0.0.1`**, so nothing is reachable from outside until you open it on purpose. The services reach each other over Docker's network, not over these ports.

### Ports

| Port | Service | Open to the outside? |
| --- | --- | --- |
| **8800** | connector, MCP endpoint `/mcp` | **Yes: this is the only port an agent needs.** Put it behind HTTPS and authentication (see below) |
| 8001 | catalog: DCAT export, search, SPARQL, registration | Optional, to publish the DCAT catalog. It also serves `POST`/`PUT`/`DELETE /datasets` without authentication, so expose only `GET` (see below) |
| 8002 | vocabulary hub | No. Ingestion has no authentication; reach it through an SSH tunnel |
| 8102 to 8104 | source proxies (in `../sources`) | No. The catalog and connector call them over the Docker network, and the PictoAccess proxy serves non-public data |

### Settings

In `dataspace/.env` (read by Compose; restart with `make up` after a change):

| Variable | Default | What to set on a server |
| --- | --- | --- |
| `CATALOG_BASE_URL` | `http://localhost:8001` | **The public address of the catalog, without a trailing slash**, e.g. `https://dataspace.example.org/catalog`. Every URI in the DCAT export (catalog, sub-catalogs, datasets, services, themes) starts with it, and each resolves under it. If the catalog is not public, leave the default |
| `CONNECTOR_BIND` | `127.0.0.1` | Keep `127.0.0.1` when a reverse proxy on the same host forwards to the connector; `0.0.0.0` publishes port 8800 directly (only behind a firewall that allows your own addresses) |
| `CATALOG_BIND` | `127.0.0.1` | Same, for port 8001 |
| `VOCHUB_BIND` | `127.0.0.1` | Keep |
| `ACCESLIBRE_API_KEY` | | Source API keys, as on a laptop |

In `sources/.env`: `SOURCES_BIND` (default `127.0.0.1`, keep it).

The registrations keep their Docker-internal addresses (`http://src-…:8000/`); that is correct on a server too, because only the catalog and connector call them. Those addresses do appear in the DCAT export as the `dcat:endpointURL` of the proxied datasets; outside parties use the data through the connector.

### HTTPS and authentication

The connector and catalog have no authentication of their own. Anyone who can reach the connector can query every source with your API keys and read the PictoAccess snapshot. A reverse proxy such as [Caddy](https://caddyserver.com) adds HTTPS and a password. A sketch (Caddy 2.8+; replace the host and the hash from `caddy hash-password`):

```caddyfile
dataspace.example.org {
    handle /mcp* {
        basic_auth {
            agent $2a$14$REPLACE_WITH_HASH
        }
        reverse_proxy 127.0.0.1:8800
    }
    handle_path /catalog/* {
        @write not method GET HEAD
        respond @write 405
        reverse_proxy 127.0.0.1:8001
    }
}
```

With this, set `CATALOG_BASE_URL=https://dataspace.example.org/catalog`; the DCAT export is at `https://dataspace.example.org/catalog/catalog`.

### Connecting an agent to the server

Use the public MCP address with the credentials as a header, for example in Claude Code:

```bash
claude mcp add --transport http accessibility-dataspace https://dataspace.example.org/mcp \
  --header "Authorization: Basic $(printf 'agent:PASSWORD' | base64)"
```

In VS Code, add `"headers": {"Authorization": "Basic …"}` next to `"url"` in the server entry. Web-hosted agents that only support OAuth or no authentication (such as ChatGPT) cannot send this header; see the next section.

### Connecting ChatGPT or another web-hosted agent

A web-hosted agent calls the connector from its own servers, so the whole stack runs on your server and only the connector is published, over HTTPS. Such agents generally accept only OAuth or no authentication, so this setup protects the connector with a **secret path**: the URL itself is the password. That is security through obscurity, acceptable for a demonstrator: anyone who learns the URL can query every source with your API keys and read the PictoAccess snapshot. Do not share it, and replace it if it leaks.

1. **DNS:** point a name at the server's public IP, e.g. `dataspace.yourdomain.org` (certificates are not issued for a bare IP).
2. **Ports:** open, and forward on the router if the server is behind NAT:

   | External port | Goes to | Why |
   | --- | --- | --- |
   | 443/tcp | Caddy → `127.0.0.1:8800` | the agent connects over HTTPS only |
   | 80/tcp | Caddy | Let's Encrypt certificate issuance and renewal |
   | 22/tcp | SSH | administration |

   Nothing else: catalog, vochub and the proxies stay on `127.0.0.1` (keep the `*_BIND` defaults and leave `SOURCE_URL_MAP` empty).
3. **Stack:** on the server, `make up` here and `make up register` in `../sources`; put the source API keys (`ACCESLIBRE_API_KEY`) in this server's `.env`.
4. **Secret:** generate one with `openssl rand -hex 16`.
5. **Caddy** (`/etc/caddy/Caddyfile`, then `systemctl reload caddy`), replacing the host and `SECRET`:

   ```caddyfile
   dataspace.yourdomain.org {
       handle /SECRET/mcp* {
           uri strip_prefix /SECRET
           reverse_proxy 127.0.0.1:8800
       }
       respond 404
   }
   ```

   Every other path returns 404, including `/mcp` without the secret.
6. **Check** from any machine: the first call returns 200 with the server's capabilities, the second 404.

   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" -X POST https://dataspace.yourdomain.org/SECRET/mcp \
     -H 'content-type: application/json' -H 'accept: application/json, text/event-stream' \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"check","version":"0"}}}'
   curl -s -o /dev/null -w "%{http_code}\n" https://dataspace.yourdomain.org/mcp
   ```
7. **ChatGPT:** add a custom connector (in ChatGPT's connector settings; custom MCP connectors may require developer mode) with the URL `https://dataspace.yourdomain.org/SECRET/mcp` and no authentication. The five tools of the connector should appear.

To also publish the DCAT catalog read-only, add the `handle_path /catalog/*` block from the previous Caddy example inside the same site and set `CATALOG_BASE_URL=https://dataspace.yourdomain.org/catalog`.

### Registering sources and ingesting documents from your laptop

Either run `make register` and `make knowledge` in `sources/` on the server, or tunnel the two private ports and run them locally (they use `localhost` by default):

```bash
ssh -N -L 8001:127.0.0.1:8001 -L 8002:127.0.0.1:8002 user@server   # leave running
make -C ../sources register knowledge
```

`CATALOG_URL` and `VOCHUB_URL` point `seed.py` and the end-to-end test elsewhere if needed; the end-to-end test also takes `MCP`, e.g. `MCP=https://dataspace.example.org/mcp` (without authentication only).

## Running components separately

Each component can run on its own machine; they only talk HTTP to each other.

```bash
make up-catalog     # catalog (the broker) only
make up-vochub      # vocabulary hub + its vector store only
make up-connector   # connector only, pointed at a catalog, vochub and sources elsewhere
make up             # everything on one machine (default)
```

### Example: catalog and vocabulary hub on a server, connector on your laptop

The connector holds the source API keys and is what your agent talks to, so running it locally keeps the keys on your machine. It needs three things on the server: the catalog, the vocabulary hub, and the source proxies (their registered addresses, such as `http://src-pictoaccess:8000/`, only resolve on the server).

1. On the server: `make up-catalog up-vochub` here, then `make up register` in `../sources`. Keep every port bound to `127.0.0.1`.
2. On the laptop, open an SSH tunnel to the five ports and leave it running:
   ```bash
   ssh -N -L 8001:127.0.0.1:8001 -L 8002:127.0.0.1:8002 \
       -L 8102:127.0.0.1:8102 -L 8103:127.0.0.1:8103 -L 8104:127.0.0.1:8104 user@server
   ```
3. On the laptop, add to `dataspace/.env` (the connector runs in Docker, so it reaches the tunnel on the host as `host.docker.internal`):
   ```bash
   CATALOG_URL=http://host.docker.internal:8001
   VOCHUB_URL=http://host.docker.internal:8002
   SOURCE_URL_MAP=http://src-iedereenoveral:8000/=http://host.docker.internal:8102/,http://src-pictoaccess:8000/=http://host.docker.internal:8103/,http://src-be-transit:8000/=http://host.docker.internal:8104/
   ACCESLIBRE_API_KEY=...
   ```
4. On the laptop: `make up-connector`, and connect the agent to `http://localhost:8800/mcp` as usual.

| Connector setting | Default (all in one Compose project) | Meaning |
| --- | --- | --- |
| `CATALOG_URL` | `http://catalog:8000` | where the connector finds the catalog |
| `VOCHUB_URL` | `http://vochub:8000` | where it finds the vocabulary hub |
| `SOURCE_URL_MAP` | empty | comma-separated `from=to` URL prefixes: registered source addresses that are not reachable from this connector, and where to reach them instead. Sources with public URLs (Acceslibre, the open data portals) need no entry |

Instead of SSH tunnels you can publish the catalog, vochub and proxies over HTTPS behind a reverse proxy with authentication (see [Running on a remote server](#running-on-a-remote-server)) and map to those addresses. Do not publish the vocabulary hub or the PictoAccess proxy without authentication. Without a variable set, `make up-connector` falls back to the defaults, which only work next to a local catalog and vochub.

## Publishing a dataset

A publisher registers a dataset with its metadata, the base URL of its API and the URL of its OpenAPI 3.x document. The catalog fetches the OpenAPI document and rejects the registration if it is missing or not OpenAPI 3.

```bash
curl -X PUT http://localhost:8001/datasets/my-source -H 'content-type: application/json' -d '{
  "id": "my-source",
  "title": "Accessible venues in Leuven",
  "description": "Wheelchair and hearing accessibility of cafes and restaurants in Leuven.",
  "publisher": {"name": "City of Leuven", "url": "https://leuven.be"},
  "licence": "https://creativecommons.org/licenses/by/4.0/",
  "endpoint_url": "https://api.example.org/v1/",
  "openapi_url": "https://api.example.org/v1/openapi.json",
  "keywords": ["wheelchair", "cafe", "rolstoel"],
  "themes": ["accessibility"],
  "languages": ["nl", "en"],
  "spatial": ["Leuven", "Flanders", "Belgium"],
  "update_frequency": "WEEKLY",
  "access_note": "Request an API key at https://api.example.org/keys"
}'
```

| Field | Required | Notes |
| --- | --- | --- |
| `id` | yes | lowercase slug; also the key used in `config/credentials.yaml` |
| `title`, `description` | yes | written for an agent deciding whether the source is relevant |
| `publisher.name` | yes | `publisher.url` optional |
| `licence` | yes* | licence URL; *may be left out only while terms are unknown, with `licence_note` saying so |
| `endpoint_url` | yes | base URL; OpenAPI paths are appended to it |
| `openapi_url` | yes | OpenAPI 3.x, JSON or YAML |
| `keywords`, `themes`, `spatial` | no | improve search; themes are slugs |
| `languages` | no | `nl`, `fr`, `en`, `de` |
| `update_frequency` | no | `CONT`, `DAILY`, `WEEKLY`, `MONTHLY`, `QUARTERLY`, `ANNUAL`, `IRREG`, `UNKNOWN` |
| `licence_note` | no | reuse conditions in words |
| `landing_page`, `contact_email`, `access_note` | no | `access_note` tells consumers how to get a key |
| `catalog` | no | sub-catalog, see below |
| `source_dcat_url` | no | the publisher's own DCAT for this dataset; copied into the catalog and linked with `dct:source` ([ADR 0003](docs/adr/0003-mobility-catalogs-source-dcat-optional-keys.md)) |

When a provider's own API is hard for an agent to use (huge responses, numeric ids, no descriptions), put a thin adapter in front of it and register the adapter instead; [../sources/iedereenoveral](../sources/iedereenoveral/README.md) is an example.

Datasets belong to a sub-catalog through the optional `catalog` field: `belgium`, `france`, `belgium-mobility` or `france-mobility`. In the DCAT export both are `dcat:Catalog`s linked from the root catalog with `dcat:catalog`; `GET /catalogs` lists them with their dataset ids, and `GET /datasets?catalog=france` filters search ([ADR](docs/adr/0001-country-sub-catalogs.md)).

Other calls: `POST /datasets` (create only), `DELETE /datasets/{id}`, `GET /datasets?q=&theme=&spatial=&language=`, `GET /catalog?format=turtle|jsonld`, `GET /catalogs/{id}`, `/services/{id}` and `/themes/{slug}` (DCAT description of each URI in the export), `GET|POST /sparql`. Registrations are stored on the `catalog-data` volume.

## API keys for sources

The connector, not the agent, holds the keys. Add an entry per dataset id to `config/credentials.yaml` that refers to an environment variable, and put the value in `.env`:

```yaml
# config/credentials.yaml
acceslibre:
  api_key: ${ACCESLIBRE_API_KEY}
```

```bash
# .env
ACCESLIBRE_API_KEY=...
```

Restart the connector after changing `.env` (`docker compose up -d connector`); edits to `credentials.yaml` apply on the next call. Where the key goes is read from the source's OpenAPI `securitySchemes` (`apiKey` in header or query, or HTTP bearer). If the OpenAPI declares none, set `in`, `name` and optionally `prefix` in the entry. Keys never appear in tool results; `catalog_search` and `get_openapi` only report `credentials_configured`.

## Vocabulary hub

```bash
curl -F file=@guide.pdf -F language=nl -F tags=criteria http://localhost:8002/documents
curl -X POST http://localhost:8002/documents/url -H 'content-type: application/json' \
     -d '{"url": "https://access-i.be/en/?p=1453", "language": "en", "tags": ["access-i"]}'
curl 'http://localhost:8002/search?q=rolstoeltoegankelijk+toilet&k=5'
```

Supported: PDF (with page numbers), HTML and web pages (main content only), DOCX, PPTX, XLSX, CSV, Markdown, text and other formats [markitdown](https://github.com/microsoft/markitdown) reads. Documents are split on headings into chunks of up to 250 words; identical content is ingested once. The embedding model is set with the `EMBED_MODEL` build argument (default `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`; `intfloat/multilingual-e5-large` is more accurate and about ten times larger). Changing it requires `make clean`, because vector sizes differ.

## Connecting an agent

Connect the external agent to the **`accessibility-dataspace` MCP connector**, at `http://localhost:8800/mcp` (Streamable HTTP). This single server exposes the vocabulary hub, catalog and registered source APIs. Source APIs and the catalog are REST APIs, not MCP servers; do not connect the agent to them directly.

For Claude Code:

```bash
claude mcp add --transport http accessibility-dataspace http://localhost:8800/mcp
```

For VS Code, add this server in the workspace MCP configuration:

```json
{
  "servers": {
    "accessibility-dataspace": {
      "type": "http",
      "url": "http://localhost:8800/mcp"
    }
  }
}
```

For other clients supporting Streamable HTTP, configure the same URL. `localhost` only works when the agent's MCP client runs on the Docker host. A client on the same Compose network can use `http://connector:8800/mcp`; a client in another Docker Desktop container can use `http://host.docker.internal:8800/mcp`. For a stack on another machine, see [Running on a remote server](#running-on-a-remote-server).

The connector provides these tools:

| Tool | Use it to |
| --- | --- |
| `vochub_search` | learn terms and criteria first |
| `catalog_search` | find sources by text, theme, area, language |
| `catalog_get_dataset` | check licence, coverage, update frequency |
| `get_openapi` | read a source's operations and parameters |
| `call_source_operation` | run a read-only operation; parameters are checked against the OpenAPI and the API key is added |

## Layout

```text
catalog/          registration API, DCAT builder (rdflib), search
vochub/           extraction (PyMuPDF, trafilatura, markitdown), chunking, embeddings (fastembed), Qdrant
connector/        MCP server; openapi_calls.py holds validation and key injection
config/           credentials.yaml: the connector's per-dataset API keys (references to env vars only)
docs/adr/         decisions
legacy/           previous Node.js prototype, kept for reference
```

## Limits of this version

No authentication or usage policies between components; the connector trusts the catalog. No call budget per question yet. See the project plan for the roadmap.

## Licence

MIT

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

The stack runs the same way on a server. Clone the repository there, copy the PictoAccess place files (git-ignored) into `sources/pictoaccess/pictoaccess_dump/places/` (see the [repository README](../README.md#deploy-to-a-server) for the `rsync` command), then run `make up` in `dataspace/` and `make up register` in `sources/`. The repository README compares the three set-ups: connector on your machine, ChatGPT, or password-protected.

- **By default every port is bound to `127.0.0.1`**, so nothing is reachable from outside until you open it on purpose. The services reach each other over Docker's network, not over these ports.
- **Every service restarts after a reboot** (`restart: unless-stopped`); registrations, vectors and the transit cache are on Docker volumes and survive. Stop the stack for good with `make down`.
- **First start:** building vochub downloads the embedding model (about 220 MB); the transit proxy then downloads about 300 MB of timetables, and its calls return 503 until that is done.
- **Updating:** `git pull`, then `make up` here and `make up register` in `../sources`. Registering again is safe: each entry is replaced, and copied source DCAT is fetched again.

### Ports

| Port | Service | Open to the outside? |
| --- | --- | --- |
| **8800** | connector, MCP endpoint `/mcp` | **Yes: this is the only port an agent needs.** Put it behind HTTPS and authentication (see below) |
| 8001 | catalog: DCAT export, search, SPARQL, registration | Optional, to publish the DCAT catalog. It also serves `POST`/`PUT`/`DELETE /datasets` without authentication, so expose only `GET` (see below) |
| 8002 | vocabulary hub | No. Ingestion has no authentication; reach it through an SSH tunnel |
| 8102 to 8107 | source proxies (in `../sources`) | No. The catalog and connector call them over the Docker network, and the PictoAccess proxy serves non-public data |

### Settings

In `dataspace/.env` (read by Compose; restart with `make up` after a change):

| Variable | Default | What to set on a server |
| --- | --- | --- |
| `CATALOG_BASE_URL` | `http://localhost:8001` | **The public address of the catalog, without a trailing slash**, e.g. `https://dataspace.example.org/catalog`. Every URI in the DCAT export (catalog, sub-catalogs, datasets, services, themes) starts with it, and each resolves under it. If the catalog is not public, leave the default |
| `CONNECTOR_BIND` | `127.0.0.1` | Keep `127.0.0.1` when a reverse proxy on the same host forwards to the connector; `0.0.0.0` publishes port 8800 directly (only behind a firewall that allows your own addresses) |
| `CATALOG_BIND` | `127.0.0.1` | Same, for port 8001 |
| `VOCHUB_BIND` | `127.0.0.1` | Keep |
| `ACCESLIBRE_API_KEY`, `TOEVLA_API_TOKEN` | | Source API keys, as on a laptop |

In `sources/.env`: `SOURCES_BIND` (default `127.0.0.1`, keep it).

The registrations keep their Docker-internal addresses (`http://src-…:8000/`); that is correct on a server too, because only the catalog and connector call them. Those addresses do appear in the DCAT export as the `dcat:endpointURL` of the proxied datasets; outside parties use the data through the connector.

### HTTPS and authentication

**The connector has no authentication in this version.** Anyone who can reach it can query every source with your API keys and read the PictoAccess snapshot. Publish it only while you need it, for example during a public presentation, and stop it afterwards (`make down`, or close ports 80 and 443). A reverse proxy on the server adds HTTPS; see [Reverse proxy: Caddy or nginx](#reverse-proxy-caddy-or-nginx). The catalog has no authentication either; publish it read-only.

**Production needs OAuth.** Web-hosted agents such as ChatGPT accept only OAuth for MCP connectors, so a password, bearer token or secret path is not an option for them. The MCP SDK the connector uses has a hook for this (`auth_server_provider` / `token_verifier` on `MCPServer`): either the connector acts as a small OAuth server, or it checks tokens from an external provider such as Keycloak. Not built in this version.

### Reverse proxy: Caddy or nginx

The reverse proxy runs on the server itself (not in Docker). It handles HTTPS and forwards requests to the ports that Compose binds to `127.0.0.1`. Use Caddy or nginx; both configurations below forward the same paths:

| Public path | Forwards to | Protection |
| --- | --- | --- |
| `/mcp` | `127.0.0.1:8800/mcp`, the connector | none (see above) |
| `/catalog/…` (optional) | `127.0.0.1:8001/…`, the catalog | read-only: only `GET` and `HEAD` pass |
| anything else (optional) | `127.0.0.1:8090`, the [viewer](../viewer/README.md) | read-only by design: it answers only `GET` and `HEAD`, on a fixed list of paths |
| anything else, without the viewer | nothing | 404 |

Replace `dataspace.example.org` with your host name. To publish the viewer, start it on the server with `make -C ../viewer up` (after `make up` here); it needs the root path, because its pages and API calls use absolute paths. If you publish the catalog, set `CATALOG_BASE_URL=https://dataspace.example.org/catalog` in `.env` and run `make up`; the DCAT export is then at `https://dataspace.example.org/catalog/catalog`.

**Caddy** (2.8 or later) fetches and renews the certificate itself. Put this in `/etc/caddy/Caddyfile`, then run `sudo systemctl reload caddy`:

```caddyfile
dataspace.example.org {
    # The connector (no authentication: publish only during presentations)
    handle /mcp* {
        reverse_proxy 127.0.0.1:8800
    }

    # Optional: the DCAT catalog, read-only
    handle_path /catalog/* {
        @write not method GET HEAD
        respond @write 405
        reverse_proxy 127.0.0.1:8001
    }

    # Optional: the viewer (read-only), on every other path. Without it: respond 404
    handle {
        reverse_proxy 127.0.0.1:8090
    }
}
```

Caddy passes the connector's streamed responses through without extra settings. It writes no access log unless you add `log`.

**nginx** needs a certificate before it starts with this file. Get one with `sudo certbot certonly --nginx -d dataspace.example.org`; certbot renews it automatically. Put this in `/etc/nginx/sites-available/dataspace`, link it into `sites-enabled/`, then run `sudo nginx -t && sudo systemctl reload nginx`:

```nginx
server {
    listen 80;
    server_name dataspace.example.org;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name dataspace.example.org;
    ssl_certificate     /etc/letsencrypt/live/dataspace.example.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dataspace.example.org/privkey.pem;

    # The connector streams its answers (server-sent events), and some source calls take a while
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header Connection "";
    proxy_buffering off;
    proxy_read_timeout 300s;

    # The connector (no authentication: publish only during presentations)
    location /mcp {
        access_log off;   # no record of who asked what
        proxy_pass http://127.0.0.1:8800;
    }

    # Optional: the DCAT catalog, read-only (other methods get 403)
    location /catalog/ {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8001/;
    }

    # Optional: the viewer (read-only), on every other path. Without it: location / { return 404; }
    location / {
        access_log off;   # search questions are in the query string
        proxy_pass http://127.0.0.1:8090;
    }
}
```

`limit_except GET` also allows `HEAD`. Without `proxy_buffering off`, nginx holds back the connector's streamed answers and agents time out.

Open ports 80 and 443 for either proxy: 443 for the agent, and 80 for certificate issuance and renewal. Check the result with the `curl` commands in step 6 of the next section. 

### Connecting an agent to the server

Use the public MCP address, for example in Claude Code:

```bash
claude mcp add --transport http accessibility-dataspace https://dataspace.example.org/mcp
```

In VS Code, put the same address as `"url"` in the server entry. For web-hosted agents, see the next section.

### Connecting ChatGPT or another web-hosted agent

A web-hosted agent calls the connector from its own servers, so the whole stack runs on your server and only the connector is published, over HTTPS, without authentication. Keep it online only during presentations. ChatGPT accepts only OAuth or no authentication; see [HTTPS and authentication](#https-and-authentication) for what production would need.

1. **DNS:** point a name at the server's public IP, e.g. `dataspace.yourdomain.org` (certificates are not issued for a bare IP).
2. **Ports:** open, and forward on the router if the server is behind NAT:

   | External port | Goes to | Why |
   | --- | --- | --- |
   | 443/tcp | Caddy → `127.0.0.1:8800` | the agent connects over HTTPS only |
   | 80/tcp | Caddy | Let's Encrypt certificate issuance and renewal |
   | 22/tcp | SSH | administration |

   Nothing else: catalog, vochub and the proxies stay on `127.0.0.1` (keep the `*_BIND` defaults and leave `SOURCE_URL_MAP` empty).
3. **Stack:** on the server, `make up` here and `make up register` in `../sources`; put the source API keys (`ACCESLIBRE_API_KEY`) in this server's `.env`.
4. **Reverse proxy:** use the Caddy or nginx configuration from [Reverse proxy: Caddy or nginx](#reverse-proxy-caddy-or-nginx). Every path other than `/mcp`, the optional `/catalog` and the optional viewer returns 404.
5. **Check** from any machine: the first call returns 200 with the server's capabilities, the second 404.

   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" -X POST https://dataspace.yourdomain.org/mcp \
     -H 'content-type: application/json' -H 'accept: application/json, text/event-stream' \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"check","version":"0"}}}'
   curl -s -o /dev/null -w "%{http_code}\n" https://dataspace.yourdomain.org/other
   ```
6. **ChatGPT:** add a custom connector (custom MCP connectors may require developer mode) with the URL `https://dataspace.yourdomain.org/mcp` and no authentication. The five tools of the connector should appear.

To also publish the DCAT catalog read-only, keep the `/catalog` block in that configuration and set `CATALOG_BASE_URL=https://dataspace.yourdomain.org/catalog`.

### Registering sources and ingesting documents from your laptop

Either run `make register` and `make knowledge` in `sources/` on the server, or tunnel the two private ports and run them locally (they use `localhost` by default):

```bash
ssh -N -L 8001:127.0.0.1:8001 -L 8002:127.0.0.1:8002 user@server   # leave running
make -C ../sources register knowledge
```

`CATALOG_URL` and `VOCHUB_URL` point `seed.py` and the end-to-end test elsewhere if needed; the end-to-end test also takes `MCP`, e.g. `MCP=https://dataspace.example.org/mcp` 

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
       -L 8102:127.0.0.1:8102 -L 8103:127.0.0.1:8103 -L 8104:127.0.0.1:8104 -L 8105:127.0.0.1:8105 -L 8106:127.0.0.1:8106 -L 8107:127.0.0.1:8107 user@server
   ```
3. On the laptop, add to `dataspace/.env` (the connector runs in Docker, so it reaches the tunnel on the host as `host.docker.internal`):
   ```bash
   CATALOG_URL=http://host.docker.internal:8001
   VOCHUB_URL=http://host.docker.internal:8002
   SOURCE_URL_MAP=http://src-iedereenoveral:8000/=http://host.docker.internal:8102/,http://src-pictoaccess:8000/=http://host.docker.internal:8103/,http://src-be-transit:8000/=http://host.docker.internal:8104/,http://src-osm:8000/=http://host.docker.internal:8105/,http://src-toerismevlaanderen:8000/=http://host.docker.internal:8106/,http://src-documents:8000/=http://host.docker.internal:8107/
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

A publisher registers a dataset with its metadata, the base URL of its API and the URL of its OpenAPI 3.x document. The catalog fetches the OpenAPI document and rejects the registration if it is missing or not OpenAPI 3. It keeps a copy, served at `/services/{id}/openapi.json`, so the DCAT export links a description that resolves from outside even when `openapi_url` is a Docker-internal address.

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
  "conforms_to": [{"url": "https://gtfs.org/documentation/schedule/reference/", "title": "GTFS Schedule reference"}],
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
| `assessment` | no, but agents rank sources by it | how the facts were collected: `methods` from `certified` (a label or on-site check by an independent body), `official` (the owner or operator: transport operator, municipality, government), `self_declared` (the venue itself), `crowd_sourced` (anyone can edit); and a `note` naming the field that tells the method per record. Shown in search results; exported as `dct:provenance` |
| `conforms_to` | no | published schemas, data models or vocabularies the data follows (`url`, `title`); exported as `dct:conformsTo` ([ADR 0004](docs/adr/0004-schemas-in-dcat.md)) |
| `distributions` | no | further distributions besides the API (`url`, `media_type`, `title`), e.g. the web page or PDF a document dataset reads; exported as `dcat:Distribution` with `dcat:mediaType` ([ADR 0005](docs/adr/0005-documents-as-datasets.md)) |
| `source_dcat_url` | no | the publisher's own DCAT for this dataset; copied into the catalog and linked with `dct:source` ([ADR 0003](docs/adr/0003-mobility-catalogs-source-dcat-optional-keys.md)) |

When a provider's own API is hard for an agent to use (huge responses, numeric ids, no descriptions), put a thin adapter in front of it and register the adapter instead; [../sources/iedereenoveral](../sources/iedereenoveral/README.md) is an example.

Datasets belong to a sub-catalog through the optional `catalog` field: `belgium`, `france`, `belgium-mobility` or `france-mobility`. In the DCAT export both are `dcat:Catalog`s linked from the root catalog with `dcat:catalog`; `GET /catalogs` lists them with their dataset ids, and `GET /datasets?catalog=france` filters search ([ADR](docs/adr/0001-country-sub-catalogs.md)).

Other calls: `POST /datasets` (create only), `DELETE /datasets/{id}`, `GET /datasets?q=&theme=&spatial=&language=`, `GET /catalog?format=turtle|jsonld`, `GET /catalogs/{id}`, `/services/{id}` and `/themes/{slug}` (DCAT description of each URI in the export), `GET /services/{id}/openapi.json` (the OpenAPI copy), `GET|POST /sparql`. Registrations are stored on the `catalog-data` volume.

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

Supported: PDF (with page numbers), HTML and web pages (main content only), DOCX, PPTX, XLSX, CSV, Markdown, text and other formats [markitdown](https://github.com/microsoft/markitdown) reads. Documents are split on headings into chunks of up to 60 words, because the default model reads only 128 tokens; each chunk is embedded with its document title and heading in front, so a passage like "vert/A (accessible en autonomie)" is still found for "Picto Access". Identical content is ingested once. After changing the chunking, delete the documents (`DELETE /documents/{id}`) and run `make knowledge` again. The embedding model is set with the `EMBED_MODEL` build argument (default `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`; `intfloat/multilingual-e5-large` is more accurate, reads 512 tokens and is about ten times larger). Changing it requires `make clean`, because vector sizes differ.

**Permanent context.** One Markdown text that the connector returns as `context` with every `vochub_search`, before the passages: rules that hold for every question, such as how to compare sources. Set it with `curl -X PUT http://localhost:8002/context -H 'content-type: application/json' -d '{"text": "…"}'` (at most 20,000 characters) and read it with `GET /context`. It is stored in the `vochub-data` volume. The viewer shows it on the vocabulary hub page. The demo text is `sources/permanent-context.md`, set by `make knowledge`. Keep it short: agents get it with every search.

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
| `vochub_search` | learn terms and criteria first; also returns the permanent context (rules for every question) |
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

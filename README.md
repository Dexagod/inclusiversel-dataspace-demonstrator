# Accessibility data space demonstrator

A small, runnable data space for accessibility information in Belgium and France, by the [KNoWS team](https://knows.idlab.ugent.be) (Ghent University). An AI agent connects to one MCP endpoint and, through it, finds sources in a DCAT catalog, learns domain terms from a vocabulary hub, reads each source's OpenAPI and queries it. Public research and open source only.

| Folder | What it is | Details |
| --- | --- | --- |
| [`dataspace/`](dataspace/) | the generic data space: catalog (broker), vocabulary hub, MCP connector | [README](dataspace/README.md) |
| [`sources/`](sources/) | everything source-specific: proxies, catalog registrations, domain knowledge and the permanent context for the vocabulary hub, end-to-end test | [README](sources/README.md) |
| [`viewer/`](viewer/) | read-only web interface over the catalog and the vocabulary hub, for people (agents use the connector) | [README](viewer/README.md) |
| [`user-profile/`](user-profile/) | how sources map disability profiles to data, and a tool that turns a user's needs and evidence preferences into context for a chatbot (:8095) | [README](user-profile/context-tool/README.md) |
| [`AGENTS.md`](AGENTS.md) | status, rules, decisions, known source quirks, open work, golden questions | for coding agents and maintainers |
| [`sources/source-inventory.md`](sources/source-inventory.md), [`sources/domain-knowledge-inventory.md`](sources/domain-knowledge-inventory.md) | every source and document from the literature study (`literatuurstudie.pdf`): added, candidate, blocked or skipped, with licences | source of truth for what is in and why |
| [`user-profiles.md`](user-profiles.md) | analysis of personal needs and preferences (not built) | read before adding anything profile-related |
| [`dataspace/docs/adr/`](dataspace/docs/adr/) | decision records for the data space's contracts | |

Requirements: Docker with Compose, [uv](https://docs.astral.sh/uv/), and for PictoAccess its export in `sources/pictoaccess/pictoaccess_dump/places/` (not in git; see below).

## Run locally

```bash
make start-full     # data space, sources, viewer and profile tool; then every source and document (first build downloads ~220 MB)
claude mcp add --transport http accessibility-dataspace http://localhost:8800/mcp
```

The `Makefile` in this folder wraps the everyday commands; `make help` lists them:

| Command | What it does |
| --- | --- |
| `make start-public`, `make start-full` | build and start everything, then load the public or the full content set ([which is which](sources/README.md#public-and-full-content)) |
| `make public`, `make full` | switch a running data space to the other set |
| `make restart` / `make stop` | restart or stop every container; registrations, documents and caches stay on their volumes |
| `make update` | `git pull`, rebuild what changed, load the content set again |
| `make reset-knowledge`, `make reset-catalog`, `make reset` | empty the vocabulary hub, the catalog or both, and load the content set again |
| `make status` | what runs and what it holds (datasets, private ones among them, documents, restricted ones) |
| `make calls` | the connector's tool calls, when `CALL_LOG=1` ([Logging tool calls](dataspace/README.md#logging-tool-calls)) |
| `make test` | offline tests of every component |

The last set chosen (`public` or `full`) is remembered in `.content-mode`, so `restart`, `update` and the resets keep it; `MODE=full` overrides it once.

The first start of the Belgian transport proxy downloads about 300 MB of timetable data; its calls return 503 until that is done (a minute or two).

## Deploy to a server

Pick one of two set-ups. All ports are bound to `127.0.0.1` by default, every service restarts after a reboot, and nothing is reachable from outside until you open it.

| Set-up | Runs on the server | Runs on your machine | Open on the server | Guide |
| --- | --- | --- | --- | --- |
| **A. Agent on your machine, connector local** (keys stay local) | catalog, vochub, proxies | connector | 22 (SSH tunnel) | [Running components separately](dataspace/README.md#running-components-separately) |
| **B. Agent anywhere, also ChatGPT** (no authentication: online only during presentations) | everything | nothing | 443 and 80 (Caddy or nginx), 22 | [HTTPS and authentication](dataspace/README.md#https-and-authentication), [Connecting ChatGPT or another web-hosted agent](dataspace/README.md#connecting-chatgpt-or-another-web-hosted-agent) |

For every set-up, first get the code and the PictoAccess export onto the server:

```bash
# on the server
git clone <this repository> data-architecture

# on your machine, from the repository root: only the place files are used (33 MB, not the 2.6 GB of images)
rsync -a sources/pictoaccess/pictoaccess_dump/places/ \
    user@server:data-architecture/sources/pictoaccess/pictoaccess_dump/places/
```

Set-up B needs a reverse proxy on the server. Ready-made configurations for Caddy and nginx are in [Reverse proxy: Caddy or nginx](dataspace/README.md#reverse-proxy-caddy-or-nginx).

Then set `dataspace/.env` (`make up` creates it from `.env.example`): source API keys (`ACCESLIBRE_API_KEY`, `TOEVLA_API_TOKEN`), and `CATALOG_BASE_URL` if you publish the DCAT catalog. Then start with `make start-public` on a published server (set-up B), or `make start-full` elsewhere ([Public and full content](sources/README.md#public-and-full-content)). All settings and ports are listed in [Running on a remote server](dataspace/README.md#running-on-a-remote-server).

First start on a published server: `make start-public`. To update it: `make update` (pull, rebuild, load the set again; safe to repeat, each entry is replaced). After a change to the vocabulary hub's chunking or search, also load the knowledge again (see [Vocabulary hub](dataspace/README.md#vocabulary-hub)).

If a source's API runs on the same server, containers may not reach it through the server's own public address; see [Sources on the same server](dataspace/README.md#sources-on-the-same-server).

No component authenticates its callers. In set-up B the connector is open to anyone with its address, so keep it online only during presentations. Production needs OAuth: web-hosted agents such as ChatGPT accept nothing else. Never publish the vocabulary hub, the catalog's write endpoints or the PictoAccess proxy. In set-up B everything in the data space is readable through the connector, so load it with `make -C sources public`: it leaves out the private sources and the licence-restricted documents ([Public and full content](sources/README.md#public-and-full-content)).

## Licence

Code: MIT (see [dataspace/LICENSE](dataspace/LICENSE)). Data stays under each source's licence, listed in its catalog registration.

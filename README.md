# Accessibility data space demonstrator

A small, runnable data space for accessibility information in Belgium and France, by the [KNoWS team](https://knows.idlab.ugent.be) (Ghent University). An AI agent connects to one MCP endpoint and, through it, finds sources in a DCAT catalog, learns domain terms from a vocabulary hub, reads each source's OpenAPI and queries it. Public research and open source only.

| Folder | What it is | Details |
| --- | --- | --- |
| [`dataspace/`](dataspace/) | the generic data space: catalog (broker), vocabulary hub, MCP connector | [README](dataspace/README.md) |
| [`sources/`](sources/) | everything source-specific: proxies, catalog registrations, domain-knowledge seed, end-to-end test | [README](sources/README.md) |
| [`AGENTS.md`](AGENTS.md) | status, rules, known source quirks, open work, golden questions | for coding agents and maintainers |

Requirements: Docker with Compose, [uv](https://docs.astral.sh/uv/), and for PictoAccess its export in `sources/pictoaccess/pictoaccess_dump/places/` (not in git; see below).

## Run locally

```bash
make -C dataspace up             # catalog, vocabulary hub, connector (first build downloads a ~220 MB model)
make -C sources up register      # source proxies, then register every source in the catalog
claude mcp add --transport http accessibility-dataspace http://localhost:8800/mcp
```

The first start of the Belgian transport proxy downloads about 300 MB of timetable data; its calls return 503 until that is done (a minute or two).

## Deploy to a server

Pick one of three set-ups. All ports are bound to `127.0.0.1` by default, every service restarts after a reboot, and nothing is reachable from outside until you open it.

| Set-up | Runs on the server | Runs on your machine | Open on the server | Guide |
| --- | --- | --- | --- | --- |
| **A. Agent on your machine, connector local** (keys stay local) | catalog, vochub, proxies | connector | 22 (SSH tunnel) | [Running components separately](dataspace/README.md#running-components-separately) |
| **B. Web-hosted agent such as ChatGPT** | everything | nothing | 443 and 80 (Caddy, secret path), 22 | [Connecting ChatGPT or another web-hosted agent](dataspace/README.md#connecting-chatgpt-or-another-web-hosted-agent) |
| **C. Agent anywhere, password-protected** | everything | nothing | 443 and 80 (Caddy, basic auth), 22 | [HTTPS and authentication](dataspace/README.md#https-and-authentication) |

For every set-up, first get the code and the PictoAccess export onto the server:

```bash
# on the server
git clone <this repository> data-architecture

# on your machine, from the repository root: only the place files are used (33 MB, not the 2.6 GB of images)
rsync -a sources/pictoaccess/pictoaccess_dump/places/ \
    user@server:data-architecture/sources/pictoaccess/pictoaccess_dump/places/
```

Then set `dataspace/.env` (`make up` creates it from `.env.example`): source API keys such as `ACCESLIBRE_API_KEY`, and `CATALOG_BASE_URL` if you publish the DCAT catalog. All settings and ports are listed in [Running on a remote server](dataspace/README.md#running-on-a-remote-server).

To update a running server: `git pull`, then `make -C dataspace up` and `make -C sources up register` (registering again is safe; it replaces each entry).

No component authenticates its callers. Never publish the vocabulary hub, the catalog's write endpoints or the PictoAccess proxy without protection; the connector is protected only by what you put in front of it.

## Licence

Code: MIT (see [dataspace/LICENSE](dataspace/LICENSE)). Data stays under each source's licence, listed in its catalog registration.

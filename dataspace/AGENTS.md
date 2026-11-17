# Rules for coding agents

- Public research and open-source only. Never paste non-public material into an agent session; commit only public data and code.
- No secrets in the repo. Source keys go in `.env`; `config/credentials.yaml` holds only `${VAR}` references.
- Crawlers and fetchers honour robots.txt and rate limits and send an identifying user agent.
- One task, one component. Do not change other components' contracts without saying so in `docs/adr/`.
- A task is done when `make check` passes (and `make e2e` in `../sources` for changes that cross components).
- Nothing source-specific in this directory: proxies, registrations, source notes and seed content live in `../sources` and use the data space only through its HTTP APIs.
- Tests run offline: use fixtures, never hit live public sites from unit tests.
- Record non-obvious decisions as a short ADR in `docs/adr/`.

Layout and commands: see README.md. Project status, open work and golden questions: `../AGENTS.md`; full design rationale: `../Accessibility Data Space Demonstrator — Project Plan & Todo List.md`.

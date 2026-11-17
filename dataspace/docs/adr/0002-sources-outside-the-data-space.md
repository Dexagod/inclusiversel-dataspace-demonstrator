# 2. Data sources live outside the data space

Date: 2026-11-16

The data space (catalog, vocabulary hub, connector) is generic; which sources join it is not its concern. Source proxies, their registrations, per-source notes, the domain-knowledge seed and the end-to-end test that exercises specific sources moved to `../sources`, with their own Compose project and Makefile.

- Sources reach the data space only through its HTTP APIs: `sources/seed.py` PUTs `*/registration.json` to the catalog and posts `domain-knowledge.yaml` to the vocabulary hub. The catalog's seed-at-start-up (`SEED_DIR`) and the `vochub/seed.py` script were removed; the data space starts empty.
- The source proxies join the data space's Docker network (`accessibility-dataspace_default`, external) so registrations can keep Docker-internal URLs. A source hosted elsewhere registers its public URL instead.
- The connector's `config/credentials.yaml` stays here: API keys belong to the operator of the connector, not to the sources.

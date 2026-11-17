# 3. Mobility sub-catalogs, copied source DCAT, optional API keys

Date: 2026-11-16

**Mobility sub-catalogs.** Transport and parking datasets go in two more sub-catalogs, `belgium-mobility` and `france-mobility`, next to `belgium` and `france` ([ADR 0001](0001-country-sub-catalogs.md)). They are entries in `CATALOGS` in `catalog/dcat.py`.

**Copying the publisher's DCAT.** A registration may set `source_dcat_url`: the publisher's own DCAT for this one dataset (Turtle, RDF/XML or JSON-LD). At registration the catalog fetches it and keeps that `dcat:Dataset` and its distributions verbatim. It adds them to the DCAT export and links our dataset to the original with `dct:source` (DCAT-AP: the dataset this one is derived from). A document with no or several `dcat:Dataset`s is rejected. Triples with malformed IRIs, such as a publisher name where an IRI belongs, are skipped. Our own registration fields stay the source of truth for search, so an agent still sees one flat record.

**Optional API keys in the connector.** Before, the connector refused to call an operation whose OpenAPI declares a security scheme when no key was configured. Opendatasoft portals declare an API key on every operation, but reads work without one; the key only raises quotas. The connector now always makes the call. If the source answers 401 or 403 and no key is configured, the result carries an `error` saying so. `requires_api_key` in `get_openapi` still reports what the OpenAPI declares.

# 4. Schemas and API descriptions linked in the DCAT export

Date: 2026-11-19

Someone who only traverses the DCAT catalog should find how each source's data is structured and how its API works, without the vocabulary hub or the connector. The export follows DCAT 3 and DCAT-AP 3:

```
dataset   dct:conformsTo        <schema>          # new: published schema, data model or vocabulary
<schema>  a dct:Standard ; dct:title "..."
dataset   dcat:distribution     dist
dist      dcat:accessService    service
service   dcat:endpointURL      <API base URL>
service   dcat:endpointDescription <catalog>/services/{id}/openapi.json   # was: openapi_url
service   dct:conformsTo        <OpenAPI 3.1 spec>
<catalog>/services/{id}/openapi.json  dct:source <openapi_url> ; dct:conformsTo <OpenAPI 3.1 spec> ;
          dct:format <IANA application/vnd.oai.openapi+json>
```

**Schemas.** A registration may list `conforms_to` (`url`, `title`): only published, resolvable schemas (GTFS, an OSLO model, the publisher's own vocabulary). Where a source has none, its OpenAPI document (its response schemas) is the schema. On the dataset, not the distribution: the distributions here are our APIs, whose structure the OpenAPI already describes; the standard describes the data.

**OpenAPI copy.** The catalog already fetched the OpenAPI document at registration to validate it; it now keeps it in the registration record and serves it. Before, `dcat:endpointDescription` pointed at `openapi_url`, which for our adapters is a Docker-internal address (`http://src-...:8000/openapi.json`) that does not resolve outside the data space. The copy is as fresh as the last registration; re-register after an API change (`make register` in `../sources`). `GET /datasets/{id}` leaves the copy out, to keep agent-facing records small. Records registered before this change keep linking `openapi_url` until registered again.

The vocabulary hub may also hold these documents for retrieval; the catalog link is the authoritative one.

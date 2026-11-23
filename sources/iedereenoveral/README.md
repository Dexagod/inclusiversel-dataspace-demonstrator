# IedereenOveral (first data provider)

IedereenOveral (https://iedereen.overal.info) is Inter's platform for the accessibility of cafes and restaurants, public toilets, Changing Places, museums and parking spaces in Flanders and Brussels. It joins the data space through a thin adapter, `sources/iedereenoveral`, that sits in front of its own API.

| | |
| --- | --- |
| Upstream API | `https://xcli-wrwg-eljt.f2.xano.io/api:SuAo_4fA` (Xano) |
| Upstream OpenAPI | `https://xcli-wrwg-eljt.f2.xano.io/apispec:SuAo_4fA?type=json&token=` (OpenAPI 3.0.0, 44 operations) |
| Adapter | `src-iedereenoveral`, port 8102. The full API is at `/` (OpenAPI at `/openapi.json`); one sub-API per kind of place, as on the website, at `/food-and-drink/`, `/toilets/` (public toilets and Changing Places), `/museums/` and `/parking/`, each with its own OpenAPI and the category fixed |
| Catalog ids | `iedereenoveral-food-and-drink`, `iedereenoveral-toilets`, `iedereenoveral-museums`, `iedereenoveral-parking` (`<kind>/registration.json`); the full API is not registered, so each kind is its own dataset |
| Access | Public reads, no key. Writes and account routes need a user bearer token and are not exposed |
| Licence | Not yet confirmed with Inter (`licence_note` in the registration) |
| robots.txt | Allows all (checked 2026-11-12) |

## Flow

```text
agent ─MCP─▶ connector ─▶ catalog: "iedereenoveral-toilets" → endpoint + OpenAPI of /toilets/
                       ─▶ src-iedereenoveral /toilets/places, /toilets/places/{id}, /toilets/facets   (compact, described)
                                └─▶ Xano API /location, /location/{slug}, lookup tables (cached 6 h)
```

1. `make register` (in `sources/`) PUTs the four `<kind>/registration.json` to the catalog, which checks each sub-API's OpenAPI.
2. `catalog_search` finds the right kind for words such as toilet, restaurant, museum, parking, Gent, Flanders.
3. `get_openapi` gives four described operations per kind, e.g. `iedereenoveral_toilets_search_places`, `_get_place`, `_facets`, `_about`.

Museums link to their own website: their detailed information was mapped with the Toegankelijkheidswijzer (Agentschap Binnenlands Bestuur with Inter). Museums and parking spaces have no place confirmed by Inter (checked 2026-11-20); food and drink has 88 of about 430, toilets about 630 of 870.
4. `call_source_operation` calls the adapter, which calls the Xano API live and returns compact records with provenance.

No API key is configured, because the public reads need none. If Inter issues a key later, add the four dataset ids to `config/credentials.yaml` and pass the key on in `app.py:upstream`.

## Why an adapter, and not the raw API

Findings from the upstream OpenAPI and test calls on 2026-11-12:

| Finding | Effect on an agent | What the adapter does |
| --- | --- | --- |
| A place detail is about 130 KB: internal ids, timestamps, image metadata, the full question definition repeated in every answer | Floods the context; the connector truncates at 20 KB and cuts off the accessibility answers | Keeps identity, address, medal, features and the answered questions as `criterion`, `value`, `detail`; about 8 KB (6%) |
| List items hold name, address and medal only inside an HTML snippet (`map_html`) | No usable search results | Parses the snippet into `name`, `address`, `medal`; about 0.5 KB for two places instead of 5.9 KB |
| Filters take numeric ids (`city_select=883` is Gent; a town has one id per postcode); `/city` is 120 KB | The agent cannot find the ids | Takes a town name, English or French alias, or postcode; maps categories, medals and facility names to ids |
| Multi-value filters work only as a JSON array (`city_select=[883,5]`); repeating the parameter keeps only the last value, against the OpenAPI default | Silently wrong results for several towns or filters | Sends JSON arrays upstream |
| `/location/{location_id}` takes the slug, not the numeric id | 404 on the obvious call | Uses the slug as the place id |
| No parameter descriptions; operation ids like `Default/location\|GET`; read, write and account routes mixed | The agent guesses | Four read-only operations with descriptions, allowed values and examples |

Answers stay in Dutch, as in the source; the agent translates. Image questions, unanswered questions and hidden questions are left out.

## Note for Inter

The upstream OpenAPI marks `POST /province`, `PATCH /province/{province_id}` and `DELETE /province/{province_id}` as "Authentication: not required". We did not call them. If that is accurate, anyone can change or delete province records; Inter should check this. The adapter and the connector only send GET requests.

## Maintenance

- New location types upstream: add them to `CATEGORIES` in `transform.py`; until then they appear with their Dutch name.
- If the HTML card format changes, search results lose name, address or medal; `tests/test_adapter.py` pins the current format with recorded fixtures (trimmed, 52 KB).
- Live checks: `make e2e` calls the real API once for a search and once for a detail.

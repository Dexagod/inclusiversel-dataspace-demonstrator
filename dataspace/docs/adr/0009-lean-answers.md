# 9. Lean answers: fewer tokens per tool call

Date: 2026-11-24

Answers felt slow. We replayed a Lille museum question through the connector: 17 tool calls (hub, catalog, three OpenAPI documents, seven source calls). The data space was not the slow part. All 17 calls together spent about 6 s inside the tools, and a hub search takes 0.1 s once the model is warm. But the agent had to read about 270 KB of answers, roughly 70k tokens, over as many model turns, and each turn costs the model seconds. Where the volume came from:

| Where | Size | Why |
| --- | --- | --- |
| Acceslibre search, 8 museums | over 20 KB, cut | most fields are `null`; the cut left a broken JSON string, so the agent had to ask again |
| `get_openapi` of an Opendatasoft dataset | 57 KB | the portal's OpenAPI describes 16 operations (catalog, exports); agents need 2 |
| `catalog_search` without a query | 50 KB | full descriptions (field lists of up to 3.5 KB) in every hit |
| every answer | +35% | the MCP SDK indents JSON |
| every `vochub_search` | 6 KB | the permanent context, repeated |

**Decisions.** Together these took the replayed session from about 270 KB to 142 KB.
- **Compact source answers.** `call_source_operation` drops `null`, `""`, `[]` and `{}` from the data (Acceslibre: 3× smaller). Missing already means unknown in the permanent context. The evidence per record ([ADR 0008](0008-evidence-per-record.md)) is still read from the uncompacted answer, because there a null field and a missing one give a different basis.
- **Cut records, not text.** An answer that is still over `MAX_RESPONSE_CHARS` loses whole records from the end of its biggest list, and says so in `records_cut` (`kept`, `of`). The answer stays valid JSON. Only a single record that is too big is still cut as text (`truncated`).
- **Compact JSON.** Every tool returns its result as one compact JSON text instead of the SDK's indented one.
- **`operations` in a registration.** This optional list names the operations agents need, for an OpenAPI that describes a whole portal. `get_openapi` then shows only those, and the catalog rejects names that are not in the OpenAPI. The Opendatasoft registrations list `getRecords` and `getRecord` (57 KB → 11 KB). Other operations can still be called.
- **Short catalog hits.** `catalog_search` returns the first 300 characters of each description, without the endpoint and OpenAPI URLs. No context is lost: the description's "how to query" part and the field list matter only once a dataset is chosen, and `get_openapi`, which agents call before any source call, now returns the full description as `dataset_description`.
- **Cached OpenAPI documents.** The connector keeps each fetched OpenAPI for an hour (`SPEC_CACHE_S`); every source call used to fetch it again, at up to 0.45 s for the remote APIs.

**Not done, for later:**
- **The permanent context once per session.** It could move to the MCP server instructions, which a client receives once at `initialize`. That needs no state on the server, so it also works with stateless HTTP. Sending it only with the first `vochub_search` does need state, so that option is out. The risk: some clients (possibly ChatGPT) do not show server instructions to the model, so check that on each client first. Gain: about 6 KB per extra hub search.
- **A batch tool** for several source calls in one turn. It only helps clients that cannot call tools in parallel. `make calls` shows whether a client does: its calls overlap in time.
- **A shared place model** that maps every source to one schema (plan 1.5, 2.1). It is not a speed gain, see the analysis below.

**A shared place model, considered.** It would save the agent reading each OpenAPI (here 3 calls, 31 KB) and would make comparing sources easier. Against it:
- The sources do not describe the same things. Acceslibre has some 100 measured fields, IedereenOveral answers a questionnaire, a label covers named disability groups, and GTFS has a 0/1/2 flag. A shared model either drops the detail the answer rules rely on (measured values beat a verdict) or becomes as large as A11yJSON, with a mapping to maintain for each of 24 datasets.
- A mapping error would be invisible to the agent, which now sees the source's own fields.
- The agent already does this mapping at question time, with the schemas in the vocabulary hub.

The part that does pay off is already in place: the `records` block is a small shared model (name, page, date, basis), mapped per registration without code. Extend it field by field when a need shows up, for example address and coordinates to match one place across sources.

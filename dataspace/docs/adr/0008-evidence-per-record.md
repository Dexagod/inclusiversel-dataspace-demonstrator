# 8. Evidence per record: a link and a basis for every place

Date: 2026-11-23

Users should be able to trust each fact in an answer, and check it. Agents cited sources too loosely: a dataset name ("French label dataset"), a homepage, or "check it with the operator". And they wrote "the hotel says" where a certification label backed the fact, because `assessment` ([ADR 0006](0006-assessment-methods.md)) describes a whole dataset, and working out the basis per record meant reading each source's own fields.

**A registration may describe its records.** The optional `records` block says where the records sit in an answer and which fields give each record's own page, date and basis:

| Key | Meaning |
| --- | --- |
| `at` | dotted paths to the records in an answer (a list, or one record under a key such as `place`), tried in order; otherwise the answer itself is one record (a detail) |
| `name` | field(s) holding the record's name; the first filled one wins |
| `url` | field(s) or templates (`https://www.pictoaccess.fr/cards/{slug}`) for the record's own page |
| `date` | field(s) holding when it was assessed or last changed |
| `basis` | rules, first match wins: `field` with `equals` or `present: true`, giving `method` (`certified`, `official`, `self_declared`, `crowd_sourced`, `unknown`), `by`, `label`, `note`; text may hold `{field}` placeholders |
| `default` | the basis when no rule matches |

A rule on a field the answer does not contain makes the basis `unknown` rather than the default: search hits often leave out what only the detail says.

**The connector adds it to the provenance.** `call_source_operation` returns `provenance.records`: per record `name`, `url`, `basis`, `by`, `label`, `date`, in the answer's order (at most 50). Sources without a `records` block get `provenance.basis`, the dataset's `assessment`. Every answer also carries `dataset_page` (the registration's landing page) when there is one. The permanent context tells agents to cite each fact with its record's `url`, to name who backs it, and to prefer a data-space record over a web page for a place found in the data space.

**Why in the registration and the connector, not in each adapter:** most sources are called directly (Acceslibre, the Opendatasoft portals), so only a declaration next to the source can describe them, and one mechanism then serves adapters and direct APIs alike. Adapters only need to return a page link where the publisher has one: IedereenOveral already did (`source_url`); PictoAccess now returns `https://www.pictoaccess.fr/cards/<slug>`, and Toerisme Vlaanderen its linked-data URI, which opens as a page. The IedereenOveral adapter also marks `confirmed_by_inter` in search hits now, by running the same search with Inter's filter in parallel.

**Not done:** comparing the same place across sources (matching by address or coordinates is unreliable) stays with the agent, which gets the evidence per record as input. Records without a page of their own (ToeVla, the transit stops) are cited by their dataset.

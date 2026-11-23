# 6. How the facts were collected: `assessment`

Date: 2026-11-20

Accessibility facts differ in how much they can be trusted. A label or an on-site check by an independent body (Inter, Access-i, Tourisme & Handicap) validates a set of facts; a venue describing itself, or anyone editing a map, does not. Agents comparing sources need to know which is which, per dataset and, where the source says so, per record.

**A registration gets an optional `assessment`:**

| Field | Meaning |
| --- | --- |
| `methods` | one or more of `certified` (a label or on-site check by an independent body), `official` (the owner or operator: transport operator, municipality, government), `self_declared` (the venue itself), `crowd_sourced` (anyone can edit) |
| `note` | in words, which field marks the method per record, e.g. IedereenOveral `confirmed_by_inter`, Acceslibre `user_type`, Toerisme Vlaanderen `a_label` |

The catalog validates the values, returns `assessment` in search hits and `GET /datasets/{id}`, and exports it as `dct:provenance` with a `dct:ProvenanceStatement` whose `rdfs:label` reads "Collection methods: … . <note>".

**The ranking is left to the agent.** The permanent context in the vocabulary hub ([ADR 0007](0007-vocabulary-hub-context-summaries-hybrid-search.md)) tells it to prefer certified facts, then official ones, then self-declared and crowd-sourced ones; to say so, and check the web, when only one weak source exists; and to compare facts side by side, with their dates, when several sources describe a place. The catalog does not sort by method, because the right order depends on the question.

**Why not a per-record field in the catalog:** the catalog describes datasets, not places. Only the source knows which records are verified, so the `note` points the agent to that field.

The method per source, as checked on 2026-11-20, is listed under "Labels and verification per source" in [AGENTS.md](../../../AGENTS.md).

# 11. Proposed: one place search across sources

Date: 2026-11-24. Status: proposed, not built.

**What we saw.** Grok answered a trip question: a weekend in Lille with a grandmother who walks with a rollator, with a hotel, quiet cultural visits and food in the centre. It made 10 tool calls. It used Acceslibre, Tourisme & Handicap and SNCF, and skipped PictoAccess, although PictoAccess was the first hit of its catalog search. Every extra source costs an agent two turns (read the OpenAPI, then call it) and some guessing of parameters. One of the calls came back empty because Tourisme & Handicap stores the town as `LILLE`. A distance of "within 1 km" was a guess, and the user's question was never compared across sources. PictoAccess covers Lille only thinly (65 places, mostly municipal services, 29 with accessibility levels), but it has the Cathédrale Notre-Dame de la Treille next to the Hospice Comtesse, which an agent should have weighed.

**The proposal.** A connector tool that searches every source covering an area in one call, in parallel, and merges what they say about each place.

```
find_places(near="50.6366,3.0700", radius_m=800, category="culture")   # discover places around a point
find_places(names=["Hospice Comtesse", "Novotel Lille Centre Grand Place"], town="Lille")   # look up places found elsewhere
```

It returns one list. Per place it gives: name, address, coordinates, the distance to `near`, and per source the basis, by whom, the proof link, the website, the date and a few key facts. Places from different sources that lie within about 50 m of each other and have similar names are grouped as one place. The comparison is then done by code, not by the agent.

**Per source, a `search` block in the registration** says how to run it:
- which operation to call;
- how `town`, `near`, `radius_m` and the free text map onto its parameters (templates, e.g. `where: ville="{TOWN}"`);
- its own words for a handful of categories: hotel, restaurant, culture, toilet, station;
- which fields hold the address and the coordinates.

This grows the `records` block of [ADR 0008](0008-evidence-per-record.md) by a few fields, as [ADR 0009](0009-lean-answers.md) suggests, instead of mapping every source to a full shared data model.

**Keep the agent's own way of working.** On the web, agents usually find candidates on a map first (places near the station), then look up accessibility per place. The tool should support that flow, not replace it. Hence the second form: the agent brings names, or names with coordinates, from its own map or web search, and gets every source's evidence for them in one call. `call_source_operation` stays for details and for sources without a `search` block. The tool must say which sources it searched and which had nothing, so a silent gap does not look like "not accessible".

**Expected gain.** About 10 calls become 1 or 2. Every source covering the area is always checked. Distances become computed facts. Comparing sources gets concrete input.

**Costs and risks.**
- A `search` block per source, to be kept up to date.
- Matching places across sources by name and distance will sometimes be wrong. So the tool groups places but never merges their facts.
- Category words never map exactly (Acceslibre `activite` slugs, Tourisme & Handicap `activite`, PictoAccess categories).
- Geocoding a place name to `near` is left to the agent, which knows most landmarks. A geocoding tool is an open question in the plan.

**Related open point: rules versus knowledge.** Each lesson from a trace tends to become one more rule in the permanent context (call the live lift status for every station; Tourisme & Handicap stores towns in capitals). That does not scale. Source-specific lessons now go into the source's own description (the `hint` in `opendatasoft/datasets.yaml`), which agents read only when they use that source. Whether general lessons belong in the permanent context, in retrieved hub passages, or in a tool like this one is a question for the related-research review.

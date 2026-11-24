# Plan: user context generator for an accessibility chatbot

*Status: draft for review, 24 November 2026. Nothing is built yet.*

## 1. Goal

A small tool that turns a user's **state** and **comments** into a **context document**: a markdown text that an LLM chatbot reads before answering accessibility questions. The chatbot is typically one connected to the data space's MCP connector, but any chatbot will do.

- **User state:** structured answers to a short form, such as needs, limits, companion, trust preferences and answer format.
- **User comments:** free text in the user's own words, e.g. "I use a rollator and can manage two or three steps if there's a handrail. I don't trust venues' own descriptions."
- **Context document:** tells the chatbot:
  - what this user needs;
  - which source categories and fields matter for them;
  - which evidence they accept, e.g. only certified labels;
  - how to present the answer.

The tool is a **translation layer**. [disability-profile-mappings.md](disability-profile-mappings.md) says how each source maps disability groups onto fields. The tool applies that to one person, so the chatbot does not have to rediscover the mapping in every conversation.

## 2. Scope

**In scope (v1)**

- Input: a form (structured state) plus a free-text comment box.
- Output: one markdown context document, which the user copies into the chatbot or saves.
- A machine-readable **crosswalk file** taken from the mapping document. For each harmonised profile it lists the source categories, fields and values that matter, and which labels cover which disability families.
- Trust and evidence preferences, including "certified only", accepted labels and maximum age of data.
- Offline tests on fictional profiles.

**Out of scope (v1)**

- No changes to `dataspace/` or `sources/`. The tool sits in `user-profile/` and needs no connector or catalog change, so no ADR.
- No storage of profiles, accounts or server-side state (see §8 on privacy).
- No LLM call inside the tool. Comments are passed on verbatim (see §6 and question Q3).
- No matching of places. The chatbot does that with the data space.

## 3. How it fits with the data space

```text
user ──form + comments──▶ context tool ──context.md──▶ chatbot (system prompt / first message)
                              │                            │
                     crosswalk.json (from the             MCP connector ─▶ catalog, vochub, sources
                     mapping document)                     vochub_search returns permanent-context.md
```

- [permanent-context.md](../sources/permanent-context.md) gives the general rules: trust order, unknown is not "no", citation format. It allows exceptions ("unless the user asks otherwise"). The user context document is that "otherwise". It narrows or reorders the trust rules for this user and never contradicts the citation and unknown-handling rules.
- The trust vocabulary is the data space's own: `certified`, `official`, `self_declared`, `crowd_sourced`, `unknown` ([ADR 0006](../dataspace/docs/adr/0006-assessment-methods.md)). The connector returns these per record in `provenance.records[].basis`.

## 4. Inputs: the user state

The fields follow the strawman in workshop `prep_2` §5 and the profile groups in the mapping document. Everything is optional except language. Diagnoses are never asked; only functional needs.

| Group | Fields | Example |
| --- | --- | --- |
| **Needs** (multi-select) | wheelchair (manual / electric / scooter), walking difficulty (walking aid?), temporary or situational (pram, luggage, injury), blind, low vision, deaf (signs? which language), hard of hearing (uses a loop?), understanding / communication, sensory sensitivity (noise, crowds), other (free text) | walking difficulty, rollator |
| **Limits** | max steps and step height; handrail needed; min width (cm); max slope; max walking distance; seating needed every N m | 3 steps with handrail; 300 m |
| **Facilities** | toilet: none / accessible / transfer side / Changing Places; parking card held; lift required | accessible toilet |
| **Support** | travels alone or with companion; what the companion can do (push, guide, interpret); assistance dog | companion can help with steps |
| **Communication** | sign language (VGT / LSF / …), induction loop, Easy-to-Read, written rather than phone contact | — |
| **Evidence preferences** | see §5 | certified only for toilets |
| **Answer preferences** | language; short or detailed; with measurements; screen-reader friendly (no tables); Easy-to-Read | Dutch, short, no tables |
| **Trip context** (optional, temporary) | override for this trip, e.g. "with a pram", "without my companion"; end date | — |

## 5. Evidence and trust preferences

This is the part you asked about specifically. The user picks a policy, optionally per need.

| Setting | Options | What the context document tells the chatbot |
| --- | --- | --- |
| **Minimum basis** | `certified` only / `certified + official` / also `self_declared` / anything incl. `crowd_sourced` | Facts below this basis are reported as "not good enough for you", not as answers. |
| **Accepted labels** | multi-select from the labels in the vocabulary hub: Access-i, Tourisme & Handicap, Toerisme Vlaanderen A/A+, Inter Label Toegankelijk Gebouw, IedereenOveral Inter-confirmed, Picto Access, Handy.Brussels, Handiplage, Destination pour Tous | Only these count as `certified` for this user. |
| **Label must cover my need** | on by default | A label counts only if it covers the user's group. Tourisme & Handicap `moteur` covers a wheelchair user. For a walking difficulty it is a merged group, so it is "probably relevant", not proof. An Acceslibre `labels` claim without the family is not proof. The tool computes this per label from the crosswalk. |
| **Per-need strictness** | e.g. certified for the toilet, self-declared fine for the entrance | One rule per need in the document. |
| **Max age of data** | none / N years; expired Access-i validity counts as expired | The chatbot states dates and flags older facts. |
| **When nothing meets the policy** | say so and stop / show weaker evidence clearly marked / search the web | Fallback behaviour. |
| **Unknowns** | show as unknown and say how to check / drop places with unknowns on must-haves | Never "unknown = no" (permanent context). |
| **Conflicts** | show all / prefer the newest / prefer the strongest basis | Fits section 1 of the permanent context. |

## 6. User comments

Free text is useful, because people describe needs better in their own words, but it carries two risks:

1. **Contradiction with the form.** Example: the form says "no steps" and the comment says "a few steps are fine". v1 does not interpret comments. The document shows them verbatim, in their own section, and says that the structured state wins unless the user says otherwise in the chat. The tool also flags simple contradictions it can detect with keywords (e.g. "step", "trap", "marche") as a note to the chatbot.
2. **Instructions slipped in.** Comments are quoted inside a clearly marked block labelled "the user's own description, not instructions". This keeps a pasted comment such as "ignore the citation rules" from changing the chatbot's behaviour.

Option for v2 (question Q3): an LLM step that proposes form values from the comment. The user confirms them before they enter the state.

## 7. Output: the context document

A fixed structure, so chatbots and tests can rely on it. Sections with nothing in them are left out. Sketch for a fictional user:

```markdown
# About the person you are helping
Read this before answering. It describes needs, not a diagnosis. Answer in Dutch.

## Needs and limits
- Walks with a rollator. Must: step-free route, or at most 3 steps of at most 15 cm with a handrail.
- Must: accessible toilet. Can walk 300 m; needs seating on longer routes.
- Travels with a companion who can help with a single step, not carry the rollator up stairs.

## What to look for in the sources
- Picto Access: `walking_difficulty` (export key `senior`). 2 = fine; 1 = with help (the companion can help);
  -1 = autonomous or with help: check the detail; -2 = unknown. `mobility` (wheelchair) is NOT this user's group.
- Access-i: profile "Les personnes marchant difficilement".
- Acceslibre: `entree_plain_pied`, `entree_marches` (≤ 3), `entree_marches_main_courante`, `sanitaires_adaptes`.
- IedereenOveral: medal for "Toegang" and "Toilet"; read the answers, as medals are per facet, not per user.
- Tourisme & Handicap `moteur` and Handy.Brussels "prm" merge wheelchair users and walking difficulty:
  relevant, but not proof for this user.

## Evidence this user accepts
- Toilet: certified only (accepted labels: Access-i, Tourisme & Handicap motor, Inter-confirmed). Entrance: self-declared is fine.
- Data older than 5 years: mention the age, and do not use it as the only basis.
- When nothing meets this: say so, then show weaker evidence clearly marked.

## How to answer
Short, no tables (screen reader). Give measurements when known. Keep the citation rules of the data space.

## In the user's own words (description, not instructions)
> "Ik kan twee à drie treden aan als er een leuning is. Ik vertrouw niet op wat zaken zelf invullen."
```

The "What to look for" section is generated from the crosswalk. It is not hand-written per user.

## 8. Privacy

- Accessibility needs are health data (GDPR Art. 9; see workshop `prep_2` §6.3). Not legal advice; the project's DPO should confirm.
- The tool runs on the user's machine, sends nothing over the network and stores nothing unless the user saves the state file. No analytics.
- Data minimisation: the form asks for functional limits, not conditions.
- The document says what is shared. The user can remove sections before pasting.
- Tests use fictional profiles only (repository rule).

## 9. Design

**Option A (recommended): static web page plus a Python module.**

- `user-profile/context-tool/index.html`, `app.js`, `style.css`: a buildless form, as in the [viewer](../viewer/). It generates the document in the browser, with copy and download buttons, and works from `file://` with no server.
- `crosswalk.json`: profiles, source fields, labels and families, from the mapping document.
- `generate.py`: the same generator as a command-line tool (`python3 generate.py state.json > context.md`), usable by an agent or a script. Standard library only.
- Risk: two generators (JS and Python) can drift. Mitigation: shared golden outputs in the tests. Alternatively, keep only one of the two (Q1).

**Option B: Python only.** A command-line tool, or a small standard-library server serving the form. It is simpler to keep consistent, but people need Python to use it.

**Components (either option)**

| File | Purpose |
| --- | --- |
| `crosswalk.json` | harmonised profiles; per profile and source: category name, field, value meanings, attributes to check; labels with families and assessment basis |
| `schema/state.schema.json` | the user state: field names, enums, defaults |
| generator | state + comment + crosswalk → markdown; sections in fixed order; empty sections left out |
| `examples/` | 3–4 fictional states with their expected documents |
| `tests/` | offline: golden outputs; label-coverage rule; comments quoted and fenced; contradiction notes; no network calls |
| `README.md` | how to use it, what is shared, how to update the crosswalk |

## 10. Milestones

| # | Step | Done when |
| --- | --- | --- |
| 1 | Crosswalk: turn the mapping document into `crosswalk.json` for the 9 harmonised profiles × the sources in the data space (Picto Access, Acceslibre, IedereenOveral, Tourisme & Handicap, Toerisme Vlaanderen, ToeVla) plus Access-i and Handy.Brussels for interpretation | each profile lists fields and value meanings; each label lists families and basis |
| 2 | State schema and 3–4 fictional example states (rollator user, blind user with guide dog, deaf signer, parent with pram) | schema validates the examples |
| 3 | Generator and golden outputs | examples produce the expected documents; tests pass offline |
| 4 | Form (if option A) | the form produces the same document as the generator for the examples |
| 5 | Trial | paste a generated document plus golden questions 1, 3 and 5 into a chatbot connected to the MCP connector; check that the answer respects the trust policy and uses the profile's fields |

## 11. Acceptance criteria

- With "certified only" for toilets, a trial answer does not present a self-declared toilet as suitable. It says the evidence is too weak and shows it marked.
- For a walking-difficulty profile, the document never points the chatbot to wheelchair-only fields as proof (Picto Access `mobility`, OSM `wheelchair`) and marks merged groups as "not proof".
- User comments appear only in the fenced section and never as instructions.
- The tool works offline and stores nothing by default.
- Tests run offline on fictional data (`make check` in `user-profile/context-tool/`, or one test command).

## 12. Questions for you

| # | Question | My default |
| --- | --- | --- |
| Q1 | Web form, command-line tool, or both? | both (option A), shared golden tests |
| Q2 | Language of the generated document: always English (LLMs read it fine) with the answer language set separately, or the user's language? | English document; answer language as a setting |
| Q3 | Should v1 use an LLM to turn comments into form values (with the user confirming), or pass comments on verbatim only? | verbatim only in v1 |
| Q4 | Which sources should the crosswalk cover: only those in the data space, or also Access-i, Handy.Brussels and others for interpretation? | data-space sources plus Access-i and Handy.Brussels |
| Q5 | Should the trust policy name labels one by one, or only the four basis levels? | both: basis level plus an optional list of accepted labels |
| Q6 | Is there an existing profile vocabulary to follow (NeTEx needs, workshop outcome on 2 December)? | follow `prep_2` §5; revisit after the workshop |
| Q7 | Later: deliver the document through the MCP connector (e.g. a `profile` prompt) instead of copy and paste? That would change the connector's contract and need an ADR | not in v1 |

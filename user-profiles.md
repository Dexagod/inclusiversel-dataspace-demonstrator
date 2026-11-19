# User profiles: personal accessibility needs in the data space

Status: analysis, 2026-11-19. Nothing here is implemented. Written for the KNoWS team working on the demonstrator.

**Question.** A person has specific needs, constraints and preferences: a wheelchair 72 cm wide, no steps above 2 cm, a Changing Places toilet, a hearing loop, an assistance dog, a quiet place. How can answers from the data space take those into account, and where should the profile live: in the public chatbot, in the connector, or somewhere else?

**Short answer.** Keep the data space and the connector stateless. The profile stays with the user. In phase 1 it lives in the chatbot or client; in phase 2 it can live in a store the user controls, such as a Solid pod. The data space adds two things:
- a shared vocabulary of needs (in the vocabulary hub);
- a stateless "check these needs against this place" helper that receives only the needs relevant to one question, and never an identity.

Server-side profiles in the connector are the option to avoid.

## 1. What a profile holds

| Kind | Examples | How to treat it |
| --- | --- | --- |
| **Hard constraints** (must hold) | door and path width ≥ 80 cm; no step above 2 cm; accessible toilet with transfer space; lift if not on the ground floor; no gluten | filter, but only on facts the source *states*; never on missing data |
| **Needs with tolerance** | a step of ≤ 2 cm is fine if a ramp is available; "with help" is acceptable when travelling with a companion | rank, and show the deviation |
| **Preferences** | prefers an A+ label over A, quiet hours, staff trained in sign language | rank only |
| **Context** (per trip, not per person) | travelling with an assistant; temporary injury; bringing an electric beach wheelchair | given per question, not stored |
| **Language and format** | answer in Dutch; easy-read; no images | client-side; never sent to sources |

**Unknown is not "no".** Most places have gaps: Acceslibre returns `null` for unfilled fields, De Lijn's GTFS uses `0` for "no information", and OSM tags are often missing (see "Facts learned" in [AGENTS.md](AGENTS.md)). A profile check must give three outcomes per need: *met*, *not met* and *unknown*. A place with unknowns is never presented as unsuitable, and never as suitable either.

### Mapping needs to what the sources say

Each source rates accessibility in its own terms. A need such as "I use a manual wheelchair" maps to different fields per source:

| Source (dataset id) | What it gives for that need | Granularity |
| --- | --- | --- |
| `iedereenoveral` | medal (gold, silver, bronze, ok, none) and questionnaire answers with measurements such as door widths | measured |
| `pictoaccess` | level per disability type, e.g. `mobility`: autonomous / with_help / inaccessible / unknown | verdict per group |
| `acceslibre` | entrance, path, toilet and room fields; `null` = unknown (field names to check per need) | measured or yes/no |
| `toerismevlaanderen` | A / A+ label; `support` flags (motor, visual, blind, auditive, deaf, mental, autism, allergies, …); free texts per topic | label + flags + text |
| `stib-stops`, `tec-stops`, `delijn-stops` | GTFS `wheelchair_boarding`: accessible / not_accessible / unknown | per stop |
| `irail-stations`, `sncf-*` | ramp, lift, induction loop; live lift status (`sncf-lift-status`) | per station, some live |
| `osm-accessibility`, `onwheels` | `wheelchair=yes/limited/no`, `toilets:wheelchair`, `hearing_loop`, `door:width`, `kerb:height` | per tag, often missing |

These translations are domain knowledge, so they belong in the **vocabulary hub**. Plan item 2.17, a SKOS mapping of equivalent terms, is the natural home: for example, "need: step-free entrance" maps to Acceslibre's step-free entrance field, OSM `wheelchair=yes`, and the PictoAccess `mobility` level `autonomous`. The skill (open work 5) then tells the agent to apply that mapping.

### Ground the profile in an existing model

Don't invent a profile format. Candidates:

| Model | What it is | Fit |
| --- | --- | --- |
| **ISO/IEC 24751** (Access for All, "personal needs and preferences") | ISO standard for describing a person's needs and preferences, originally for adapting digital learning resources | good conceptual base (needs vs preferences); its vocabulary is about digital content, not buildings |
| **A11yJSON** (Sozialhelden, used by Accessibility.Cloud) | open schema for the accessibility of *places* (entrances, toilets, widths in units) | best match for the place side; a profile could express its constraints as conditions on A11yJSON fields |
| **schema.org** `accessibilityFeature` / `accessibilityHazard` | properties mainly for creative works and digital content | weak for buildings; useful for media and events |
| **GPII / Cloud4all preference sets** | earlier EU work on portable personal preferences | to check: current status and maintenance |

Suggestion: describe constraints as conditions over A11yJSON-like place properties, and keep the needs-versus-preferences split from ISO/IEC 24751. Accessibility.Cloud is already a candidate source (source inventory, candidate 3), so this also prepares for that.

## 2. Where the profile can live

| Option | How it works | For | Against |
| --- | --- | --- | --- |
| **(a) In the chatbot / client** | the user tells their assistant, or it sits in the assistant's memory or custom instructions, or a local file for Claude Code; the agent applies it when it plans calls and reads results | no change to the data space; no health data on our servers; works today with Claude and ChatGPT | not portable between assistants; the user's needs go to the LLM provider (see §3); quality depends on the agent following the skill |
| **(b) In the connector** | per-user profile stored server-side; tools such as `search_for_me` filter and rank | consistent behaviour across clients; one place to improve matching | needs user identity, so OAuth on the MCP endpoint; we become controller of special-category data (§3); the connector stops being a stateless door; ChatGPT set-up B (secret path) has no identity at all |
| **(c) A store the user controls** (Solid pod, credential wallet) | the profile lives in the user's pod; the client, or the connector acting for the user, reads the parts the user grants, per request | the user owns and revokes it; portable across assistants; fits the KNoWS team's Solid work and data-space thinking (sovereignty, usage policies) | needs a Solid-capable client, or connector auth to the pod; more moving parts; public chatbots can't read a pod themselves today |
| **(d) In the sources** | — | — | no: sources must never learn who asks or why |

**Recommendation: (a) now, (c) as the research step, avoid (b).** In all options the *matching logic* can be a shared, stateless piece (§4). Only *where the profile is stored* differs.

## 3. Privacy and law

- **Special-category data.** A profile that says "uses a wheelchair", "is deaf" or "has autism" is data concerning health under GDPR article 9. Processing it needs a legal ground, in practice explicit consent (art. 9(2)(a)), plus data minimisation, purpose limitation and security. Storing profiles server-side (option b) makes the operator a controller of such data. That is a heavy commitment for a research demonstrator.
- **Leaks into source calls.** `call_source_operation` passes parameters to third-party APIs, and the connector echoes the full `request_url` in `provenance` (`dataspace/connector/server.py`). A query such as `wheelchair=yes&near=<home address>` tells the source something about the user. The rule: send sources only *place* filters (town, category, generic facility filters), never identifiers, home locations or the full profile. Filtering on sensitive needs that need not go upstream happens on our side or in the client.
- **Leaks to LLM providers.** With a public chatbot, everything the user states goes to the provider (OpenAI, Anthropic, …) under the user's own agreement with them. We can't prevent that. We can avoid *adding* to it: don't push stored profiles into the conversation unless the user asks.
- **Logs.** Reverse-proxy access logs and any future connector logging would capture tool arguments. The nginx example already sets `access_log off` for the MCP path (`dataspace/README.md`, "Reverse proxy: Caddy or nginx"). Keep it that way for any profile-carrying tool.
- **Organisation rule.** Public research and open source only, so demo profiles must be fictional personas, never real users' data. Personas also make the golden questions repeatable.

## 4. How it would flow technically (MCP)

Three ways to bring a profile into an MCP interaction, in order of preference:

1. **Needs as tool arguments.** A new stateless tool (name to decide), for example `check_needs(dataset_id, place_id, needs=[…])`. It fetches the place through the existing source call and returns per need: `met` / `not_met` / `unknown`, the evidence (field, value, source, retrieval date, licence) and a short explanation. The client sends only the needs relevant to the question. Nothing is stored, and the same tool serves all clients.
2. **Profile as an MCP prompt or resource.** The connector offers a *template* ("describe your needs as …", with the vocabulary from §1). The user, or the client, fills it in. That helps assistants ask the right questions; the filled-in profile stays client-side.
3. **Client-side only.** The agent receives the normal results and applies the profile itself, guided by the skill (plan step 7, "map each source's criteria to the user's need"). This is the zero-change baseline and works today.

**Filter or rank.** Hard filtering at the source discards places whose data is merely incomplete. Use source-side filters only where the source has an explicit field that the user marks as hard. Rank everything else, and show unknowns separately: "3 places meet all your needs; 5 more might, but these facts are unknown: …".

**Explain per need, with citations.** Every match claim cites the source field and value; the skill already requires source, URL, date and licence. When sources disagree (e.g. the PictoAccess verdict vs Acceslibre's measured width), show both. For transit, add the live parts where they exist: a lift that is "operational right now" (`sncf-lift-status`) matters more to a wheelchair user than a static flag.

## 5. Public chatbots connecting

- **What they bring.** Claude and ChatGPT have their own memory and custom instructions, so a user can already say "remember I use a 72 cm wheelchair and need a transfer toilet". Option (a) works without any change on our side.
- **What they can't do.** They reach the connector through set-up B (secret path, no authentication) or set-up C (basic auth; ChatGPT can't send it). In set-up B the connector has no idea *who* is calling, so per-user state (option b) is impossible there without OAuth. The MCP specification defines OAuth-based authorization, but adding it means running an authorization server and user accounts: a product decision, not a demo tweak.
- **Why stateless is safest.** No accounts, no stored health data, and no difference in behaviour between clients beyond what the user tells their own assistant. The connector stays "the single door" from the plan, and its tools stay read-only.

## 6. Recommendation and phases

| Phase | What | Where | Effort |
| --- | --- | --- | --- |
| **1 (with the skill, open work 5)** | Needs vocabulary and source mappings (§1) in the vocabulary hub; skill steps that ask for needs, separate hard from soft, and report met / not met / unknown per need with citations; 2 or 3 fictional personas added to the golden questions | `sources/` (hub documents), `agent/skills/` | small; no contract change |
| **1b** | Optional stateless `check_needs` tool in the connector (§4.1); a contract change, so it needs an ADR | `dataspace/connector/` | medium |
| **2 (research)** | Profile in a Solid pod in the A11yJSON-like format, read by a Solid-aware client, or by the connector with the user's grant, per request; usage policy "only for this query" | new component outside `dataspace/` | larger; good fit for KNoWS research |
| **Avoid** | server-side profiles in the connector without auth, consent and a DPIA; sending profiles or home locations to sources; real users' profiles in the demonstrator | — | — |

## Open questions for you

1. Is the profile a research topic in its own right (Solid, usage policies), or only a demo feature? That decides whether phase 2 is in scope.
2. Which needs come first for the congress demo: mobility only, or also sensory, autism and allergies?
3. Should `check_needs` be a connector tool (shared, testable) or only skill instructions (zero code)? A tool makes the met / not met / unknown logic consistent across agents.
4. Which personas should the golden questions use, and who reviews them with disability organisations (e.g. Inter) for realism?
5. If profiles are ever stored server-side, who is the controller, and is a DPIA needed? Ask the UGent data protection officer before building it.

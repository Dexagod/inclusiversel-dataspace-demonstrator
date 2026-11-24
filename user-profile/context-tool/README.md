# Profile context tool (first iteration)

Turns a user's accessibility needs, evidence preferences and own comments into a **context document**: markdown that an LLM chatbot reads before answering. That is usually a chatbot connected to the data space's MCP connector. Research software; plan and rationale in [../context-tool-plan.md](../context-tool-plan.md), source mappings in [../disability-profile-mappings.md](../disability-profile-mappings.md).

Python 3.10+, standard library only. Runs locally, makes no network calls, stores nothing.

## Use

```bash
make up                                     # Docker service on http://127.0.0.1:8095 (also started by the root `make start`)
make down
make run                                    # without Docker (PORT=... to change)
python3 generate.py examples/rollator.json  # command line: state file in, markdown out
make check                                  # offline tests on fictional profiles
make golden                                 # rewrite examples/*.md after an intended change; review the diff
```

In the form, the document updates as you type. **Copy** or **Download .md** it and paste it into the chatbot as the first message or system prompt. **Save profile** writes the state as JSON, and **Load profile** reads it back. Nothing is kept by the server: it does not log requests.

The page uses the [viewer](../../viewer/README.md)'s `styles.css` and `favicon.svg`, served from `viewer/static`, so the two interfaces look alike without a copy. The container gets them through a read-only mount. Without Docker, set `VIEWER_STATIC` if the viewer is elsewhere.

### On a server, behind Caddy or nginx

On a server the tool is published under `/profile/`, next to the viewer under `/viewer/`, e.g. https://dataspace.example.org/profile/. `make start-public` (or `make start-full`) starts it; the proxy forwards the prefix to `127.0.0.1:8095`. All paths are relative, so the tool also works at the root. The proxy blocks for `/profile/` → `127.0.0.1:8095` are in "Reverse proxy: Caddy or nginx" in [dataspace/README.md](../../dataspace/README.md). Unlike the viewer, the tool needs `POST /generate`; the snippets let only that `POST` through.

Settings in `user-profile/context-tool/.env`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `PROFILE_BIND` | `127.0.0.1` | address the port binds to; leave it for a proxy on the same machine |
| `PROFILE_VIEWER_URL` | empty: `../viewer/` (= `/viewer/`) behind the proxy, `http://localhost:8090/` otherwise | the sidebar's link to the viewer; set it only if the viewer lives elsewhere |

A profile sent to a published tool crosses the network, so serve it over HTTPS only and keep the proxy's access log off. The tool itself stores and logs nothing.

## The state

A JSON object; every part is optional. See [examples/](examples/) for complete files.

| Key | Content |
| --- | --- |
| `language` | answer language: `nl`, `fr`, `en`, `de` |
| `needs` | any of the profiles in `crosswalk.json`: `wheelchair`, `walking_difficulty`, `temporary_mobility`, `blind`, `low_vision`, `deaf`, `hard_of_hearing`, `cognitive`, `sensory_sensitivity` |
| `details` | `wheelchair_type`, `walking_aid`, `sign_language`, `other` (free text) |
| `limits` | `max_steps` (0 = step-free), `max_step_height_cm`, `handrail_needed`, `min_width_cm`, `max_slope_pct`, `max_walk_m`, `seating_every_m` |
| `facilities` | `toilet` (`accessible`, `transfer_left`, `transfer_right`, `changing_places`), `lift_required`, `parking_card` |
| `support` | `companion` (true/false), `companion_can` (`push`, `single_step`, `guide`, `interpret`, `transfer`), `assistance_dog` |
| `communication` | `sign_language`, `induction_loop`, `subtitles`, `easy_to_read`, `written_contact` |
| `evidence` | `min_basis` (`certified`, `official`, `self_declared`, `crowd_sourced`; the data space's `assessment` values), `per_need` (e.g. `{"toilet": "certified"}`), `accepted_labels` (ids in `crosswalk.json`), `label_must_cover_need` (default true), `max_age_years`, `when_nothing_meets` (`show_weaker_marked`, `say_so`, `search_web`), `unknowns` (`show`, `exclude_must`), `conflicts` (`show_all`, `newest`, `strongest`) |
| `answer` | `length` (`short`, `detailed`), `measurements`, `screen_reader`, `easy_to_read` |
| `trip` | `note`, `until`: a temporary situation that overrides the usual needs |
| `comment` | the user's own words |

Unknown needs, labels or option values are rejected with a message. Unknown keys are ignored.

## How it decides

- **Per need**, the document lists what to use (source, dataset ids, field, value meanings). It also lists what is related but merged with other groups, and what must not be used as proof. Example: Picto Access `mobility` is not proof for someone who walks with difficulty. All of this comes from `crosswalk.json`.
- **Labels** count as certification only if the user accepts them, and by default only for the groups they cover:
  - `yes`: proof for that group.
  - `merged`: relevant, not proof. For example, Tourisme & Handicap `moteur` for walking difficulty.
  - `facts`: the checked facts count, not a verdict. Examples: Inter-confirmed IedereenOveral records and ToeVla screenings.
  - Labels that a venue only claims (Acceslibre `labels`) never count as certification.
- **Comments** are quoted in their own section, marked as a description and not as instructions. The form wins where they conflict. Simple contradictions are flagged: steps against step-free only, being alone against having a companion, a dog against no assistance dog.
- The document adds to the data space's [permanent context](../../sources/permanent-context.md). It never relaxes its citation rules or its rule that unknown is not "no".

## Not in this iteration

- No LLM step to turn comments into form values.
- No delivery through the MCP connector; that would change the connector and need an ADR.
- No separate JSON Schema file: validation lives in `generate.py`.
- The mapping file covers the sources in the data space, plus Access-i and Handy.Brussels for interpretation. Update it together with the mapping document.

Profiles describe needs, which count as health data (GDPR Art. 9). Keep real profiles out of the repository; the examples are fictional.

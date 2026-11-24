# From disability profiles to data: how each accessibility source maps users onto fields

*Status: working document, 24 November 2026. Covers every source in section 2.2 ("Bronnen en aggregatie van toegankelijkheidsinformatie") of the literature study ([literatuurstudie.pdf](../literatuurstudie.pdf), pp. 11–25).*

## Purpose and scope

For each source this document answers three questions:

1. **Profiles.** Which user groups or disability categories does the source distinguish, if any?
2. **Mapping.** How does a profile reach concrete data? Through a score field per group, a label with disability families, a facet medal, feature tags, or only through measured attributes.
3. **Schema.** Is the schema public, what are the exact field names and value scales, and what is unknown?

It complements three workshop preparation documents (Workshop #3, 2 December 2026, kept outside this repository) and does not repeat them:

- `prep_1_source_metadata.md`: provenance, dates, licences and labels per source.
- `prep_2_user_profiles.md`: cross-source alignment of categories, profile → information requirements, a strawman profile.
- `prep_3_common_data_model.md`: candidate common data models (a11yJSON, OSM, NeTEx, DATAtourisme and others).

This document adds field-level detail where we could read a schema, an API, a dataset or our own adapter code. The sources used for that detail are listed below.

| Mark | Meaning |
| --- | --- |
| **LS** | stated in the literature study |
| **Schema** | read from a published schema or dataset metadata (24 Nov 2026) |
| **Adapter** | read from this repository's adapter code and test fixtures in [`sources/`](../sources/) |
| **prep** | taken from the workshop preparation documents (verified there on 23–24 Nov 2026) |
| **Not verified** | not confirmed; listed again in [Open questions](#open-questions) |

### Mapping types

Sources link people to data in five ways. Each source section names its type.

| Type | How a profile reaches data | Example |
| --- | --- | --- |
| **P: score per profile** | one field per user group, holding an outcome | Picto Access `handicaps.moteur = 2` |
| **L: label families** | a label plus the disability families it covers | Tourisme & Handicap `handicap_moteur = Oui` |
| **F: facet rating** | an outcome per part of the venue, not per person | IedereenOveral gold medal for "Toegang" |
| **T: feature tags / attributes** | facts about the venue; the reader decides who they suit | Acceslibre `entree_largeur_mini = 90` |
| **W: wheelchair only** | one dimension, usually a 3-level scale | OSM `wheelchair=limited` |

---

## 2.2.1 Picto Access (France)

**Type:** P (8 profiles), with a detailed questionnaire (T) underneath.

**Profiles and field names.** Picto Access holds the same 8 groups under three sets of names. Our adapter's mapping (Adapter, [`sources/pictoaccess/app.py`](../sources/pictoaccess/app.py)) connects the export keys to the open-data columns:

| LS group (p. 11) | Export key (`accessibility.handicaps`) | Open-data column (data.gouv.fr, prep) | Adapter name |
| --- | --- | --- | --- |
| cannot walk (wheelchair) | `moteur` | `Motor_Accessibility` ("Handicap moteur") | `mobility` |
| difficulty walking | `senior` | `Walking_Impairment_Accessibility` ("Trouble de la marche") | `walking_difficulty` |
| difficulty understanding, communicating, deciding | `psychique` | `Mental_Health_Accessibility` ("Handicap psychique") | `cognitive` |
| blind | `mal-voyant` | `Visual_Impairment_Accessibility` ("Malvoyant") | `blind` |
| low vision | `mal-voyant-partiel` | `Partial_Visual_Impairment_Accessibility` ("Malvoyant partiel") | `low_vision` |
| deaf | `mal-entendant` | `Hearing_Impairment_Accessibility` ("Malentendant") | `deaf` |
| hard of hearing | `mal-entendant-partiel` | `Partial_Hearing_Impairment_Accessibility` ("Malentendant partiel") | `hard_of_hearing` |
| temporary mobility limitation (pram, luggage) | `femme-enceinte` | `Temporary_Mobility_Limitation_Accessibility` | `temporary_mobility` |

The export keys explain two puzzles that prep_2 §9 left open:

- The data-flow documentation's example columns `Senior_Accessibility` and `Pregnancy_Accessibility` are the internal keys `senior` and `femme-enceinte`. In the published CSV they became "walking impairment" and "temporary mobility limitation", so the CSV has no missing groups.
- "Malvoyant" without a qualifier stands for **blind**; "Malvoyant partiel" stands for low vision. The same pattern holds for hearing. The label "Handicap psychique" covers the group that the website describes as understanding, communicating and deciding. The export's own labels (`readable_handicaps[].name`, checked 24 Nov 2026) confirm this:

  | Export key | Label in the export |
  | --- | --- |
  | `moteur` | "Personne touchée par une incapacité à marcher" |
  | `senior` | "Personne éprouvant des difficultés à marcher" |
  | `psychique` | "Personne touchée par des difficultés de la compréhension, de la communication et de la décision" |
  | `mal-voyant` | "Personne touchée par une cécité totale" |
  | `mal-voyant-partiel` | "Personne touchée par une déficience visuelle partielle" |
  | `mal-entendant` | "Personne touchée par une surdité totale" |
  | `mal-entendant-partiel` | "Personne touchée par une déficience auditive partielle" |
  | `femme-enceinte` | "Trouble de la mobilité dû à une situation handicapante temporaire (ex: poussette ou valise)" |

  The open-data column titles ("Malvoyant", "Handicap psychique") are therefore loose renderings of these groups, not different groups.

**Value scale.** One integer per group:

| Value | Export: `readable_handicaps[].level` and its label | Open-data documentation (prep) | Website wording (prep) |
| --- | --- | --- | --- |
| `2` | `AccessibleSolo`, "Accessible en autonomie" | fully accessible | "Accessible en autonomie" (letter A on the domino pictogram) |
| `1` | `AccessibleWithHelp`, "Accessible avec accompagnement ou partiellement" | accessible with help | "partiellement ou avec accompagnement" (B) |
| `-1` | `AccessibleFromPoor`, "Accessible en autonomie OU accessible avec accompagnement ou partiellement" | accessible **with difficulty** | no wording |
| `0` | `Inaccessible` | inaccessible | "Inaccessible" (C) |
| `-2` | `Unknown`, "Ne sait pas" | not evaluated (about 15% of values) | "Absence d'information" |

The export itself defines `-1` as "autonomous or with help, unspecified". The open-data documentation's "with difficulty" is a different reading, which an agent should not use. `-1` occurs only for some groups (in a sample, walking, wheelchair, temporary mobility, deaf and hard of hearing); the questionnaire probably cannot tell the two levels apart for those groups (**not verified**).

**Beneath the scores.** The full record holds a hierarchical questionnaire (access, reception, services and equipment, surroundings) with measurements, yes/no answers, free text, comments and photos (LS). prep_1 notes that criteria are linked to target groups in the page data, so the score is probably derived from these answers. The scoring rule is not published.

**Other profile-related fields.**

- User feedback: a percentage per group of "fully accessible / with help / not accessible" (LS).
- `brands`: the organisation a place belongs to (university, transport network) (Adapter).

**Schema availability.**

- Open CSV on data.gouv.fr (ODbL, daily, 19 columns) with the 8 scores, `Handicap_Text_EN/FR` and `Last_Update_Date` (prep).
- The full questionnaire comes only through the token-protected API. The demonstrator uses a private export of it ([`sources/pictoaccess/README.md`](../sources/pictoaccess/README.md)).
- No published schema document for the questionnaire.

---

## 2.2.2 Acceslibre (France)

**Type:** T (attributes). The only group vocabulary is attached to labels (L).

**Profiles.** Acceslibre records **facts about the building, not profiles**. Disability families appear in one place only: `labels_familles_handicap`, the families covered by a label the venue holds.

**Schema.** Public Table Schema "Accessibilité ERP — Base" v0.0.20, 76 fields, on schema.data.gouv.fr (`MTES-MCT/acceslibre-erp-base`). Extensions add fields for large establishments, accommodation, polling stations, schools, health care and sports venues (Schema). The API returns the same fields grouped in blocks (`transport`, `cheminement_ext`, `entree`, `accueil`, `sanitaires`, `commentaire`, `registre`, `conformite`), plus `user_type` and `sources[]` (prep).

**Attributes by the profile they serve.** The schema does not assign fields to profiles; the grouping below is ours (Schema):

| Profile served | Fields (type, enum) |
| --- | --- |
| Wheelchair / walking difficulty | `*_plain_pied` (bool) for path, entrance and reception; `*_nombre_marches` / `entree_marches` (int); `*_rampe` = `aucune` / `fixe` / `amovible`; `*_ascenseur`, `*_ascenseur_pmr` (bool); `entree_largeur_mini` (int, cm); `entree_porte_type` = `manuelle` / `automatique`; `entree_porte_manoeuvre` = `battante` / `coulissante` / `tourniquet` / `tambour`; `entree_pmr` (separate accessible entrance); `cheminement_ext_terrain_stable`, `_pente_degre_difficulte` = `légère` / `importante`, `_pente_longueur` = `courte` / `moyenne` / `longue`, `_devers` = `aucun` / `léger` / `important`, `*_retrecissement` (narrowing < 90 cm); `stationnement_pmr`, `stationnement_ext_pmr`; `sanitaires_adaptes` |
| Walking difficulty (stairs) | `*_main_courante` (handrail), `*_sens_marches` = `montant` / `descendant` |
| Blind / low vision | `cheminement_ext_bande_guidage` (guidance strip); `*_reperage_marches` (contrasting step edges, warning strip); `entree_reperage`; `entree_vitree_vitrophanie` (glass marking); `entree_balise_sonore` (audio beacon); `accueil_audiodescription` = `avec_équipement_permanent` / `avec_app` / `avec_équipement_occasionnel` / `sans_équipement` |
| Deaf / hard of hearing | `accueil_equipements_malentendants` = `bim` (fixed induction loop) / `bmp` (portable loop) / `lsf` (sign language) / `lpc` (cued speech) / `sts` (subtitles, live transcription) / `autres`; `entree_dispositif_appel_type` = `bouton` / `interphone` / `visiophone` |
| Cognitive / all | `accueil_visibilite` (reception visible from entrance); `accueil_personnels` = `aucun` / `formés` / `non-formés`; `entree_aide_humaine` (human help available) |
| Labels (L) | `labels` = `th` (Tourisme & Handicap) / `dpt` (Destination pour Tous) / `mobalib` / `handiplage` / `autre`; `labels_familles_handicap` = `moteur` / `visuel` / `auditif` / `mental` |
| Legal | `conformite` (self-declared compliance), `registre_url` (public accessibility register) |

**Points to note.**

- A boolean left empty means **unknown**, not "no". The website shows "Inconnu" (prep). Without `clean=true` the API returns `null` (AGENTS.md).
- Most fields are booleans. Toilets and lifts have no dimensions, and slopes have no percentage (prep_2 §4).
- `labels` and `labels_familles_handicap` are claims passed on, not verified. A manager can type in "Tourisme & Handicap" (prep_1).
- The API filter `equipments` uses its own shortcuts (e.g. `having_adapted_parking`) on top of these fields (AGENTS.md, golden question 10).

---

## 2.2.3 IedereenOveral (Flanders and Brussels, Inter)

**Type:** F (medal per facet), with T underneath and a little-used target-audience field.

**Schema availability.** Neither the schema nor the questions are public (LS). The Xano API is public but undocumented. Its lookup tables reveal the structure (Adapter, [`sources/iedereenoveral/transform.py`](../sources/iedereenoveral/transform.py), fixtures recorded 12 Nov 2026).

**Structure of a place.**

```text
location
 ├─ locationtype_id      Eten en drinken | Publiek toilet | Changing place | Museum | Parkeerplaatsen
 ├─ valuation_id         overall medal
 ├─ confirmed_by_inter   bool ("Goedgekeurd door Inter" badge)
 ├─ gold_filter_id[]     filters (features) the place meets at gold level
 ├─ targetaudience_id[]  target audiences
 └─ categories[]         facets, e.g. Toegang, Toilet, Verbruiksruimte; each has valuation_id
     └─ subcategories[]  concepts, e.g. toilet door; each has valuation_id
         └─ requirements[]   question + answeroption (value, valuation_id, minimum_valuation_id,
                             targetaudience_id[])
```

**Medal scale (`valuation`).** `Gold` / `Goud`, `Silver` / `Zilver`, `Bronze` / `Brons`, `None` / `Geen medaille`, plus three values for items that are not graded: `OK`, `Present` / `Aanwezig` and `Info`. Inter defines gold as usable independently, silver as usable with help, bronze as attention paid to accessibility, and no medal as not meeting the criteria (LS). The worst answer sets the medal (prep_1). The criteria per facet are not published.

**Target audiences (`targetaudience`).** This is the only profile list in the source: `Blinden en slechtzienden`, `Doven en slechthorenden`, `Motorische beperking`, `Verstandelijke beperking`, `Autisme`, `Ouderen`, `Andere`. The field exists on a place and on each answered requirement. In the recorded detail fixture it is empty everywhere. How often Inter fills it is **not verified**.

**Filters (`filter`), i.e. features per location type.** Examples by profile served:

- Mobility: "Toegankelijke toegang", "Drempelloze toegang", "Toegankelijk toilet", "Aangepast toilet", "Onderrijdbare wastafel in aangepast toilet", "Toegankelijke verbruiksruimte", "Voorbehouden plaats voor personen met een handicap".
- Vision: "Contrasten", "Goede verlichting", "Beluisteren van tekstmateriaal".
- Hearing: "Balie - ringleiding", "Visueel brandalarm".
- Cognitive and sensory: "Rustige hoeken", "Stille ruimte", "Visueel stappenplan", "Zintuiglijke beleving".
- Other: "Stomavriendelijk toilet", "Info over allergenen", "Genderneutraal toilet", "Babyverzorgingstafel".

The answers themselves are Dutch text with measurements where relevant (e.g. passage width of the toilet door) (LS). The adapter returns them as `criterion`, `value`, `detail` and `audiences`.

---

## 2.2.4 Toegankelijkheidswijzer (Flemish museums)

**Type:** T (text per topic). No profiles.

**Structure.** A widget on the museum's own website, a collapsible hierarchy with these topics: public transport, reserved parking, entrance and circulation, adapted toilets, specific services and facilities, discounts for people with a disability, and photos (LS). The text includes exact measurements where relevant (LS).

**Mapping to profiles.** None in the data. The reader judges suitability from the text. prep_1 mentions summary icons, but their definitions were not found.

**Schema availability.** The LS says there is no API. prep_1 found a public, undocumented JSON:API (56 widgets) with `updated-at` per point of interest, and open-source code. Its field names were **not examined** here. Museums enter the data and Inter checks it, but the widget does not say so (prep_1). IedereenOveral imports these museums as location type "Museum" (prep_1).

---

## 2.2.5 Access-i (Wallonia and Brussels)

**Type:** P (7 profiles), with text and measurements per profile.

**Profiles.** These are the brochure's own terms (prep), with English glosses:

| Access-i profile | English |
| --- | --- |
| Les personnes en fauteuil roulant | wheelchair users |
| Les personnes marchant difficilement | difficulty walking |
| Les personnes aveugles | blind |
| Les personnes malvoyantes | low vision |
| Les personnes sourdes | deaf |
| Les personnes malentendantes | hard of hearing |
| Les personnes avec des difficultés de compréhension | difficulty understanding |

**Value scale.** Three levels per profile, with no "not accessible" level (prep):

- "Accessible !" (can come alone);
- "Accessible avec un coup de main ponctuel !" (with occasional help);
- "Attention, particularités !" (read the points of attention).

A venue unsuitable for a profile still receives the third level.

**Beneath the verdict.** Each profile has its own text with measurements, following the visit from parking and arrival through entrance, reception, circulation, facilities and (for hotels) rooms (LS). The criteria come from the CAWaB framework. The criteria document and the rule from measurements to verdict are not published (prep_1).

**Profile-related metadata.** Auditing organisation, audit date, and validity "Du … au …" (3 years, or the duration of an event) (prep_1).

**Schema availability.** HTML pages only (`access-i.be/<lang>/je-recherche/<slug>`). There is no API or dataset, and reuse needs Access-i's approval, which has been requested (AGENTS.md). The search interface filters by profile (LS), so the profile is at least a structured attribute in their backend.

---

## 2.2.6 AccessNow (international)

**Type:** T (feature tags) plus an overall W-like rating. No profiles.

**Tags.** The public definitions page lists them (prep): "Accessible Parking", "Accessible Washroom", "Alternative Entrance", "ASL (Sign Language)", "Automatic Door", "Braille", "Customer Service", "Digital Menu", "Elevator", "Handrails", "Large Print", "Lighting", "Lowered Counters", "Outdoor Access Only", "Quiet", "Ramp", "Scent-Free", "Service Animal Friendly", "Spacious", "StopGap Ramp". The LS said the tags were not public; prep_1 corrects this.

**Rating.** One pin per place: Accessible / Partially Accessible / Not Accessible. It is not split by profile, and in practice it reflects mobility.

**Mapping to profiles.** Only implicit: mobility through Ramp, Elevator, Accessible Washroom and Spacious; vision through Braille, Large Print and Lighting; hearing through ASL; sensory through Quiet and Scent-Free; assistance animals through Service Animal Friendly.

**Schema availability.** No public API or dataset (LS). Tags are added in user reviews with author and date.

---

## 2.2.7 Accessible.net (France)

**Type:** T (icons per need) with filters by target group.

**Structure.** Each place or event page shows icons for facilities by accessibility need, plus a text description whose depth depends on who entered it (LS). The site offers filters by target group (LS), but their labels were **not found** (prep_2 §9). Each record has a source badge: "Auto-description" (owner data) or the logo of the tourism body that verified it (prep_1).

**Schema availability.** No API or open dataset (LS). The icon set and the target-group list are not documented publicly.

---

## 2.2.8 OnWheels (Belgium, on OpenStreetMap)

**Type:** W + T, stored as OSM tags.

**Fields.** The app writes standard OSM tags: `wheelchair=yes` / `limited` / `no` / `designated`, `toilets:wheelchair`, `kerb`, `incline`, `step_count`, `capacity:disabled` for parking. It adds its own detail tags for entrances (`entrance:width`, `entrance:step_count`) and toilet dimensions (`toilets:wheelchair:door_width`, `toilets:wheelchair:space_side` and others). The OSM wiki says the toilet-dimension tags "have never been voted or approved" (prep_3). It covers places, entrances, toilets, parking, kerbs, transit stops and indoor spaces (LS).

**Mapping to profiles.** Wheelchair users only. In OSM, `limited` allows an entrance step of at most 7 cm (prep_3). Other profiles are left to general OSM tags such as `tactile_paving`, `hearing_loop`, `blind:description` and `deaf:description` (prep_2), which OnWheels does not focus on.

**Schema availability.** The OSM wiki documents the tags, but values are not validated (`wheelchair` has 316 distinct values, prep_3). The demonstrator's [`sources/osm/`](../sources/osm/) adapter reads OnWheels features and native accessibility tags. Its registration is parked (AGENTS.md).

---

## 2.2.9 Wheelmap (international, Sozialhelden)

**Type:** W (traffic light) + toilet flag. With Accessibility.Cloud: T in a11yJSON.

**Fields.**

- Green / orange / red stands for OSM `wheelchair=yes` / `limited` / `no` (LS).
- Toilet yes/no stands for `toilets:wheelchair` (LS).
- The a11yJSON grades define partial access: `fully` (no steps), `partially` (one step ≤ 7.5 cm or a mobile ramp, most rooms step-free) and `not` (prep_2).

**Accessibility.Cloud and a11yJSON.** a11yJSON describes objects (Entrance, Door, Restroom, Stairs, Signage, Staff, Media) with attributes such as `hasFixedRamp`, `slopeAngle`, `hasInductionLoop`, `hasTactileGuideStrips` and `isQuiet`. Profiles appear only as an optional `PersonalProfile` with booleans `wheelchair`, `mobilityImpairment`, `blindness`, `visualImpairment`, `hearingImpairment`, `learningImpairment`, `muteness` and `guideDog`. These feed `accessibleWith` and `partiallyAccessibleWith`. The guideline is "Describe objects, not people" (prep_2). Real-time lift and escalator status comes through Accessibility.Cloud (LS).

**Schema availability.** Public: the OSM wiki and the a11yJSON documentation and source code.

---

## 2.2.10 Drempelvrij (Belgium)

**Type:** W (wheelchair-oriented yes/no fields) + text.

**Fields per place** (LS): wheelchair accessible; adapted sanitary; adapted parking; threshold-free entrance; suitable paths. Values are ✓, ~ and ? (unknown) (prep_1). A text describes access, circulation, lifts, surfaces and obstacles, and a "Goed om te weten" section covers reservations and points of attention.

**Mapping to profiles.** Wheelchair users only. Certifications from elsewhere (Access-i) are cited per record, sometimes as if they were conformity claims ("Access-i gecertificeerd … voor rolstoelgebruikers") (prep_1).

**Schema availability.** No API or dataset (LS). Pages carry JSON-LD, but without date or source (prep_1). Its fields were **not examined**.

---

## 2.2.11 Handy.Brussels (Brussels)

**Type:** P (filters with two levels) + pictograms (T) + text.

**Profiles** (prep): "Accessible for prm" (persons with reduced mobility), "Accessible impaired pedestrians", "… person with a mental disability", "Facilities for the blind and visually impaired", "Facilities for the deaf and hearing impaired". Each has a variant "… with help". Blind and low vision are merged, and so are deaf and hard of hearing.

**Value scale.** Independent or with help, per group. Absence of a pictogram does not say whether the group was assessed.

**Other structure.** A large pictogram set (e.g. "Accessible Type I", "Parking accessible"), the full list only **partly verified**. A structured text overview covers parking, access, circulation and more (LS).

**Schema availability.** No API or dataset (LS). All rights reserved; page dates are often 2017–2019 (prep_1). Data is collected with partners such as Access-i (LS), so some records may reuse Access-i's profiles. **Not verified**.

---

## 2.2.12 All Access (Province of Luxembourg)

**Type:** T (pictograms and attention points) + text per profile.

**Structure.** Pictograms and text for facilities and attention points, so users judge for themselves (LS). The detail pages give **text per profile**, in French (prep_1). prep_1's label table records 7 profiles behind the "Label All Access", which suggests Access-i's 7. The criteria and validity of that label are not published, and the pictogram set was **not checked**.

**Schema availability.** No API or dataset (LS). All rights reserved (prep_1). The province funds Access-i certification (prep_1), which may explain the overlap with Access-i profiles.

---

## 2.2.13 Euan's Guide (United Kingdom)

**Type:** reviews (free text with ratings). No structured profile mapping found.

The LS section is only a heading. Visitors write reviews with pseudonym and month/year. For unclaimed venues, everything comes from visitors (prep_1). The terms forbid scraping, text and data mining and AI training (prep_1), so we stopped there. The review fields and any accessibility categories were **not examined**. Euan's Guide is not a candidate for an adapter.

---

## 2.2.14 Forêt de Saint-Hubert accessible (Belgium)

**Type:** republisher of All Access (see 2.2.12).

The LS section is only a heading; the LS (p. 25) names it as a platform that reuses All Access data. The site (FR, NL, EN, DE) says its information comes from the All Access service of the Province of Luxembourg, was verified, and is not self-declared (prep_1). We assume its mapping from profiles to data follows All Access. How trails are described (per profile, pictograms, gradients) was **not examined**.

---

## Summary across sources

| Source | Type | Profiles (number) | Field holding the profile link | Scale | Machine-readable |
| --- | --- | --- | --- | --- | --- |
| Picto Access | P | 8 | `accessibility.handicaps.<key>` / `*_Accessibility` columns | 2 / 1 / -1 / 0 / -2 | CSV (ODbL); API with token |
| Acceslibre | T (+L) | 4 families, labels only | `labels_familles_handicap` | attributes: bool, int, enum | API (key), CSV, public schema |
| IedereenOveral | F | 7 audiences (little used) | `valuation_id` per facet; `targetaudience_id` | Gold / Silver / Bronze / None (+ OK / Present / Info) | undocumented API |
| Toegankelijkheidswijzer | T | none | — | text | undocumented JSON:API |
| Access-i | P | 7 | per-profile verdict on the page | 3 levels, no "not accessible" | HTML only, reuse needs approval |
| AccessNow | T | none | tags | overall 3-level pin | no |
| Accessible.net | T | filters exist, labels not found | icons | — | no |
| OnWheels | W + T | wheelchair | OSM `wheelchair`, `entrance:*`, `toilets:wheelchair:*` | yes / limited / no / designated | OSM (ODbL) |
| Wheelmap / a11yJSON | W (+T) | wheelchair; optional 8 booleans in a11yJSON | `wheelchair`; `accessibleWith` | traffic light; fully / partially / not | OSM, a11yJSON |
| Drempelvrij | W | wheelchair | 5 yes/no fields | ✓ / ~ / ? | no (JSON-LD on pages) |
| Handy.Brussels | P | 5 (merged groups) | filter / pictogram per group | independent / with help | no |
| All Access | T (+P text) | 7 (probably Access-i's) | text per profile | — | no |
| Euan's Guide | reviews | none found | — | ratings | no; terms forbid mining |
| Forêt de Saint-Hubert | as All Access | as All Access | — | — | no |

Beyond prep_2, what this means for a profile model:

1. **Only three sources in section 2.2 have a per-profile outcome field an agent can read or filter on:** Picto Access (8, with data), Access-i (7, HTML only, not reusable yet) and Handy.Brussels (5, HTML only). Of these, only Picto Access is in the demonstrator.
2. **The profile lists nearly agree on 7 groups:** wheelchair, walking difficulty, blind, low vision, deaf, hard of hearing, cognitive. Picto Access adds temporary mobility, and IedereenOveral adds autism and older people. A profile vocabulary built on these 7, plus "situational" and "sensory sensitivity", covers every list in section 2.2.
3. **Families, merged groups and wheelchair-only sources lose information.** Examples are Tourisme & Handicap / Acceslibre `moteur`, Handy.Brussels "prm" and the many wheelchair-only sources. A user who walks with difficulty cannot rely on a `moteur` or `wheelchair` outcome in either direction.
4. **For the demonstrator,** the field-level mapping above can become a machine-readable crosswalk (source field → harmonised profile → required attribute) in the vocabulary hub. prep_2 §9 proposes this as future work. Nothing in this document changes the connector or the adapters.

---

## Open questions

| Question | For |
| --- | --- |
| Picto Access `-1`: the export says "autonomous or with help" (`AccessibleFromPoor`); the open-data documentation says "with difficulty". Ask Picto Access to correct the documentation, and why `-1` occurs only for some groups | Picto Access / APF France Handicap |
| Picto Access: rule from questionnaire answers to the 8 scores | Picto Access |
| IedereenOveral: criteria per facet for each medal; how often `targetaudience_id` is filled and by whom | Inter |
| Access-i: CAWaB criteria per profile and the rule from measurements to verdict | Access-i |
| Toegankelijkheidswijzer: fields of the JSON:API and meaning of the summary icons | Toerisme Vlaanderen / Inter |
| Accessible.net target-group filters; All Access and Handy.Brussels pictogram sets | not found on public pages |
| Drempelvrij JSON-LD fields; Forêt de Saint-Hubert trail descriptions; Euan's Guide review fields | not examined (Euan's Guide: terms forbid mining) |

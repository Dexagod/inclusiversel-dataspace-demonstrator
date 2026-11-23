# Domain-knowledge inventory

This file lists the documents the vocabulary hub holds or could hold: labels and certifications, data schemas, assessment methods and practical procedures. Most come from chapter 3 of the literature study (`literatuurstudie.pdf`). For each document it records:
- which are **ingested**, which are **candidates** and which are **skipped**, and why;
- what form each document takes and how it gets into the hub;
- the reuse terms of each site, with the page where they are stated.

Data sources have their own file: [source-inventory.md](source-inventory.md). The documents themselves are listed in [domain-knowledge.yaml](domain-knowledge.yaml), and `make knowledge` loads them.

**Keep this file current.** When you add or remove an entry in `domain-knowledge.yaml`, update its row and the "Last checked" date. The hub stores text passages of each document and cites them back to the URL. That is a copy, so check the site's terms before adding a document. Write down terms only when you have read them on the site itself, and link that page. These readings are not legal advice.

Last checked: **2026-11-23**. Checked with live, read-only requests, and against the 35 documents in the local hub.

## Legend

| Column | Values |
| --- | --- |
| **Status** | **Ingested**: in `domain-knowledge.yaml` and in the hub. **Candidate**: could be added; next step given. **Skipped**: not added; reason given |
| **Form** | HTML page, PDF, schema (documentation of a data model), RDF |
| **Into the hub by** | **URL**: `make knowledge` fetches it. **File**: a `file:` entry in `domain-knowledge.yaml`, uploaded from this repository by `make knowledge`. **Upload**: the site blocks automated fetches, so upload the file with `POST /documents` |
| **Terms** | **Open**: an open licence or explicit free reuse. **Not stated**: no terms found. **Restricted**: terms limit or forbid reproduction; kept for local tests and closed demos only, tagged `licence-restricted` (see below) |
| **Passages** | number of chunks in the hub; 1 or 2 usually means the page held little text |

## Ingested

| Document | Kind | Form | Passages | Terms |
| --- | --- | --- | --- | --- |
| [Acceslibre field documentation](https://acceslibre.beta.gouv.fr/contrib/documentation/) | criteria | HTML | 44 | Open: [Licence Ouverte 2.0](https://acceslibre.beta.gouv.fr/mentions-legales) |
| [Acceslibre data schema](https://schema.data.gouv.fr/MTES-MCT/acceslibre-schema/latest.html) | schema | HTML | 26 | Open: Licence Ouverte 2.0 (site footer) |
| [Acceslibre ERP base schema](https://schema.data.gouv.fr/MTES-MCT/acceslibre-erp-base/) | schema | HTML | 26 | Open: Licence Ouverte 2.0 |
| [IedereenOveral for professionals](https://www.vlaanderen.be/inter/overheden-en-professionelen/iedereenoveral) | source description | HTML | 8 | Open: [free reuse](https://www.vlaanderen.be/over-vlaanderenbe/disclaimer) |
| [Inter screening (IedereenOveral medals)](https://www.vlaanderen.be/inter/toolbox-toegankelijke-steden-en-gemeenten/toerisme/screening-bezienswaardigheden-horeca-en-handelszaken) | label, criteria | HTML | 10 | Open (vlaanderen.be) |
| [Inter Label Toegankelijk Gebouw](https://www.vlaanderen.be/inter/overheden-en-professionelen/werken-aan-toegankelijke-gebouwen/label-toegankelijk-gebouw) | label | HTML | 20 | Open (vlaanderen.be) |
| [Changing Places](https://www.vlaanderen.be/inter/mensen-met-een-handicap/changing-places) | procedure | HTML | 4 | Open (vlaanderen.be) |
| [Navigeer en parkeer](https://www.vlaanderen.be/inter/mensen-met-een-handicap/navigeer-en-parkeer) | procedure | HTML | 10 | Open (vlaanderen.be) |
| [Iedereen fietst](https://www.vlaanderen.be/inter/mensen-met-een-handicap/iedereen-fietst) | procedure | HTML | 7 | Open (vlaanderen.be) |
| [Zon, zee, zorgeloos](https://www.vlaanderen.be/inter/mensen-met-een-handicap/zon-zee-zorgeloos) | procedure | HTML | 44 | Open (vlaanderen.be) |
| [Accessible events on UiTinVlaanderen](https://www.vlaanderen.be/inter/mensen-met-een-handicap/agenda-toegankelijke-evenementen/toegankelijke-evenementen-op-uitinvlaanderen) | procedure | HTML | 3 | Open (vlaanderen.be) |
| [Inter evaluation: plan vs. built](https://publicaties.vlaanderen.be/view-file/69606) | evaluation | PDF, 116 pp | 712 | Probably open (vlaanderen.be disclaimer); unverified for publicaties.vlaanderen.be |
| [Destination pour Tous](https://www.entreprises.gouv.fr/priorites-et-actions/proximite-et-territoires/renforcer-le-secteur-du-tourisme/destination-pour-tous) | label | HTML | 12 | Open: etalab-2.0 (site footer) |
| [A11yJSON](https://sozialhelden.github.io/a11yjson/) | schema | HTML | 9 | Open: MIT ([repository](https://github.com/sozialhelden/a11yjson/blob/main/LICENSE)) |
| [OSM accessibility tagging](https://wiki.openstreetmap.org/wiki/Disabilities) | schema | HTML | 31 | Open: [CC BY-SA 2.0](https://wiki.openstreetmap.org/wiki/Wiki_content_license) |
| [Registre public d'accessibilité](https://handicap.gouv.fr/registre-daccessibilite-obligatoire-un-guide-pour-les-erp) | legislation | HTML | 9 | Not checked (site under maintenance, HTTP 503, on 2026-11-18) |
| [GTFS pathways](https://raw.githubusercontent.com/MobilityData/gtfs.org/main/docs/en/documentation/schedule/examples/pathways.md) | schema | Markdown (gtfs.org refuses automated requests; same page from its GitHub repository) | 30 | Not stated (the GTFS specification repository is Apache 2.0) |
| [NeTEx accessibility white paper](https://transmodel-cen.eu/wp-content/uploads/2024/07/08.NeTEx-Accessibility-WhitePaper_1.06.pdf) | schema | PDF, 11 pp | 45 | Not stated |
| [Handiplage label](https://handiplage.fr/) | label | HTML | 11 | Not stated |
| [Picto Access pictograms (Limoges press release)](https://limoges.fr/sites/default/files/espace_presse/2025/CP%20Picto%20Access%2003%202025-1.pdf) | label | PDF | 8 | Not checked |
| [Access-i: what it is and how places are audited](https://access-i.be/en/?p=1453) | criteria | HTML | 14 | **Restricted**: [prior permission by e-mail](https://access-i.be/en/mentions-legales/) |
| [Access-i: what certification means](https://access-i.be/en/faqs/ca-veut-dire-quoi-etre-certifie-par-access-i/) | label | HTML | 2 | **Restricted**: as above |
| [Tourisme & Handicap (Atout France)](https://www.atout-france.fr/fr/tourisme-et-handicap) | label | HTML | 4 | **Restricted, conflicting**: footer says etalab-2.0, [mentions légales](https://www.atout-france.fr/fr/informations/mentions-legales) forbid reproduction without written permission |
| [Destination Innovante Durable](https://france-congres-evenements.org/did-label/) | label | HTML | 13 | **Restricted**: [personal, non-commercial use only](https://france-congres-evenements.org/mentions-legales/) |
| [Toerisme Vlaanderen labels A and A+](https://toerismevlaanderen.be/nl/kwaliteit/inclusie/toegankelijkheid/a-label) | label | HTML | 10 | **Restricted**: "all rights reserved", [disclaimer](https://toerismevlaanderen.be/nl/legal-disclaimer) gives no reuse right |
| [Handy.brussels pictograms](https://handy.brussels/en/amt-concept/pictogrammes/) | label | HTML | 4 | **Restricted**: "© AMT Concept – all rights reserved" |
| [VisitFlanders accessible travel](https://www.visitflanders.com/en/travel-information/accessibility) | procedure | HTML | 15 | **Restricted**: [no storing or reproducing without written consent](https://www.visitflanders.com/en/disclaimer) |
| [VisitWallonia: specific needs](https://visitwallonia.be/fr-be/3/je-suis/voyageur-a-besoins-specifiques) | procedure | HTML | 10 | **Restricted**: consultation only (site CGU) |
| [Routen accessible routes](https://www.routen.be/toegankelijkheid) | procedure | HTML | 12 | **Restricted**: "alle rechten voorbehouden" |
| Literature study (`literatuurstudie.pdf`, this repository) | label, criteria, schema, source description | PDF, 86 pp, file entry | 393 | Own work of this project |
| [GTFS accessibility features](https://raw.githubusercontent.com/MobilityData/gtfs.org/main/docs/en/getting-started/features/accessibility.md) | schema | Markdown (gtfs.org repository) | 11 | Not stated (the GTFS specification repository is Apache 2.0) |
| [GTFS pathways and levels](https://raw.githubusercontent.com/MobilityData/gtfs.org/main/docs/en/getting-started/features/pathways.md) | schema | Markdown (gtfs.org repository) | 22 | Not stated (as above) |
| [Profil NeTEx accessibilité France v2.4](https://normes.transport.data.gouv.fr/normes/netex/accessibilite/) | schema | HTML, about 20,000 words | 394 | Not checked |
| [Données d'accessibilité et Acceslibre Mobilités](https://www.ecologie.gouv.fr/politiques-publiques/donnees-daccessibilite-acceslibre-mobilites) | legislation, schema | HTML | 114 | Not checked (government site) |
| [Schéma des politiques des données d'accessibilité (2025)](https://www.ecologie.gouv.fr/sites/default/files/documents/2025%2006%20Schema%20Politiques%20des%20donn%C3%A9es%20accessibilit%C3%A9_0.pdf) | legislation | PDF, 1 page (diagram) | 7 | Not checked (government site) |

**Licence knowingly disregarded (decided 2026-11-18):** nine ingested documents come from sites whose terms forbid or limit reproduction; they are the rows marked **Restricted**. They stay in the hub because the hub is used only in local tests and closed demos, never published.
- Each one has the tag `licence-restricted` in `domain-knowledge.yaml` and in the hub.
- **A public deployment must leave them out:** run `make public` in `sources/` instead of `make full`; it skips the tagged entries and removes them from the hub if an earlier `make full` added them.
- A new document with restrictive terms may be added the same way: tag it `licence-restricted` and mark its row **Restricted** here.

This applies only to vocabulary-hub documents. Data sources still need their licence or the publisher's permission. Access-i data in particular stays blocked until Access-i approves.

**Known problem:** `make knowledge` fetches every URL again, even ones already in the hub. While handicap.gouv.fr is under maintenance, it reports one failure and exits with an error. The other documents are still loaded.

## Candidates

| Document | Kind | Form | Into the hub by | Terms | Next step |
| --- | --- | --- | --- | --- | --- |
| [DATAtourisme ontology, documentation](https://www.datatourisme.fr/ontology/core/doc/index-en.html) | schema | HTML (generated from the RDF ontology) | URL | Not stated (licence field is a placeholder) | Add this page instead of the RDF ontology, which was removed because it is not readable text. Do it together with DATAtourisme as a source. |
| Tourisme & Handicap criteria: [arrêté of 18 April 2024](https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000049449360/2026-10-12) | legislation | HTML | Upload (Légifrance blocks automated fetches) | Official texts; Légifrance terms not checked | The national criteria grid itself is not on an official page; tourism offices host older copies (2016 to 2018). Use the legal text. |
| iRail station facilities: [repository README](https://github.com/iRail/stations) | schema | HTML | URL | Open: CC0 | Explains the fields of `irail-stations` (ramp, lift, platform height); it fits the added source. |
| UiTdatabank facility terms ([taxonomy](https://taxonomy.uitdatabank.be/terms)) | schema | HTML | URL | publiq terms: use with attribution | Only if UiTdatabank becomes a source. |
| SNCF Assist'enGare rules (replaced Accès Plus in January 2024) | procedure | HTML | Upload (SNCF sites block automated fetches) | Not checked | Find the official page and check its terms; useful with `sncf-assistance`. |
| [Handiplage beach guide](https://handiplage.fr/nos-plages-accessibles/guide-touristique/) | label | HTML | URL | Not stated | Adds the per-beach details behind the label. |
| [NeTEx FAQ](https://transmodel-cen.eu/index.php/faq-netex/) | schema | HTML | URL | Not stated | Low priority; the white paper is ingested. |
| [Handigo](https://handigo.com/home/) | label | HTML | URL | Not stated | Only together with the Certivéa label (skipped). |
| [Tourisme & Handicap days, Dunkerque](https://tourisme-handicaps.org/wp-content/uploads/DUNKERQUE.pdf) | events | PDF, 20 pp | URL | Not checked | Low value: an event programme for one year. |

## Skipped

| Document | Reason |
| --- | --- |
| [Certivéa Label Accessibilité](https://certivea.fr/certifications/label-accessibilite/) | The server sends an incomplete TLS chain, so automated fetches fail. Its [terms](https://certivea.fr/mentions-legales/) reserve all reproduction rights. |
| [DATAtourisme ontology (RDF)](http://datatourisme.fr/ontology/core/) | RDF, not readable text; the documentation page above is the candidate. |
| [Apidae accessibility input guide](https://aide.apidae-tourisme.com/hc/fr/articles/11674196268572-Guides-de-saisie-valoriser-l-offre-adapt%C3%A9e-aux-personnes-en-situation-de-handicap) | Behind a Cloudflare challenge; Apidae is not a source either. |
| [De Lijn accessible stops](https://www.delijn.be/nl/content/toegankelijke-haltes/) | Explains the three stop symbols, but the [terms](https://www.delijn.be/en/content/disclaimer/) allow private and personal use only. Reconsider if De Lijn open data becomes a source. |
| [Evelity deployment guide](https://www.evelity.com/en/deployment-guide) | [Terms](https://www.evelity.com/en/legal-information) prohibit scraping and extraction. |
| [Westtoer Routechirurg](https://www.westtoer.be/praktisch/routechirurg) | The page needs JavaScript; there is no text to fetch. |
| [UiTdatabank introduction](https://docs.publiq.be/docs/uitdatabank/introduction) | 404; the documentation site needs JavaScript. |
| [MeerMobiel](https://www.meermobiel.be/) | The home page is mostly image links, with almost no text. |
| [SNCF station accessibility page (Montparnasse)](https://www.garesetconnexions.sncf/fr/gares-services/paris-montparnasse/accessibilite) | Bot wall; covered by the `sncf-station-equipment` data. |
| List of buildings with the Label Toegankelijk Gebouw | No public list exists; only individual news items. |
| [Access-i cycle routes](https://access-i.be/en/access-i-assesses-the-accessibility-of-cycle-routes-in-wallonia/) | Wait for Access-i's approval. |
| Section 3.4 of the literature study (data standards) | Still empty in the study; the standards it will cover (A11yJSON, OSM, GTFS, NeTEx, Acceslibre) are ingested above. |

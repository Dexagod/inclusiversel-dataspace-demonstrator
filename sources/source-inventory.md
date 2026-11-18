# Source inventory

This file lists every data source named in the literature study (`literatuurstudie.pdf`, chapter 2) and every source the data space uses, and records how far each one has got. It covers:
- which sources are **added**, which are **candidates**, which are **blocked** and which are **skipped**, and why;
- how each is reached (API, dataset, website and so on) and whether we built a proxy;
- the licence or terms of use, with the page where they are stated;
- where the literature study is wrong or out of date.

Domain knowledge (labels, schemas, procedures) has its own file: [domain-knowledge-inventory.md](domain-knowledge-inventory.md).

**Keep this file current.** When you add, block or skip a source, update its row and the "Last checked" date. Write down a licence only when you have read it on the publisher's own page, and link that page. "Not stated" is a valid answer; a guess is not. These licence readings come from the publishers' pages and are not legal advice.

Last checked: **2026-11-18**. Checked with live, read-only requests to the publishers' pages and APIs, and in the code and registrations in this folder.

## Legend

| Column | Values |
| --- | --- |
| **Status** | **Added**: registered in the catalog. **Candidate**: could be added; next step given. **Blocked**: waiting for permission. **Skipped**: not added; reason given. **Portal**: a catalog of other sources, used to find data, not queried as a source |
| **Access** | **API** (with or without an OpenAPI), **dataset** (file download: CSV, GTFS, NeTEx, RDF), **SPARQL**, **website**, **app** (mobile only), **PDF** |
| **Integration** | **Direct**: the connector calls the publisher's own API, with no code of ours. **Proxy (live)**: our adapter in `sources/<id>/` calls the publisher on each request. **Proxy (snapshot)**: our adapter serves a downloaded or provided copy. **None** |
| **Key** | whether the publisher requires an API key or account |

## Overview

| Source | Area | Study § | Status | Access | Integration | Key | Licence or terms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| IedereenOveral | Flanders, Brussels | 2.2.3 | **Added** | API (undocumented Xano backend of the website) | Proxy (live) `iedereenoveral/` | no | not stated; to confirm with Inter |
| PictoAccess | France | 2.2.1 | **Added** | dataset: full export provided by PictoAccess; open subset on data.gouv.fr | Proxy (snapshot) `pictoaccess/` | (export by token) | demonstrator use agreed; open subset [ODbL](https://www.data.gouv.fr/datasets/donnees-daccessibilite-des-etablissements-partenaires-picto-access) |
| Acceslibre | France | 2.2.2 | **Added** | API with [OpenAPI](https://acceslibre.beta.gouv.fr/api/openapi); dataset on data.gouv.fr | Direct | yes (on request) | dataset: [Licence Ouverte 2.0](https://www.data.gouv.fr/datasets/accessibilite-des-etablissements-recevant-du-public-erp-pour-les-personnes-en-situation-de-handicap); API spec states none |
| Tourisme & Handicap label list | France | 3.2.5 | **Added** (`tourisme-handicap`) | API (Opendatasoft Explore, data.economie.gouv.fr); dataset on data.gouv.fr | Direct | no | not stated on either portal (data.gouv.fr: `notspecified`) |
| SNCF stations, lift status, station equipment, assistance | France | 2.4.1 | **Added** (4 datasets) | API (Opendatasoft Explore, ressources.data.sncf.com) | Direct | no | [ODbL](https://data.sncf.com/pages/licence) |
| STIB, TEC, De Lijn stops | Belgium | 2.4.2 | **Added** (3 datasets) | dataset (static GTFS from data.belgianmobility.io) | Proxy (snapshot, daily) `be-transit/` | no (anonymous: 100 requests a day) | [CC BY 4.0](https://data.belgianmobility.io/en/terms.html), operator is licensor |
| iRail stations | Belgium | 2.4.2 | **Added** (`irail-stations`) | dataset ([CSV on GitHub](https://github.com/iRail/stations), incl. `facilities.csv`) | Proxy (snapshot, daily) `be-transit/` | no | CC0 (README badge), but lift data from OSM (ODbL); conflict flagged by the repository |
| ODWB PMR parking (Liège, Brabant wallon, Marche-en-Famenne, La Louvière, Databusters) | Wallonia | not in study | **Added** (5 datasets) | API (Opendatasoft Explore, odwb.be) | Direct | no | CC BY, except Marche (conflicting metadata) and La Louvière (not specified) |
| ODWB Liège PMR toilets | Wallonia | not in study | **Added** | API (Opendatasoft Explore) | Direct | no | CC BY |
| Access-i | Wallonia, Brussels | 2.2.5 | **Blocked** | website | None | – | [mentions légales](https://access-i.be/mentions-legales/): reproduction only after prior permission by e-mail; database protected. Permission requested |
| Toerisme Vlaanderen linked open data | Flanders | 2.1.3, 3.2.3 | **Candidate** | SPARQL, JSON:API, RDF dump | needs adapter | no | not stated |
| VisitFlanders Toegankelijkheidszoeker | Flanders, Brussels | 2.3.1 | **Candidate** (after Toerisme Vlaanderen) | API (undocumented, answers without key) | needs adapter | no | not stated for the API; [website disclaimer](https://www.visitflanders.com/en/disclaimer) forbids storing or reproducing without consent |
| DATAtourisme | France | 2.3.5 | **Candidate** | API ([docs](https://api.datatourisme.fr/v1/docs)); daily exports on data.gouv.fr | Direct if an OpenAPI exists, else adapter | yes (free, form + CGU) | [Licence Ouverte 2.0](https://www.datatourisme.fr/utiliser-les-donnees/): credit producer and update date |
| Accessibility.Cloud | worldwide | 2.7.2 | **Candidate** | API ([docs](https://github.com/sozialhelden/accessibility-cloud/blob/main/app/docs/json-api.md)) | needs adapter (no OpenAPI) | yes (free token, non-commercial only) | per source, returned in each response |
| OpenStreetMap (Overpass) | worldwide | 2.7.1 | **Candidate** | API (Overpass) | needs adapter (no OpenAPI) | no | [ODbL](https://www.openstreetmap.org/copyright) |
| UiTdatabank (publiq) | Flanders, Brussels | 2.3.7 | **Candidate** (costs money) | API (Search API) | needs adapter or direct | yes; test free, production from €125/year | [terms](https://www.publiq.be/projecten/publiq-platform/gebruiksvoorwaarden): attribution, no commercial use, no resale |
| De Lijn open data (data.delijn.be) | Flanders | 2.4.2 | **Candidate** (check first) | API | Direct or adapter | yes (free, instant) | "Licentie voor gratis hergebruik" (PDF linked from [data.delijn.be](https://data.delijn.be)) |
| French GTFS feeds (transport.data.gouv.fr) | France | 2.4.1 | **Candidate** | dataset (GTFS per network); [API](https://transport.data.gouv.fr/api/openapi) lists them | Proxy (snapshot), like `be-transit/` | no | per feed |
| SNCF `accessibilite_gares` (NeTEx) | France | 2.4.1 | **Candidate** (low priority) | dataset (one NeTEx XML file) | Proxy (snapshot) | no | ODbL |
| More Opendatasoft datasets | BE, FR | 2.1.2 | **Candidate** | API (Explore) | Direct (add to `opendatasoft/datasets.yaml`) | no | per dataset |
| Navigeer en Parkeer (Inter) | West Flanders | 2.6.3 | **Candidate** (ask Inter) | dataset (GPS files after a Microsoft Forms request) | Proxy (snapshot) | form | not stated |
| OpenRouteService | worldwide | 2.5.5 | **Candidate** (low priority) | API (wheelchair profile) | Direct or adapter | yes (free plan) | not checked; a report says `api.openrouteservice.org` closes Nov 2026 (unconfirmed) |
| Toegankelijkheidswijzer | Flanders (museums) | 2.2.4 | **Skipped** (covered by IedereenOveral) | website widget | None | – | not stated; Inter says the data now feeds [IedereenOveral](https://www.vlaanderen.be/inter/overheden-en-professionelen/iedereenoveral/toegankelijkheidsinfo-over-musea) |
| Tourisme & Handicap Hauts-de-France 2022 | Hauts-de-France | 2.3.3 | **Skipped** (duplicate) | dataset on data.gouv.fr | None | no | `notspecified` |
| AccessNow | worldwide | 2.2.6 | **Skipped** | website, app | None | – | "All rights reserved"; terms page did not render |
| Accessible.net | France | 2.2.7 | **Skipped** | website | None | – | not stated |
| OnWheels | worldwide | 2.2.8 | **Skipped** (reach through OSM) | app writing to OSM | None | – | ODbL (OSM) |
| Wheelmap | worldwide | 2.2.9 | **Skipped** (reach through OSM, Accessibility.Cloud) | website, app | None | – | ODbL (OSM part) |
| Drempelvrij | Belgium | 2.2.10 | **Skipped** | website | None | – | not stated |
| Handy.Brussels | Brussels | 2.2.11 | **Skipped** | website | None | – | not stated |
| All Access (Province of Luxembourg) | Wallonia | 2.2.12 | **Skipped** | website | None | – | not checked |
| Euan's Guide | UK, worldwide | 2.2.13 (heading only) | **Skipped** (terms forbid) | website | None | – | [terms](https://www.euansguide.com/terms-conditions) §16: no text or data mining, no scraping |
| Forêt de Saint-Hubert accessible | Wallonia | 2.2.14 (heading only) | **Skipped** | website | None | – | not checked |
| VisitWallonia | Wallonia | 2.3.2 | **Skipped** (refers to Access-i) | website | None | – | consultation only |
| Tourisme en Hauts-de-France | Hauts-de-France | 2.3.3 | **Skipped** (data comes through DATAtourisme) | website | None | – | not checked |
| Apidae | France | 2.3.4 | **Skipped** | API ([dev docs](https://dev.apidae-tourisme.com)) for members | None | access conditions not stated | not stated |
| My Easy Access | Marseille, Vichy, Clermont-Ferrand | 2.3.6 | **Skipped** | website, app, PDF | None | – | not checked |
| MeerMobiel | Flanders, Brussels | 2.4.2 | **Skipped** (information only, no data) | website | None | – | not stated |
| StreetCo, StreetNav | France | 2.5.1 | **Skipped** | app; B2B API for cities (not public) | None | on request | not stated |
| Okeenea, Evelity | France | 2.5.2 | **Skipped** | app | None | – | [scraping prohibited](https://www.evelity.com/en/legal-information) |
| Wemap | France | 2.5.3 | **Skipped** (platform, no data of its own) | API ([documented](https://developers.getwemap.com/docs/rest), access on request) | None | on request | not stated |
| Ezymob, Handimap/HITinéraire, Route4u, PIAF | France | 2.5.4, 2.5.5 | **Skipped** | app (Handimap: B2B routing API) | None | – | not checked |
| Iedereen Fietst, Routen, RouteYou, VisitVlaamsBrabant, Gfietst.be | Flanders | 2.6.1 | **Skipped** | website | None | – | not checked; Routen "all rights reserved" |
| Cirkwi | France | 2.6.1 | **Skipped** | website; no public API documentation found | None | – | [CGU](https://www.cirkwi.com/fr/cgu): no derived works without permission |
| Zon, Zee … Zorgeloos; Handiplage | coast BE; France | 2.6.2 | **Skipped** (knowledge, not data) | website | None | – | not stated |
| Parkeerhulp België | Belgium | 2.6.3 | **Skipped** (not public) | website behind a Cloudflare Access login | None | login | not stated |
| Toilettes Publiques | France | 2.6.4 | **Skipped** (reach through OSM) | website | None | – | [ODbL](https://www.toilettespubliques.fr/mentions-legales/) (OSM) |
| HogeNood | Netherlands | 2.6.4 | **Skipped** (paid) | API in the paid Goud package only | None | paid | [business terms](https://www.hogenood.nl/juridisch-algemene-voorwaarden-bedrijven) |
| Changing Places (Inter) | Flanders | 2.6.4 | **Skipped** (no dataset) | website (map) | None | – | not stated |
| Resto.be, Booking.com | Belgium, worldwide | 2.6.5, 2.6.7 | **Skipped** (commercial, self-declared) | website | None | – | not checked |
| Google Places | worldwide | 2.7.3 | **Skipped** (paid, restrictive terms) | API (`accessibilityOptions`) | None | yes, paid (Place Details Pro) | [terms](https://cloud.google.com/maps-platform/terms/maps-service-terms): only coordinates may be cached, 30 days; no use with non-Google maps |
| Apple Maps | worldwide | 2.7.4 | **Skipped** (no accessibility fields in the API) | API | None | yes | not checked |
| BIM models | – | 2.8 | **Skipped** (no public source) | – | None | – | – |
| data.gov.be | Belgium | 2.1.1.1 | **Portal** | DCAT-AP dump ([CC0](https://github.com/Fedict/dcat)); experimental LDF server | – | no | metadata CC0 |
| data.gouv.fr | France | 2.1.1.2 | **Portal** | API ([swagger](https://www.data.gouv.fr/api/1/swagger.json)); official read-only [MCP server](https://guides.data.gouv.fr/intelligence-artificielle/le-serveur-mcp-de-data.gouv.fr) | – | no | per dataset |
| accessibilite.data.gouv.fr | France | 2.1.3 | **Portal** (front-end over data.gouv.fr) | via the data.gouv.fr API | – | no | etalab-2.0 for site content |
| Datavindplaats / metadata.vlaanderen.be | Flanders | 2.1.2 | **Portal** | Datavindplaats API (key by e-mail); metadata.vlaanderen.be is a public GeoNetwork with CSW | – | Datavindplaats only | not stated |
| ODWB | Wallonia, Brussels | 2.1.2 | **Portal** (and source of 6 added datasets) | API (Explore v2.1) | – | no | [per dataset](https://www.odwb.be/terms/terms-and-conditions/) |
| Open Data Hauts-de-France, Géo2France | Hauts-de-France | 2.1.2, 2.1.3 | **Portal** | GeoNetwork API, CSW | – | no | per record |
| transportdata.be | Belgium | 2.1.3 | **Portal** | CKAN API (in maintenance on 2026-11-18) | – | no | per dataset |
| transport.data.gouv.fr | France | 2.1.3, 2.4.1 | **Portal** | API with [OpenAPI](https://transport.data.gouv.fr/api/openapi) | – | no | per dataset |
| data.belgianmobility.io | Belgium | 2.4.2 | **Portal** (and source of 3 added datasets) | dataset downloads, GTFS-RT | – | no; registration raises quota | CC BY 4.0 |
| geo.be, cartes.gouv.fr | BE, FR | 2.1.3 | **Portal** | map viewers and catalogs | – | – | per dataset |

## Added sources

Each of these has a `registration.json` in this folder and passes `make test` / `make e2e`. Dataset ids and sub-catalogs are listed in [AGENTS.md](../AGENTS.md#catalog-and-sources).

| Registration | Why this integration |
| --- | --- |
| `iedereenoveral/` | The raw API returns 130 KB per place, numeric ids and silently drops array values, so the proxy reshapes it for agents ([README](iedereenoveral/README.md)). |
| `pictoaccess/` | The PictoAccess API is unavailable; PictoAccess provided an export. The export is not public and is git-ignored. The open data.gouv.fr subset only has 0/1/2 levels per disability group. |
| `acceslibre/` | Its own API has an OpenAPI; registering it is enough. Known quirks (`zone`, `commune`, duplicates) are in AGENTS.md. |
| `opendatasoft/` (11 datasets) | All Opendatasoft portals share one Explore API with an OpenAPI and a DCAT export, so `make_registrations.py` generates the registrations and copies the publisher's DCAT. |
| `be-transit/` (4 datasets) | GTFS zips (12 to 184 MB) cannot be queried; the proxy loads a daily snapshot and answers per stop. |

**Follow-up:** the Acceslibre registration still says its licence is unconfirmed. The same data is published on data.gouv.fr under Licence Ouverte 2.0, but the API itself states no licence, so the registration keeps a note rather than a licence (open work 2 in AGENTS.md).

## Candidates, in suggested order

| # | Source | Why it is worth it | Next step |
| --- | --- | --- | --- |
| 1 | **Toerisme Vlaanderen linked open data** | Flemish accommodation and attractions with an `AccessibilityInformation` model (about 40 properties) and the A / A+ labels, open SPARQL, no key. It fills the Flanders tourism gap and lets an agent verify an A-label. | Ask Toerisme Vlaanderen for the licence (none stated). Then an adapter that turns a few SPARQL queries into OpenAPI operations (open work 8). |
| 2 | **DATAtourisme** | National French tourism data with accessibility properties and Tourisme & Handicap labels; Licence Ouverte 2.0. | Request a free key; check whether `api.datatourisme.fr` has an OpenAPI. Its bulk "Diffuseur" feeds close in October 2027, so use the API. |
| 3 | **Accessibility.Cloud** | Aggregates many sources in one schema (A11yJSON), with licence per record. | Create a non-commercial token; adapter (no OpenAPI). Check which sources it holds for BE and FR. |
| 4 | **OpenStreetMap (Overpass)** | `wheelchair=*`, toilets, kerbs; covers OnWheels, Wheelmap and Toilettes Publiques at once. | Adapter with a few fixed queries (open work 11); attribute ODbL. |
| 5 | **De Lijn open data** | De Lijn's three-level stop classification (autonomous, with help, visual) is richer than GTFS `wheelchair_boarding`. | Get the free key; check that the API actually returns the classification (not found in the public docs or OGC layer). |
| 6 | **More Opendatasoft datasets** | Cheapest additions: one line in `datasets.yaml` each. | Search ODWB, SNCF and French regional portals for PMR datasets. |
| 7 | **French GTFS feeds** | Stop accessibility for French networks (Lille, Limoges for the golden questions). The `gtfs-stops` API lacks accessibility, so feeds must be read. | Reuse the `be-transit/` snapshot approach for a few networks; licence per feed. |
| 8 | **UiTdatabank** | Accessible events, with a `facility` taxonomy (wheelchair, audio description, induction loop). | Decide whether the €125/year production plan is acceptable; terms forbid commercial use. |
| 9 | **VisitFlanders Toegankelijkheidszoeker** | Same kind of data as #1, through an undocumented API. | Only if #1 does not hold the same records; needs permission (website terms forbid storing). |
| 10 | **Navigeer en Parkeer** | Measured disabled parking spaces in West Flanders. | Ask Inter for the files and reuse terms. |
| 11 | **SNCF `accessibilite_gares` NeTEx, OpenRouteService** | Station detail; wheelchair routing. | Low priority. |

## Blocked

| Source | Waiting for | Rule |
| --- | --- | --- |
| Access-i | written approval (requested by e-mail) | No adapter, crawler or snapshot before approval (AGENTS.md, open work 1). Golden questions 4 and 6 depend on it. |

## Literature study: inconsistencies found

Checked against the live sources on 2026-11-18. Section numbers refer to `literatuurstudie.pdf`.

| § | Study says | Found |
| --- | --- | --- |
| 2.2.1, 3.2.1 | PictoAccess gives a letter score per group and publishes letter scores on data.gouv.fr | The full export and the data.gouv.fr dataset use numeric levels (data.gouv.fr: 0, 1, 2; export: 2, 1, -1, 0, -2), not letters. Letters only appear on the banner. |
| 2.2.13, 2.2.14 | Euan's Guide, Forêt de Saint-Hubert accessible | Headings only, no text. Euan's Guide's terms forbid text and data mining. |
| 2.9 | Overview table | Still a TODO. This file's overview can serve as its basis. |
| 2.1.2 | Datavindplaats has a documented API with a key | Two systems: Datavindplaats (key by e-mail, no public documentation found) and metadata.vlaanderen.be (public GeoNetwork with CSW, no key). |
| 2.1.3 | Toerisme Vlaanderen has "only two downloadable datasets" | Two files of one dataset (Basisregister Logies, CSV and TTL). Through SPARQL it also holds accessibility information and the A / A+ labels, plus a dataset on attractions, not offered as a download. No licence stated. |
| 2.2.2 | Acceslibre API is free but access must be requested | Correct. The dataset licence is Licence Ouverte 2.0, which the study does not mention. |
| 2.2.4 | Toegankelijkheidswijzer has no API or dataset | Its data now feeds IedereenOveral (per Inter), so IedereenOveral's API is the machine route. |
| 2.3.1 | Toegankelijkheidszoeker has an undocumented backend API | Correct; it answers without a key. The study does not link it to the linked open data above. |
| 2.3.4 | Apidae API is paid | Access conditions and price are not stated on the developer site; unverified. |
| 2.3.5 | DATAtourisme via API with key | Correct. Also daily exports on data.gouv.fr; bulk Diffuseur feeds close in October 2027. Licence Ouverte 2.0 not mentioned. |
| 2.3.7 | UiTdatabank: free up to a limit, then paid | Test environment free, production from €125 a year, 60,000 calls a day. The study does not mention its accessibility `facility` taxonomy. |
| 2.4.1 | SNCF accessibility of stations via a dataset and API | All datasets exist (ODbL). `accessibilite_gares` holds one record: a link to a NeTEx file. Accès Plus has been replaced by Assist'enGare (January 2024). |
| 2.4.2 | belgianmobility APIs need a free profile | Static GTFS and NeTEx download without a key (anonymous: 100 requests a day); registration raises the quota. Licence CC BY 4.0. |
| 2.4.2 | iRail GitHub has the information "in GTFS format"; accessibility only as `hasPRMsection` | The repository holds CSV files derived from the NMBS GTFS. `facilities.csv` has station accessibility (ramp, lift, platform height, induction loop). The field is spelled `hasPrmSection`. |
| 2.4.2 | De Lijn publishes its stop classification through its open data portal | Not found in the public API documentation or the stops OGC layer; unverified. The symbols are explained on [delijn.be](https://www.delijn.be/nl/content/toegankelijke-haltes/). |
| 2.5.1 to 2.5.5 | No public API for StreetCo, Wemap, Handimap | Wemap has a publicly documented API (access on request); StreetCo and Handimap offer B2B APIs. None publishes open data. |
| 2.6.3 | Parkeerhulp België maps parking from public sources | The site is behind a login; not publicly reachable. |
| 2.7.2 | Accessibility.Cloud: key after creating an account | Free access is for non-commercial use only. |
| 2.7.3 | Google Places offers accessibility tags | Correct (`accessibilityOptions`), but paid (Place Details Pro) and the terms allow caching only coordinates, for 30 days. |
| 3.2.5 | Tourisme & Handicap dataset on data.gouv.fr | Correct, but no licence is stated (`notspecified`); the same list on data.economie.gouv.fr has none either. |
| headings | numbering | "2.2.1.1" is reused under Acceslibre (should be 2.2.2.1); 3.2.5 is used twice; 2.6.6 is missing. |

Not verified on 2026-11-18: All Access, Forêt de Saint-Hubert, the cycling-route sites, Okeenea, Ezymob, PIAF, Resto.be, Booking.com, the transportdata.be CKAN API (in maintenance), Accessibility.Cloud's list of sources (needs a token), and the OpenRouteService licence.

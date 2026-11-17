# PictoAccess adapter

`sources/pictoaccess` serves a local export of the PictoAccess accessibility export (`pictoaccess_export.py`, one JSON file per place). It loads the files at start-up and never calls PictoAccess. The export is not part of this repository; compose mounts `pictoaccess_dump/places` read-only (override with `PICTOACCESS_PLACES_DIR` in `sources/.env`). Photos are not served; records keep their PictoAccess photo URLs.

| Operation | What it does |
| --- | --- |
| `pictoaccess_search_places` | Filters: `q` (name/description), `address`, `city`, `postal_code` (prefix), `country` (ISO 2), `category` (name or slug, e.g. building function), `group`, `latitude`+`longitude`+`radius_km`, and a level filter per disability type. Returns summaries. |
| `pictoaccess_get_place` | The complete PictoAccess record, unchanged. |
| `pictoaccess_related_places` | Places sharing a group with this place (per group), and places within `radius_km`. |
| `pictoaccess_facets` | Categories, groups, countries, disability types, levels with counts. |

## Mapping

- **Levels.** PictoAccess has no letter grades; each place has a level per disability type in `accessibility.handicaps`: `2` autonomous, `1` with_help, `-1` autonomous_or_with_help (PictoAccess does not say which), `0` inaccessible, `-2` unknown. Checked against `readable_handicaps[].level` for every place in the export.
- **Disability types.** `moteur` → mobility (unable to walk), `senior` → walking_difficulty, `psychique` → cognitive, `mal-voyant` → blind, `mal-voyant-partiel` → low_vision, `mal-entendant` → deaf, `mal-entendant-partiel` → hard_of_hearing, `femme-enceinte` → temporary_mobility.
- **Groups.** PictoAccess `brands`: the organisation or site a place belongs to, e.g. "Université de Rouen Normandie" and per campus "Université Rouen Normandie - Campus Madrillet". About 44% of places have one. Places without a group (e.g. some campus buildings) are only found as related through the `nearby` list.
- **Country.** Free text upstream (`france`, `France`, `FR`, ...), normalised to ISO codes; 627 places have none and are returned with `country: null`, not assumed French.
- Only `published` places are served.

Reuse terms are not yet confirmed with PictoAccess.

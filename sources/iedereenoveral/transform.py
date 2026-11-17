"""Turn IedereenOveral (Xano) responses into compact place records.

The upstream detail record is ~130 KB, mostly database internals (ids, timestamps, image metadata,
question definitions repeated per answer). Agents need only: what the place is, where, its medal,
and the answered accessibility questions as short statements. That is ~5-10% of the size.
"""

import re
from datetime import datetime, timezone
from html import unescape

SITE = "https://iedereen.overal.info"

# English slugs for the upstream location types (Dutch names in /locationtype).
CATEGORIES = {
    "food_and_drink": "Eten en drinken",
    "public_toilet": "Publiek toilet",
    "changing_place": "Changing place",
    "museum": "Museum",
    "parking": "Parkeerplaatsen",
}
CATEGORY_SLUG = {v: k for k, v in CATEGORIES.items()}

# Common non-Dutch names for towns; the upstream city table uses Dutch names (and 'Brussels').
TOWN_ALIASES = {
    "ghent": "gent", "gand": "gent", "bruges": "brugge", "antwerp": "antwerpen", "anvers": "antwerpen",
    "louvain": "leuven", "malines": "mechelen", "courtrai": "kortrijk", "ostend": "oostende",
    "ostende": "oostende", "bruxelles": "brussels", "brussel": "brussels", "ypres": "ieper",
}


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v not in (None, "", [], {})}


def _iso(ms) -> str | None:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).date().isoformat() if ms else None


def _point(coordinates) -> dict | None:
    data = (coordinates or {}).get("data") or {}
    return {"lat": data["lat"], "lon": data["lng"]} if "lat" in data and "lng" in data else None


class Lookups:
    """Upstream reference tables: cities, medals (valuation), location types, filters, audiences."""

    def __init__(self, city, valuation, locationtype, filter, targetaudience):
        self.cities = city
        self.medal_by_id = {v["id"]: v["name"].lower() for v in valuation}
        self.medal_by_nl = {v["name_nl"].lower(): v["name"].lower() for v in valuation}
        self.medal_ids = {v["name"].lower(): v["id"] for v in valuation}
        self.type_ids = {t["name"]: t["id"] for t in locationtype}
        self.filter_by_id = {f["id"]: f["name"] for f in filter}
        self.filter_ids: dict[str, list[int]] = {}
        for f in filter:
            self.filter_ids.setdefault(f["name"].lower(), []).append(f["id"])
        self.audience_by_id = {a["id"]: a["name"] for a in targetaudience}

    def city_ids(self, town: str) -> list[int]:
        """All city ids whose name or postcode matches; a town has one id per postcode."""
        t = town.strip().lower()
        t = TOWN_ALIASES.get(t, t)
        return [c["id"] for c in self.cities if c["city"].strip().lower() == t or c["zipcode"] == t]


def summary(item: dict, lk: Lookups) -> dict:
    """A search hit. Upstream list items carry name, address and medal only inside an HTML card."""
    html = item.get("map_html") or ""
    name = re.search(r"<b>(.*?)</b>", html, re.S)
    addr = re.search(r"<p[^>]*>(.*?)<br>(.*?)</p>", html, re.S)
    medal = re.search(r'<img[^>]*alt="([^"]*)"', html)
    type_name = (item.get("_locationtype") or {}).get("name")
    return _clean({
        "id": item.get("slug"),
        "name": unescape(name.group(1)).strip() if name else None,
        "category": CATEGORY_SLUG.get(type_name, type_name),
        "address": ", ".join(unescape(x).strip() for x in addr.groups()) if addr else None,
        "location": _point(item.get("coordinates")),
        "medal": lk.medal_by_nl.get(unescape(medal.group(1)).lower()) if medal else None,
        "source_url": f"{SITE}/locaties/{item['slug']}" if item.get("slug") else None,
    })


def _statement(r: dict, lk: Lookups) -> dict | None:
    req = r.get("requirement") or {}
    if not (r.get("is_answered") and r.get("is_visible")) or req.get("type") == "Image":
        return None
    answer = r.get("answer")
    if isinstance(answer, list):
        answer = ", ".join(map(str, answer))
    option = r.get("answeroption") or {}
    if req.get("type") == "Number":
        value = f"{answer} {req.get('unit_of_measure') or ''}".strip()
        detail = None
    else:
        value = option.get("display_value") or answer
        detail = option.get("label") if option.get("label") not in (None, value) else None
    if value in (None, ""):
        return None
    return _clean({
        "criterion": req.get("question") or req.get("name"),
        "value": value,
        "detail": detail.strip().rstrip(":") if detail else None,
        "audiences": [lk.audience_by_id[a] for a in r.get("targetaudience_id") or [] if a in lk.audience_by_id],
    })


def detail(d: dict, lk: Lookups, area: str | None = None) -> dict:
    """One place: identity, address, medal, and per area the answered accessibility questions."""
    city = d.get("city") or {}
    areas = []
    for c in d.get("categories") or []:
        if area and c.get("name", "").lower() != area.lower():
            continue
        statements = []
        for s in c.get("subcategories") or []:
            for r in s.get("requirements") or []:
                st = _statement(r, lk)
                if st:
                    statements.append({"topic": s.get("name"), **st})
        if statements:
            areas.append(_clean({"area": c.get("name"), "medal": lk.medal_by_id.get(c.get("valuation_id")),
                                 "statements": statements}))
    type_name = (d.get("_locationtype") or {}).get("name")
    return _clean({
        "id": d.get("slug"),
        "name": d.get("name"),
        "category": CATEGORY_SLUG.get(type_name, type_name),
        "address": _clean({"street": f"{d.get('street') or ''} {d.get('number') or ''}".strip(),
                           "postcode": city.get("zipcode"), "town": city.get("city"),
                           "province": d.get("province"), "country": d.get("country")}),
        "location": _point(d.get("coordinates")),
        "medal": lk.medal_by_id.get(d.get("valuation_id")),
        "confirmed_by_inter": d.get("confirmed_by_inter"),
        "features": sorted({lk.filter_by_id[f] for f in d.get("gold_filter_id") or [] if f in lk.filter_by_id}),
        "contact": _clean({"phone": d.get("phone"), "website": d.get("website"), "email": d.get("email")}),
        "updated_at": _iso(d.get("updated_at")),
        "accessibility": areas,
        "source_url": f"{SITE}/locaties/{d['slug']}" if d.get("slug") else None,
    })

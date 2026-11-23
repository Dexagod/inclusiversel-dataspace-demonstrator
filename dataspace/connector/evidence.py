"""Evidence per record: the record's own page, how its facts were checked, by whom, and when (ADR 0008).

A registration's `records` block says where the records sit in an answer and which fields hold this, e.g.
  {"at": ["results"], "name": ["nom"], "url": ["web_url"], "date": ["updated_at"],
   "basis": [{"field": "user_type", "equals": "gestionnaire", "method": "self_declared", "by": "the manager"}],
   "default": {"method": "crowd_sourced"}}
Paths are dotted ("accessibility.updated_at"); a value with "{...}" is a template filled from the record.
"""

import re

MISSING = object()
LIMIT = 50  # records listed per answer


def get(obj, path: str):
    for part in path.split(".") if path else []:
        if not isinstance(obj, dict) or part not in obj:
            return MISSING
        obj = obj[part]
    return obj


def _text(v) -> str:
    return ", ".join(str(x) for x in v) if isinstance(v, list) else str(v)


def fill(template: str | None, rec: dict) -> str | None:
    """A field path, or a template such as "https://x.org/{slug}"; None when a value is missing or empty."""
    if not template:
        return None
    if "{" not in template:
        v = get(rec, template)
        return None if v is MISSING or v in (None, "", []) else _text(v)
    values = {}
    for path in re.findall(r"\{([^{}]+)\}", template):
        v = get(rec, path)
        if v is MISSING or v in (None, "", []):
            return None
        values[path] = _text(v)
    return re.sub(r"\{([^{}]+)\}", lambda m: values[m.group(1)], template)


def first(rec: dict, options: list[str]) -> str | None:
    return next((v for v in (fill(o, rec) for o in options or []) if v), None)


def words(text: str | None, rec: dict) -> str | None:
    """`by`, `label` and `note` are plain text, optionally with {field} placeholders (never a bare field path)."""
    return fill(text, rec) if text and "{" in text else text


def _outcome(rule: dict, rec: dict) -> dict:
    return {"basis": rule["method"], **{k: words(rule.get(k), rec) for k in ("by", "label", "note")}}


def basis(rec: dict, rules: list[dict], default: dict | None) -> dict:
    """First matching rule wins. A rule on a field this answer lacks makes the basis unknown: a search hit may
    leave out what only the detail says."""
    for rule in rules or []:
        v = get(rec, rule["field"])
        if rule.get("present"):
            if v is not MISSING and v not in (None, "", [], False):
                return _outcome(rule, rec)
            continue
        if v is MISSING:
            return {"basis": "unknown", "note": f"'{rule['field']}' is not in this answer; the record's detail has it"}
        if str(v).lower() == str(rule.get("equals")).lower():
            return _outcome(rule, rec)
    return _outcome(default, rec) if default else {"basis": "unknown"}


def records(body, spec: dict) -> list[dict]:
    """One evidence entry per record in a source answer, in the answer's order."""
    items = None
    for path in spec.get("at") or []:
        v = get(body, path)
        if isinstance(v, (list, dict)):  # a list of records, or one record under a key (e.g. "place")
            items = v if isinstance(v, list) else [v]
            break
    if items is None:
        if isinstance(body, list):
            items = body
        elif isinstance(body, dict) and first(body, spec.get("name")):
            items = [body]  # a detail answer: the record itself
        else:
            return []
    out = []
    for rec in items[:LIMIT]:
        if not isinstance(rec, dict):
            continue
        entry = {"name": first(rec, spec.get("name")), "url": first(rec, spec.get("url")),
                 "date": first(rec, spec.get("date")), **basis(rec, spec.get("basis"), spec.get("default"))}
        out.append({k: v for k, v in entry.items() if v})
    return out

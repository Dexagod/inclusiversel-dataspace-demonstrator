"""Write <id>/registration.json for every entry of datasets.yaml, from the Opendatasoft portal's own metadata.

The registration points the catalog at the portal's live Explore API (its OpenAPI) and at the portal's DCAT export
for the dataset, which the catalog copies verbatim.
"""

import html
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import httpx
import yaml

HERE = Path(__file__).parent
UA = {"user-agent": "accessibility-dataspace-demo/0.1 (open research demonstrator)"}


def text(s: str | None, limit: int) -> str:
    s = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()
    return s if len(s) <= limit else s[:limit].rsplit(" ", 1)[0] + " …"


def registration(entry: dict) -> dict:
    api = f"https://{entry['portal']}/api/explore/v2.1"
    meta = httpx.get(f"{api}/catalog/datasets/{entry['dataset_id']}", headers=UA, timeout=30).raise_for_status().json()
    m = meta["metas"]["default"]
    fields = ", ".join(f"{f['name']} ({f.get('label') or f['type']})" for f in meta["fields"])
    how = (f"Query it live with operation getRecords and dataset_id='{entry['dataset_id']}'. Filter with 'where' "
           f"(ODSQL, e.g. search(\"Lille\") or a field comparison), choose fields with 'select', at most 100 per 'limit'. "
           f"{m.get('records_count')} records. Fields: {fields}.")
    reg = {
        "id": entry["id"],
        "catalog": entry["catalog"],
        "title": m["title"],
        "description": " ".join(x for x in [text(m.get("description"), 700), entry.get("hint"), how] if x),
        "publisher": {"name": m.get("publisher") or entry["portal"]},
        "endpoint_url": f"{api}/",
        "openapi_url": f"{api}/swagger.json",
        "source_dcat_url": f"{api}/catalog/exports/dcat?where=" + quote(f'dataset_id="{entry["dataset_id"]}"'),
        "conforms_to": [{"url": f"{api}/catalog/datasets/{entry['dataset_id']}",
                         "title": f"Schema of '{m['title']}': its fields with name, type and label (Opendatasoft)"}],
        "keywords": sorted(set((m.get("keyword") or []) + entry.get("keywords", []))),
        "themes": ["accessibility"] + (["mobility"] if entry["catalog"].endswith("-mobility") else []),
        "languages": [lang for lang in [m.get("language") or "fr"] if lang in {"nl", "fr", "en", "de"}],
        "spatial": entry.get("spatial", []),
        "landing_page": f"https://{entry['portal']}/explore/dataset/{entry['dataset_id']}/",
        "access_note": "Open Explore API; no key needed for reading.",
    }
    if m.get("license_url"):
        reg["licence"] = m["license_url"]
    else:
        reg["licence_note"] = f"Licence as stated by the publisher: {m.get('license') or 'none'}."
    reg.update({k: v for k, v in entry.items() if k not in {"portal", "dataset_id", "catalog", "keywords", "spatial", "hint"}})
    return reg


if __name__ == "__main__":
    for entry in yaml.safe_load((HERE / "datasets.yaml").read_text(encoding="utf-8")):
        reg = registration(entry)
        out = HERE / entry["id"] / "registration.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {out.relative_to(HERE)}  ({reg.get('licence') or reg.get('licence_note')})", file=sys.stderr)
        time.sleep(1)

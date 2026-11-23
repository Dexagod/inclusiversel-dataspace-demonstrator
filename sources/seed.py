"""Set up the data space's content through its public HTTP APIs.

  python seed.py register    PUT every **/registration.json to the catalog (needs the source proxies running)
  python seed.py knowledge   ingest domain-knowledge.yaml into the vocabulary hub (needs internet for `url:` entries;
                             `file:` entries are uploaded from this repository), and set permanent-context.md as the
                             hub's permanent context
"""

import os
import sys
from pathlib import Path

import httpx
import yaml

HERE = Path(__file__).parent
CATALOG = os.environ.get("CATALOG_URL", "http://localhost:8001").rstrip("/")
VOCHUB = os.environ.get("VOCHUB_URL", "http://localhost:8002").rstrip("/")


def register() -> int:
    failed = 0
    for f in sorted(HERE.glob("**/registration.json")):
        reg = yaml.safe_load(f.read_text(encoding="utf-8"))
        r = httpx.put(f"{CATALOG}/datasets/{reg['id']}", json=reg, timeout=30)
        print(f"{'+' if r.is_success else '!'} {r.status_code} {reg['id']}" + ("" if r.is_success else f": {r.text[:300]}"))
        failed += not r.is_success
    return failed


def knowledge() -> int:
    r = httpx.put(f"{VOCHUB}/context", json={"text": (HERE / "permanent-context.md").read_text(encoding="utf-8")}, timeout=30)
    print(f"{'+' if r.is_success else '!'} {r.status_code} permanent context" + ("" if r.is_success else f": {r.text[:200]}"))
    failed = 0 if r.is_success else 1
    for entry in yaml.safe_load((HERE / "domain-knowledge.yaml").read_text(encoding="utf-8")):
        if "file" in entry:  # a local file, path relative to this folder
            meta = {k: ",".join(v) if isinstance(v, list) else v for k, v in entry.items() if k != "file" and v}
            path = HERE / entry["file"]
            r = httpx.post(f"{VOCHUB}/documents", files={"file": (path.name, path.read_bytes())}, data=meta, timeout=600)
        else:
            r = httpx.post(f"{VOCHUB}/documents/url", json=entry, timeout=600)
        if r.is_success:
            d = r.json()
            print(f"{'=' if d['duplicate'] else '+'} {d['chunks']:4} chunks  {d['title']}")
        else:
            failed += 1
            print(f"! {r.status_code} {entry.get('url') or entry['file']}: {r.text[:200]}")
    return failed


if __name__ == "__main__":
    steps = {"register": register, "knowledge": knowledge}
    if len(sys.argv) != 2 or sys.argv[1] not in steps:
        sys.exit(__doc__)
    sys.exit(1 if steps[sys.argv[1]]() else 0)

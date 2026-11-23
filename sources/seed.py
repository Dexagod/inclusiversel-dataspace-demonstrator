"""Set up the data space's content through its public HTTP APIs.

  python seed.py full        everything: every data source and every document (local use, closed demos)
  python seed.py public      only what may be published: leaves out, and removes if present,
                             - data sources whose registration.json says "visibility": "private"
                             - documents tagged licence-restricted in domain-knowledge.yaml
  python seed.py register    only the data sources, all of them (as in full)
  python seed.py knowledge   only the documents, all of them (as in full), and permanent-context.md as the hub's
                             permanent context; needs internet for `url:` entries, `file:` entries are uploaded

Running public after full (or the other way round) switches a running data space between the two.
"""

import os
import sys
from pathlib import Path

import httpx
import yaml

HERE = Path(__file__).parent
CATALOG = os.environ.get("CATALOG_URL", "http://localhost:8001").rstrip("/")
VOCHUB = os.environ.get("VOCHUB_URL", "http://localhost:8002").rstrip("/")
RESTRICTED = "licence-restricted"


def register(public: bool = False) -> int:
    failed = 0
    for f in sorted(HERE.glob("**/registration.json")):
        reg = yaml.safe_load(f.read_text(encoding="utf-8"))
        private = reg.pop("visibility", "public") == "private"  # a seed setting, not catalog metadata
        if public and private:
            r = httpx.delete(f"{CATALOG}/datasets/{reg['id']}", timeout=30)
            print(f"- {r.status_code} {reg['id']} (private: removed)" if r.status_code != 404 else f"- {reg['id']} (private: not registered)")
            failed += r.status_code not in (204, 404)
            continue
        r = httpx.put(f"{CATALOG}/datasets/{reg['id']}", json=reg, timeout=30)
        print(f"{'+' if r.is_success else '!'} {r.status_code} {reg['id']}" + ("" if r.is_success else f": {r.text[:300]}"))
        failed += not r.is_success
    return failed


def knowledge(public: bool = False) -> int:
    r = httpx.put(f"{VOCHUB}/context", json={"text": (HERE / "permanent-context.md").read_text(encoding="utf-8")}, timeout=30)
    print(f"{'+' if r.is_success else '!'} {r.status_code} permanent context" + ("" if r.is_success else f": {r.text[:200]}"))
    failed = 0 if r.is_success else 1
    if public:  # remove what an earlier full run added
        for d in httpx.get(f"{VOCHUB}/documents", timeout=30).json():
            if RESTRICTED in (d.get("tags") or []):
                r = httpx.delete(f"{VOCHUB}/documents/{d['doc_id']}", timeout=30)
                print(f"- {r.status_code} {d['title']} ({RESTRICTED}: removed)")
                failed += not r.is_success
    for entry in yaml.safe_load((HERE / "domain-knowledge.yaml").read_text(encoding="utf-8")):
        if public and RESTRICTED in (entry.get("tags") or []):
            continue
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
    steps = {"register": register, "knowledge": knowledge,
             "full": lambda: register() + knowledge(),
             "public": lambda: register(public=True) + knowledge(public=True)}
    if len(sys.argv) != 2 or sys.argv[1] not in steps:
        sys.exit(__doc__)
    sys.exit(1 if steps[sys.argv[1]]() else 0)

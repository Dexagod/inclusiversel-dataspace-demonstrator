"""Set up the data space's content through its public HTTP APIs.

  python seed.py full        everything: every data source and every document (local use, closed demos)
  python seed.py public      only what may be published: leaves out, and removes if present,
                             - data sources whose registration.json says "visibility": "private"
                             - documents tagged licence-restricted in domain-knowledge.yaml
  python seed.py register    only the data sources, all of them (as in full)
  python seed.py knowledge   only the documents, all of them (as in full), and permanent-context.md as the hub's
                             permanent context; needs internet for `url:` entries, `file:` entries are uploaded
  python seed.py clear-catalog     remove every dataset from the catalog
  python seed.py clear-knowledge   remove every document from the vocabulary hub
  python seed.py status            what the catalog, hub, connector and viewer hold and whether they answer

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
    present = httpx.get(f"{VOCHUB}/documents", timeout=30).json()
    for entry in yaml.safe_load((HERE / "domain-knowledge.yaml").read_text(encoding="utf-8")):
        if public and RESTRICTED in (entry.get("tags") or []):
            continue
        r = ingest(entry)
        if r.is_success and too_short(r.json(), entry, present):
            httpx.delete(f"{VOCHUB}/documents/{r.json()['doc_id']}", timeout=30)
            r = ingest(entry)  # some sites now and then serve only a loading screen; one more try
        if r.is_success:
            d = r.json()
            print(f"{'=' if d['duplicate'] else '+'} {d['chunks']:4} chunks  {d['title']}")
            failed += keep_one_version(d, entry, present)
        else:
            failed += 1
            print(f"! {r.status_code} {entry.get('url') or entry['file']}: {r.text[:200]}")
    return failed


def ingest(entry: dict) -> httpx.Response:
    if "file" in entry:  # a local file, path relative to this folder
        meta = {k: ",".join(v) if isinstance(v, list) else v for k, v in entry.items() if k != "file" and v}
        path = HERE / entry["file"]
        return httpx.post(f"{VOCHUB}/documents", files={"file": (path.name, path.read_bytes())}, data=meta, timeout=600)
    return httpx.post(f"{VOCHUB}/documents/url", json=entry, timeout=600)


def earlier_versions(new: dict, entry: dict, present: list[dict]) -> list[dict]:
    return [d for d in present if d["doc_id"] != new["doc_id"] and (
        (entry.get("url") and d.get("url") == entry["url"]) or (entry.get("file") and d.get("title") == new["title"]))]


def too_short(new: dict, entry: dict, present: list[dict]) -> bool:
    """Less than half as long as the longest earlier version: the page probably did not load properly."""
    same = earlier_versions(new, entry, present)
    return bool(same) and new["chunks"] < max(d["chunks"] for d in same) / 2


def keep_one_version(new: dict, entry: dict, present: list[dict]) -> int:
    """A changed page is a new document (new content, new id): drop the older versions of the same entry. Unless the
    new one is less than half as long, which usually means the page did not load (a cookie wall, a loading screen):
    then keep the old one and drop the new."""
    same = earlier_versions(new, entry, present)
    if not same:
        return 0
    old = max(same, key=lambda d: d["chunks"])
    if too_short(new, entry, present):
        print(f"! kept the earlier version of {new['title']}: the new one has {new['chunks']} chunks against "
              f"{old['chunks']}; check the page")
        drop = [new]
    else:
        drop = same
    for d in drop:
        httpx.delete(f"{VOCHUB}/documents/{d['doc_id']}", timeout=30)
    return 0  # a warning, not a failure: the hub still holds a good version


def clear_catalog() -> int:
    failed = 0
    for d in httpx.get(f"{CATALOG}/datasets", timeout=30).json():
        r = httpx.delete(f"{CATALOG}/datasets/{d['id']}", timeout=30)
        print(f"- {r.status_code} {d['id']}")
        failed += not r.is_success
    return failed


def clear_knowledge() -> int:
    failed = 0
    for d in httpx.get(f"{VOCHUB}/documents", timeout=30).json():
        r = httpx.delete(f"{VOCHUB}/documents/{d['doc_id']}", timeout=30)
        print(f"- {r.status_code} {d['title']}")
        failed += not r.is_success
    return failed


def status() -> int:
    """One line per service; private and restricted content counted, so the mode is visible."""
    private = {yaml.safe_load(f.read_text(encoding="utf-8"))["id"] for f in HERE.glob("**/registration.json")
               if '"visibility": "private"' in f.read_text(encoding="utf-8")}
    checks = {
        "catalog": (f"{CATALOG}/datasets", lambda b: f"{len(b)} datasets, private among them: "
                    f"{sorted(private & {d['id'] for d in b}) or 'none'}"),
        "vocabulary hub": (f"{VOCHUB}/documents", lambda b: f"{len(b)} documents, {sum(RESTRICTED in d['tags'] for d in b)} "
                           f"{RESTRICTED}, {sum(d['chunks'] for d in b)} passages"),
        "connector": (os.environ.get("CONNECTOR_URL", "http://localhost:8800") + "/health", lambda b: "answers"),
        "viewer": (os.environ.get("VIEWER_URL", "http://localhost:8090") + "/health", lambda b: "answers"),
    }
    down = 0
    for name, (url, describe) in checks.items():
        try:
            r = httpx.get(url, timeout=10)
            r.raise_for_status()
            print(f"{name:15} {describe(r.json())}")
        except (httpx.HTTPError, ValueError) as e:
            print(f"{name:15} DOWN ({type(e).__name__}) at {url}")
            down += 1
    return down


if __name__ == "__main__":
    steps = {"register": register, "knowledge": knowledge,
             "full": lambda: register() + knowledge(),
             "public": lambda: register(public=True) + knowledge(public=True),
             "clear-catalog": clear_catalog, "clear-knowledge": clear_knowledge, "status": status}
    if len(sys.argv) != 2 or sys.argv[1] not in steps:
        sys.exit(__doc__)
    sys.exit(1 if steps[sys.argv[1]]() else 0)

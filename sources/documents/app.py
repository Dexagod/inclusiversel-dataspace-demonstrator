"""Documents as datasets: a published web page or PDF, served as sections an agent can outline, search and read.

Every `<id>/registration.json` in this folder is one document. Its first entry in `distributions` is the page or
PDF to read; the adapter mounts a sub-API at /<id>/ with its own OpenAPI, so each document is its own catalog
entry. Documents are fetched at most every REFRESH_HOURS (honouring robots.txt), kept in memory, never changed.
"""

import json
import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path as FilePath
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from fastapi import FastAPI, HTTPException, Path, Query

from extract import fold, html_sections, pdf_sections, with_ids

HERE = FilePath(__file__).parent
REFRESH_S = float(os.environ.get("REFRESH_HOURS", "24")) * 3600
RETRY_S = 900
MAX_BYTES = 50_000_000
AGENT = "accessibility-dataspace-demo"
UA = {"user-agent": f"{AGENT}/0.1 (open research demonstrator)"}
TEXT_LIMIT = 1500  # characters per search hit; get_section gives the rest


class Refused(Exception):
    pass


def fetch(url: str) -> httpx.Response:
    parts = urlsplit(url)
    robots = RobotFileParser()
    try:
        r = httpx.get(f"{parts.scheme}://{parts.netloc}/robots.txt", headers=UA, timeout=20, follow_redirects=True)
        robots.parse(r.text.splitlines() if r.status_code == 200 else [])
    except httpx.HTTPError:
        robots.parse([])
    if not robots.can_fetch(AGENT, url):
        raise Refused(f"robots.txt of {parts.netloc} does not allow fetching {url}")
    r = httpx.get(url, headers=UA, timeout=60, follow_redirects=True)
    r.raise_for_status()
    if len(r.content) > MAX_BYTES:
        raise Refused(f"{url} is larger than {MAX_BYTES // 1_000_000} MB")
    return r


def parse(r: httpx.Response) -> dict:
    ctype = r.headers.get("content-type", "").lower()
    if r.content[:5] == b"%PDF-" or "pdf" in ctype:
        title, sections, date = pdf_sections(r.content)
        kind = "application/pdf"
    else:
        title, sections = html_sections(r.text)
        date, kind = None, "text/html"
    return {"title": title, "sections": with_ids(sections), "document_date": date, "media_type": kind,
            "last_modified": r.headers.get("last-modified")}


class Document:
    def __init__(self, reg: dict):
        self.reg = reg
        self.url = reg["distributions"][0]["url"]
        self.data: dict | None = None
        self.next_refresh = 0.0
        self.lock = threading.Lock()

    def get(self) -> dict:
        if self.data is not None and time.time() < self.next_refresh:
            return self.data
        with self.lock:
            if self.data is None or time.time() >= self.next_refresh:
                try:
                    data = parse(fetch(self.url))
                    data["retrieved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    old = self.data or {}
                    same = [s["text"] for s in data["sections"]] == [s["text"] for s in old.get("sections", [])]
                    data["content_changed_at"] = old["content_changed_at"] if same and old else data["retrieved_at"]
                    self.data, self.next_refresh = data, time.time() + REFRESH_S
                except (httpx.HTTPError, Refused, ValueError) as e:
                    if self.data is None:
                        raise HTTPException(503, f"the document could not be read: {e}; retry later",
                                            headers={"Retry-After": "300"}) from e
                    self.next_refresh = time.time() + RETRY_S  # keep serving the last good copy
        return self.data

    def provenance(self) -> dict:
        d = self.data or {}
        return {"source": self.reg["title"], "source_url": self.url, "publisher": self.reg["publisher"]["name"],
                "licence": self.reg.get("licence"), "licence_note": self.reg.get("licence_note"),
                "media_type": d.get("media_type"), "document_date": d.get("document_date"),
                "last_modified": d.get("last_modified"), "retrieved_at": d.get("retrieved_at"),
                "content_changed_at": d.get("content_changed_at"),
                "mode": f"text of the published document, fetched at most every {REFRESH_S / 3600:g} hours, unchanged"}


def summary(s: dict, limit: int | None = None) -> dict:
    text = s["text"] if limit is None or len(s["text"]) <= limit else s["text"][:limit] + " …"
    return {"id": s["id"], "heading_path": s["path"], "page": s["page"], "text": text}


def document_app(doc: Document) -> FastAPI:
    reg, p = doc.reg, doc.reg["id"].replace("-", "_")
    langs = ", ".join(reg.get("languages", [])) or "unknown"
    sub = FastAPI(
        title=f"{reg['title']} (document)",
        version="0.1.0",
        description=(
            f"{reg['description']}\n\nThis API serves the text of one published document, {doc.url} "
            f"(language: {langs}), as sections that follow the document's own headings; PDF sections are pages. "
            f"Use {p}_get_outline for the structure, {p}_search to find sections (search with words in the "
            f"document's language), and {p}_get_section for the full text of one section. Each answer gives "
            "document_date, last_modified, retrieved_at and content_changed_at: documents can be seasonal or out "
            "of date, so check them, and cite the document URL."),
    )

    @sub.get("/outline", operation_id=f"{p}_get_outline", summary="Title, dates and the list of sections")
    def outline():
        d = doc.get()
        return {"title": d["title"], "source_url": doc.url,
                "sections": [{"id": s["id"], "heading_path": s["path"], "page": s["page"],
                              "words": len(s["text"].split())} for s in d["sections"]],
                "provenance": doc.provenance()}

    @sub.get("/search", operation_id=f"{p}_search", summary="Sections containing the given words, best first",
             description="Matches words regardless of case and accents, also inside longer words "
                         "('strandrolstoel' finds 'strandrolstoelen'). Words in a section's headings count more.")
    def search(q: str = Query(..., min_length=2, description="Words to look for, in the document's language"),
               limit: int = Query(5, ge=1, le=20)):
        terms = [t for t in fold(q).split() if len(t) > 1]
        hits = []
        for i, s in enumerate(doc.get()["sections"]):
            text, heads = fold(s["text"]), fold(" ".join(s["path"]))
            found = [t for t in terms if t in text or t in heads]
            if found:
                score = len(found) * 10 + sum(text.count(t) + 3 * heads.count(t) for t in found)
                hits.append((-score, i, s))
        hits.sort(key=lambda h: h[:2])
        return {"count": len(hits), "results": [summary(s, TEXT_LIMIT) for *_, s in hits[:limit]],
                "provenance": doc.provenance()}

    @sub.get("/sections/{section_id:path}", operation_id=f"{p}_get_section", summary="Full text of one section")
    def get_section(section_id: str = Path(description="A section id from the outline or a search hit")):
        for s in doc.get()["sections"]:
            if s["id"] == section_id:
                return {**summary(s), "provenance": doc.provenance()}
        raise HTTPException(404, "no section with this id; ids can change when the document changes, "
                                 "so look it up again in the outline")

    return sub


DOCUMENTS = [Document(json.loads(f.read_text(encoding="utf-8"))) for f in sorted(HERE.glob("*/registration.json"))]


@asynccontextmanager
async def lifespan(_app):
    def warm():
        for doc in DOCUMENTS:
            try:
                doc.get()
            except HTTPException:
                pass  # the first request tries again
    threading.Thread(target=warm, daemon=True).start()
    yield


app = FastAPI(title="Documents as datasets (adapters)", lifespan=lifespan)


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "documents": {d.reg["id"]: d.data is not None for d in DOCUMENTS}}


for _doc in DOCUMENTS:
    app.mount(f"/{_doc.reg['id']}", document_app(_doc))

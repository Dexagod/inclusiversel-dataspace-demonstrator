"""Offline tests: fetching is replaced by fixtures; the PDF is generated."""

import httpx
import pymupdf
import pytest
from fastapi.testclient import TestClient

import app as docs
import extract

PAGE = """<html><head><title>Beaches</title></head><body><nav>Menu</nav><main>
<h1>Beaches</h1><p>In <strong>July and August</strong>.</p>
<h2>Offer</h2>
<div class="acc"><div class="summary"><button aria-expanded="false"><span>De Panne</span></button></div>
  <div class="panel" aria-hidden="true" style="display:none"><h3>What is there?</h3><ul><li>Free beach wheelchairs</li></ul>
  <h3>Borrow a wheelchair?</h3><p>Call <a href="tel:+3258">058</a>.</p></div></div>
<div class="acc"><div class="summary"><button aria-expanded="false"><span>Oostende</span></button></div>
  <div class="panel"><h3>What is there?</h3><p>Accessible toilet with hoist.</p></div></div>
<details><summary>Bredene</summary><p>Strandrolstoelen aan strandpost 4.</p></details>
<h2>Video</h2><p>A report.</p><span class="vl-u-visually-hidden">(opens in new window)</span>
</main><footer>Footer</footer></body></html>"""


def pdf_bytes() -> bytes:
    doc = pymupdf.open()
    for text in ("Programme 2025", "Plage accessible à Zuydcoote", "Contact"):
        doc.new_page().insert_text((72, 72), text)
    doc.set_toc([[1, "Programme", 1], [1, "Animations", 2]])
    doc.set_metadata({"title": "Journées", "modDate": "D:20250225091832+01'00'"})
    return doc.tobytes()


def test_accordion_titles_become_headings_with_their_panels_below():
    title, sections = extract.html_sections(PAGE)
    paths = [" > ".join(s["path"]) for s in extract.with_ids(sections)]
    assert title == "Beaches"
    assert "Beaches > Offer > De Panne > What is there?" in paths
    assert "Beaches > Offer > De Panne > Borrow a wheelchair?" in paths
    assert "Beaches > Offer > Oostende > What is there?" in paths
    assert "Beaches > Offer > Bredene" in paths
    assert "Beaches > Video" in paths  # back at the h2 level after the accordions
    text = " ".join(s["text"] for s in sections)
    assert "Menu" not in text and "Footer" not in text and "opens in new window" not in text


def test_pdf_pages_take_their_heading_path_from_the_toc():
    title, sections, date = extract.pdf_sections(pdf_bytes())
    sections = extract.with_ids(sections)
    assert (title, date) == ("Journées", "2025-02-25")
    assert [(s["id"], s["path"]) for s in sections] == [
        ("p1/programme", ["Programme"]), ("p2/animations", ["Animations"]), ("p3/animations", ["Animations"])]


def test_section_ids_are_unique():
    s = extract.with_ids([{"path": ["A"], "page": None, "text": "x"}, {"path": ["A"], "page": None, "text": "y"}])
    assert [x["id"] for x in s] == ["a", "a-2"]


REG = {"id": "beaches", "title": "Beaches", "description": "Accessible beaches.", "publisher": {"name": "Inter"},
       "licence_note": "free reuse", "languages": ["en"],
       "distributions": [{"url": "https://example.org/beaches", "media_type": "text/html"}]}


@pytest.fixture
def served(monkeypatch):
    state = {"body": PAGE.encode(), "ctype": "text/html", "robots": "", "calls": 0}

    def fake_get(url, **kw):
        req = httpx.Request("GET", url)
        if url.endswith("/robots.txt"):
            return httpx.Response(200, text=state["robots"], request=req)
        state["calls"] += 1
        if state["body"] is None:
            raise httpx.ConnectError("down")
        return httpx.Response(200, content=state["body"], headers={"content-type": state["ctype"]}, request=req)

    monkeypatch.setattr(docs.httpx, "get", fake_get)
    doc = docs.Document(REG)
    return TestClient(docs.document_app(doc)), doc, state


def test_outline_search_and_section(served):
    client, _, state = served
    out = client.get("/outline").json()
    assert out["provenance"]["source_url"] == "https://example.org/beaches"
    ids = [s["id"] for s in out["sections"]]
    hit = client.get("/search", params={"q": "oostende toilet"}).json()["results"][0]
    assert hit["heading_path"] == ["Beaches", "Offer", "Oostende", "What is there?"]
    assert client.get("/search", params={"q": "strandrolstoel"}).json()["results"][0]["heading_path"][-1] == "Bredene"
    assert client.get(f"/sections/{ids[2]}").json()["id"] == ids[2]  # ids contain slashes
    assert client.get("/sections/nope").status_code == 404
    assert state["calls"] == 1  # fetched once, then served from memory


def test_pdf_document(served):
    client, _, state = served
    state.update(body=pdf_bytes(), ctype="application/pdf")
    body = client.get("/search", params={"q": "zuydcoote"}).json()
    assert body["results"][0]["page"] == 2 and body["provenance"]["document_date"] == "2025-02-25"


def test_robots_txt_is_honoured(served):
    client, _, state = served
    state["robots"] = "User-agent: *\nDisallow: /\n"
    r = client.get("/outline")
    assert r.status_code == 503 and "robots.txt" in r.json()["detail"] and state["calls"] == 0


def test_last_good_copy_survives_an_outage_and_changes_are_dated(served):
    client, doc, state = served
    first = client.get("/outline").json()["provenance"]
    doc.next_refresh = 0
    state["body"] = None
    assert client.get("/outline").status_code == 200
    doc.next_refresh = 0
    state["body"] = PAGE.replace("Free beach", "Two free beach").encode()
    changed = client.get("/outline").json()["provenance"]
    assert changed["content_changed_at"] >= first["content_changed_at"] and changed["retrieved_at"]

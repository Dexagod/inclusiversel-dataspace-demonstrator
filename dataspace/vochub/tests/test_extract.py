from extract import Section, chunk, extract

HTML = b"""<!doctype html><html><head><title>Picto Access</title></head><body>
<nav>Home | Contact | Login</nav>
<article><h1>Pictogrammes</h1><p>Le niveau A (vert) signifie que le lieu est accessible en autonomie.
Ce texte explique les trois niveaux A, B et C pour chacun des huit pictogrammes du dispositif.</p>
<h2>Niveau B</h2><p>Le niveau B (jaune) signifie que le lieu est accessible avec une aide ponctuelle,
par exemple une rampe amovible ou un accompagnement du personnel sur place.</p></article>
<footer>Mentions legales</footer></body></html>"""


def test_chunk_keeps_heading_path_and_page():
    md = "# Toilets\n\nDoor 90 cm.\n\n## Grab rails\n\nBoth sides.\n\n# Entrance\n\nLevel."
    out = chunk([Section(md, page=3)])
    assert [(c["heading"], c["text"]) for c in out] == [
        ("Toilets", "Door 90 cm."), ("Toilets > Grab rails", "Both sides."), ("Entrance", "Level.")]
    assert {c["page"] for c in out} == {3}


def test_chunk_splits_long_text():
    out = chunk([Section(" ".join(["woord"] * 600))], max_words=250)
    assert [len(c["text"].split()) for c in out] == [250, 250, 100]


def test_html_main_content_only():
    ex = extract(HTML, "text/html; charset=utf-8", "page.html")
    text = "\n".join(s.text for s in ex.sections)
    assert ex.kind == "html" and "niveau A" in text and "Mentions legales" not in text
    assert any(c["heading"] == "Pictogrammes > Niveau B" for c in chunk(ex.sections))


def test_pdf_pages():
    import pymupdf

    doc = pymupdf.open()
    for t in ["Eerste pagina over rolstoelen.", "Tweede pagina over toiletten."]:
        doc.new_page().insert_text((72, 72), t)
    ex = extract(doc.tobytes(), "application/octet-stream", "x.bin")
    assert ex.kind == "pdf" and [s.page for s in ex.sections] == [1, 2]
    assert "toiletten" in ex.sections[1].text


def test_markitdown_formats():
    ex = extract(b"name,wheelchair\nDe Krook,yes\n", "text/csv", "places.csv")
    assert "De Krook" in ex.sections[0].text

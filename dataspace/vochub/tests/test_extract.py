from extract import Section, chunk, extract

HTML = b"""<!doctype html><html><head><title>Picto Access</title></head><body>
<nav>Home | Contact | Login</nav>
<article><h1>Pictogrammes</h1><p>Le niveau A (vert) signifie que le lieu est accessible en autonomie.
Ce texte explique les trois niveaux A, B et C pour chacun des huit pictogrammes du dispositif.</p>
<h2>Niveau B</h2><p>Le niveau B (jaune) signifie que le lieu est accessible avec une aide ponctuelle,
par exemple une rampe amovible ou un accompagnement du personnel sur place.</p></article>
<footer>Mentions legales</footer></body></html>"""


def test_chunk_keeps_heading_path_and_page():
    md = ("# Toilets\n\nThe door is 90 cm wide.\n\n## Grab rails\n\nGrab rails on both sides of the toilet.\n\n"
          "# Entrance\n\nThe entrance is level, without steps.")
    out = chunk([Section(md, page=3)])
    assert [(c["heading"], c["text"]) for c in out] == [
        ("Toilets", "The door is 90 cm wide."), ("Toilets > Grab rails", "Grab rails on both sides of the toilet."),
        ("Entrance", "The entrance is level, without steps.")]
    assert {c["page"] for c in out} == {3}


def test_chunk_drops_pieces_without_content():
    out = chunk([Section("14"), Section("| 0:1 | Type of contenu : |"),
                 Section("Bronnen\n\nDe labels worden toegekend na een audit ter plaatse.", page=2)])
    assert [c["text"] for c in out] == ["Bronnen\n\nDe labels worden toegekend na een audit ter plaatse."]


def test_chunk_starts_from_section_path():
    out = chunk([Section("Het A-label bestaat in twee niveaus: A en A+.", page=5, path=["3. Labels", "3.1 A-label"])])
    assert out[0]["heading"] == "3. Labels > 3.1 A-label"


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
    doc.set_toc([[1, "1. Rolstoelen", 1], [2, "1.1 Toiletten", 2]])
    doc.set_metadata({"subject": "Een studie over toegankelijkheid."})
    ex = extract(doc.tobytes(), "application/octet-stream", "x.bin")
    assert ex.kind == "pdf" and [s.page for s in ex.sections] == [1, 2]
    assert "toiletten" in ex.sections[1].text
    assert [s.path for s in ex.sections] == [["1. Rolstoelen"], ["1. Rolstoelen", "1.1 Toiletten"]]
    assert ex.description == "Een studie over toegankelijkheid."


def test_markitdown_formats():
    ex = extract(b"name,wheelchair\nDe Krook,yes\n", "text/csv", "places.csv")
    assert "De Krook" in ex.sections[0].text

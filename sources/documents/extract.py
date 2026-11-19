"""Turn a published web page or PDF into sections that follow its own structure.

Web page: the main content becomes Markdown; accordion and disclosure titles (<summary>, button[aria-expanded])
are turned into headings first, since sites often put the real structure there (e.g. one accordion per town).
PDF: one section per page; the PDF's table of contents, when it has one, gives each page its heading path.
"""

import re
import unicodedata

HEADINGS = [f"h{i}" for i in range(1, 7)]
MAX_WORDS = 400


def fold(text: str) -> str:
    """Lowercase without accents, for matching: 'Strandrolstoel lenen?' and 'strandrolstoel' meet."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", fold(text)).strip("-")[:40] or "section"


def _promote_disclosure_titles(root, soup) -> None:
    """<button aria-expanded>De Panne</button> + panel  ->  <hN>De Panne</hN> with the panel's headings below it."""
    items = []
    for t in root.select("summary, button[aria-expanded]"):
        text = t.get_text(" ", strip=True)
        if not text:
            continue
        item = t  # the accordion item: the nearest ancestor holding the title and something else (the panel)
        while item.parent is not None and item.parent is not root and \
                len([c for c in item.parent.children if getattr(c, "name", None)]) < 2:
            item = item.parent
        item = item.parent if item.parent is not None and item.parent is not root else t  # never the whole page
        outside = (h for h in t.find_all_previous(HEADINGS)
                   if not any(p is i for p in h.parents for i in items))
        prev = next(outside, None)
        level = min(int(prev.name[1]) + 1, 6) if prev else 2
        new = soup.new_tag(f"h{level}")
        new.string = text
        t.replace_with(new)
        inner = [h for h in item.find_all(HEADINGS) if h is not new]
        if inner:
            top = min(int(h.name[1]) for h in inner)
            for h in inner:
                h.name = f"h{min(6, level + 1 + int(h.name[1]) - top)}"
        items.append(item)


def html_sections(html: str) -> tuple[str | None, list[dict]]:
    from bs4 import BeautifulSoup
    from markdownify import markdownify

    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else None
    root = soup.find("main") or soup.find(attrs={"role": "main"}) or soup.body or soup
    for el in root.select("script, style, noscript, svg, nav, footer, form, iframe, template, "
                          "[class*=visually-hidden], [class*=sr-only]"):
        el.decompose()
    _promote_disclosure_titles(root, soup)
    md = markdownify(str(root), heading_style="ATX", strip=["img"])
    return title, markdown_sections(md)


def markdown_sections(md: str, page: int | None = None, path: list[str] | None = None) -> list[dict]:
    """One section per heading; text before the first heading gets the given path."""
    out: list[dict] = []
    stack: list[tuple[int, str]] = [(0, p) for p in path or []]
    buf: list[str] = []

    def flush():
        text = re.sub(r"\n{3,}", "\n\n", "\n".join(buf)).strip()
        buf.clear()
        if not text:
            return
        words = text.split()
        parts = [text] if len(words) <= MAX_WORDS else \
            [" ".join(words[i:i + MAX_WORDS]) for i in range(0, len(words), MAX_WORDS)]
        for part in parts:
            out.append({"path": [t for _, t in stack], "page": page, "text": part})

    for line in md.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if m and m.group(2):
            flush()
            level = len(m.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            heading = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", m.group(2))  # [text](url) -> text
            stack.append((level, re.sub(r"\s+", " ", heading).strip()))
        else:
            buf.append(line)
    flush()
    return out


def pdf_sections(data: bytes) -> tuple[str | None, list[dict], str | None]:
    """(title, sections, document date from the PDF metadata)."""
    import pymupdf

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        toc = doc.get_toc()  # [level, title, page]
        out = []
        for i, page in enumerate(doc, 1):
            stack: list[tuple[int, str]] = []
            for level, heading, p in toc:
                if p > i:
                    break
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, heading.strip()))
            out += markdown_sections(page.get_text(), page=i, path=[t for _, t in stack])
        meta = doc.metadata or {}
        raw = meta.get("modDate") or meta.get("creationDate") or ""
        m = re.match(r"D:(\d{4})(\d{2})(\d{2})", raw)
        return meta.get("title") or None, out, "-".join(m.groups()) if m else None


def with_ids(sections: list[dict]) -> list[dict]:
    """Readable, stable ids from the heading path (or page): 'aanbod/de-panne/strandrolstoel-lenen'."""
    seen: dict[str, int] = {}
    for s in sections:
        base = "/".join(slug(p) for p in s["path"]) or "start"
        if s["page"] is not None:
            base = f"p{s['page']}" + (f"/{base}" if s["path"] else "")
        seen[base] = seen.get(base, 0) + 1
        s["id"] = base if seen[base] == 1 else f"{base}-{seen[base]}"
    return sections

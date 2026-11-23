"""Turn documents of many kinds into text sections, then into heading-aware chunks.

PDF: PyMuPDF, one section per page (keeps page numbers); the PDF's table of contents gives each page its heading path.
HTML / web pages: trafilatura main-content extraction to Markdown (drops menus, footers).
Everything else (docx, pptx, xlsx, csv, epub, md, txt, json, xml ...): markitdown to Markdown.
"""

import io
import re
from dataclasses import dataclass
from pathlib import PurePosixPath

# The default embedding model reads only the first 128 tokens (about 1.6 per word in Dutch and French), and each
# chunk is embedded with its document title and heading in front; anything past the limit is silently ignored.
MAX_WORDS = 60
# Pieces with fewer real words (a page number, a lone "Bronnen", an empty table row) carry no content but match on
# their title alone.
MIN_WORDS = 5


@dataclass
class Section:
    text: str
    page: int | None = None
    path: list[str] | None = None  # heading path the section starts under (PDF table of contents)


@dataclass
class Extracted:
    title: str | None
    sections: list[Section]
    kind: str
    description: str | None = None  # the document's own summary (HTML meta description, PDF subject)


def _is_pdf(data: bytes, content_type: str, name: str) -> bool:
    return data[:5] == b"%PDF-" or "pdf" in content_type or name.lower().endswith(".pdf")


def _is_html(data: bytes, content_type: str, name: str) -> bool:
    head = data[:1000].lstrip().lower()
    return ("html" in content_type or name.lower().endswith((".html", ".htm"))
            or head.startswith((b"<!doctype html", b"<html")))


def extract(data: bytes, content_type: str = "", name: str = "") -> Extracted:
    content_type = (content_type or "").lower()
    if _is_pdf(data, content_type, name):
        import pymupdf

        with pymupdf.open(stream=data, filetype="pdf") as doc:
            toc = doc.get_toc()  # [[level, title, page], ...]
            sections = []
            for i, page in enumerate(doc, 1):
                stack: list[tuple[int, str]] = []
                for level, heading, p in toc:
                    if p > i:
                        break
                    while stack and stack[-1][0] >= level:
                        stack.pop()
                    stack.append((level, " ".join(heading.split())))
                sections.append(Section(page.get_text(), page=i, path=[h for _, h in stack] or None))
            meta = doc.metadata or {}
            return Extracted(meta.get("title") or None, sections, "pdf", meta.get("subject") or None)
    if _is_html(data, content_type, name):
        import trafilatura

        html = data.decode("utf-8", errors="replace")
        md = trafilatura.extract(html, output_format="markdown", include_tables=True, include_links=False) or ""
        meta = trafilatura.extract_metadata(html)
        return Extracted(meta.title if meta else None, [Section(md)], "html", meta.description if meta else None)

    from markitdown import MarkItDown, StreamInfo

    ext = PurePosixPath(name).suffix or None
    result = MarkItDown().convert_stream(io.BytesIO(data), stream_info=StreamInfo(
        mimetype=content_type.split(";")[0] or None, extension=ext, filename=name or None))
    return Extracted(result.title, [Section(result.markdown)], (ext or content_type or "text").lstrip("."))


def chunk(sections: list[Section], max_words: int = MAX_WORDS) -> list[dict]:
    """Split on Markdown headings and blank lines; pack paragraphs up to max_words; keep the heading path.
    Pieces under MIN_WORDS words are dropped."""
    chunks: list[dict] = []
    headings: list[str] = []
    for sec in sections:
        buf: list[str] = []
        if sec.path is not None:
            headings = list(sec.path)

        def flush():
            text = "\n\n".join(buf).strip()
            if len(re.findall(r"[^\W\d_]{2,}", text)) >= MIN_WORDS:  # real words: not "|", "0:1" or page numbers
                chunks.append({"text": text, "page": sec.page, "heading": " > ".join(headings) or None})
            buf.clear()

        for para in re.split(r"\n\s*\n", sec.text):
            para = para.strip()
            if not para:
                continue
            m = re.match(r"^(#{1,6})\s+(.*)", para)
            if m:
                flush()
                level = len(m.group(1))
                del headings[level - 1:]
                headings.append(m.group(2).splitlines()[0].strip())
                rest = para.split("\n", 1)[1] if "\n" in para else ""
                if rest.strip():
                    buf.append(rest.strip())
                continue
            words = para.split()
            while len(words) > max_words:  # a single huge paragraph
                flush()
                buf.append(" ".join(words[:max_words]))
                words = words[max_words:]
                flush()
            if sum(len(b.split()) for b in buf) + len(words) > max_words:
                flush()
            buf.append(" ".join(words) if len(para.split()) != len(words) else para)
        flush()
    return chunks

"""Vocabulary hub: ingest domain documents and web pages, return cited passages. Retrieval only, no LLM."""

import hashlib
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastembed import SparseTextEmbedding, TextEmbedding
from pydantic import AnyHttpUrl, BaseModel, Field
from qdrant_client import QdrantClient, models

from extract import chunk, extract

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
MODEL = os.environ.get("EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
CACHE = os.environ.get("MODEL_CACHE", None)
# "passages": dense (meaning) and sparse (BM25 keywords) vectors per chunk. The older "chunks" collection held dense
# vectors only; it is left alone, re-ingest with `make knowledge` (sources/).
COLLECTION = "passages"
PER_DOC = 2  # at most this many passages per document in one answer, so one long document cannot fill it
MAX_BYTES = 50 * 1024 * 1024
USER_AGENT = "accessibility-dataspace-demo/0.1 (open research demonstrator)"
# One text the connector returns with every search: how to weigh and combine what the sources say.
CONTEXT_FILE = Path(os.environ.get("CONTEXT_FILE", "data/context.md"))

state = {}


@asynccontextmanager
async def lifespan(_app):
    embedder = TextEmbedding(MODEL, cache_dir=CACHE)
    # BM25 without stemming: documents are in Dutch, French and English, and names and codes must match as written
    keywords = SparseTextEmbedding("Qdrant/bm25", cache_dir=CACHE, disable_stemmer=True)
    qdrant = QdrantClient(url=QDRANT_URL, check_compatibility=False)
    if not qdrant.collection_exists(COLLECTION):
        dim = len(next(iter(embedder.query_embed("probe"))))
        qdrant.create_collection(
            COLLECTION, vectors_config={"dense": models.VectorParams(size=dim, distance=models.Distance.COSINE)},
            sparse_vectors_config={"bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)})
        for field in ("doc_id", "language", "tags"):
            qdrant.create_payload_index(COLLECTION, field, models.PayloadSchemaType.KEYWORD)
        qdrant.create_payload_index(COLLECTION, "chunk_index", models.PayloadSchemaType.INTEGER)
    state.update(embedder=embedder, keywords=keywords, qdrant=qdrant)
    yield


app = FastAPI(title="Accessibility vocabulary hub", version="0.1.0", lifespan=lifespan,
              description="Ingest PDFs, office documents and web pages; search them for cited passages.")


def _doc_filter(doc_id: str) -> models.Filter:
    return models.Filter(must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))])


def ingest(data: bytes, content_type: str, name: str, meta: dict) -> dict:
    ex = extract(data, content_type, name)
    summary = (meta.get("summary") or ex.description or "").strip() or None
    # The summary is a passage of its own: broad questions ("which labels exist?") find documents through it
    chunks = ([{"text": summary, "page": None, "heading": "Summary"}] if summary else []) + chunk(ex.sections)
    if not chunks:
        raise HTTPException(422, "no text could be extracted from this document")
    doc_id = hashlib.sha256("\n".join(c["text"] for c in chunks).encode()).hexdigest()[:16]
    qdrant: QdrantClient = state["qdrant"]
    doc = {"doc_id": doc_id, "title": meta.get("title") or ex.title or name or meta.get("url"), "url": meta.get("url"),
           "kind": ex.kind, "language": meta.get("language"), "tags": meta.get("tags") or [],
           "licence": meta.get("licence"), "summary": summary, "ingested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "chunks": len(chunks)}
    if qdrant.count(COLLECTION, count_filter=_doc_filter(doc_id), exact=True).count:
        return {**doc, "duplicate": True}
    # Title and heading in front: a passage alone often does not say what it is about ("vert/A" without "Picto Access")
    texts = ["\n".join(x for x in (doc["title"], c["heading"], c["text"]) if x) for c in chunks]
    dense = state["embedder"].passage_embed(texts)
    sparse = state["keywords"].passage_embed(texts)
    qdrant.upsert(COLLECTION, points=[
        models.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}/{i}")),
                           vector={"dense": d.tolist(), "bm25": models.SparseVector(indices=b.indices.tolist(),
                                                                                    values=b.values.tolist())},
                           payload={**doc, **c, "chunk_index": i})
        for i, (c, d, b) in enumerate(zip(chunks, dense, sparse))])
    return {**doc, "duplicate": False}


def _tags(raw: str | None) -> list[str]:
    return [t.strip() for t in (raw or "").split(",") if t.strip()]


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL}


@app.post("/documents", status_code=201, operation_id="upload_document",
          summary="Upload a file (PDF, DOCX, PPTX, XLSX, HTML, Markdown, text, CSV ...)")
async def upload(file: UploadFile = File(...), title: str | None = Form(None), url: str | None = Form(None),
                 language: str | None = Form(None, description="ISO 639-1 code"),
                 tags: str | None = Form(None, description="Comma separated"),
                 licence: str | None = Form(None, description="Licence URL or permission note"),
                 summary: str | None = Form(None, description="A few sentences on what the document is about; "
                                                              "default: the document's own description, if any")):
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "file larger than 50 MB")
    return ingest(data, file.content_type or "", file.filename or "",
                  {"title": title, "url": url, "language": language, "tags": _tags(tags), "licence": licence,
                   "summary": summary})


class UrlIn(BaseModel):
    url: AnyHttpUrl
    title: str | None = None
    language: str | None = None
    tags: list[str] = []
    licence: str | None = None
    summary: str | None = Field(None, description="A few sentences on what the document is about; "
                                                  "default: the page's own description, if any")


@app.post("/documents/url", status_code=201, operation_id="ingest_url",
          summary="Fetch a web page or an online document and ingest it")
async def from_url(body: UrlIn):
    url = str(body.url)
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers={"user-agent": USER_AGENT}) as c:
            r = await c.get(url)
            r.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"could not fetch {url}: {e}") from e
    if len(r.content) > MAX_BYTES:
        raise HTTPException(413, "document larger than 50 MB")
    return ingest(r.content, r.headers.get("content-type", ""), url.split("?")[0].rsplit("/", 1)[-1],
                  {**body.model_dump(), "url": url})


@app.get("/documents", operation_id="list_documents", summary="List ingested documents")
def list_documents():
    first = models.Filter(must=[models.FieldCondition(key="chunk_index", match=models.MatchValue(value=0))])
    docs, offset = [], None
    while True:
        points, offset = state["qdrant"].scroll(COLLECTION, scroll_filter=first, limit=256, offset=offset)
        docs += [{k: v for k, v in p.payload.items() if k not in {"text", "page", "heading", "chunk_index"}} for p in points]
        if offset is None:
            return docs


@app.delete("/documents/{doc_id}", status_code=204, operation_id="delete_document", summary="Remove a document")
def delete_document(doc_id: str):
    state["qdrant"].delete(COLLECTION, points_selector=models.FilterSelector(filter=_doc_filter(doc_id)))


@app.get("/search", operation_id="search", summary="Passages most relevant to a question, with citations",
         description="Meaning and keyword search combined (reciprocal rank fusion; the score only orders the hits), "
                     f"at most {PER_DOC} passages per document.")
def search(q: str = Query(..., min_length=2), k: int = Query(5, ge=1, le=50),
           language: str | None = None, tag: str | None = None):
    must = []
    if language:
        must.append(models.FieldCondition(key="language", match=models.MatchValue(value=language)))
    if tag:
        must.append(models.FieldCondition(key="tags", match=models.MatchValue(value=tag)))
    flt = models.Filter(must=must) if must else None
    dense = next(iter(state["embedder"].query_embed(q))).tolist()
    b = next(iter(state["keywords"].query_embed(q)))
    sparse = models.SparseVector(indices=b.indices.tolist(), values=b.values.tolist())
    # Meaning and keywords each propose candidates; reciprocal rank fusion merges the two rankings.
    groups = state["qdrant"].query_points_groups(
        COLLECTION, group_by="doc_id", group_size=PER_DOC, limit=k, query_filter=flt,
        prefetch=[models.Prefetch(query=dense, using="dense", limit=100, filter=flt),
                  models.Prefetch(query=sparse, using="bm25", limit=100, filter=flt)],
        query=models.FusionQuery(fusion=models.Fusion.RRF)).groups
    hits = sorted((h for g in groups for h in g.hits), key=lambda h: h.score, reverse=True)[:k]
    keys = ["text", "title", "url", "page", "heading", "language", "tags", "licence", "doc_id"]
    return [{"score": round(h.score, 4), **{key: h.payload.get(key) for key in keys}} for h in hits]


class ContextIn(BaseModel):
    text: str = Field(max_length=20_000)


@app.get("/context", operation_id="get_context", summary="The permanent context returned with every search")
def get_context():
    if not CONTEXT_FILE.exists():
        return {"text": "", "updated_at": None}
    updated = datetime.fromtimestamp(CONTEXT_FILE.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    return {"text": CONTEXT_FILE.read_text(encoding="utf-8"), "updated_at": updated}


@app.put("/context", operation_id="set_context", summary="Replace the permanent context (Markdown)")
def set_context(body: ContextIn):
    CONTEXT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONTEXT_FILE.with_suffix(".tmp")
    tmp.write_text(body.text, encoding="utf-8")
    tmp.replace(CONTEXT_FILE)  # atomic: readers never see half a file
    return get_context()

"""Vocabulary hub: ingest domain documents and web pages, return cited passages. Retrieval only, no LLM."""

import hashlib
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastembed import TextEmbedding
from pydantic import AnyHttpUrl, BaseModel
from qdrant_client import QdrantClient, models

from extract import chunk, extract

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
MODEL = os.environ.get("EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
CACHE = os.environ.get("MODEL_CACHE", None)
COLLECTION = "chunks"
MAX_BYTES = 50 * 1024 * 1024
USER_AGENT = "accessibility-dataspace-demo/0.1 (open research demonstrator)"

state = {}


@asynccontextmanager
async def lifespan(_app):
    embedder = TextEmbedding(MODEL, cache_dir=CACHE)
    qdrant = QdrantClient(url=QDRANT_URL, check_compatibility=False)
    if not qdrant.collection_exists(COLLECTION):
        dim = len(next(iter(embedder.query_embed("probe"))))
        qdrant.create_collection(COLLECTION, vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE))
        for field in ("doc_id", "language", "tags"):
            qdrant.create_payload_index(COLLECTION, field, models.PayloadSchemaType.KEYWORD)
        qdrant.create_payload_index(COLLECTION, "chunk_index", models.PayloadSchemaType.INTEGER)
    state.update(embedder=embedder, qdrant=qdrant)
    yield


app = FastAPI(title="Accessibility vocabulary hub", version="0.1.0", lifespan=lifespan,
              description="Ingest PDFs, office documents and web pages; search them for cited passages.")


def _doc_filter(doc_id: str) -> models.Filter:
    return models.Filter(must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))])


def ingest(data: bytes, content_type: str, name: str, meta: dict) -> dict:
    ex = extract(data, content_type, name)
    chunks = chunk(ex.sections)
    if not chunks:
        raise HTTPException(422, "no text could be extracted from this document")
    doc_id = hashlib.sha256("\n".join(c["text"] for c in chunks).encode()).hexdigest()[:16]
    qdrant: QdrantClient = state["qdrant"]
    doc = {"doc_id": doc_id, "title": meta.get("title") or ex.title or name or meta.get("url"), "url": meta.get("url"),
           "kind": ex.kind, "language": meta.get("language"), "tags": meta.get("tags") or [],
           "licence": meta.get("licence"), "ingested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "chunks": len(chunks)}
    if qdrant.count(COLLECTION, count_filter=_doc_filter(doc_id), exact=True).count:
        return {**doc, "duplicate": True}
    vectors = state["embedder"].passage_embed([c["text"] for c in chunks])
    qdrant.upsert(COLLECTION, points=[
        models.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}/{i}")), vector=v.tolist(),
                           payload={**doc, **c, "chunk_index": i})
        for i, (c, v) in enumerate(zip(chunks, vectors))])
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
                 licence: str | None = Form(None, description="Licence URL or permission note")):
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "file larger than 50 MB")
    return ingest(data, file.content_type or "", file.filename or "",
                  {"title": title, "url": url, "language": language, "tags": _tags(tags), "licence": licence})


class UrlIn(BaseModel):
    url: AnyHttpUrl
    title: str | None = None
    language: str | None = None
    tags: list[str] = []
    licence: str | None = None


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


@app.get("/search", operation_id="search", summary="Passages most relevant to a question, with citations")
def search(q: str = Query(..., min_length=2), k: int = Query(5, ge=1, le=50),
           language: str | None = None, tag: str | None = None):
    must = []
    if language:
        must.append(models.FieldCondition(key="language", match=models.MatchValue(value=language)))
    if tag:
        must.append(models.FieldCondition(key="tags", match=models.MatchValue(value=tag)))
    vector = next(iter(state["embedder"].query_embed(q))).tolist()
    hits = state["qdrant"].query_points(COLLECTION, query=vector, limit=k,
                                        query_filter=models.Filter(must=must) if must else None).points
    keys = ["text", "title", "url", "page", "heading", "language", "tags", "licence", "doc_id"]
    return [{"score": round(h.score, 4), **{key: h.payload.get(key) for key in keys}} for h in hits]

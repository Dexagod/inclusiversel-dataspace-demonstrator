"""DCAT catalog: publishers register datasets (metadata + API location + OpenAPI), agents search them.

Registration records (JSON files on a volume) are the source of truth; the DCAT graph is derived from them.
"""

import json
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal
from pathlib import Path

import httpx
import yaml
from fastapi import FastAPI, HTTPException, Query, Request, Response
from rdflib import URIRef
from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, model_validator

from dcat import CATALOGS, FREQUENCIES, LANGUAGES, build_graph, extract_dataset

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data")) / "datasets"
BASE_URL = os.environ.get("CATALOG_BASE_URL", "http://localhost:8001").rstrip("/")


class Publisher(BaseModel):
    name: str = Field(min_length=1)
    url: AnyHttpUrl | None = None


class Registration(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$", description="Stable slug, e.g. 'acceslibre'")
    catalog: str | None = Field(default=None, description=f"Sub-catalog the dataset belongs to: {sorted(CATALOGS)}")
    title: str = Field(min_length=1)
    description: str = Field(min_length=1, description="Plain-language description an agent can use to judge relevance")
    publisher: Publisher
    licence: AnyHttpUrl | None = Field(default=None, description="URL of the licence, e.g. https://creativecommons.org/licenses/by/4.0/. "
                                       "Leave empty only while reuse terms are unknown, and explain in licence_note")
    licence_note: str | None = Field(default=None, description="Reuse conditions in words, e.g. 'terms not yet confirmed'")
    endpoint_url: AnyHttpUrl = Field(description="Base URL of the API; OpenAPI paths are resolved against it")
    openapi_url: AnyHttpUrl = Field(description="URL of the OpenAPI 3.x document describing the API")
    source_dcat_url: AnyHttpUrl | None = Field(default=None, description="URL of the publisher's own DCAT description of "
                                               "this dataset (one dcat:Dataset; Turtle, RDF/XML or JSON-LD); it is copied "
                                               "into this catalog and linked with dct:source")
    keywords: list[str] = []
    themes: list[str] = Field(default=["accessibility"], description="Theme slugs")
    languages: list[str] = Field(default=[], description=f"ISO 639-1 codes: {sorted(LANGUAGES)}")
    spatial: list[str] = Field(default=[], description="Covered areas as labels, e.g. 'Flanders', 'Ghent'")
    update_frequency: str | None = Field(default=None, description=f"One of {sorted(FREQUENCIES)}")
    landing_page: AnyHttpUrl | None = None
    contact_email: str | None = None
    access_note: str | None = Field(default=None, description="How consumers obtain access, e.g. where to request an API key")

    @model_validator(mode="after")
    def _licence_or_note(self):
        if not (self.licence or self.licence_note):
            raise ValueError("give a licence URL, or a licence_note explaining why there is none yet")
        return self

    @field_validator("languages")
    @classmethod
    def _languages(cls, v):
        bad = [x for x in v if x not in LANGUAGES]
        if bad:
            raise ValueError(f"unknown language codes {bad}; use one of {sorted(LANGUAGES)}")
        return v

    @field_validator("catalog")
    @classmethod
    def _catalog(cls, v):
        if v is not None and v not in CATALOGS:
            raise ValueError(f"unknown catalog {v!r}; use one of {sorted(CATALOGS)}")
        return v

    @field_validator("update_frequency")
    @classmethod
    def _frequency(cls, v):
        if v is not None and v not in FREQUENCIES:
            raise ValueError(f"unknown frequency {v!r}; use one of {sorted(FREQUENCIES)}")
        return v

    @field_validator("themes")
    @classmethod
    def _themes(cls, v):
        bad = [x for x in v if not re.fullmatch(r"[a-z0-9-]+", x)]
        if bad:
            raise ValueError(f"themes must be lowercase slugs, got {bad}")
        return v


datasets: dict[str, dict] = {}


async def check_openapi(url: str) -> None:
    """Reject a registration whose OpenAPI document cannot be fetched or is not OpenAPI 3.x."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
        doc = yaml.safe_load(r.text)  # YAML is a superset of JSON
    except Exception as e:
        raise HTTPException(422, f"openapi_url could not be fetched or parsed: {e}") from e
    if not isinstance(doc, dict) or not str(doc.get("openapi", "")).startswith("3"):
        raise HTTPException(422, "openapi_url must point to an OpenAPI 3.x document (Swagger 2 is not supported)")


async def fetch_source_dcat(url: str) -> dict:
    """Fetch the publisher's DCAT for this dataset; reject the registration if it is not one readable dcat:Dataset."""
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(url, headers={"accept": "text/turtle, application/rdf+xml;q=0.9, application/ld+json;q=0.8"})
            r.raise_for_status()
        uri, turtle = extract_dataset(r.text, r.headers.get("content-type", ""))
    except Exception as e:
        raise HTTPException(422, f"source_dcat_url could not be fetched or read as DCAT: {e}") from e
    return {"uri": uri, "turtle": turtle}


def save(record: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DATA_DIR / f"{record['id']}.json.tmp"
    tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False))
    tmp.replace(DATA_DIR / f"{record['id']}.json")
    datasets[record["id"]] = record


async def register(reg: Registration) -> dict:
    record = reg.model_dump(mode="json")
    await check_openapi(record["openapi_url"])
    if record.get("source_dcat_url"):
        record["source_dcat"] = await fetch_source_dcat(record["source_dcat_url"])
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record["registered_at"] = datasets.get(reg.id, {}).get("registered_at", now)
    record["modified"] = now
    save(record)
    return record


@asynccontextmanager
async def lifespan(_app):
    for f in sorted(DATA_DIR.glob("*.json")):
        datasets[f.stem] = json.loads(f.read_text())
    yield


app = FastAPI(
    title="Accessibility data space catalog",
    version="0.1.0",
    description="Register datasets with their API and OpenAPI document; search them; export the catalog as DCAT.",
    lifespan=lifespan,
)


def summary(d: dict) -> dict:
    keys = ["id", "catalog", "title", "description", "publisher", "themes", "spatial", "languages", "licence",
            "licence_note", "endpoint_url", "openapi_url", "access_note"]
    return {k: d.get(k) for k in keys}


@app.get("/health")
def health():
    return {"status": "ok", "datasets": len(datasets)}


@app.post("/datasets", status_code=201, operation_id="register_dataset", summary="Register a new dataset")
async def create(reg: Registration):
    if reg.id in datasets:
        raise HTTPException(409, f"dataset {reg.id!r} exists; use PUT /datasets/{reg.id} to update it")
    return await register(reg)


@app.put("/datasets/{dataset_id}", operation_id="upsert_dataset", summary="Create or replace a dataset registration")
async def upsert(dataset_id: str, reg: Registration):
    if reg.id != dataset_id:
        raise HTTPException(422, "id in body must match the path")
    return await register(reg)


@app.delete("/datasets/{dataset_id}", status_code=204, operation_id="delete_dataset", summary="Remove a dataset")
def delete(dataset_id: str):
    if datasets.pop(dataset_id, None) is None:
        raise HTTPException(404, "dataset not found")
    (DATA_DIR / f"{dataset_id}.json").unlink(missing_ok=True)


@app.get("/datasets", operation_id="search_datasets", summary="Search datasets by text and filters")
def search(
    q: str = Query("", description="Free text; datasets matching more words rank higher"),
    theme: str | None = None,
    spatial: str | None = Query(None, description="Substring of a covered area label"),
    language: str | None = Query(None, description="ISO 639-1 code"),
    catalog: str | None = Query(None, description=f"Only datasets of this sub-catalog: {sorted(CATALOGS)}"),
):
    words = [w for w in re.findall(r"\w+", q.lower()) if len(w) > 2]
    hits = []
    for d in datasets.values():
        if theme and theme not in d["themes"]:
            continue
        if spatial and not any(spatial.lower() in s.lower() for s in d["spatial"]):
            continue
        if language and language not in d["languages"]:
            continue
        if catalog and d.get("catalog") != catalog:
            continue
        hay = json.dumps([d["title"], d["description"], d["keywords"], d["themes"], d["spatial"],
                          d["publisher"]["name"]], ensure_ascii=False).lower()
        score = sum(w in hay for w in words)
        if words and not score:
            continue
        hits.append((score, d["id"], summary(d)))
    return [h[2] for h in sorted(hits, key=lambda h: (-h[0], h[1]))]


@app.get("/datasets/{dataset_id}", operation_id="get_dataset", summary="Full registration of one dataset")
def get(dataset_id: str):
    if dataset_id not in datasets:
        raise HTTPException(404, "dataset not found")
    return datasets[dataset_id]


@app.get("/catalogs", operation_id="list_catalogs", summary="Sub-catalogs and the ids of their datasets")
def catalogs():
    return [{"id": cid, **c, "datasets": sorted(i for i, d in datasets.items() if d.get("catalog") == cid)}
            for cid, c in CATALOGS.items()]


@app.get("/catalog", operation_id="get_catalog", summary="The whole catalog as DCAT (Turtle or JSON-LD)")
def catalog(request: Request, format: str | None = Query(None, pattern="^(turtle|jsonld)$")):
    return rdf(build_graph(datasets.values(), BASE_URL), request, format)


def rdf(graph, request: Request, format: str | None) -> Response:
    if (format or ("jsonld" if "json" in request.headers.get("accept", "") else "turtle")) == "jsonld":
        return Response(graph.serialize(format="json-ld"), media_type="application/ld+json")
    return Response(graph.serialize(format="turtle"), media_type="text/turtle")


@app.get("/{kind}/{item_id}", operation_id="describe", summary="DCAT description of a sub-catalog, data service or theme",
         description="Makes the URIs in the DCAT export resolvable: /catalogs/{id}, /services/{id}, /themes/{slug}.")
def describe(request: Request, kind: Literal["catalogs", "services", "themes"], item_id: str,
             format: str | None = Query(None, pattern="^(turtle|jsonld)$")):
    graph = build_graph(datasets.values(), BASE_URL)
    uri = URIRef(f"{BASE_URL}/{kind}/{item_id}")
    sub = graph.cbd(uri)
    for s, p in graph.subject_predicates(uri):  # e.g. the datasets of a theme
        sub.add((s, p, uri))
    if not len(sub):
        raise HTTPException(404, f"no {kind[:-1]} {item_id!r} in this catalog")
    return rdf(sub, request, format)


@app.api_route("/sparql", methods=["GET", "POST"], operation_id="sparql", summary="SPARQL query over the DCAT graph")
async def sparql(request: Request, query: str | None = None):
    if query is None and request.method == "POST":
        form = await request.form()
        query = form.get("query")
    if not query:
        raise HTTPException(400, "query is required")
    try:
        result = build_graph(datasets.values(), BASE_URL).query(query)
    except Exception as e:
        raise HTTPException(400, f"invalid SPARQL: {e}") from e
    if result.type == "CONSTRUCT" or result.type == "DESCRIBE":
        return Response(result.serialize(format="turtle"), media_type="text/turtle")
    return Response(result.serialize(format="json"), media_type="application/sparql-results+json")

"""HTTP API - the contract in docs/architecture/api.md, trimmed to what is built.

Deliberately thin: every decision lives in `analyst.agent`. A request becomes one
`ask()` call, and the response IS the agent's `Answer` model - so the API cannot
drift from what notebook 15 measured.

Uploads (`/api/v1/documents`) are private. Every route that reads or writes one
needs the admin key in `X-API-Key`, and with no key configured they are switched
off - so a public deploy cannot expose them by accident.

Run:  uv run uvicorn analyst.api:app --port 8400
"""

import secrets
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from sqlalchemy import text

from analyst import uploads
from analyst.agent import Answer, Tools, ask, ask_document, connect
from analyst.config import ROOT, get_settings
from analyst.db import session_scope
from analyst.embedding import DEFAULT_MODEL, Embedder
from analyst.llm import LLM
from analyst.models import Document, ElementRow, FigureDescription
from analyst.retrievers import store_for, uploaded
from analyst.tools import Company
from analyst.vectorstore import VectorStore
from analyst.vision import png

ApiKey = Annotated[str | None, Header()]
NOT_FOUND = "No uploaded document with that id."


@lru_cache
def embedder() -> Embedder:
    """One model per process, shared by the agent and the upload job."""
    return Embedder(DEFAULT_MODEL)


@lru_cache
def agent() -> tuple[LLM, Tools]:
    """Built once per process: it loads the embedding model and the corpus list."""
    return connect(get_settings(), embedder=embedder())


@lru_cache
def upload_store() -> VectorStore:
    return store_for(get_settings(), DEFAULT_MODEL, uploads.VARIANT)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Finish any upload a restart interrupted - in a thread, so startup is not held up.
    threading.Thread(target=uploads.resume, args=(embedder, get_settings()), daemon=True).start()
    yield


app = FastAPI(title="Indian Equity Research Analyst", version="0.1.0", lifespan=lifespan)


def private(x_api_key: ApiKey = None) -> None:
    """The gate on everything upload-related. Compared in constant time, so response
    timing says nothing about how much of a guessed key was right."""
    key = get_settings().admin_api_key
    if key is None or not key.get_secret_value():
        raise HTTPException(503, "Private uploads are disabled: ADMIN_API_KEY is not set.")
    if not x_api_key or not secrets.compare_digest(x_api_key.encode(),
                                                   key.get_secret_value().encode()):
        raise HTTPException(401, "A valid X-API-Key header is required.")


def _visible(doc: Document | None, x_api_key: str | None) -> None:
    """An upload's pages are as private as the upload. Without the key its elements do
    not exist (404), rather than exist-but-forbidden (401)."""
    if doc is not None and doc.source == "upload":
        try:
            private(x_api_key)
        except HTTPException as e:
            raise HTTPException(404, "unknown element_id") from e


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    # Set: answer from this one uploaded PDF (document mode). Private, like the upload.
    document_id: str | None = Field(default=None, max_length=80)


@app.post("/api/v1/ask")
def ask_question(req: AskRequest, x_api_key: ApiKey = None) -> Answer:
    """A refusal is a 200 with `abstained: true` - declining to guess is correct behaviour."""
    if req.document_id is not None:
        private(x_api_key)
        doc = uploads.get(req.document_id)
        if doc is None:
            raise HTTPException(404, NOT_FOUND)
        if doc.status == uploads.Status.FAILED:
            raise HTTPException(409, f"That document could not be processed: {doc.error}")
        if doc.status != uploads.Status.READY:
            raise HTTPException(409, "That document is still being processed.")
    llm, tools = agent()
    try:
        if req.document_id is None:
            return ask(req.question, llm, tools)
        search = uploaded(embedder(), upload_store())
        return ask_document(req.question, req.document_id, llm, search)
    except httpx.HTTPError as e:
        # An upstream rate limit is not the client's fault: 503, not 429 (api.md).
        raise HTTPException(503, "LLM provider unavailable") from e


@app.get("/api/v1/companies")
def companies() -> list[Company]:
    return list(agent()[1].corpus.values())


@app.post("/api/v1/documents", status_code=202, dependencies=[Depends(private)])
def upload_document(file: UploadFile, background: BackgroundTasks,
                    title: Annotated[str | None, Form(max_length=300)] = None) -> uploads.Upload:
    """Stored and queued. Parsing and indexing run after the response - poll the GET."""
    data = file.file.read(uploads.MAX_BYTES + 1)  # +1: enough to know it is too big
    if problem := uploads.check_pdf(data):
        raise HTTPException(413 if len(data) > uploads.MAX_BYTES else 415, problem)
    doc, queued = uploads.save(data, uploads.title_from(title, file.filename), get_settings())
    if queued:
        background.add_task(uploads.process, doc.document_id, embedder, get_settings())
    return doc


@app.get("/api/v1/documents", dependencies=[Depends(private)])
def list_documents() -> list[uploads.Upload]:
    return uploads.list_uploads()


@app.get("/api/v1/documents/{document_id}", dependencies=[Depends(private)])
def get_document(document_id: str) -> uploads.Upload:
    doc = uploads.get(document_id)
    if doc is None:
        raise HTTPException(404, NOT_FOUND)
    return doc


@app.delete("/api/v1/documents/{document_id}", status_code=204,
            dependencies=[Depends(private)])
def delete_document(document_id: str) -> Response:
    try:
        uploads.remove(document_id, upload_store())
    except KeyError as e:
        raise HTTPException(404, NOT_FOUND) from e
    except uploads.UploadError as e:
        raise HTTPException(409, str(e)) from e
    return Response(status_code=204)


@app.get("/api/v1/elements/{element_id}")
def element(element_id: str, x_api_key: ApiKey = None) -> dict[str, object]:
    """Resolve a citation to the element it points at - what the UI opens on click."""
    with session_scope() as s:
        el = s.get(ElementRow, element_id)
        if el is None:
            raise HTTPException(404, "unknown element_id")
        doc, fig = s.get(Document, el.document_id), s.get(FigureDescription, element_id)
        _visible(doc, x_api_key)
        return {
            "element_id": el.element_id, "document_id": el.document_id,
            "title": doc.title if doc else None, "page": el.page, "type": el.type,
            "bbox": el.bbox, "text": el.text, "table_json": el.table_json,
            "figure": {"kind": fig.kind, "description": fig.description,
                       "described_by": fig.model} if fig else None,
        }


@app.get("/api/v1/figures/{element_id}")
def figure(element_id: str, x_api_key: ApiKey = None) -> Response:
    """The image as PNG: browsers cannot display the JPEG 2000 some reports embed."""
    with session_scope() as s:
        el = s.get(ElementRow, element_id)
        path = el.image_path if el is not None and el.type == "figure" else None
        if el is not None:
            _visible(s.get(Document, el.document_id), x_api_key)
    if not path:
        raise HTTPException(404, "no figure with that element_id")
    return Response(png(ROOT / path.replace("\\", "/")), media_type="image/png")


@app.get("/health")
def health() -> JSONResponse:
    """503 when a dependency is down. The LLM is not called here - that would spend quota."""
    deps = {"postgres": "down", "qdrant": "down"}
    try:
        with session_scope() as s:
            s.execute(text("SELECT 1"))
        deps["postgres"] = "ok"
    except Exception:
        pass
    try:
        QdrantClient(url=get_settings().qdrant_url, timeout=3).get_collections()
        deps["qdrant"] = "ok"
    except Exception:
        pass
    ok = all(v == "ok" for v in deps.values())
    settings = get_settings()
    return JSONResponse({"status": "ok" if ok else "degraded", "dependencies": deps,
                         "llm": f"{settings.llm_provider}/{settings.llm_model}"},
                        status_code=200 if ok else 503)

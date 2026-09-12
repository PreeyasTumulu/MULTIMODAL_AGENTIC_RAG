"""HTTP API - the contract in docs/architecture/api.md, trimmed to what is built.

Deliberately thin: every decision lives in `analyst.agent`. A request becomes one
`ask()` call, and the response IS the agent's `Answer` model - so the API cannot
drift from what notebook 15 measured.

Run:  uv run uvicorn analyst.api:app --port 8400
"""

from functools import lru_cache

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from sqlalchemy import text

from analyst.agent import Answer, Tools, ask, connect
from analyst.config import ROOT, get_settings
from analyst.db import session_scope
from analyst.llm import LLM
from analyst.models import Document, ElementRow, FigureDescription
from analyst.tools import Company
from analyst.vision import png

app = FastAPI(title="Indian Equity Research Analyst", version="0.1.0")


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@lru_cache
def agent() -> tuple[LLM, Tools]:
    """Built once per process: it loads the embedding model."""
    return connect(get_settings())


@app.post("/api/v1/ask")
def ask_question(req: AskRequest) -> Answer:
    """A refusal is a 200 with `abstained: true` - declining to guess is correct behaviour."""
    llm, tools = agent()
    try:
        return ask(req.question, llm, tools)
    except httpx.HTTPError as e:
        # An upstream rate limit is not the client's fault: 503, not 429 (api.md).
        raise HTTPException(503, "LLM provider unavailable") from e


@app.get("/api/v1/companies")
def companies() -> list[Company]:
    return list(agent()[1].corpus.values())


@app.get("/api/v1/elements/{element_id}")
def element(element_id: str) -> dict[str, object]:
    """Resolve a citation to the element it points at - what the UI opens on click."""
    with session_scope() as s:
        el = s.get(ElementRow, element_id)
        if el is None:
            raise HTTPException(404, "unknown element_id")
        doc, fig = s.get(Document, el.document_id), s.get(FigureDescription, element_id)
        return {
            "element_id": el.element_id, "document_id": el.document_id,
            "title": doc.title if doc else None, "page": el.page, "type": el.type,
            "bbox": el.bbox, "text": el.text, "table_json": el.table_json,
            "figure": {"kind": fig.kind, "description": fig.description,
                       "described_by": fig.model} if fig else None,
        }


@app.get("/api/v1/figures/{element_id}")
def figure(element_id: str) -> Response:
    """The image as PNG: browsers cannot display the JPEG 2000 some reports embed."""
    with session_scope() as s:
        el = s.get(ElementRow, element_id)
        path = el.image_path if el is not None and el.type == "figure" else None
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

"""Private PDF uploads: store, parse, chunk, embed - in the background, one at a time.

An upload is deliberately NOT part of the measured corpus. It has no company or
fiscal year, is indexed into its own Qdrant collection, and is answered in
document mode (`agent.ask_document`). Keeping it apart is what keeps every number
in results/ reproducible however many PDFs are uploaded.

It reuses the corpus pipeline's own steps - `parsing.extract_elements`,
`chunking.chunk_document`, the same embedder - so an upload is read exactly the way
the annual reports were. Two things are left out on purpose: images (describing
them needs the local vision model, which a cloud box does not have) and OCR (the
project has none, ADR-004), so a scanned PDF is rejected with a reason.
"""

import hashlib
import re
import threading
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import delete, insert, select, update

from analyst.chunking import SourceElement, TitleContext, chunk_document
from analyst.config import ROOT, Settings
from analyst.db import session_scope
from analyst.embedding import DEFAULT_MODEL, Embedder
from analyst.models import Document, ElementRow
from analyst.parsing import extract_elements, pdf_info
from analyst.provenance import Element
from analyst.retrievers import store_for
from analyst.vectorstore import VectorStore

VARIANT = "uploads"  # -> collection elements_uploads_bge-small, apart from the corpus
MAX_BYTES = 50 * 1024 * 1024
MAX_PAGES = 1000  # ~6,000 chunks: about 25 minutes of CPU embedding
MIN_CHARS_PER_PAGE = 30  # below this the PDF has no real text layer
BATCH = 64


class Status(StrEnum):
    QUEUED = "queued"
    PARSING = "parsing"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


ACTIVE = (Status.QUEUED, Status.PARSING, Status.INDEXING)


class Upload(BaseModel):
    """What the API returns about an upload."""

    document_id: str
    title: str
    status: str
    progress: float
    pages: int | None
    chunks: int | None
    size_bytes: int
    error: str | None
    uploaded_at: datetime


class UploadError(Exception):
    """A reason to show the user, as opposed to a bug."""


def _view(d: Document) -> Upload:
    return Upload(document_id=d.document_id, title=d.title, status=d.status,
                  progress=d.progress, pages=d.n_pages, chunks=d.n_chunks,
                  size_bytes=d.size_bytes, error=d.error, uploaded_at=d.fetched_at)


def check_pdf(data: bytes) -> str | None:
    """Why these bytes cannot be accepted, or None. The type is read from the bytes
    themselves: a file name or a Content-Type header is whatever the client says."""
    if len(data) > MAX_BYTES:
        return f"The file is over {MAX_BYTES // 2**20} MB."
    if not data.startswith(b"%PDF-"):
        return "That is not a PDF."
    return None


def title_from(given: str | None, filename: str | None) -> str:
    """A readable title: the one given, else the file name without its extension."""
    raw = given or re.sub(r"\.pdf$", "", filename or "", flags=re.IGNORECASE)
    return " ".join(re.sub(r"[_\s]+", " ", raw).split())[:300] or "Untitled document"


def document_id_for(data: bytes) -> str:
    """Content-addressed, like the corpus: the same PDF uploaded twice is one document."""
    return f"upload-{hashlib.sha256(data).hexdigest()[:16]}"


def save(data: bytes, title: str, settings: Settings) -> tuple[Upload, bool]:
    """Store the file and a queued row. Returns (upload, needs_processing).

    A duplicate that is ready (or in progress) is returned as it is; one that failed
    is queued again, so uploading the same file twice is also how to retry.
    """
    doc_id = document_id_for(data)
    path = settings.data_dir / "uploads" / f"{doc_id}.pdf"
    with session_scope() as s:
        doc = s.get(Document, doc_id)
        if doc is not None and doc.status != Status.FAILED:
            return _view(doc), False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        if doc is None:
            doc = Document(document_id=doc_id, ticker=None, doc_type="upload", fiscal_year=None,
                           title=title, source_url="upload", local_path=_relative(path),
                           sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data),
                           source="upload")
            s.add(doc)
        doc.title, doc.status, doc.progress, doc.error = title, Status.QUEUED, 0.0, None
        s.flush()
        s.refresh(doc)
        return _view(doc), True


def list_uploads() -> list[Upload]:
    with session_scope() as s:
        docs = s.execute(select(Document).where(Document.source == "upload")
                         .order_by(Document.fetched_at.desc())).scalars().all()
        return [_view(d) for d in docs]


def get(document_id: str) -> Upload | None:
    with session_scope() as s:
        d = s.get(Document, document_id)
        return _view(d) if d is not None and d.source == "upload" else None


def remove(document_id: str, store: VectorStore) -> None:
    """Vectors, elements (by FK cascade), the row and the file. Refused mid-processing:
    the job would recreate what was just deleted."""
    with session_scope() as s:
        d = s.get(Document, document_id)
        if d is None or d.source != "upload":
            raise KeyError(document_id)
        if d.status in (Status.PARSING, Status.INDEXING):
            raise UploadError("It is still being processed - try again when it finishes.")
        path = ROOT / d.local_path
        s.delete(d)
    if store.exists():
        store.delete_document(document_id)
    path.unlink(missing_ok=True)


# One job at a time: embedding a long PDF is the heaviest thing the API does, and two
# at once would only compete for the same CPU and memory.
_lock = threading.Lock()


def process(document_id: str, embedder: Callable[[], Embedder], settings: Settings) -> None:
    """The background job. Every failure lands on the row as a readable reason."""
    with _lock:
        try:
            _process(document_id, embedder, settings)
        except UploadError as e:
            _set(document_id, status=Status.FAILED, error=str(e))
        except Exception as e:  # a bug, but the user still needs to see the upload failed
            _set(document_id, status=Status.FAILED, error=f"Processing failed: {e}"[:500])


def resume(embedder: Callable[[], Embedder], settings: Settings) -> None:
    """At API start: finish whatever a restart interrupted, oldest first."""
    with session_scope() as s:
        pending = s.execute(select(Document.document_id)
                            .where(Document.source == "upload", Document.status.in_(ACTIVE))
                            .order_by(Document.fetched_at)).scalars().all()
    for doc_id in pending:
        process(doc_id, embedder, settings)


def _process(document_id: str, embedder: Callable[[], Embedder], settings: Settings) -> None:
    with session_scope() as s:
        doc = s.get(Document, document_id)
        if doc is None:  # deleted while it waited for the lock
            return
        path, title = ROOT / doc.local_path, doc.title

    # --- parse: the corpus parser, images off (see module docstring)
    try:
        pages, locked = pdf_info(path)
    except Exception as e:
        raise UploadError("The PDF could not be opened - it may be damaged.") from e
    if locked:
        raise UploadError("The PDF is password-protected.")
    if pages > MAX_PAGES:
        raise UploadError(f"The PDF has {pages:,} pages; the limit is {MAX_PAGES:,}.")
    _set(document_id, status=Status.PARSING, progress=0.0, n_pages=pages)
    elements: list[Element] = []
    for el in extract_elements(path, document_id, settings.data_dir / "figures",
                               with_figures=False):
        if el.page % 10 == 0 and (not elements or elements[-1].page != el.page):
            _set(document_id, progress=el.page / pages)  # every 10th page is often enough
        elements.append(el)
    if sum(len(e.text or "") for e in elements) < MIN_CHARS_PER_PAGE * pages:
        raise UploadError("No text layer found - this looks like a scanned PDF, and OCR "
                          "is not supported.")
    with session_scope() as s:  # replace, so a retried upload never keeps stale elements
        s.execute(delete(ElementRow).where(ElementRow.document_id == document_id))
        s.execute(insert(ElementRow), [
            {"element_id": e.element_id, "document_id": document_id, "page": e.page,
             "type": e.type.value, "seq": e.order, "text": e.text,
             "table_json": e.table_json, "bbox": list(e.bbox) if e.bbox else None}
            for e in elements])

    # --- chunk + embed into the uploads collection
    source = [SourceElement(element_id=e.element_id, document_id=document_id, page=e.page,
                            seq=e.order, type=e.type.value, text=e.text,
                            table_json=e.table_json) for e in elements]
    chunks = chunk_document(source, None, None, context=TitleContext(title))
    if not chunks:
        raise UploadError("No readable passages were found in this PDF.")
    _set(document_id, status=Status.INDEXING, progress=0.0)
    model, store = embedder(), store_for(settings, DEFAULT_MODEL, VARIANT)
    store.ensure()
    store.delete_document(document_id)  # a retry starts clean
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i : i + BATCH]
        vectors = list(model.embed_documents([c.embed_text for c in batch], parallel=None))
        store.upsert(batch, vectors)
        _set(document_id, progress=(i + len(batch)) / len(chunks))
    _set(document_id, status=Status.READY, progress=1.0, n_chunks=len(chunks))


def _set(document_id: str, **values: object) -> None:
    with session_scope() as s:
        s.execute(update(Document).where(Document.document_id == document_id).values(**values))


def _relative(path: Path) -> str:
    """Stored relative to the repo, so the same row works on the host and in a container."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)

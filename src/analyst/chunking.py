"""Elements -> chunks, the unit that actually gets embedded.

Three rules, each with a reason:

1. A table is never separated from its header. A 200-row statement is split by
   rows when it must be, but every piece repeats the header - "12,345" with no
   column label is noise to the embedder and to the reranker.

2. Text is grouped under the heading above it. "Revenue grew 12%" is ambiguous
   without "Speciality segment" sitting over it, and the embedding of an
   ambiguous sentence is an ambiguous vector.

3. Every chunk keeps the element IDs it came from. Retrieval returns a chunk;
   a citation must point at an element on a page. Losing that link here means
   losing citations everywhere downstream.
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict

# BGE-family encoders truncate at 512 tokens. Prose runs roughly 4 chars/token,
# so ~1200 characters fits with room for the heading prefix.
TARGET_CHARS = 1200
OVERLAP_CHARS = 200
MIN_CHUNK_CHARS = 80

# Tables are budgeted separately and far more tightly. Dense numeric text
# tokenizes much worse than prose - "520,412.5" is several tokens, not one - so
# a table runs closer to 2.5 chars/token. Measured before this cap existed, the
# largest table chunk was 6,643 characters: well over the encoder limit, so most
# of it was silently truncated and never embedded at all. Anything beyond the
# limit is not "extra context", it is content the retriever cannot see.
MAX_TABLE_CHARS = 900
MAX_TABLE_ROWS = 25


class Chunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_id: str
    document_id: str
    ticker: str
    fiscal_year: int
    element_ids: list[str]
    pages: list[int]
    type: str
    heading: str | None
    text: str

    @property
    def page(self) -> int:
        return self.pages[0]


@dataclass
class SourceElement:
    """Flat view of an elements row, so chunking needs no database session."""

    element_id: str
    document_id: str
    page: int
    seq: int
    type: str
    text: str | None
    table_json: dict[str, object] | None = None


@dataclass
class _Buffer:
    parts: list[tuple[str, int, str]] = field(default_factory=list)  # text, page, element_id

    @property
    def length(self) -> int:
        return sum(len(p[0]) for p in self.parts) + max(0, len(self.parts) - 1)

    def clear(self) -> None:
        self.parts = []


def _prefix(heading: str | None) -> str:
    return f"{heading}\n\n" if heading else ""


def _table_parts(tj: dict[str, object] | None) -> tuple[list[str], list[list[str]]]:
    """Narrow JSONB (typed `object`) into strings, with isinstance rather than casts.

    table_json comes back from Postgres as arbitrary JSON. Asserting its shape
    with a cast would hide a malformed row; checking it degrades to an empty
    table instead, which the caller already handles.
    """
    if not tj:
        return [], []
    raw_header, raw_rows = tj.get("header"), tj.get("rows")
    header = [str(h) for h in raw_header] if isinstance(raw_header, list) else []
    rows = (
        [[str(c) for c in r] for r in raw_rows if isinstance(r, list)]
        if isinstance(raw_rows, list)
        else []
    )
    return header, rows


def _table_chunks(
    el: SourceElement, heading: str | None, ticker: str, fiscal_year: int
) -> Iterator[Chunk]:
    header, rows = _table_parts(el.table_json)

    if not rows:
        if el.text:
            yield Chunk(
                chunk_id=f"{el.element_id}#0",
                document_id=el.document_id,
                ticker=ticker,
                fiscal_year=fiscal_year,
                element_ids=[el.element_id],
                pages=[el.page],
                type="table",
                heading=heading,
                text=_prefix(heading) + el.text,
            )
        return

    header_line = " | ".join(header)
    fixed = len(_prefix(heading)) + len(header_line) + 1

    # Pack rows by CHARACTER budget, not a fixed row count: row width varies by
    # an order of magnitude between a two-column summary and a wide segment table.
    windows: list[list[list[str]]] = []
    current: list[list[str]] = []
    used = fixed
    for row in rows:
        line = " | ".join(row)
        if current and (used + len(line) + 1 > MAX_TABLE_CHARS or len(current) >= MAX_TABLE_ROWS):
            windows.append(current)
            current, used = [], fixed
        current.append(row)
        used += len(line) + 1
    if current:
        windows.append(current)

    for i, window in enumerate(windows):
        body = "\n".join(" | ".join(r) for r in window)
        yield Chunk(
            chunk_id=f"{el.element_id}#{i}",
            document_id=el.document_id,
            ticker=ticker,
            fiscal_year=fiscal_year,
            element_ids=[el.element_id],
            pages=[el.page],
            type="table",
            heading=heading,
            # Header repeated on every slice: this is the whole point.
            text=f"{_prefix(heading)}{header_line}\n{body}",
        )


def _flush_text(
    buf: _Buffer, heading: str | None, ticker: str, fiscal_year: int, index: int
) -> Chunk | None:
    if not buf.parts:
        return None
    text = "\n".join(p[0] for p in buf.parts)
    if len(text) < MIN_CHUNK_CHARS:
        return None
    pages = sorted({p[1] for p in buf.parts})
    element_ids = [p[2] for p in buf.parts]
    return Chunk(
        chunk_id=f"{element_ids[0]}#{index}",
        document_id=buf.parts[0][2].split(":")[0],
        ticker=ticker,
        fiscal_year=fiscal_year,
        element_ids=element_ids,
        pages=pages,
        type="text",
        heading=heading,
        text=_prefix(heading) + text,
    )


def chunk_document(
    elements: Sequence[SourceElement], ticker: str, fiscal_year: int
) -> list[Chunk]:
    """Elements of ONE document, already ordered by (page, seq)."""
    out: list[Chunk] = []
    heading: str | None = None
    buf = _Buffer()
    text_index = 0

    def flush() -> None:
        nonlocal text_index
        chunk = _flush_text(buf, heading, ticker, fiscal_year, text_index)
        if chunk:
            out.append(chunk)
            text_index += 1
        buf.clear()

    for el in elements:
        if el.type == "heading":
            # A new heading ends the previous section: mixing two sections into
            # one chunk is how a retriever ends up citing the wrong segment.
            flush()
            heading = (el.text or "").strip() or None
            continue

        if el.type == "table":
            flush()
            out.extend(_table_chunks(el, heading, ticker, fiscal_year))
            continue

        if el.type != "text" or not el.text:
            continue

        if buf.length + len(el.text) > TARGET_CHARS and buf.parts:
            flush()
            # Carry the tail of the previous chunk forward so a sentence split
            # across the boundary is still retrievable from either side.
            tail = out[-1].text[-OVERLAP_CHARS:] if out else ""
            if tail and out and out[-1].type == "text":
                buf.parts.append((tail, el.page, el.element_id))

        buf.parts.append((el.text, el.page, el.element_id))

    flush()
    return out

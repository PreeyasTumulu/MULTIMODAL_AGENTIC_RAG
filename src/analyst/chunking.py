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

4. A chunk states which company and year it belongs to. ADR-007 measured the
   vocabulary gap from the query side; this is the document side of it. The
   element answering "Sun Pharma's total revenue in FY2024" is a bare grid of
   numbers that names neither the company (only 8% of answer chunks do) nor,
   in a quarter of cases, the year. `DocContext` supplies both.
"""

import re
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

# The encoder's hard stop, in characters, per content type. BGE truncates at 512
# tokens; prose runs ~4 chars/token and dense numeric text ~2.5. Anything past
# this is not "extra context", it is content the retriever cannot see - and the
# row packer above was the only path that respected it. 160 chunks (1.6%),
# the largest 5,116 characters, were still being silently cut.
ENCODER_TOKENS = 512
CHARS_PER_TOKEN = {"text": 4.0, "table": 2.5}


def budget(kind: str) -> int:
    return int(ENCODER_TOKENS * CHARS_PER_TOKEN[kind])


# Running page bands, not section titles: "226 / Statutory Reports / Corporate
# Overview / Financial Statements" is printed on every page of the section. A
# quarter of all chunks carried one, and the single worst heading repeated on
# 507 chunks. A string identical across hundreds of chunks cannot help tell them
# apart; it only dilutes the vector and spends the encoder budget.
#
# Matched against a WHOLE line, never a substring. "Financial Statements" alone
# is a band; "CONSOLIDATED FINANCIAL STATEMENTS OF ICICI BANK LIMITED" names the
# company and stays. Anchoring is what keeps the filter from eating real titles.
_FURNITURE = re.compile(
    r"""^\s*(
        \d{1,4}                                   # a bare page number
      | page\s+\d{1,4}
      | statutory\s+reports
      | corporate\s+overview
      | financial\s+statements
      | (integrated\s+)?annual\s+report[\s\d/-]*
    )\s*$""",
    re.IGNORECASE | re.VERBOSE,
)


def clean_heading(heading: str | None) -> str | None:
    """Drop page furniture; keep anything that might be a real section title."""
    if not heading:
        return None
    kept = [ln for ln in heading.splitlines() if ln.strip() and not _FURNITURE.match(ln)]
    return " ".join(" ".join(kept).split()) or None


@dataclass(frozen=True)
class DocContext:
    """Who and when, stated on every chunk of one document.

    Deliberately NOT the statement title. Recovering one by scanning backwards
    was measured and rejected: a title was found for only 65% of answer
    elements, 3% of them on the element's own page, a median of 21 elements
    back - and most matches were prose ("Refer consolidated statement of changes
    in equity for detailed movement..."), not titles. It would have attached
    plausible-looking wrong context more often than right context.
    """

    ticker: str
    company: str
    fiscal_year: int

    @property
    def prefix(self) -> str:
        """Both vocabularies, because both halves of the retriever read this.

        "FY2025" is what the question asks; "year ended March 31, 2025" is what
        an Indian filing prints. `expand_query` adds the same date form on the
        query side, so the two now meet.
        """
        return (
            f"{self.company} ({self.ticker}) "
            f"FY{self.fiscal_year} year ended March 31, {self.fiscal_year}"
        )


class _NoContext(DocContext):
    """The baseline arm: carries the ticker and year a Chunk needs, prints
    nothing. Keeps `chunk_document` free of `if context is None` branches."""

    def __init__(self, ticker: str, fiscal_year: int) -> None:
        super().__init__(ticker=ticker, company="", fiscal_year=fiscal_year)

    @property
    def prefix(self) -> str:
        return ""


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
    context: str = ""

    @property
    def page(self) -> int:
        return self.pages[0]

    @property
    def embed_text(self) -> str:
        """What is embedded. `text` stays the verbatim passage, so a citation
        still quotes the document rather than something we assembled."""
        return f"{self.context}\n{self.text}" if self.context else self.text


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


def _split(text: str, limit: int) -> list[str]:
    """Break an oversized element on line boundaries, falling back to a hard cut.

    Needed because a single element larger than the budget was never split: the
    row packer only ever split a table it had parsed into rows. A 5,116-char
    element became one chunk and the encoder read the first ~1,280 of it.
    """
    if len(text) <= limit:
        return [text]
    out, cur = [], ""
    for line in text.splitlines(keepends=True):
        while len(line) > limit:  # one line longer than the whole budget
            out.append(line[:limit])
            line = line[limit:]
        if len(cur) + len(line) > limit and cur:
            out.append(cur)
            cur = ""
        cur += line
    if cur.strip():
        out.append(cur)
    return [p for p in (x.strip() for x in out) if p]


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
    el: SourceElement, heading: str | None, ctx: DocContext, reserve: int
) -> Iterator[Chunk]:
    ticker, fiscal_year = ctx.ticker, ctx.fiscal_year
    header, rows = _table_parts(el.table_json)

    def make(i: int, text: str) -> Chunk:
        return Chunk(
            chunk_id=f"{el.element_id}#{i}",
            document_id=el.document_id,
            ticker=ticker,
            fiscal_year=fiscal_year,
            element_ids=[el.element_id],
            pages=[el.page],
            type="table",
            heading=heading,
            text=text,
            context=ctx.prefix,
        )

    if not rows:
        # Unparsed table: still a table's worth of digits, so it gets the table
        # budget and the same splitting the row packer would have given it.
        if el.text:
            body = _prefix(heading) + el.text
            for i, piece in enumerate(_split(body, budget("table") - reserve)):
                yield make(i, piece)
        return

    header_line = " | ".join(header)
    fixed = reserve + len(_prefix(heading)) + len(header_line) + 1
    limit = budget("table")

    # A header that leaves no room for a row is not a header. The worst in this
    # corpus is 3,328 characters across 3 cells - a full infographic page the
    # table detector flattened - and repeating it on every slice put 138 chunks
    # over the encoder limit no matter how few rows each carried. Drop the
    # repeat-the-header strategy for these and just split the whole thing.
    if fixed >= limit:
        flat = _prefix(heading) + "\n".join([header_line, *(" | ".join(r) for r in rows)])
        for i, piece in enumerate(_split(flat, limit - reserve)):
            yield make(i, piece)
        return

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

    i = 0
    for window in windows:
        body = "\n".join(" | ".join(r) for r in window)
        # Header repeated on every slice: this is the whole point. Split guards
        # the case the packer cannot help - a SINGLE row over the budget, the
        # longest here being 1,750 characters, which it must emit whole or not
        # at all. Normally a no-op.
        for piece in _split(f"{_prefix(heading)}{header_line}\n{body}", limit - reserve):
            yield make(i, piece)
            i += 1


def _flush_text(
    buf: _Buffer, heading: str | None, ctx: DocContext, index: int, reserve: int
) -> Iterator[Chunk]:
    if not buf.parts:
        return
    text = "\n".join(p[0] for p in buf.parts)
    if len(text) < MIN_CHUNK_CHARS:
        return
    pages = sorted({p[1] for p in buf.parts})
    element_ids = [p[2] for p in buf.parts]
    # A single paragraph is never cut mid-way when packing, so a buffer can still
    # arrive over budget on the strength of one oversized element.
    for j, piece in enumerate(_split(_prefix(heading) + text, budget("text") - reserve)):
        yield Chunk(
            chunk_id=f"{element_ids[0]}#{index}" if j == 0 else f"{element_ids[0]}#{index}.{j}",
            document_id=buf.parts[0][2].split(":")[0],
            ticker=ctx.ticker,
            fiscal_year=ctx.fiscal_year,
            element_ids=element_ids,
            pages=pages,
            type="text",
            heading=heading,
            text=piece,
            context=ctx.prefix,
        )


def chunk_document(
    elements: Sequence[SourceElement],
    ticker: str,
    fiscal_year: int,
    context: DocContext | None = None,
    strip_furniture: bool = True,
) -> list[Chunk]:
    """Elements of ONE document, already ordered by (page, seq).

    `context` and `strip_furniture` are what ADR-008 measures. Passing no
    context reproduces the pre-ADR-008 chunks exactly, which is what makes the
    A/B an A/B rather than two unrelated indexes.
    """
    ctx = context or _NoContext(ticker, fiscal_year)
    # The prefix is embedded with the chunk, so it has to be paid for out of the
    # same budget. Charged here rather than discovered by the encoder.
    reserve = len(ctx.prefix) + 1 if ctx.prefix else 0

    out: list[Chunk] = []
    heading: str | None = None
    buf = _Buffer()
    text_index = 0

    def flush() -> None:
        nonlocal text_index
        made = list(_flush_text(buf, heading, ctx, text_index, reserve))
        if made:
            out.extend(made)
            text_index += 1
        buf.clear()

    for el in elements:
        if el.type == "heading":
            # A new heading ends the previous section: mixing two sections into
            # one chunk is how a retriever ends up citing the wrong segment.
            flush()
            raw = (el.text or "").strip() or None
            heading = clean_heading(raw) if strip_furniture else raw
            continue

        if el.type == "table":
            flush()
            out.extend(_table_chunks(el, heading, ctx, reserve))
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

"""Database rows -> chunks, ready to embed.

Split out of the notebooks because ADR-008 needs the SAME corpus built two ways
- with and without a contextual prefix - and an A/B where the two arms are built
by two copies of a loop is not an A/B.

Kept out of `chunking.py` on purpose: that module takes flat dataclasses and
touches no database, which is why its tests need no Postgres.
"""

from sqlalchemy import select

from analyst.chunking import Chunk, DocContext, SourceElement, chunk_document
from analyst.db import session_scope
from analyst.models import Company, Document, ElementRow, FigureDescription
from analyst.vision import KEEP


def load_chunks(
    with_context: bool = False, strip_furniture: bool | None = None, with_figures: bool = False
) -> list[Chunk]:
    """Every document, chunked.

    The two treatments are separately controllable because ADR-008's first run
    could not tell them apart: its `ctx` arm stripped furniture AND added a
    prefix, so a +0.25 R@5 could not be assigned to either. `strip_furniture`
    defaults to following `with_context`, which reproduces the original `fix`
    and `ctx` arms exactly, and can be set independently for the `strip` arm.

    `with_figures` adds one chunk per figure whose vision description says it
    carries information (ADR-010). Off by default, so every earlier arm still
    rebuilds exactly as it was measured.
    """
    strip = with_context if strip_furniture is None else strip_furniture
    described: dict[str, str] = {}
    if with_figures:
        with session_scope() as s:
            described = dict(s.execute(
                select(FigureDescription.element_id, FigureDescription.description)
                .where(FigureDescription.kind.in_(KEEP))).tuples().all())
    out: list[Chunk] = []
    with session_scope() as s:
        for d in s.execute(select(Document).order_by(Document.ticker)).scalars().all():
            company = s.get(Company, d.ticker)
            rows = s.execute(
                select(ElementRow.element_id, ElementRow.document_id, ElementRow.page,
                       ElementRow.seq, ElementRow.type, ElementRow.text, ElementRow.table_json)
                .where(ElementRow.document_id == d.document_id)
                .order_by(ElementRow.page, ElementRow.seq)
            ).all()
            # Only figure rows have no text of their own, so `or` fills exactly those.
            els = [SourceElement(element_id=r[0], document_id=r[1], page=r[2], seq=r[3],
                                 type=r[4], text=r[5] or described.get(r[0]), table_json=r[6])
                   for r in rows]
            ctx = (
                DocContext(ticker=d.ticker,
                           company=company.name if company else d.ticker,
                           fiscal_year=d.fiscal_year)
                if with_context else None
            )
            out.extend(chunk_document(els, d.ticker, d.fiscal_year, context=ctx,
                                      strip_furniture=strip))
    return out

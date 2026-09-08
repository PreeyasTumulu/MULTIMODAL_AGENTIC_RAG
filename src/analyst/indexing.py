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
from analyst.models import Company, Document, ElementRow


def load_chunks(with_context: bool = False) -> list[Chunk]:
    """Every document, chunked. `with_context` is the ADR-008 arm.

    The two arms differ in exactly two ways - the prefix and the page-furniture
    filter - and in nothing else, so a delta between them is attributable.
    """
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
            els = [SourceElement(element_id=r[0], document_id=r[1], page=r[2], seq=r[3],
                                 type=r[4], text=r[5], table_json=r[6]) for r in rows]
            ctx = (
                DocContext(ticker=d.ticker,
                           company=company.name if company else d.ticker,
                           fiscal_year=d.fiscal_year)
                if with_context else None
            )
            out.extend(chunk_document(els, d.ticker, d.fiscal_year, context=ctx,
                                      strip_furniture=with_context))
    return out

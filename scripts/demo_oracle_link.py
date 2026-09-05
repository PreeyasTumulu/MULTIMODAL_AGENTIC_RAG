"""Prove the join: an oracle number, located on a real page of a real report.

This is Day 3's benchmark generator in miniature. If this works, the auto-labelled
(question, answer, source page) triples work.

    uv run python scripts/demo_oracle_link.py SUNPHARMA 2025
"""

import sys
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from analyst.db import session_scope
from analyst.models import Document, ElementRow, Fact
from analyst.numfmt import find_value

CONCEPTS = ("Total Revenue", "Net Income", "Gross Profit", "Operating Income")


def main() -> None:
    ticker = sys.argv[1] if len(sys.argv) > 1 else "SUNPHARMA"
    fy = int(sys.argv[2]) if len(sys.argv) > 2 else 2025

    with session_scope() as s:
        doc = s.execute(
            select(Document)
            .where(Document.ticker == ticker, Document.fiscal_year == fy)
        ).scalar_one_or_none()
        if doc is None:
            print(f"no document for {ticker} FY{fy}")
            return

        facts = s.execute(
            select(Fact.concept, Fact.value)
            .where(Fact.ticker == ticker)
            .where(Fact.concept.in_(CONCEPTS))
            # A real date, not a string: psycopg will not compare date to varchar.
            .where(Fact.period_end == date(fy, 3, 31))
        ).all()

        elements = s.execute(
            select(ElementRow.element_id, ElementRow.page, ElementRow.type, ElementRow.text)
            .where(ElementRow.document_id == doc.document_id)
            .where(ElementRow.text.is_not(None))
            .order_by(ElementRow.page, ElementRow.seq)
        ).all()

    print(f"\ndocument : {doc.document_id}")
    print(f"           {doc.title}  ({doc.n_pages} pages, {len(elements)} text-bearing elements)")
    print(f"oracle   : facts WHERE ticker={ticker} AND period_end={fy}-03-31\n")

    for concept, value in facts:
        crore = Decimal(value) / Decimal(10**7)
        hit = None
        for element_id, page, etype, text in elements:
            matched = find_value(Decimal(value), text or "")
            if matched:
                hit = (element_id, page, etype, matched)
                break
        print(f"  {concept:<20} Rs {crore:>12,.0f} cr")
        if hit:
            element_id, page, etype, matched = hit
            print(f"  {'':<20} -> FOUND as '{matched}' on page {page} ({etype})")
            print(f"  {'':<20}    {element_id}")
        else:
            print(f"  {'':<20} -> not located; this fact is DISCARDED from the benchmark")
        print()


if __name__ == "__main__":
    main()

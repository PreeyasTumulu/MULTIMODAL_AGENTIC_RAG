"""Relational schema.

Day 1 covers the STRUCTURED half of the corpus: companies, daily prices, and the
financial facts that act as the evaluation oracle. Document/element tables arrive
on Day 2 as an Alembic migration.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Money in paise-precision INR. Reliance FY26 revenue is ~1.06e13, so an 18-digit
# type would be uncomfortably close to the ceiling. 30 digits is free insurance.
MONEY = Numeric(30, 4)
PRICE = Numeric(18, 4)


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    sector: Mapped[str] = mapped_column(String(50), index=True)
    yf_symbol: Mapped[str] = mapped_column(String(30), unique=True)
    # NOT always the quote currency. Infosys quotes in INR but reports its
    # statements in USD, which silently breaks cross-company comparison and the
    # benchmark generator unless it is carried explicitly.
    financial_currency: Mapped[str] = mapped_column(String(3), server_default="INR")


class Price(Base):
    """Daily OHLCV. One row per (ticker, trading day)."""

    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(
        ForeignKey("companies.ticker", ondelete="CASCADE"), index=True
    )
    trade_date: Mapped[date] = mapped_column(Date)
    open: Mapped[Decimal] = mapped_column(PRICE)
    high: Mapped[Decimal] = mapped_column(PRICE)
    low: Mapped[Decimal] = mapped_column(PRICE)
    close: Mapped[Decimal] = mapped_column(PRICE)
    adj_close: Mapped[Decimal] = mapped_column(PRICE)
    volume: Mapped[int] = mapped_column(BigInteger)

    __table_args__ = (
        UniqueConstraint("ticker", "trade_date", name="uq_prices_ticker_date"),
        Index("ix_prices_ticker_date", "ticker", "trade_date"),
    )


class Document(Base):
    """A source PDF.

    `fiscal_year` is the year the Indian FY *ends* (FY2024-25 -> 2025), which is
    exactly `facts.period_end`'s year. That is the join key between the
    unstructured and structured halves of the corpus - no mapping table needed.
    """

    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    ticker: Mapped[str] = mapped_column(
        ForeignKey("companies.ticker", ondelete="CASCADE"), index=True
    )
    doc_type: Mapped[str] = mapped_column(String(40), index=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(300))
    source_url: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    local_path: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    n_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("ticker", "doc_type", "fiscal_year", name="uq_documents_identity"),
    )


class ElementRow(Base):
    """One extracted unit of a document: a text block, heading, table or figure.

    The relational mirror of `provenance.Element`. Chunking (Day 3) reads from
    here, so `bbox` and `page` survive all the way to a rendered citation.
    """

    __tablename__ = "elements"

    element_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.document_id", ondelete="CASCADE"), index=True
    )
    page: Mapped[int] = mapped_column(Integer, index=True)
    type: Mapped[str] = mapped_column(String(20), index=True)
    # "order" is a SQL keyword; naming the column seq avoids relying on quoting.
    seq: Mapped[int] = mapped_column(Integer)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    table_json: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    bbox: Mapped[list[float] | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (Index("ix_elements_doc_page", "document_id", "page"),)


class FigureDescription(Base):
    """What a vision model says a figure shows (ADR-010).

    Generated text, not the filing's - so it lives beside `elements`, never inside
    `elements.text`, and records which model wrote it. A citation built from it
    can then say who described the figure instead of quoting a model as if it
    were the annual report.
    """

    __tablename__ = "figure_descriptions"

    element_id: Mapped[str] = mapped_column(
        ForeignKey("elements.element_id", ondelete="CASCADE"), primary_key=True
    )
    model: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(20), index=True)
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Fact(Base):
    """A single reported financial line item.

    This table is the EVALUATION ORACLE. Every row is a (question, answer) pair
    waiting to happen, and `period_end` + `concept` give us the search keys used
    to locate the same number inside the annual report PDF on Day 3.
    """

    __tablename__ = "facts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(
        ForeignKey("companies.ticker", ondelete="CASCADE"), index=True
    )
    statement: Mapped[str] = mapped_column(String(30), index=True)
    concept: Mapped[str] = mapped_column(String(120), index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    value: Mapped[Decimal] = mapped_column(MONEY)
    unit: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(40))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "ticker", "statement", "concept", "period_end", name="uq_facts_identity"
        ),
    )

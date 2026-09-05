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
    Numeric,
    String,
    UniqueConstraint,
    func,
)
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

"""The agent's database tools: fixed, parametrised, read-only queries.

The LLM supplies parameters - a ticker, two dates - and never SQL. That makes the
SRS's SQL-safety requirements (FR-5.4 to 5.6) hold by construction rather than by
validation: there is no statement to inject into. Each query also runs inside a
READ ONLY transaction, so even a future bug in this file cannot write.

`facts` is deliberately unreachable from here. It is the evaluation oracle, and a
system that can read the answer key scores 100% and proves nothing.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, text

from analyst import models
from analyst.db import session_scope


@dataclass(frozen=True)
class Company:
    ticker: str
    name: str
    filing_years: tuple[int, ...]  # fiscal years with an indexed annual report


@dataclass(frozen=True)
class PriceSummary:
    ticker: str
    start: date
    end: date
    first_close: Decimal
    last_close: Decimal
    high_close: Decimal
    low_close: Decimal
    sessions: int


def load_corpus() -> dict[str, Company]:
    """Every company, and which fiscal years have a filing to answer from."""
    with session_scope() as s:
        s.execute(text("SET TRANSACTION READ ONLY"))
        years: dict[str, list[int]] = defaultdict(list)
        for ticker, fy in s.execute(select(models.Document.ticker, models.Document.fiscal_year)):
            years[ticker].append(fy)
        return {c.ticker: Company(c.ticker, c.name, tuple(sorted(years[c.ticker])))
                for c in s.execute(select(models.Company)).scalars()}


def price_summary(ticker: str, start: date | None, end: date | None) -> PriceSummary | None:
    """Closing-price change over a window - the latest 365 days when none is given."""
    with session_scope() as s:
        s.execute(text("SET TRANSACTION READ ONLY"))
        rows = s.execute(select(models.Price.trade_date, models.Price.close)
                         .where(models.Price.ticker == ticker)
                         .order_by(models.Price.trade_date)).all()
    if not rows:
        return None
    last = rows[-1][0]
    end = min(end or last, last)
    start = start or end - timedelta(days=365)
    window = [(d, c) for d, c in rows if start <= d <= end]
    if not window:
        return None
    closes = [c for _, c in window]
    return PriceSummary(ticker, window[0][0], window[-1][0], closes[0], closes[-1],
                        max(closes), min(closes), len(window))

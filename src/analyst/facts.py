"""Turn Yahoo Finance statement frames into oracle rows.

Kept out of scripts/ deliberately: this is the logic worth unit-testing, and it
must be testable without a network call.
"""

from datetime import date
from decimal import Decimal

import pandas as pd
from pydantic import BaseModel, ConfigDict

from analyst.pdutil import index_to_date

# yfinance attribute name for each statement we ingest.
STATEMENT_ATTRS: dict[str, str] = {
    "income_statement": "income_stmt",
    "balance_sheet": "balance_sheet",
    "cash_flow": "cashflow",
}

SOURCE = "yfinance"


class FactRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticker: str
    statement: str
    concept: str
    period_end: date
    value: Decimal
    unit: str
    source: str = SOURCE


def infer_unit(concept: str, currency: str = "INR") -> str:
    """Not every line item is money, and the money is not always rupees.

    Storing EPS or a share count as a currency amount would silently corrupt any
    ratio the Calculator agent computes later, so the unit is part of the fact's
    identity. `currency` must come from Yahoo's `financialCurrency`, never be
    assumed from the exchange.
    """
    c = concept.lower()
    if "eps" in c or "per share" in c:
        return f"{currency}/share"
    if "share" in c and any(w in c for w in ("issued", "outstanding", "number")):
        return "shares"
    if any(w in c for w in ("rate", "ratio", "margin", "yield")):
        return "ratio"
    return currency


def melt_statement(
    df: pd.DataFrame | None,
    ticker: str,
    statement: str,
    currency: str = "INR",
) -> list[FactRow]:
    """Wide (concepts x periods) -> long (one row per fact).

    Drops NaN cells: yfinance pads the oldest fiscal year with missing values,
    and a NaN is an absence of evidence, not a zero.
    """
    if df is None or df.empty:
        return []

    rows: list[FactRow] = []
    for concept, series in df.iterrows():
        concept_name = str(concept)
        unit = infer_unit(concept_name, currency)
        for period, raw in series.items():
            if raw is None or pd.isna(raw):
                continue
            rows.append(
                FactRow(
                    ticker=ticker,
                    statement=statement,
                    concept=concept_name,
                    period_end=index_to_date(period),
                    value=Decimal(str(raw)),
                    unit=unit,
                )
            )
    return rows

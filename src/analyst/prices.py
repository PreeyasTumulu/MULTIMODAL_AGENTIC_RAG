"""Normalise Yahoo Finance OHLCV frames."""

from datetime import date
from decimal import Decimal

import pandas as pd
from pydantic import BaseModel, ConfigDict

from analyst.pdutil import index_to_date


class PriceRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticker: str
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adj_close: Decimal
    volume: int


def drop_partial_bar(df: pd.DataFrame) -> pd.DataFrame:
    """Remove the in-progress session.

    THE Day-1 gotcha. While a market is open, yfinance returns a row for today
    with Open/High/Low/Volume populated but Close = NaN. Naively taking
    df.iloc[-1]["Close"] therefore yields NaN in production, and only during
    market hours - the worst kind of bug to reproduce.
    """
    return df[df["Close"].notna()]


def to_rows(df: pd.DataFrame, ticker: str) -> list[PriceRow]:
    def dec(v: object) -> Decimal:
        return Decimal(str(round(float(v), 4)))  # type: ignore[arg-type]

    rows: list[PriceRow] = []
    for ts, r in df.iterrows():
        rows.append(
            PriceRow(
                ticker=ticker,
                trade_date=index_to_date(ts),
                open=dec(r["Open"]),
                high=dec(r["High"]),
                low=dec(r["Low"]),
                close=dec(r["Close"]),
                adj_close=dec(r.get("Adj Close", r["Close"])),
                volume=int(r["Volume"]),
            )
        )
    return rows

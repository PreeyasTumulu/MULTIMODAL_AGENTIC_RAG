"""Ingest daily OHLCV for every company in the corpus.

Idempotent: safe to re-run. Running it again tomorrow adds tomorrow's bar and
leaves history untouched.

    uv run python scripts/acquire_prices.py
"""

import pandas as pd
import yfinance as yf
from sqlalchemy.dialects.postgresql import insert
from tenacity import retry, stop_after_attempt, wait_exponential

from analyst.corpus import load_corpus
from analyst.db import session_scope
from analyst.logging import configure_logging, get_logger
from analyst.models import Company, Price
from analyst.prices import drop_partial_bar, to_rows

log = get_logger("acquire_prices")
PERIOD = "5y"
CHUNK = 500


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_history(symbol: str) -> pd.DataFrame:
    # yfinance ships no type stubs, so the call is Any. Annotate at the boundary
    # rather than sprinkling casts downstream.
    df: pd.DataFrame = yf.Ticker(symbol).history(period=PERIOD, auto_adjust=False)
    if df.empty:
        raise ValueError(f"no price rows returned for {symbol}")
    return df


def main() -> None:
    configure_logging()
    companies = load_corpus()
    log.info("corpus.loaded", n=len(companies))

    with session_scope() as s:
        for c in companies:
            s.execute(
                insert(Company)
                .values(ticker=c.ticker, name=c.name, sector=c.sector, yf_symbol=c.yf_symbol)
                .on_conflict_do_update(
                    index_elements=[Company.ticker],
                    set_={"name": c.name, "sector": c.sector, "yf_symbol": c.yf_symbol},
                )
            )
    log.info("companies.upserted", n=len(companies))

    total = 0
    for c in companies:
        raw = fetch_history(c.yf_symbol)
        clean = drop_partial_bar(raw)
        dropped = len(raw) - len(clean)
        rows = to_rows(clean, c.ticker)

        with session_scope() as s:
            for i in range(0, len(rows), CHUNK):
                s.execute(
                    insert(Price)
                    .values([r.model_dump() for r in rows[i : i + CHUNK]])
                    .on_conflict_do_nothing(constraint="uq_prices_ticker_date")
                )

        total += len(rows)
        log.info(
            "prices.ingested",
            ticker=c.ticker,
            rows=len(rows),
            partial_bars_dropped=dropped,
            first=str(rows[0].trade_date) if rows else None,
            last=str(rows[-1].trade_date) if rows else None,
        )

    log.info("done", total_rows=total)


if __name__ == "__main__":
    main()

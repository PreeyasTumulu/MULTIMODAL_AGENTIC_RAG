"""Ingest reported financials - the EVALUATION ORACLE.

Every row written here is a verifiable (question, answer) pair. On Day 3 we
search the parsed annual reports for these exact values to auto-label which page
contains the answer, which is how the benchmark gets built without hand-writing
several hundred questions.

    uv run python scripts/acquire_facts.py
"""

import pandas as pd
import yfinance as yf
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from tenacity import retry, stop_after_attempt, wait_exponential

from analyst.corpus import load_corpus
from analyst.db import session_scope
from analyst.facts import STATEMENT_ATTRS, FactRow, melt_statement
from analyst.logging import configure_logging, get_logger
from analyst.models import Company, Fact

log = get_logger("acquire_facts")
CHUNK = 500


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_statements(symbol: str) -> tuple[dict[str, pd.DataFrame | None], str]:
    """Return the statement frames AND the currency they are reported in.

    `financialCurrency` is NOT the same as the quote currency: INFY.NS quotes in
    INR but reports in USD. Assuming the exchange implies the currency produces
    numbers that are wrong by ~85x, silently.
    """
    t = yf.Ticker(symbol)
    frames = {name: getattr(t, attr, None) for name, attr in STATEMENT_ATTRS.items()}
    currency = str(t.info.get("financialCurrency") or "INR").upper()
    return frames, currency


def main() -> None:
    configure_logging()
    companies = load_corpus()
    total = 0

    for c in companies:
        frames, currency = fetch_statements(c.yf_symbol)
        if currency != "INR":
            log.warning("facts.non_inr_reporting", ticker=c.ticker, currency=currency)

        with session_scope() as s:
            s.execute(
                update(Company)
                .where(Company.ticker == c.ticker)
                .values(financial_currency=currency)
            )

        rows: list[FactRow] = []
        for statement, df in frames.items():
            rows.extend(melt_statement(df, c.ticker, statement, currency))

        if not rows:
            log.warning("facts.empty", ticker=c.ticker)
            continue

        with session_scope() as s:
            for i in range(0, len(rows), CHUNK):
                stmt = insert(Fact).values([r.model_dump() for r in rows[i : i + CHUNK]])
                s.execute(
                    stmt.on_conflict_do_update(
                        constraint="uq_facts_identity",
                        set_={"value": stmt.excluded.value, "unit": stmt.excluded.unit},
                    )
                )

        periods = sorted({r.period_end for r in rows})
        total += len(rows)
        log.info(
            "facts.ingested",
            ticker=c.ticker,
            rows=len(rows),
            concepts=len({r.concept for r in rows}),
            periods=f"{periods[0]}..{periods[-1]}",
        )

    log.info("done", total_facts=total)


if __name__ == "__main__":
    main()

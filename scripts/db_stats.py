"""Print the current state of the corpus. Run it any time to see what is loaded.

    uv run python scripts/db_stats.py
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from analyst.db import session_scope

COUNTS = """
SELECT 'companies' AS table, count(*) AS rows FROM companies
UNION ALL SELECT 'prices',    count(*) FROM prices
UNION ALL SELECT 'facts',     count(*) FROM facts
UNION ALL SELECT 'documents', count(*) FROM documents
UNION ALL SELECT 'elements',  count(*) FROM elements
ORDER BY 1
"""

ELEMENTS = """
SELECT d.ticker, d.fiscal_year AS fy, d.n_pages AS pages,
       count(*) FILTER (WHERE e.type = 'text')    AS text,
       count(*) FILTER (WHERE e.type = 'heading') AS heading,
       count(*) FILTER (WHERE e.type = 'table')   AS "table",
       count(*) FILTER (WHERE e.type = 'figure')  AS figure
FROM documents d JOIN elements e ON e.document_id = d.document_id
GROUP BY d.ticker, d.fiscal_year, d.n_pages
ORDER BY d.ticker, d.fiscal_year
"""

# Proof that provenance survived: a real extracted table, addressable by page.
SAMPLE_TABLE = """
SELECT element_id, page, table_json->>'n_rows' AS rows,
       left(table_json->>'header', 60) AS header
FROM elements
WHERE type = 'table' AND (table_json->>'n_rows')::int BETWEEN 4 AND 12
ORDER BY document_id, page LIMIT 4
"""

# The kind of question the SQL Agent will answer on Day 5, written by hand today
# so we can see the oracle is real before we build anything on top of it.
CURRENCIES = """
SELECT financial_currency AS ccy, count(*) AS companies, string_agg(ticker, ', ') AS tickers
FROM companies GROUP BY 1 ORDER BY 2 DESC
"""

REVENUE = """
SELECT c.sector,
       c.ticker,
       c.financial_currency                                  AS ccy,
       round(f26.value / 1e7)                                AS fy26_cr,
       round(f25.value / 1e7)                                AS fy25_cr,
       round(100.0 * (f26.value - f25.value) / f25.value, 1) AS yoy_pct
FROM companies c
JOIN facts f26 ON f26.ticker = c.ticker
              AND f26.concept = 'Total Revenue'
              AND f26.period_end = DATE '2026-03-31'
JOIN facts f25 ON f25.ticker = c.ticker
              AND f25.concept = 'Total Revenue'
              AND f25.period_end = DATE '2025-03-31'
ORDER BY c.sector, yoy_pct DESC
"""

# DISTINCT ON gives each ticker its OWN latest session. An earlier version keyed
# off a global (SELECT max(trade_date) FROM prices), which returned NULL for any
# company whose last bar was dropped as NaN - a query bug that looks like a data bug.
PRICE_JOIN = """
SELECT DISTINCT ON (p.ticker)
       p.ticker, p.trade_date AS latest_session, round(p.close, 2) AS close
FROM prices p
ORDER BY p.ticker, p.trade_date DESC
LIMIT 5
"""


def show(session: Session, title: str, sql: str) -> None:
    print(f"\n--- {title} ---")
    rows = session.execute(text(sql))
    cols = list(rows.keys())
    print("  " + " | ".join(f"{c:>14}" for c in cols))
    for r in rows:
        print("  " + " | ".join(f"{v!s:>14}" for v in r))


def main() -> None:
    with session_scope() as s:
        show(s, "row counts", COUNTS)
        show(s, "reporting currency (NOT always the quote currency)", CURRENCIES)
        show(s, "elements extracted per document", ELEMENTS)
        show(s, "sample extracted tables (provenance intact)", SAMPLE_TABLE)
        show(s, "Total Revenue FY26 vs FY25 (crore, in reporting ccy)", REVENUE)
        show(s, "latest close, sample", PRICE_JOIN)


if __name__ == "__main__":
    main()

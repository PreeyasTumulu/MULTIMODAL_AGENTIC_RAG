from decimal import Decimal

import pandas as pd

from analyst.facts import infer_unit, melt_statement


def test_infer_unit_distinguishes_money_from_per_share_and_counts() -> None:
    assert infer_unit("Total Revenue") == "INR"
    assert infer_unit("Basic EPS") == "INR/share"
    assert infer_unit("Diluted EPS") == "INR/share"
    assert infer_unit("Ordinary Shares Number") == "shares"
    assert infer_unit("Tax Rate For Calcs") == "ratio"


def test_infer_unit_respects_reporting_currency() -> None:
    """INFY quotes in INR but reports in USD - regression guard."""
    assert infer_unit("Total Revenue", "USD") == "USD"
    assert infer_unit("Basic EPS", "USD") == "USD/share"
    assert infer_unit("Ordinary Shares Number", "USD") == "shares"
    assert infer_unit("Tax Rate For Calcs", "USD") == "ratio"


def test_melt_drops_nan_instead_of_writing_zero() -> None:
    df = pd.DataFrame(
        {
            pd.Timestamp("2025-03-31"): [100.0, None],
            pd.Timestamp("2024-03-31"): [90.0, 5.0],
        },
        index=["Total Revenue", "Basic EPS"],
    )
    rows = melt_statement(df, "TCS", "income_statement")
    assert len(rows) == 3
    assert not any(r.concept == "Basic EPS" and r.period_end.year == 2025 for r in rows)
    rev = next(r for r in rows if r.concept == "Total Revenue" and r.period_end.year == 2025)
    assert rev.value == Decimal("100.0")
    assert rev.unit == "INR"


def test_melt_handles_missing_and_empty_frames() -> None:
    assert melt_statement(None, "TCS", "income_statement") == []
    assert melt_statement(pd.DataFrame(), "TCS", "income_statement") == []

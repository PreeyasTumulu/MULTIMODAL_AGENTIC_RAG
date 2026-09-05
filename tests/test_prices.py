import pandas as pd

from analyst.prices import drop_partial_bar, to_rows


def _frame() -> pd.DataFrame:
    """Second row mimics a session still in progress: Close is NaN."""
    return pd.DataFrame(
        {
            "Open": [100.0, 102.0],
            "High": [105.0, 106.0],
            "Low": [99.0, 101.0],
            "Close": [104.0, None],
            "Adj Close": [104.0, None],
            "Volume": [1000, 500],
        },
        index=pd.to_datetime(["2026-09-03", "2026-09-04"]),
    )


def test_partial_bar_is_dropped() -> None:
    df = drop_partial_bar(_frame())
    assert len(df) == 1
    assert str(df.index[-1].date()) == "2026-09-03"


def test_to_rows_after_dropping_partial_bar_has_no_nan_close() -> None:
    rows = to_rows(drop_partial_bar(_frame()), "TCS")
    assert len(rows) == 1
    assert float(rows[0].close) == 104.0
    assert rows[0].volume == 1000

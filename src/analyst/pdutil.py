"""Small pandas helpers."""

from datetime import date

import pandas as pd


def index_to_date(label: object) -> date:
    """Convert a DataFrame index/column label to a plain date.

    pandas-stubs types index labels as `Hashable`, but yfinance statement frames
    are indexed by `Timestamp`. Round-tripping through `str` keeps this honest
    for the type checker and works for `Timestamp`, `datetime` and ISO strings
    alike, instead of asserting a type we have not verified.
    """
    return pd.Timestamp(str(label)).date()

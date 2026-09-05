"""Indian number formatting, and how to find an oracle value inside a report.

This is the load-bearing piece of the evaluation strategy.

The oracle stores absolute rupees (Reliance FY25 revenue = 9,646,930,000,000).
An annual report never prints that. It prints "9,64,693" under a heading that
says "Rs in crore", or "96,469.3" under "Rs in ten million", or "964,693" if the
typesetter used Western grouping. A naive `str(value) in text` finds nothing and
you conclude - wrongly - that retrieval failed.

So we generate every plausible printed form of a value and look for any of them.
A value we cannot locate is DISCARDED from the benchmark rather than counted as
a failure: absence of a match means our formatting guess was wrong or the vendor
figure disagrees with the filing, and neither is the retriever's fault.
"""

import re
from decimal import Decimal

# Indian financial reports scale by these; the heading says which one.
SCALES: dict[str, Decimal] = {
    "absolute": Decimal(1),
    "thousand": Decimal(10**3),
    "lakh": Decimal(10**5),
    "million": Decimal(10**6),
    "crore": Decimal(10**7),
    "billion": Decimal(10**9),
}

# Printed figures below this are too short to match uniquely: "12" appears on
# every page of a 300-page report and would produce false positives.
MIN_DIGITS = 4


def indian_group(digits: str) -> str:
    """12345678 -> 1,23,45,678 (last 3, then 2 at a time)."""
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    parts: list[str] = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join([*parts, tail])


def western_group(digits: str) -> str:
    """12345678 -> 12,345,678."""
    return f"{int(digits):,}"


def candidate_strings(value: Decimal) -> set[str]:
    """Every plausible way this value could be printed in an Indian report."""
    out: set[str] = set()
    magnitude = abs(value)
    if magnitude == 0:
        return out

    for scale in SCALES.values():
        scaled = magnitude / scale
        if scaled < 1:
            continue
        for places in (0, 1, 2):
            q = scaled.quantize(Decimal(1) if places == 0 else Decimal(f"0.{'0' * places}"))
            whole, _, frac = str(q).partition(".")
            if len(whole) < MIN_DIGITS:
                continue
            for grouped in (whole, western_group(whole), indian_group(whole)):
                out.add(f"{grouped}.{frac}" if frac else grouped)
    return out


# NBSP and thin space are written as numeric escapes: they are invisible in
# source, and PDF text extraction emits both inside numbers.
_WS = re.compile(r"[\s\u00a0\u2009]+")


def normalise(text: str) -> str:
    """Collapse whitespace so a figure split across a line break still matches."""
    return _WS.sub("", text)


def find_value(value: Decimal, text: str) -> str | None:
    """Return the matched printed form, or None.

    Whitespace is stripped from both sides because PDF text extraction routinely
    inserts spaces inside a number ("9,64, 693").
    """
    haystack = normalise(text)
    for cand in sorted(candidate_strings(value), key=len, reverse=True):
        if normalise(cand) in haystack:
            return cand
    return None

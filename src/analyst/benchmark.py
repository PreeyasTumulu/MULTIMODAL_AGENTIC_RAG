"""Generate the evaluation benchmark from the oracle.

The whole reason this domain was chosen. Reported financials give us values we
know to be true; locating each one inside its own annual report yields an
auto-labelled (question, answer, source page) triple. No hand-written questions,
and no LLM call anywhere in this file.

**The false-positive fix.** ADR-004 recorded a raw oracle match rate of 47-57%
and flagged it as a ceiling rather than a score, because a 4-digit figure can
collide by chance somewhere in 300 pages. The fix is proximity: a number is
accepted only when a label for its concept appears in the SAME extracted
element. Elements are already page-level blocks and whole tables, so "same
element" is a natural and strict window - a revenue figure must be sitting in
the revenue row, not merely somewhere in the document.

That trades coverage for trustworthiness, which is the correct direction. A
benchmark with 120 questions you can rely on beats one with 900 you cannot.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from analyst.numfmt import candidate_strings, find_value_tolerant, normalise

# Yahoo's taxonomy on the left, what an Indian annual report actually prints on
# the right. Only concepts listed here can produce a question: an unmapped
# concept has no reliable label to anchor against, and a question we cannot
# anchor is a question we should not ask.
CONCEPT_ALIASES: dict[str, tuple[str, ...]] = {
    "Total Revenue": (
        "total revenue", "revenue from operations", "total income",
        "revenue from contracts", "total revenue from operations",
    ),
    "Net Income": (
        "net income", "net profit", "profit for the year", "profit after tax",
        "profit for the period",
    ),
    "Gross Profit": ("gross profit",),
    "Operating Income": ("operating income", "operating profit", "profit from operations"),
    "Total Assets": ("total assets",),
    "Total Expenses": ("total expenses", "total expenditure"),
    "Operating Revenue": ("revenue from operations", "operating revenue"),
    "Cost Of Revenue": ("cost of revenue", "cost of materials", "cost of sales"),
    "Research And Development": ("research and development", "r&d expenses"),
    "Stockholders Equity": ("total equity", "shareholders' funds", "total shareholders"),
    "Retained Earnings": ("retained earnings", "reserves and surplus"),
    "Cash And Cash Equivalents": ("cash and cash equivalents",),
    "Inventory": ("inventories", "inventory"),
    "Total Debt": ("total debt", "total borrowings"),
    "EBITDA": ("ebitda",),
    "Basic EPS": ("basic earnings per share", "basic eps"),
    "Diluted EPS": ("diluted earnings per share", "diluted eps"),
}

QUESTION_TEMPLATES = {
    "Total Revenue": "What was {name}'s total revenue in FY{fy}?",
    "Net Income": "What was {name}'s net profit in FY{fy}?",
    "Gross Profit": "What was {name}'s gross profit in FY{fy}?",
    "Operating Income": "What was {name}'s operating profit in FY{fy}?",
    "Total Assets": "What were {name}'s total assets at the end of FY{fy}?",
    "Total Expenses": "What were {name}'s total expenses in FY{fy}?",
    "Operating Revenue": "What was {name}'s revenue from operations in FY{fy}?",
    "Cost Of Revenue": "What was {name}'s cost of revenue in FY{fy}?",
    "Research And Development": "How much did {name} spend on research and development in FY{fy}?",
    "Stockholders Equity": "What was {name}'s total equity at the end of FY{fy}?",
    "Retained Earnings": "What were {name}'s retained earnings at the end of FY{fy}?",
    "Cash And Cash Equivalents": (
        "How much cash and cash equivalents did {name} hold at the end of FY{fy}?"
    ),
    "Inventory": "What was the value of {name}'s inventories at the end of FY{fy}?",
    "Total Debt": "What was {name}'s total debt at the end of FY{fy}?",
    "EBITDA": "What was {name}'s EBITDA in FY{fy}?",
    "Basic EPS": "What was {name}'s basic earnings per share in FY{fy}?",
    "Diluted EPS": "What was {name}'s diluted earnings per share in FY{fy}?",
}

# Explicit, because deriving the noun by slicing the template on "'s " breaks on
# any template phrased differently ("How much did X spend on...").
CONCEPT_NOUNS: dict[str, str] = {
    "Total Revenue": "total revenue",
    "Net Income": "net profit",
    "Gross Profit": "gross profit",
    "Operating Income": "operating profit",
    "Total Assets": "total assets",
    "Total Expenses": "total expenses",
    "Operating Revenue": "revenue from operations",
    "Cost Of Revenue": "cost of revenue",
    "Research And Development": "research and development spend",
    "Stockholders Equity": "total equity",
    "Retained Earnings": "retained earnings",
    "Cash And Cash Equivalents": "cash and cash equivalents",
    "Inventory": "inventories",
    "Total Debt": "total debt",
    "EBITDA": "EBITDA",
    "Basic EPS": "basic earnings per share",
    "Diluted EPS": "diluted earnings per share",
}

CRORE = Decimal(10**7)
_ALNUM = re.compile(r"[^a-z0-9& ]+")


@dataclass
class ElementView:
    element_id: str
    page: int
    type: str
    text: str


class BenchmarkQuestion(BaseModel):
    model_config = ConfigDict(frozen=True)

    question_id: str
    question: str
    question_type: str
    ticker: str
    fiscal_year: int
    concept: str
    answer_value: str
    answer_display: str
    unit: str
    document_id: str
    expected_element_ids: list[str]
    expected_pages: list[int]
    matched_as: str
    match_kind: str
    evidence_type: str


def fy_window(fiscal_year: int) -> tuple[date, date]:
    """Date bounds for an Indian fiscal year end, as real `date` objects.

    Exists because passing an f-string here fails at runtime with
    `operator does not exist: date >= character varying` - psycopg does not
    coerce str to date. Made a function so the mistake is impossible to repeat.
    Widened to a window because a few filers report 31 March +/- a few days.
    """
    return date(fiscal_year, 3, 1), date(fiscal_year, 4, 30)


def label_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse spaces - for alias matching only."""
    return _ALNUM.sub(" ", text.lower()).replace("  ", " ")


def display(value: Decimal, unit: str) -> str:
    if unit in ("INR", "USD"):
        symbol = "Rs" if unit == "INR" else "$"
        return f"{symbol} {value / CRORE:,.0f} crore"
    if unit.endswith("/share"):
        return f"{unit.split('/')[0]} {value:,.2f} per share"
    return f"{value:,.2f} {unit}"


def locate(
    value: Decimal, concept: str, elements: Sequence[ElementView]
) -> tuple[ElementView, str, str] | None:
    """Find `value` in an element that also carries a label for `concept`.

    Returns (element, printed form, match kind) or None.

    Two passes, strongest first:
      1. **exact**    - the value appears verbatim in some printed form
      2. **tolerant** - a number within 0.5% appears, absorbing the difference
                        between the vendor's figure and the filed one

    Both passes require an alias in the SAME element, so tolerance never opens
    the door to a coincidental number elsewhere on the page.
    """
    aliases = CONCEPT_ALIASES.get(concept)
    if not aliases:
        return None

    labelled = [el for el in elements if any(a in label_text(el.text) for a in aliases)]
    if not labelled:
        return None

    # Pass 1: exact. Longest candidates first so "5,20,412.5" wins over "20,412".
    cands = sorted((normalise(c) for c in candidate_strings(value)), key=len, reverse=True)
    for el in labelled:
        haystack = normalise(el.text)
        for cand in cands:
            if cand in haystack:
                return el, cand, "exact"

    # Pass 2: tolerant. Keep the closest match across all labelled elements.
    best: tuple[ElementView, str, Decimal] | None = None
    for el in labelled:
        hit = find_value_tolerant(value, el.text)
        if hit is None:
            continue
        token, error = hit
        if best is None or error < best[2]:
            best = (el, token, error)
    if best is not None:
        return best[0], best[1], "tolerant"
    return None


def build_questions(
    ticker: str,
    company_name: str,
    fiscal_year: int,
    document_id: str,
    facts: Sequence[tuple[str, Decimal, str]],
    elements: Sequence[ElementView],
) -> list[BenchmarkQuestion]:
    """One document's worth of value-lookup questions."""
    out: list[BenchmarkQuestion] = []
    for concept, value, unit in facts:
        template = QUESTION_TEMPLATES.get(concept)
        if template is None:
            continue
        hit = locate(value, concept, elements)
        if hit is None:
            continue
        el, matched, kind = hit
        out.append(
            BenchmarkQuestion(
                question_id=f"{ticker}-FY{fiscal_year}-{concept.replace(' ', '')}",
                question=template.format(name=company_name, fy=fiscal_year),
                question_type="value_lookup",
                ticker=ticker,
                fiscal_year=fiscal_year,
                concept=concept,
                answer_value=str(value),
                answer_display=display(value, unit),
                unit=unit,
                document_id=document_id,
                expected_element_ids=[el.element_id],
                expected_pages=[el.page],
                matched_as=matched,
                match_kind=kind,
                evidence_type=el.type,
            )
        )
    return out


def build_growth_questions(
    ticker: str,
    company_name: str,
    lookups: Sequence[BenchmarkQuestion],
) -> list[BenchmarkQuestion]:
    """Multi-hop: the same concept located in two different fiscal years.

    Both years must already be anchored, so a growth question can never be
    less trustworthy than the lookups it is built from.
    """
    by_concept: dict[str, list[BenchmarkQuestion]] = {}
    for q in lookups:
        by_concept.setdefault(q.concept, []).append(q)

    out: list[BenchmarkQuestion] = []
    for concept, qs in by_concept.items():
        if len(qs) < 2:
            continue
        older, newer = sorted(qs, key=lambda q: q.fiscal_year)[-2:]
        a, b = Decimal(older.answer_value), Decimal(newer.answer_value)
        if a == 0:
            continue
        pct = (b - a) / a * 100
        noun = CONCEPT_NOUNS[concept]
        out.append(
            BenchmarkQuestion(
                question_id=f"{ticker}-FY{older.fiscal_year}to{newer.fiscal_year}-"
                f"{concept.replace(' ', '')}-growth",
                question=(
                    f"By what percentage did {company_name}'s {noun} change "
                    f"from FY{older.fiscal_year} to FY{newer.fiscal_year}?"
                ),
                question_type="growth",
                ticker=ticker,
                fiscal_year=newer.fiscal_year,
                concept=concept,
                answer_value=f"{pct:.2f}",
                answer_display=f"{pct:+.1f}%",
                unit="percent",
                document_id=newer.document_id,
                expected_element_ids=[*older.expected_element_ids, *newer.expected_element_ids],
                expected_pages=[*older.expected_pages, *newer.expected_pages],
                matched_as=f"{older.matched_as} -> {newer.matched_as}",
                match_kind=(
                    "exact" if older.match_kind == newer.match_kind == "exact" else "tolerant"
                ),
                evidence_type="multi_document",
            )
        )
    return out

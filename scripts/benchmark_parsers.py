"""Benchmark PDF parsers on the task we actually care about.

Most parser comparisons measure characters extracted per second. That is the
wrong metric: a parser that extracts a lot of text but mangles the digits inside
financial tables is worse than useless here.

So the headline metric is ORACLE RECALL - of the financial facts we already know
to be true for this company and fiscal year, what fraction can be located in the
text this parser produced? That is a direct predictor of how many benchmark
questions Day 3 will be able to generate, and it is measurable without a single
LLM call.

    uv run python scripts/benchmark_parsers.py
    uv run python scripts/benchmark_parsers.py --pages 60   # speed-only subset
"""

import argparse
import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from analyst.db import session_scope
from analyst.logging import configure_logging, get_logger
from analyst.models import Document, Fact
from analyst.numfmt import candidate_strings, normalise

log = get_logger("benchmark_parsers")

# Below this, a printed figure is short enough to collide by chance.
MIN_ABS_VALUE = Decimal(10**7)


@dataclass
class ParseResult:
    parser: str
    pages: int
    seconds: float
    chars: int
    page_texts: list[str]


def parse_pymupdf(path: Path, max_pages: int | None) -> ParseResult:
    import pymupdf

    t0 = time.perf_counter()
    doc = pymupdf.open(path)
    n = doc.page_count if max_pages is None else min(doc.page_count, max_pages)
    texts = [doc[i].get_text() for i in range(n)]
    doc.close()
    return ParseResult("pymupdf", n, time.perf_counter() - t0, sum(map(len, texts)), texts)


def parse_pdfplumber(path: Path, max_pages: int | None) -> ParseResult:
    import pdfplumber

    t0 = time.perf_counter()
    texts: list[str] = []
    with pdfplumber.open(path) as pdf:
        n = len(pdf.pages) if max_pages is None else min(len(pdf.pages), max_pages)
        for i in range(n):
            texts.append(pdf.pages[i].extract_text() or "")
    return ParseResult("pdfplumber", n, time.perf_counter() - t0, sum(map(len, texts)), texts)


PARSERS: dict[str, Callable[[Path, int | None], ParseResult]] = {
    "pymupdf": parse_pymupdf,
    "pdfplumber": parse_pdfplumber,
}


def oracle_recall(
    res: ParseResult, facts: list[tuple[str, Decimal]]
) -> tuple[int, int, dict[str, int]]:
    """Two-phase search: reject against the whole document, then locate the page.

    Searching every fact against every page directly is O(facts x pages x
    candidates) and needlessly slow; almost all facts are absent, and a single
    concatenated haystack rejects those in one pass.
    """
    whole = normalise("\n".join(res.page_texts))
    norm_pages = [normalise(t) for t in res.page_texts]
    found = 0
    located: dict[str, int] = {}

    for concept, value in facts:
        cands = [normalise(c) for c in candidate_strings(value)]
        hit = next((c for c in cands if c in whole), None)
        if hit is None:
            continue
        found += 1
        for i, page in enumerate(norm_pages):
            if hit in page:
                located[concept] = i + 1
                break
    return found, len(facts), located


def load_facts(ticker: str, fiscal_year: int) -> list[tuple[str, Decimal]]:
    with session_scope() as s:
        rows = s.execute(
            select(Fact.concept, Fact.value)
            .where(Fact.ticker == ticker)
            .where(Fact.unit.in_(("INR", "USD")))
            .order_by(Fact.concept)
        ).all()
    seen: set[str] = set()
    out: list[tuple[str, Decimal]] = []
    for concept, value in rows:
        if concept in seen or abs(value) < MIN_ABS_VALUE:
            continue
        seen.add(concept)
        out.append((concept, value))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=None, help="cap pages (speed comparison)")
    ap.add_argument("--parsers", default="pymupdf,pdfplumber")
    args = ap.parse_args()
    configure_logging()

    with session_scope() as s:
        targets = [
            (d.ticker, d.fiscal_year, Path(d.local_path))
            for d in s.execute(select(Document).order_by(Document.ticker)).scalars().all()
        ]

    header = (
        f"{'document':<34} {'parser':<12} {'pages':>5} {'sec':>7} "
        f"{'kchars':>7} {'oracle recall':>16}"
    )
    print("\n" + header)
    print("-" * len(header))

    for ticker, fy, path in targets:
        facts = load_facts(ticker, fy)
        for name in args.parsers.split(","):
            res = PARSERS[name](path, args.pages)
            found, total, located = oracle_recall(res, facts)
            pct = f"{100 * found / total:.0f}%" if total else "n/a"
            print(
                f"{path.stem:<34} {name:<12} {res.pages:>5} {res.seconds:>7.1f} "
                f"{res.chars / 1000:>7.0f} {f'{found}/{total} ({pct})':>16}"
            )
            if located and name == "pymupdf":
                sample = sorted(located.items(), key=lambda kv: kv[1])[:3]
                for concept, page in sample:
                    print(f"{'':>36}  -> {concept[:40]:<40} p.{page}")


if __name__ == "__main__":
    main()

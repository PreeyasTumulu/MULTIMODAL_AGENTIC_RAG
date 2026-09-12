"""The agent with a scripted LLM and fake evidence - no model, no Qdrant, no Postgres.

Each test pins one ownership rule: the LLM points, Python verifies and computes,
and anything that cannot be verified is refused rather than shown.
"""

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal

import pytest

from analyst.agent import Route, Tools, ask
from analyst.llm import Reply
from analyst.tools import Company, PriceSummary
from analyst.vectorstore import Hit

CORPUS = {
    "SUNPHARMA": Company("SUNPHARMA", "Sun Pharmaceutical Industries", (2024, 2025)),
    "TCS": Company("TCS", "Tata Consultancy Services", ()),
}
LOOKUP = {"intent": "value_lookup", "tickers": ["SUNPHARMA"], "fiscal_years": [2025],
          "concept": "Net Income"}
Q = "What was Sun Pharma's net profit in FY2025?"


def hit(text: str, fy: int = 2025, eid: str = "") -> Hit:
    eid = eid or f"E{fy}"
    return Hit(chunk_id=f"{eid}#0", element_ids=[eid], document_id=f"SUN-FY{fy}",
               ticker="SUNPHARMA", fiscal_year=fy, pages=[7], type="table", text=text, score=0.9)


def said(figure: str, unit: str | None = None) -> dict[str, object]:
    """An extractor reply naming `figure`, citing evidence block 1."""
    return {"answer": figure, "value": figure, "unit": unit, "sources": [1]}


class Script:
    """Replays JSON replies in order, the way the real client returns them."""

    def __init__(self, *replies: Mapping[str, object]) -> None:
        self.replies = list(replies)

    def complete(self, system: str, user: str) -> Reply:
        return Reply(dict(self.replies.pop(0)), 10, 5, 1.0, cached=False)


def tools(hits: Sequence[Hit] = (), prices: PriceSummary | None = None) -> Tools:
    def search(text: str, ticker: str | None, fy: int | None, concept: str | None,
               limit: int) -> list[Hit]:
        return [h for h in hits if fy in (None, h.fiscal_year)]

    return Tools(CORPUS, search, lambda ticker, start, end: prices)


def test_a_figure_printed_in_the_cited_evidence_is_answered() -> None:
    llm = Script(LOOKUP, {"answer": "Net profit was 109,290 million.", "value": "109,290",
                          "unit": "Million", "sources": [1]})
    a = ask(Q, llm, tools([hit("Net profit for the year (Rs Million) | 109,290 | 95,764")]))
    assert (a.abstained, a.values, a.llm_calls) == (False, ["109,290"], 2)
    assert a.citations[0].element_ids == ["E2025"] and "unit" not in str(a.answer)


@pytest.mark.parametrize("bad", [
    {"answer": "Net profit was 120,000 million.", "value": "120,000", "sources": [1]},  # invented
    {"answer": "Net profit was 109,290 million.", "value": "109,290", "sources": [7]},  # unseen
])
def test_an_unverifiable_figure_is_refused_after_one_wider_look(bad: dict[str, object]) -> None:
    a = ask(Q, Script(LOOKUP, bad, bad), tools([hit("Net profit for the year | 109,290 | 95,764")]))
    assert (a.abstained, a.abstain_reason, a.answer, a.values) == (True, "not_grounded", None, [])
    assert a.llm_calls == 3  # route, extract, ONE retry - then stop


def test_a_figure_left_in_the_sentence_is_still_verified_and_cited_precisely() -> None:
    """llama3.2 wrote the figure into `answer` and left `value` null - a slip, not a lie."""
    reply = {"answer": "It was Rs 1,09,290 million in FY2025.", "value": None, "sources": [1, 2]}
    a = ask(Q, Script(LOOKUP, reply), tools([hit("Net profit for the year | 109,290 | 95,764"),
                                             hit("Employees 5,555", eid="OTHER")]))
    assert a.values == ["109,290"]
    assert [c.element_ids for c in a.citations] == [["E2025"]]  # only the block printing it
    assert str(a.answer).endswith("does not state the unit)")  # no unit printed: said so


GROWTH = {"intent": "growth", "tickers": ["SUNPHARMA"], "fiscal_years": [2024, 2025],
          "concept": "Net Income"}


def test_growth_is_computed_in_python_converting_units_the_evidence_prints() -> None:
    llm = Script(GROWTH, said("95,764", "Rs Million"), said("10,929.0", "Rs crore"))
    a = ask("How did it change?", llm, tools([hit("Net profit (Rs Million) 95,764", 2024),
                                              hit("Net profit (Rs crore) 10,929.0", 2025)]))
    # 95,764 million = 9,576.4 crore -> 10,929.0 crore is +14.12%
    assert [c.result for c in a.computations] == ["14.12"] and a.values == ["95,764", "10,929.0"]


def test_growth_ignores_a_unit_the_evidence_does_not_print() -> None:
    """Regression: llama3.2 called two ICICI Bank figures "million" and "crore" -> +1,129.6%."""
    llm = Script(GROWTH, said("442,563,735", "million"), said("510,291,955", "crore"))
    a = ask("How did it change?", llm, tools([hit("Profit for the year 442,563,735", 2024),
                                              hit("Profit for the year 510,291,955", 2025)]))
    assert [c.result for c in a.computations] == ["15.30"]


def test_a_company_without_a_filing_is_refused_before_any_extraction() -> None:
    a = ask("What was TCS's net profit in FY2025?", Script({**LOOKUP, "tickers": ["TCS"]}), tools())
    assert (a.abstained, a.abstain_reason, a.llm_calls) == (True, "out_of_corpus", 1)


def test_advice_is_unsupported() -> None:
    a = ask("Should I buy Sun Pharma?", Script({"intent": "unsupported", "tickers": ["SUNPHARMA"]}),
            tools())
    assert (a.abstain_reason, a.llm_calls) == ("unsupported_question", 1)


def test_router_output_is_checked_against_the_corpus() -> None:
    """What the local models actually returned: a NAME for a ticker, junk in lists."""
    messy = {"intent": "Value Lookup", "tickers": ["Sun Pharmaceutical Industries", "NOPE"],
             "fiscal_years": ["FY2025", None], "concept": "Profit"}
    a = ask(Q, Script(messy, {"answer": None}, {"answer": None}), tools([hit("x")]))
    assert a.route == Route(intent="value_lookup", tickers=["SUNPHARMA"], fiscal_years=[2025])


def test_a_price_change_needs_no_extraction_call() -> None:
    """Also the router regression: llama3.2 named no ticker for "How has Reliance Industries
    traded?", so the company is found in the question instead."""
    p = PriceSummary("SUNPHARMA", date(2025, 9, 4), date(2026, 9, 4), Decimal(1600),
                     Decimal(1800), Decimal(1900), Decimal(1500), 247)
    a = ask("How has Sun Pharmaceutical Industries traded?",
            Script({"intent": "price", "tickers": []}), tools(prices=p))
    assert ([c.result for c in a.computations], a.llm_calls) == (["12.50"], 1)

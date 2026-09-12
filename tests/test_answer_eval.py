"""Grading against the oracle - plain comparisons, no LLM judge."""

from analyst.agent import Answer, Computation
from analyst.answer_eval import Unanswerable, grade, summarise, unanswerable
from analyst.benchmark import BenchmarkQuestion
from analyst.tools import Company


def question(kind: str = "value_lookup", value: str = "673508300000") -> BenchmarkQuestion:
    return BenchmarkQuestion(
        question_id="q", question="?", question_type=kind, ticker="HDFCBANK", fiscal_year=2025,
        concept="Net Income", answer_value=value, answer_display="", unit="INR",
        document_id="d", expected_element_ids=["E"], expected_pages=[52], matched_as="",
        match_kind="exact", evidence_type="table",
    )


def growth(result: str) -> Answer:
    return Answer(question="?", computations=[Computation(expression="", result=result,
                                                          unit="percent")])


def test_a_figure_is_right_at_whatever_scale_the_filing_printed() -> None:
    """HDFC Bank FY2025 net profit: Rs 67,351 crore at the vendor, 67,347.4 in the filing."""
    assert grade(question(), Answer(question="?", values=["67,347.4"])).correct
    assert not grade(question(), Answer(question="?", values=["60,347.4"])).correct


def test_growth_is_right_within_one_point() -> None:
    assert grade(question("growth", "15.30"), growth("14.51")).correct
    assert not grade(question("growth", "15.30"), growth("13.90")).correct


def test_refusing_is_wrong_when_answerable_and_right_when_not() -> None:
    refused = Answer(question="?", abstained=True, abstain_reason="out_of_corpus")
    assert not grade(question(), refused).correct
    assert grade(Unanswerable(question_id="u", question="?", expected="out_of_corpus"),
                 refused).correct


def test_unanswerable_covers_missing_filings_future_years_and_advice() -> None:
    qs = unanswerable({"TCS": Company("TCS", "Tata Consultancy Services", ()),
                       "SUN": Company("SUN", "Sun Pharmaceutical Industries", (2024, 2025))})
    assert [u.expected for u in qs] == ["out_of_corpus", "out_of_corpus", "unsupported_question"]
    assert "FY2031" in qs[1].question


def test_a_confident_wrong_answer_is_counted_apart_from_a_refusal() -> None:
    m = summarise([grade(question(), Answer(question="?", values=["1,111.1"])),
                   grade(question(), Answer(question="?", abstained=True))])
    assert (m["accuracy"], m["wrong_answer"], m["false_refusal"]) == (0.0, 0.5, 0.5)

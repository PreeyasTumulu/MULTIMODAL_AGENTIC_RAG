from decimal import Decimal

from analyst.benchmark import ElementView, build_questions, label_text, locate
from analyst.numfmt import find_value_tolerant, parse_printed


def _el(text: str, page: int = 1, etype: str = "table") -> ElementView:
    return ElementView(element_id=f"DOC:p{page:04d}:e0000", page=page, type=etype, text=text)


# --- numeric parsing -------------------------------------------------------


def test_parse_printed_ignores_grouping_style() -> None:
    assert parse_printed("9,64,693") == Decimal("964693")
    assert parse_printed("964,693") == Decimal("964693")
    assert parse_printed("964693.50") == Decimal("964693.50")


def test_parse_printed_rejects_short_numbers() -> None:
    """A 2-3 digit token collides by chance; it is not evidence."""
    assert parse_printed("42") is None
    assert parse_printed("999") is None


def test_tolerant_match_absorbs_vendor_rounding() -> None:
    """The real HDFCBANK case: vendor says 67,351 cr, the filing prints 67,347.36 cr."""
    vendor = Decimal("673510000000")
    hit = find_value_tolerant(vendor, "Profit for the year 67,347.36")
    assert hit is not None
    token, error = hit
    assert token == "67,347.36"
    assert error < Decimal("0.001")


def test_tolerant_match_rejects_a_genuinely_different_number() -> None:
    assert find_value_tolerant(Decimal("673510000000"), "Profit for the year 41,200.00") is None


def test_tolerant_match_picks_the_closest_not_the_first() -> None:
    hit = find_value_tolerant(Decimal("673510000000"), "67,600.00 and later 67,349.00")
    assert hit is not None
    assert hit[0] == "67,349.00"


# --- anchoring -------------------------------------------------------------


def test_locate_requires_the_label_in_the_same_element() -> None:
    """The false-positive fix: the number alone is not enough."""
    value = Decimal("520412500000")  # Rs 52,041 cr
    with_label = _el("Revenue from operations 520,412.5")
    number_only = _el("Some unrelated paragraph mentioning 520,412.5", page=9)

    assert locate(value, "Total Revenue", [number_only]) is None
    hit = locate(value, "Total Revenue", [number_only, with_label])
    assert hit is not None
    assert hit[0].page == 1
    assert hit[2] == "exact"


def test_locate_prefers_exact_over_tolerant() -> None:
    value = Decimal("673510000000")
    tolerant = _el("Profit for the year 67,347.36", page=2)
    exact = _el("Profit for the year 67,351", page=5)
    hit = locate(value, "Net Income", [tolerant, exact])
    assert hit is not None
    assert hit[2] == "exact"
    assert hit[0].page == 5


def test_unmapped_concept_produces_no_question() -> None:
    """No alias means no anchor, and an unanchored question must not be asked."""
    assert locate(Decimal("520412500000"), "Some Yahoo Concept", [_el("520,412.5")]) is None


def test_build_questions_carries_provenance() -> None:
    qs = build_questions(
        ticker="SUNPHARMA",
        company_name="Sun Pharmaceutical Industries",
        fiscal_year=2025,
        document_id="DOC",
        facts=[("Total Revenue", Decimal("520412500000"), "INR")],
        elements=[_el("Revenue from operations 520,412.5", page=259)],
    )
    assert len(qs) == 1
    q = qs[0]
    assert q.expected_pages == [259]
    assert q.expected_element_ids == ["DOC:p0259:e0000"]
    assert q.answer_display == "Rs 52,041 crore"
    assert q.question_type == "value_lookup"


def test_label_text_normalises_punctuation() -> None:
    assert "shareholders funds" in label_text("Shareholders' Funds:")

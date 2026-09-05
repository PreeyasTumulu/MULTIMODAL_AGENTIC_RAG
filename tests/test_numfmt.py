from decimal import Decimal

from analyst.numfmt import candidate_strings, find_value, indian_group, western_group


def test_indian_grouping() -> None:
    assert indian_group("12345678") == "1,23,45,678"
    assert indian_group("964693") == "9,64,693"
    assert indian_group("1000") == "1,000"
    assert indian_group("123") == "123"


def test_western_grouping() -> None:
    assert western_group("12345678") == "12,345,678"
    assert western_group("964693") == "964,693"


def test_reliance_revenue_is_findable_in_crore_indian_grouping() -> None:
    """The real case: oracle holds absolute rupees, the report prints crore."""
    revenue = Decimal("9646930000000")  # RELIANCE FY25, absolute INR
    page = "Total Revenue        9,64,693        8,99,041   (Rs in crore)"
    assert find_value(revenue, page) == "9,64,693"


def test_same_value_found_with_western_grouping() -> None:
    revenue = Decimal("9646930000000")
    assert find_value(revenue, "Revenue from operations 964,693") == "964,693"


def test_value_found_when_pdf_extraction_inserts_spaces() -> None:
    """PDF text extraction routinely splits a figure: '9,64, 693'."""
    revenue = Decimal("9646930000000")
    assert find_value(revenue, "Revenue 9,64, 693 crore") is not None


def test_short_numbers_are_not_candidates() -> None:
    """A 2-digit figure would match on every page and poison the benchmark."""
    cands = candidate_strings(Decimal("4200"))
    assert all(len(c.replace(",", "").split(".")[0]) >= 4 for c in cands)


def test_absent_value_returns_none() -> None:
    assert find_value(Decimal("9646930000000"), "no figures on this page at all") is None


def test_zero_has_no_candidates() -> None:
    assert candidate_strings(Decimal(0)) == set()

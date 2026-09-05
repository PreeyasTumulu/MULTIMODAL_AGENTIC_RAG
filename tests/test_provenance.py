from analyst.provenance import (
    Element,
    ElementType,
    SourceRef,
    make_document_id,
    make_element_id,
)


def test_document_id_is_deterministic() -> None:
    a = make_document_id("TCS", "annual_report", 2025, "deadbeefcafe")
    b = make_document_id("TCS", "annual_report", 2025, "deadbeefcafe")
    assert a == b == "TCS-annual_report-FY2025-deadbeef"


def test_element_id_sorts_in_document_order() -> None:
    doc = "TCS-annual_report-FY2025-deadbeef"
    ids = [make_element_id(doc, p, o) for p, o in [(10, 2), (2, 1), (10, 1)]]
    assert sorted(ids) == [
        make_element_id(doc, 2, 1),
        make_element_id(doc, 10, 1),
        make_element_id(doc, 10, 2),
    ]


def test_element_exposes_its_own_citation() -> None:
    el = Element(
        element_id="d:p0042:e0001",
        document_id="d",
        page=42,
        type=ElementType.TABLE,
        order=1,
        text="Revenue table",
        bbox=(0.0, 0.0, 100.0, 50.0),
    )
    assert el.source == SourceRef(
        document_id="d",
        page=42,
        element_id="d:p0042:e0001",
        bbox=(0.0, 0.0, 100.0, 50.0),
    )
    assert el.source.cite() == "d p.42"

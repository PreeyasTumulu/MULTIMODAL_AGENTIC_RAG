from analyst.chunking import (
    MAX_TABLE_CHARS,
    MAX_TABLE_ROWS,
    TARGET_CHARS,
    DocContext,
    SourceElement,
    budget,
    chunk_document,
)


def _el(
    seq: int,
    etype: str,
    text: str | None,
    page: int = 1,
    table: dict[str, object] | None = None,
) -> SourceElement:
    return SourceElement(
        element_id=f"DOC:p{page:04d}:e{seq:04d}",
        document_id="DOC",
        page=page,
        seq=seq,
        type=etype,
        text=text,
        table_json=table,
    )


def test_heading_is_prepended_to_the_text_beneath_it() -> None:
    """'Revenue grew 12%' is ambiguous without its section title."""
    chunks = chunk_document(
        [
            _el(0, "heading", "Speciality Segment"),
            _el(1, "text", "Revenue grew 12 percent year on year. " * 4),
        ],
        "SUNPHARMA",
        2025,
    )
    assert len(chunks) == 1
    assert chunks[0].text.startswith("Speciality Segment\n\n")
    assert chunks[0].heading == "Speciality Segment"


def test_a_new_heading_ends_the_previous_chunk() -> None:
    """Mixing two sections into one chunk makes the retriever cite the wrong one."""
    chunks = chunk_document(
        [
            _el(0, "heading", "Segment A"),
            _el(1, "text", "Alpha content here. " * 6),
            _el(2, "heading", "Segment B"),
            _el(3, "text", "Beta content here. " * 6),
        ],
        "X",
        2025,
    )
    assert len(chunks) == 2
    assert chunks[0].heading == "Segment A"
    assert chunks[1].heading == "Segment B"
    assert "Beta" not in chunks[0].text
    assert "Alpha" not in chunks[1].text


def test_table_becomes_its_own_chunk_and_keeps_its_header() -> None:
    table = {
        "header": ["Particulars", "FY2025", "FY2024"],
        "rows": [["Revenue", "520,412.5", "438,860.1"]],
        "n_rows": 1,
    }
    chunks = chunk_document(
        [_el(0, "heading", "Profit and Loss"), _el(1, "table", "ignored", table=table)],
        "SUNPHARMA",
        2025,
    )
    assert len(chunks) == 1
    assert chunks[0].type == "table"
    assert "Particulars | FY2025 | FY2024" in chunks[0].text
    assert "520,412.5" in chunks[0].text


def test_large_table_is_split_but_every_slice_repeats_the_header() -> None:
    """A slice without its header is just digits - noise to the embedder."""
    rows = [[f"Line item {i}", f"{i}000", f"{i}500"] for i in range(MAX_TABLE_ROWS * 2 + 3)]
    table = {"header": ["Particulars", "FY2025", "FY2024"], "rows": rows, "n_rows": len(rows)}
    chunks = chunk_document([_el(0, "table", "x", table=table)], "X", 2025)
    assert len(chunks) > 1
    assert all("Particulars | FY2025 | FY2024" in c.text for c in chunks)
    assert len({c.chunk_id for c in chunks}) == len(chunks)


def test_no_table_chunk_exceeds_the_encoder_budget() -> None:
    """Regression: the largest table chunk was 6,643 chars and was being
    silently truncated by the encoder, so most of it was never embedded."""
    wide = [[f"Very long line item description number {i}", f"{i}0,000.00", f"{i}5,000.00"]
            for i in range(200)]
    table = {"header": ["Particulars", "FY2025", "FY2024"], "rows": wide, "n_rows": len(wide)}
    chunks = chunk_document([_el(0, "table", "x", table=table)], "X", 2025)
    assert chunks
    assert max(len(c.text) for c in chunks) <= MAX_TABLE_CHARS + 120


def test_long_text_is_split_near_the_target_size() -> None:
    paras = [_el(i, "text", "word " * 60) for i in range(20)]
    chunks = chunk_document(paras, "X", 2025)
    assert len(chunks) > 1
    # Allow one paragraph of overshoot: a paragraph is never cut mid-way.
    assert all(len(c.text) < TARGET_CHARS * 2 for c in chunks)


def test_every_chunk_keeps_the_element_ids_it_came_from() -> None:
    """Without this link, retrieval cannot produce a citation."""
    chunks = chunk_document(
        [_el(0, "heading", "H"), _el(1, "text", "Body text here. " * 8)], "X", 2025
    )
    assert chunks[0].element_ids == ["DOC:p0001:e0001"]
    assert chunks[0].pages == [1]
    assert chunks[0].page == 1


def test_figures_are_skipped_until_they_have_a_description() -> None:
    chunks = chunk_document([_el(0, "figure", None)], "X", 2025)
    assert chunks == []


def test_empty_table_json_does_not_crash() -> None:
    chunks = chunk_document([_el(0, "table", "fallback text " * 10, table={})], "X", 2025)
    assert len(chunks) == 1
    assert chunks[0].type == "table"


# --- ADR-008: contextual prefixes, heading hygiene, and the encoder budget ---


def _ctx() -> DocContext:
    return DocContext(ticker="SUNPHARMA", company="Sun Pharmaceutical Industries",
                      fiscal_year=2024)


def test_context_is_embedded_but_the_citation_text_stays_verbatim() -> None:
    """The prefix helps the encoder; it must not end up quoted as the document."""
    chunks = chunk_document(
        [_el(0, "heading", "Revenue"), _el(1, "text", "Some body content here. " * 6)],
        "SUNPHARMA", 2024, context=_ctx(),
    )
    c = chunks[0]
    assert "Sun Pharmaceutical Industries" in c.embed_text
    assert "year ended March 31, 2024" in c.embed_text
    assert "Sun Pharmaceutical Industries" not in c.text
    assert c.embed_text.endswith(c.text)


def test_no_context_reproduces_the_baseline_exactly() -> None:
    """The A/B arm: without a context the chunk is what it was before ADR-008."""
    els = [_el(0, "heading", "Revenue"), _el(1, "text", "Body content here. " * 6)]
    plain = chunk_document(els, "X", 2025)
    assert plain[0].context == ""
    assert plain[0].embed_text == plain[0].text


def test_page_furniture_headings_are_dropped() -> None:
    """'226 / Statutory Reports / Corporate Overview' is a running page band,
    printed identically on every page - it cannot tell two chunks apart."""
    chunks = chunk_document(
        [
            _el(0, "heading", "226\nStatutory Reports\nCorporate Overview\nFinancial Statements"),
            _el(1, "text", "Body content here. " * 6),
        ],
        "X", 2025,
    )
    assert chunks[0].heading is None
    assert "Statutory Reports" not in chunks[0].text


def test_a_real_section_title_survives_the_furniture_filter() -> None:
    chunks = chunk_document(
        [
            _el(0, "heading", "212\nConsolidated Balance Sheet\nStatutory Reports"),
            _el(1, "text", "Body content here. " * 6),
        ],
        "X", 2025,
    )
    assert chunks[0].heading == "Consolidated Balance Sheet"


def test_an_oversized_single_element_is_split_not_truncated() -> None:
    """Regression: the row packer was the only path that respected the budget,
    so one 5,116-char element became one chunk and the encoder read ~1,280."""
    huge = "\n".join(f"Sentence number {i} of a very long unbroken passage." for i in range(200))
    chunks = chunk_document([_el(0, "text", huge)], "X", 2025)
    assert len(chunks) > 1
    assert all(len(c.embed_text) <= budget("text") for c in chunks)


def test_an_unparsed_table_is_split_to_the_table_budget() -> None:
    """table_json with no rows fell through to raw text with no cap at all."""
    dump = "\n".join(f"Line item {i} | {i}0,000.00 | {i}5,000.00" for i in range(300))
    chunks = chunk_document([_el(0, "table", dump, table={})], "X", 2025)
    assert len(chunks) > 1
    assert all(len(c.embed_text) <= budget("table") for c in chunks)


def test_the_prefix_is_charged_against_the_chunk_budget() -> None:
    """Adding context must shrink the passage, not overflow the encoder."""
    rows = [[f"Line item {i}", f"{i}0,000.00", f"{i}5,000.00"] for i in range(200)]
    table = {"header": ["Particulars", "FY2024", "FY2023"], "rows": rows, "n_rows": len(rows)}
    with_ctx = chunk_document([_el(0, "table", "x", table=table)], "SUNPHARMA", 2024,
                              context=_ctx())
    assert all(len(c.embed_text) <= budget("table") for c in with_ctx)
    # Same content, more chunks, because each one now carries the prefix too.
    without = chunk_document([_el(0, "table", "x", table=table)], "SUNPHARMA", 2024)
    assert len(with_ctx) >= len(without)

"""PDF -> typed elements with provenance.

Uses PyMuPDF, chosen on measured evidence rather than reputation: on identical
60-page subsets of six real annual reports it extracted the same text as
pdfplumber (within 2%) and found the same oracle values (within 3 points) while
running 30-60x faster. See docs/adr/0004-pdf-parser.md.

Ordering rule: tables are located FIRST and their regions claimed, then text
blocks that fall inside a claimed region are skipped. Without that, every number
in every table appears twice - once as a table cell and once as loose text - and
the retriever ends up ranking the mangled copy above the structured one.
"""

from collections.abc import Iterator
from pathlib import Path

import pymupdf

from analyst.provenance import BBox, Element, ElementType, make_element_id

# A heading is set larger than the page's body text. Absolute point sizes vary
# far too much between annual report designers to hardcode.
HEADING_RATIO = 1.15
MIN_TEXT_CHARS = 2

# Ignore decorative rules, bullets and background textures.
MIN_FIGURE_PX = 120
MIN_FIGURE_AREA = 40_000


def _overlaps(a: BBox, b: BBox, tol: float = 2.0) -> bool:
    return not (
        a[2] < b[0] + tol or a[0] > b[2] - tol or a[3] < b[1] + tol or a[1] > b[3] - tol
    )


def _median_font_size(page: pymupdf.Page) -> float:
    sizes = [
        span["size"]
        for block in page.get_text("dict")["blocks"]
        if block.get("type") == 0
        for line in block["lines"]
        for span in line["spans"]
    ]
    if not sizes:
        return 0.0
    sizes.sort()
    return float(sizes[len(sizes) // 2])


def _extract_tables(
    page: pymupdf.Page, document_id: str, page_no: int, order: int
) -> tuple[list[Element], list[BBox], int]:
    elements: list[Element] = []
    claimed: list[BBox] = []
    try:
        finder = page.find_tables()
    except Exception:
        return elements, claimed, order

    for table in finder.tables:
        rows = [[("" if c is None else str(c)).strip() for c in row] for row in table.extract()]
        rows = [r for r in rows if any(c for c in r)]
        if len(rows) < 2:
            continue
        bbox = tuple(round(v, 2) for v in table.bbox)
        header, *body = rows
        elements.append(
            Element(
                element_id=make_element_id(document_id, page_no, order),
                document_id=document_id,
                page=page_no,
                type=ElementType.TABLE,
                order=order,
                # Linearised for embedding. The EXACT values stay in table_json;
                # nothing computes arithmetic off this string.
                text=" | ".join(header) + "\n" + "\n".join(" | ".join(r) for r in body),
                table_json={"header": header, "rows": body, "n_rows": len(body)},
                bbox=bbox,
            )
        )
        claimed.append(bbox)
        order += 1
    return elements, claimed, order


def _extract_text_blocks(
    page: pymupdf.Page,
    document_id: str,
    page_no: int,
    claimed: list[BBox],
    order: int,
) -> tuple[list[Element], int]:
    elements: list[Element] = []
    median = _median_font_size(page)

    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        bbox = tuple(round(v, 2) for v in block["bbox"])
        if any(_overlaps(bbox, c) for c in claimed):
            continue
        text = "\n".join(
            "".join(span["text"] for span in line["spans"]) for line in block["lines"]
        ).strip()
        if len(text) < MIN_TEXT_CHARS:
            continue
        sizes = [s["size"] for ln in block["lines"] for s in ln["spans"]]
        biggest = max(sizes) if sizes else 0.0
        is_heading = median > 0 and biggest >= median * HEADING_RATIO and len(text) < 200
        elements.append(
            Element(
                element_id=make_element_id(document_id, page_no, order),
                document_id=document_id,
                page=page_no,
                type=ElementType.HEADING if is_heading else ElementType.TEXT,
                order=order,
                text=text,
                bbox=bbox,
            )
        )
        order += 1
    return elements, order


def _extract_figures(
    page: pymupdf.Page,
    doc: pymupdf.Document,
    document_id: str,
    page_no: int,
    figure_dir: Path,
    order: int,
) -> tuple[list[Element], int]:
    elements: list[Element] = []
    for xref, *_ in page.get_images(full=True):
        try:
            info = doc.extract_image(xref)
        except Exception:
            continue
        pix_w, pix_h = info.get("width", 0), info.get("height", 0)
        if min(pix_w, pix_h) < MIN_FIGURE_PX or pix_w * pix_h < MIN_FIGURE_AREA:
            continue
        rects = page.get_image_rects(xref)
        bbox = tuple(round(v, 2) for v in rects[0]) if rects else None
        element_id = make_element_id(document_id, page_no, order)
        out = figure_dir / f"{element_id.replace(':', '_')}.{info['ext']}"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(info["image"])
        elements.append(
            Element(
                element_id=element_id,
                document_id=document_id,
                page=page_no,
                type=ElementType.FIGURE,
                order=order,
                # No caption yet. Day 7's vision pass fills text= with a
                # description; until then the figure is stored, not understood.
                image_path=str(out),
                bbox=bbox,
            )
        )
        order += 1
    return elements, order


def extract_elements(
    pdf_path: Path,
    document_id: str,
    figure_dir: Path,
    max_pages: int | None = None,
    with_figures: bool = True,
) -> Iterator[Element]:
    doc = pymupdf.open(pdf_path)
    try:
        n = doc.page_count if max_pages is None else min(doc.page_count, max_pages)
        for i in range(n):
            page = doc[i]
            page_no = i + 1
            order = 0
            tables, claimed, order = _extract_tables(page, document_id, page_no, order)
            yield from tables
            blocks, order = _extract_text_blocks(page, document_id, page_no, claimed, order)
            yield from blocks
            if with_figures:
                figures, order = _extract_figures(
                    page, doc, document_id, page_no, figure_dir, order
                )
                yield from figures
    finally:
        doc.close()


def page_count(pdf_path: Path) -> int:
    doc = pymupdf.open(pdf_path)
    try:
        return int(doc.page_count)
    finally:
        doc.close()

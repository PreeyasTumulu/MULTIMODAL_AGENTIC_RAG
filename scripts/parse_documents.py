"""Parse every downloaded PDF into typed elements with provenance.

Re-runnable: element IDs are deterministic, so re-parsing overwrites in place
rather than duplicating, and any index built on top stays valid.

    uv run python scripts/parse_documents.py
    uv run python scripts/parse_documents.py --pages 40 --no-figures   # quick pass
"""

import argparse
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from analyst.config import get_settings
from analyst.db import session_scope
from analyst.logging import configure_logging, get_logger
from analyst.models import Document, ElementRow
from analyst.parsing import extract_elements, page_count
from analyst.provenance import Element, ElementType

log = get_logger("parse_documents")
CHUNK = 1000


def to_row(el: Element) -> dict[str, object]:
    return {
        "element_id": el.element_id,
        "document_id": el.document_id,
        "page": el.page,
        "type": el.type.value,
        "seq": el.order,
        "text": el.text,
        "table_json": el.table_json,
        "image_path": el.image_path,
        "bbox": list(el.bbox) if el.bbox else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=None)
    ap.add_argument("--no-figures", action="store_true")
    args = ap.parse_args()

    configure_logging()
    settings = get_settings()
    figure_dir = settings.data_dir / "figures"

    with session_scope() as s:
        docs = [
            (d.document_id, d.ticker, d.fiscal_year, Path(d.local_path))
            for d in s.execute(select(Document).order_by(Document.ticker)).scalars().all()
        ]

    grand_total = 0
    for document_id, ticker, fy, path in docs:
        if not path.exists():
            log.warning("pdf.missing", doc=document_id)
            continue

        counts: dict[str, int] = {t.value: 0 for t in ElementType}
        batch: list[dict[str, object]] = []
        total = 0

        with session_scope() as s:
            for el in extract_elements(
                path,
                document_id,
                figure_dir / document_id,
                max_pages=args.pages,
                with_figures=not args.no_figures,
            ):
                counts[el.type.value] += 1
                batch.append(to_row(el))
                total += 1
                if len(batch) >= CHUNK:
                    _flush(s, batch)
                    batch = []
            if batch:
                _flush(s, batch)

            s.execute(
                update(Document)
                .where(Document.document_id == document_id)
                .values(n_pages=page_count(path))
            )

        grand_total += total
        log.info(
            "parsed",
            ticker=ticker,
            fy=fy,
            elements=total,
            text=counts["text"],
            heading=counts["heading"],
            table=counts["table"],
            figure=counts["figure"],
        )

    log.info("done", total_elements=grand_total)


def _flush(session: Session, rows: list[dict[str, object]]) -> None:
    stmt = insert(ElementRow).values(rows)
    session.execute(
        stmt.on_conflict_do_update(
            index_elements=[ElementRow.element_id],
            set_={
                "text": stmt.excluded.text,
                "table_json": stmt.excluded.table_json,
                "image_path": stmt.excluded.image_path,
                "bbox": stmt.excluded.bbox,
                "type": stmt.excluded.type,
            },
        )
    )


if __name__ == "__main__":
    main()

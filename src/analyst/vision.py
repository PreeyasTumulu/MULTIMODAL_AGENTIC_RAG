"""Figures -> searchable text: triage first, description second (ADR-010).

Measured before anything was built:

- the 418 images PyMuPDF extracted are mostly NOT charts - four samples were a
  plant photo, blank line art, a CSR photo and a QR code;
- charts drawn as vector paths are never extracted as images, and counting
  drawing paths does not find them either: the most path-heavy pages were
  leadership photo grids, icon-laden text pages and ruled statement tables.

So a local vision model first says what KIND of image it is, and only the kinds
that carry information are indexed. The model is not asked whether an image is
"informative": gemma3:4b called a QR code and a CSR photo informative, while its
`kind` label was right on all four samples.
"""

from collections import Counter
from pathlib import Path

import pymupdf
from sqlalchemy import select

from analyst.config import ROOT
from analyst.db import session_scope
from analyst.llm import LLM
from analyst.models import ElementRow, FigureDescription

KEEP = ("chart", "table", "infographic", "diagram")  # the kinds that get indexed
KINDS = (*KEEP, "photo", "logo", "qr_code", "decorative")
PROMPT = (
    "This image was extracted from an Indian listed company's annual report. Reply with a JSON "
    'object only: {"kind": one of ' + ", ".join(KINDS) + ', "description": at most 80 words - '
    "what it shows, with every label, year and number you can read, exactly as printed}"
)


def png(path: Path) -> bytes:
    """Every image as RGB PNG: Ollama cannot decode JPEG 2000 (50 of the 418 are .jpx),
    and PNG cannot hold CMYK, which print-ready report images often are."""
    pix = pymupdf.Pixmap(str(path))
    if pix.n - pix.alpha > 3:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    return bytes(pix.tobytes("png"))


def describe(llm: LLM, path: Path) -> tuple[str, str]:
    """(kind, description). An unrecognised kind counts as decorative: not indexed, not guessed."""
    r = llm.complete(PROMPT, "Classify and describe this figure.", images=[png(path)])
    kind = str(r.data.get("kind") or "").strip().lower().replace(" ", "_")
    return (kind if kind in KINDS else "decorative"), str(r.data.get("description") or "")


def describe_all(llm: LLM, limit: int | None = None) -> Counter[str]:
    """Describe every figure this model has not described yet.

    Resumable, with one commit per image: the full batch is roughly an hour on this
    GPU, and an interruption should cost one image, not the run.
    """
    with session_scope() as s:
        done = select(FigureDescription.element_id).where(FigureDescription.model == llm.name)
        todo = s.execute(select(ElementRow.element_id, ElementRow.image_path)
                         .where(ElementRow.type == "figure", ElementRow.element_id.not_in(done))
                         .order_by(ElementRow.element_id).limit(limit)).all()
    kinds: Counter[str] = Counter()
    for element_id, image_path in todo:
        # Stored as parsed on Windows ("data\figures\..."); normalised so Linux reads it too.
        kind, text = describe(llm, ROOT / str(image_path).replace("\\", "/"))
        with session_scope() as s:
            s.merge(FigureDescription(element_id=element_id, model=llm.name, kind=kind,
                                      description=text))
        kinds[kind] += 1
    return kinds

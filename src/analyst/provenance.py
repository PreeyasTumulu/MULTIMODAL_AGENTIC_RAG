"""Provenance contract.

THE most important 60 lines written on Day 1.

Every downstream subsystem - chunking, embedding, retrieval, reranking, the
citation renderer, the evaluation harness - depends on being able to answer
"where exactly did this come from?". That answer cannot be reconstructed after
parsing. If a document/page/element/bbox is not attached at extraction time it
is gone forever, and the explainability requirement collapses with it.

IDs are deterministic: re-parsing the same file yields identical IDs, so an
index can be rebuilt without invalidating an existing evaluation set.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

# (x0, y0, x1, y1) in PDF points, origin at top-left of the page.
BBox = tuple[float, float, float, float]


class ElementType(StrEnum):
    TEXT = "text"
    HEADING = "heading"
    TABLE = "table"
    FIGURE = "figure"
    CAPTION = "caption"


class SourceRef(BaseModel):
    """A citation target. This is what the UI renders and the evaluator checks."""

    model_config = ConfigDict(frozen=True)

    document_id: str
    page: int | None = Field(default=None, ge=1, description="1-indexed, as a human reads it")
    element_id: str | None = None
    bbox: BBox | None = None

    def cite(self) -> str:
        return f"{self.document_id}" + (f" p.{self.page}" if self.page else "")


class Element(BaseModel):
    """One extracted unit of a document, before chunking.

    `text` is the representation that gets embedded. For a TABLE it is a
    linearised summary; the exact values live in `table_json` so that arithmetic
    is done on numbers, never on a language model's reading of a number.
    """

    model_config = ConfigDict(frozen=True)

    element_id: str
    document_id: str
    page: int = Field(ge=1)
    type: ElementType
    order: int = Field(ge=0, description="reading order within the page")
    text: str | None = None
    table_json: dict[str, object] | None = None
    image_path: str | None = None
    bbox: BBox | None = None

    @property
    def source(self) -> SourceRef:
        return SourceRef(
            document_id=self.document_id,
            page=self.page,
            element_id=self.element_id,
            bbox=self.bbox,
        )


def make_document_id(ticker: str, doc_type: str, fiscal_year: int, sha256: str) -> str:
    """Human-readable AND stable. Readable IDs make eval failures debuggable."""
    return f"{ticker}-{doc_type}-FY{fiscal_year}-{sha256[:8]}"


def make_element_id(document_id: str, page: int, order: int) -> str:
    """Zero-padded so lexical sort equals document order."""
    return f"{document_id}:p{page:04d}:e{order:04d}"

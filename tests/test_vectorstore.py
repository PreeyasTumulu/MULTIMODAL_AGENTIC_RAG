"""Store helpers are pure functions, so they test without Qdrant running."""

import numpy as np
import pytest
from qdrant_client import models

from analyst.chunking import Chunk
from analyst.vectorstore import _filter, _payload, _sparse, _to_hit, point_id


class FakeSparse:
    """Shaped like fastembed's SparseEmbedding: numpy indices and values."""

    def __init__(self) -> None:
        self.indices = np.array([7, 42])
        self.values = np.array([1.5, 0.5])


def chunk() -> Chunk:
    return Chunk(
        chunk_id="c1", document_id="doc", ticker="RELIANCE", fiscal_year=2025,
        element_ids=["e1", "e2"], pages=[3, 4], type="table", heading="Revenue",
        text="Revenue from operations | 520,412.5",
    )


def test_point_id_is_deterministic_so_reindexing_overwrites() -> None:
    """The property that makes indexing idempotent instead of duplicating."""
    assert point_id("c1") == point_id("c1") != point_id("c2")


def test_payload_carries_the_pointer_not_the_answer() -> None:
    """The store returns element_ids; the figure itself is read from Postgres."""
    p = _payload(chunk())
    assert p["element_ids"] == ["e1", "e2"] and p["pages"] == [3, 4]


def test_hit_survives_a_payload_with_missing_keys() -> None:
    """An older point written before a field existed must not crash a search."""
    hit = _to_hit(models.ScoredPoint(id=1, version=0, score=0.5, payload={}))
    assert hit.element_ids == [] and hit.pages == [] and hit.score == 0.5


@pytest.mark.parametrize(
    ("ticker", "year", "n"), [(None, None, 0), ("INFY", None, 1), ("INFY", 2025, 2)]
)
def test_filter_builds_only_the_conditions_given(
    ticker: str | None, year: int | None, n: int
) -> None:
    f = _filter(ticker, year)
    must = f.must if f else None
    assert len(must) == n if isinstance(must, list) else n == 0


def test_no_filter_is_none_not_an_empty_filter() -> None:
    """An empty Filter is not the same as no filter to Qdrant."""
    assert _filter(None, None) is None


def test_sparse_converts_numpy_to_plain_lists() -> None:
    """qdrant-client will not serialise numpy arrays."""
    sv = _sparse(FakeSparse())  # type: ignore[arg-type]
    assert sv.indices == [7, 42] and sv.values == [1.5, 0.5]
    assert all(isinstance(i, int) for i in sv.indices)


def test_dense_and_hybrid_collections_never_collide() -> None:
    """Qdrant fixes the vector layout at creation, so they must be separate."""
    from analyst.retrievers import collection_for, hybrid_collection_for

    assert collection_for("elements", "bge-small") != hybrid_collection_for("elements", "bge-small")


def test_hybrid_rejects_an_unknown_filter_policy() -> None:
    from analyst.retrievers import hybrid

    with pytest.raises(ValueError, match="unknown filter policy"):
        hybrid(None, None, None, "ticker+yr")  # type: ignore[arg-type]

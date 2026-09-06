"""Retrievers - the things `evaluation.evaluate` scores.

One factory per strategy, each returning a `SearchFn`. Day 4's hybrid and
reranked retrievers land here beside `dense`, so swapping strategy never
touches the scoring code.

Kept out of `evaluation.py` deliberately: importing a retriever pulls in
fastembed and Qdrant, and the evaluation tests must run without either.
"""

from analyst.benchmark import BenchmarkQuestion
from analyst.config import Settings
from analyst.embedding import Embedder
from analyst.evaluation import SearchFn
from analyst.vectorstore import Hit, VectorStore


def collection_for(prefix: str, model: str) -> str:
    """One naming rule, so 07 (index) and 08 (evaluate) cannot disagree."""
    return f"{prefix}_{model}"


def open_store(settings: Settings, model: str) -> tuple[Embedder, VectorStore]:
    """Embedder plus its collection. Dim comes from the model, never typed twice."""
    embedder = Embedder(model)
    store = VectorStore(
        settings.qdrant_url, collection_for(settings.collection_prefix, model), embedder.dim
    )
    return embedder, store


def dense(embedder: Embedder, store: VectorStore, use_filters: bool = True) -> SearchFn:
    """Vector search, optionally narrowed by metadata before scoring."""

    def search(q: BenchmarkQuestion, limit: int) -> list[Hit]:
        return store.search(
            embedder.embed_query(q.question),
            limit=limit,
            ticker=q.ticker if use_filters else None,
            # A growth question spans two years, so a single-year filter would
            # exclude half its evidence by construction.
            fiscal_year=(
                q.fiscal_year if use_filters and q.question_type == "value_lookup" else None
            ),
        )

    return search

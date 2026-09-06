"""Retrievers - the things `evaluation.evaluate` scores.

One factory per strategy, each returning a `SearchFn`. Day 4's hybrid and
reranked retrievers land here beside `dense`, so swapping strategy never
touches the scoring code.

Kept out of `evaluation.py` deliberately: importing a retriever pulls in
fastembed and Qdrant, and the evaluation tests must run without either.
"""

from analyst.benchmark import BenchmarkQuestion
from analyst.config import Settings
from analyst.embedding import MODELS, Embedder, SparseEmbedder
from analyst.evaluation import SearchFn
from analyst.vectorstore import Hit, HybridStore, VectorStore


def collection_for(prefix: str, model: str) -> str:
    """One naming rule, so 07 (index) and 08 (evaluate) cannot disagree."""
    return f"{prefix}_{model}"


def store_for(settings: Settings, model: str) -> VectorStore:
    """Collection handle without loading the model - dim comes from the spec.

    Separate from `open_store` so "is this model indexed?" costs a REST call
    rather than a model download.
    """
    return VectorStore(
        settings.qdrant_url, collection_for(settings.collection_prefix, model), MODELS[model].dim
    )


def open_store(settings: Settings, model: str) -> tuple[Embedder, VectorStore]:
    """Embedder plus its collection, ready to index or query."""
    return Embedder(model), store_for(settings, model)


# What `dense` accepts. This is not a bool because the policies diverge at depth:
# measured on bge-small at depth 200, `none` scores 0.273 and `ticker+year` 0.432.
# `ticker` alone has not been measured yet - notebook 08 scores it.
FILTERS = ("none", "ticker", "ticker+year")


def dense(embedder: Embedder, store: VectorStore, filters: str = "ticker+year") -> SearchFn:
    """Vector search, optionally narrowed by metadata before scoring.

    `ticker+year` applies the year only to `value_lookup`. A growth question
    spans two years, so a single-year filter drops half its evidence - forcing
    it anyway scores *higher* (0.477), but only because the benchmark accepts
    either year's anchor, and a question needing both is still unanswered.
    """
    if filters not in FILTERS:
        raise ValueError(f"unknown filter policy {filters!r}; have {list(FILTERS)}")

    by_year = filters == "ticker+year"

    def search(q: BenchmarkQuestion, limit: int) -> list[Hit]:
        year = q.fiscal_year if by_year and q.question_type == "value_lookup" else None
        return store.search(
            embedder.embed_query(q.question),
            limit=limit,
            ticker=None if filters == "none" else q.ticker,
            fiscal_year=year,
        )

    return search


def hybrid_collection_for(prefix: str, model: str) -> str:
    """Separate from the dense collection: Qdrant fixes a collection's vector
    layout at creation, so hybrid cannot be added to one that already exists."""
    return f"{prefix}_hybrid_{model}"


def open_hybrid(settings: Settings, model: str) -> tuple[Embedder, SparseEmbedder, HybridStore]:
    store = HybridStore(
        settings.qdrant_url,
        hybrid_collection_for(settings.collection_prefix, model),
        MODELS[model].dim,
    )
    return Embedder(model), SparseEmbedder(), store


def hybrid(
    embedder: Embedder,
    sparse: SparseEmbedder,
    store: HybridStore,
    filters: str = "ticker+year",
    prefetch: int | None = None,
) -> SearchFn:
    """Dense + BM25, fused by RRF. The Day 4 lever.

    Same filter policies as `dense`, so the two are directly comparable in the
    ledger - which is the whole point of measuring a delta.
    """
    if filters not in FILTERS:
        raise ValueError(f"unknown filter policy {filters!r}; have {list(FILTERS)}")
    by_year = filters == "ticker+year"

    def search(q: BenchmarkQuestion, limit: int) -> list[Hit]:
        year = q.fiscal_year if by_year and q.question_type == "value_lookup" else None
        return store.search(
            embedder.embed_query(q.question),
            sparse.embed_query(q.question),
            limit=limit,
            ticker=None if filters == "none" else q.ticker,
            fiscal_year=year,
            prefetch=prefetch,
        )

    return search

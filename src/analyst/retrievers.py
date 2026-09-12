"""Retrievers - the things `evaluation.evaluate` scores.

One factory per strategy, each returning a `SearchFn`, so swapping strategy
never touches the scoring code.

Kept out of `evaluation.py` deliberately: importing a retriever pulls in
fastembed and Qdrant, and the evaluation tests must run without either.
"""

from collections.abc import Callable, Sequence

from analyst.benchmark import CONCEPT_ALIASES, BenchmarkQuestion
from analyst.config import Settings
from analyst.embedding import MODELS, Embedder, Reranker, SparseEmbedder
from analyst.evaluation import SearchFn
from analyst.vectorstore import Hit, HybridStore, VectorStore

# What every retriever accepts. Not a bool because the policies diverge at
# depth: measured on bge-small at depth 200, `none` scores 0.273 and
# `ticker+year` 0.432.
FILTERS = ("none", "ticker", "ticker+year")


def collection_for(prefix: str, model: str, variant: str = "") -> str:
    """One naming rule, so 07 (index) and 08 (evaluate) cannot disagree.

    `variant` names an alternative build of the same corpus - ADR-008's `ctx`
    and `fix` arms. Empty by default, so every collection indexed before it
    existed keeps exactly the name it already has.
    """
    return f"{prefix}_{variant}_{model}" if variant else f"{prefix}_{model}"


def hybrid_collection_for(prefix: str, model: str, variant: str = "") -> str:
    """Separate from the dense collection: Qdrant fixes a collection's vector
    layout at creation, so hybrid cannot be added to one that already exists."""
    return collection_for(f"{prefix}_hybrid", model, variant)


def store_for(settings: Settings, model: str, variant: str = "") -> VectorStore:
    """Collection handle without loading the model - dim comes from the spec.

    Separate from `open_store` so "is this model indexed?" costs a REST call
    rather than a model download.
    """
    return VectorStore(
        settings.qdrant_url,
        collection_for(settings.collection_prefix, model, variant),
        MODELS[model].dim,
    )


def open_store(settings: Settings, model: str, variant: str = "") -> tuple[Embedder, VectorStore]:
    """Embedder plus its collection, ready to index or query."""
    return Embedder(model), store_for(settings, model, variant)


def open_hybrid(
    settings: Settings, model: str, variant: str = ""
) -> tuple[Embedder, SparseEmbedder, HybridStore]:
    store = HybridStore(
        settings.qdrant_url,
        hybrid_collection_for(settings.collection_prefix, model, variant),
        MODELS[model].dim,
    )
    return Embedder(model), SparseEmbedder(), store


def expand(text: str, concept: str | None, fiscal_year: int | None) -> str:
    """Rewrite a question in the vocabulary the filings actually print.

    The measured problem, not a guess: a question and the element answering it
    share a median of TWO words. "total revenue in FY2024" is printed as
    "Revenue from contracts with customers" under "Year ended March 31, 2024".
    No retriever can bridge that, because the words are not the same ones.

    `CONCEPT_ALIASES` already holds the mapping - it is how the benchmark
    located each anchor in the first place. The retriever simply never used it.
    Indian fiscal years end 31 March, which is why the date form is hard-coded.

    Measured on bge-small, ticker+year: recall at depth 200 went 0.432 -> 0.682.
    """
    aliases = " ".join(CONCEPT_ALIASES.get(concept or "", ()))
    year = f" year ended March 31, {fiscal_year}" if fiscal_year else ""
    return f"{text} {aliases}{year}"


def expand_query(q: BenchmarkQuestion) -> str:
    """`expand` driven by the benchmark's own labels - what every leaderboard row used.

    ⚠️ That is an upper bound. In production the concept and year come from the
    router (`filings` below), which can get them wrong.
    """
    return expand(q.question, q.concept, q.fiscal_year)


def _check(filters: str) -> bool:
    """Validate the policy and return whether the year filter applies."""
    if filters not in FILTERS:
        raise ValueError(f"unknown filter policy {filters!r}; have {list(FILTERS)}")
    return filters == "ticker+year"


def _scope(q: BenchmarkQuestion, filters: str, by_year: bool) -> tuple[str | None, int | None]:
    """Ticker and year to narrow on, per policy.

    The year applies only to `value_lookup`: a growth question spans two years,
    so a single-year filter drops half its evidence.
    """
    year = q.fiscal_year if by_year and q.question_type == "value_lookup" else None
    return (None if filters == "none" else q.ticker), year


def dense(
    embedder: Embedder, store: VectorStore, filters: str = "ticker+year", expand: bool = False
) -> SearchFn:
    """Vector search, optionally narrowed by metadata before scoring."""
    by_year = _check(filters)

    def search(q: BenchmarkQuestion, limit: int) -> list[Hit]:
        ticker, year = _scope(q, filters, by_year)
        text = expand_query(q) if expand else q.question
        return store.search(embedder.embed_query(text), limit=limit,
                            ticker=ticker, fiscal_year=year)

    return search


def hybrid(
    embedder: Embedder,
    sparse: SparseEmbedder,
    store: HybridStore,
    filters: str = "ticker+year",
    expand: bool = False,
    prefetch: int | None = None,
) -> SearchFn:
    """Dense + BM25, fused server-side by RRF.

    Measured weaker than expected: BM25 had little to grip on, because **no
    benchmark question contains the figure it asks for** - the number lives only
    in the document. Kept because it composes with query expansion, which gives
    the lexical half real words to match.
    """
    by_year = _check(filters)

    def search(q: BenchmarkQuestion, limit: int) -> list[Hit]:
        ticker, year = _scope(q, filters, by_year)
        text = expand_query(q) if expand else q.question
        return store.search(
            embedder.embed_query(text), sparse.embed_query(text), limit=limit,
            ticker=ticker, fiscal_year=year, prefetch=prefetch,
        )

    return search


HitSearch = Callable[[BenchmarkQuestion, int], Sequence[Hit]]
"""A retriever that returns full `Hit`s. Reranking needs the chunk text, which
the leaner `Retrieved` protocol used for scoring deliberately does not carry."""


def reranked(
    inner: HitSearch, reranker: Reranker, depth: int = 100, expand: bool = False
) -> HitSearch:
    """Reorder a shortlist from `inner` with a cross-encoder.

    Composes over any retriever - dense, hybrid, expanded - because they are all
    just a `SearchFn`. That is the payoff of injecting the retriever instead of
    importing it.

    `depth` is the shortlist size, and it is the whole game: recall@depth of the
    inner retriever is a hard ceiling here, since reordering cannot introduce a
    chunk that was never fetched.
    """

    def search(q: BenchmarkQuestion, limit: int) -> list[Hit]:
        n = max(depth, limit)
        candidates = inner(q, n)
        if not candidates:
            return []
        text = expand_query(q) if expand else q.question
        scores = reranker.scores(text, [h.text for h in candidates])
        order = sorted(range(len(candidates)), key=lambda i: scores[i], reverse=True)
        return [candidates[i] for i in order[:limit]]

    return search


def filings(
    embedder: Embedder, store: VectorStore
) -> Callable[[str, str | None, int | None, str | None, int], list[Hit]]:
    """What the agent searches with: the leaderboard's best configuration.

    Dense + query expansion over ADR-008's `ctx` index, filtered by ticker and
    year. Identical to the measured retriever with one difference that matters:
    the ticker, year and concept arrive from the ROUTER, not from benchmark labels.
    """

    def search(text: str, ticker: str | None, fiscal_year: int | None, concept: str | None,
               limit: int) -> list[Hit]:
        return store.search(embedder.embed_query(expand(text, concept, fiscal_year)),
                            limit=limit, ticker=ticker, fiscal_year=fiscal_year)

    return search

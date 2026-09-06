"""Text embeddings via fastembed (ONNX).

Why fastembed rather than sentence-transformers: it runs on onnxruntime and
needs no torch. The torch wheel is ~2.5 GB and would buy nothing here, because
the models we can actually fit are 70-210 MB and run fine on CPU. It also
supplies the cross-encoder reranker needed on Day 4, so one dependency covers
both.

**Queries and documents are embedded differently.** BGE models are trained with
an instruction prefix on the query side only; embedding a question the same way
as a passage measurably degrades retrieval. fastembed's `query_embed` applies
the right prefix, so the asymmetry is handled here rather than forgotten at the
call site.
"""

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass

import numpy as np
from fastembed import SparseTextEmbedding, TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder
from fastembed.sparse.sparse_embedding_base import SparseEmbedding


@dataclass(frozen=True)
class ModelSpec:
    key: str
    name: str
    dim: int
    size_gb: float


# Deliberately all small: the deployment target has no GPU, and a model that
# cannot run there is not a candidate however good its benchmark scores are.
MODELS: dict[str, ModelSpec] = {
    "bge-small": ModelSpec("bge-small", "BAAI/bge-small-en-v1.5", 384, 0.07),
    "bge-base": ModelSpec("bge-base", "BAAI/bge-base-en-v1.5", 768, 0.21),
    "arctic-s": ModelSpec("arctic-s", "snowflake/snowflake-arctic-embed-s", 384, 0.13),
    "minilm": ModelSpec("minilm", "sentence-transformers/all-MiniLM-L6-v2", 384, 0.09),
}

DEFAULT_MODEL = "bge-small"


class Embedder:
    def __init__(self, key: str = DEFAULT_MODEL) -> None:
        if key not in MODELS:
            raise KeyError(f"unknown embedding model {key!r}; have {sorted(MODELS)}")
        self.spec = MODELS[key]
        self._model = TextEmbedding(model_name=self.spec.name)

    @property
    def dim(self) -> int:
        return self.spec.dim

    def embed_documents(
        self, texts: Iterable[str], batch_size: int = 64, parallel: int = 4
    ) -> Iterator[np.ndarray]:
        """`parallel` is process-level data parallelism, and it is what matters.

        Measured on this 16-thread machine: onnxruntime intra-op threads made
        things worse (4.3-4.5 -> 3.1-3.9 chunks/sec), while process-level
        parallel=8 reached 6.2-6.3. The model is small enough that one instance
        cannot saturate the CPU, so more copies beat more threads per copy.
        (An early run recorded 8.7; two careful re-measurements said 6.2. Use
        6.2 - the first number came from a short, badly sampled window.)

        Defaulted to 4 rather than 8: each worker loads its own copy of the model,
        and a run at parallel=8 died partway through a 9,982-chunk index on a
        machine with ~2 GB free RAM. Slightly slower and it finishes.
        """
        yield from self._model.embed(texts, batch_size=batch_size, parallel=parallel)

    def embed_query(self, text: str) -> np.ndarray:
        """Single query vector, with the model's query-side instruction prefix."""
        return next(iter(self._model.query_embed([text])))


# BM25 is statistical, not neural: 10 MB, no ONNX session, and it runs anywhere
# the deployment target can run Python. That matters because the AWS free-tier
# box has no GPU.
SPARSE_MODEL = "Qdrant/bm25"


class SparseEmbedder:
    """Lexical term weights, the half dense retrieval is systematically bad at.

    The Day 3 failure is numeric table rows collapsing together in embedding
    space: "520,412.5" and "438,860.1" are near-identical to a dense encoder and
    entirely different tokens to BM25. This is the Day 4 lever.
    """

    def __init__(self, name: str = SPARSE_MODEL) -> None:
        self._model = SparseTextEmbedding(model_name=name)

    def embed_documents(
        self, texts: Iterable[str], batch_size: int = 64, parallel: int = 4
    ) -> Iterator[SparseEmbedding]:
        yield from self._model.embed(texts, batch_size=batch_size, parallel=parallel)

    def embed_query(self, text: str) -> SparseEmbedding:
        """BM25 scores a query without document term frequencies, so the query
        side genuinely differs from the document side - same asymmetry as BGE."""
        return next(iter(self._model.query_embed([text])))


# 80 MB and CPU-only. bge-reranker-base is stronger and 1 GB, which the
# GPU-less deploy target cannot justify for a first measurement.
RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"


class Reranker:
    """Cross-encoder: scores the query and passage *together*.

    A bi-encoder (everything above) embeds the query and the passage separately
    and compares the two vectors, so it never sees them side by side. A cross
    encoder reads the pair jointly and is far more accurate - and far too slow
    to run over 9,982 chunks, which is why it only ever reorders a shortlist.

    It therefore cannot improve on what retrieval already surfaced: recall at
    the shortlist depth is a hard ceiling on anything this can do.
    """

    def __init__(self, name: str = RERANK_MODEL) -> None:
        self._model = TextCrossEncoder(model_name=name)

    def scores(self, query: str, documents: Sequence[str]) -> list[float]:
        return list(self._model.rerank(query, list(documents)))

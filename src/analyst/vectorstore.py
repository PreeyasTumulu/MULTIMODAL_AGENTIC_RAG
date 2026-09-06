"""Qdrant wrappers: dense-only, and dense+sparse hybrid.

The store holds vectors and a pointer. It never holds an authoritative value:
a hit gives back `element_ids`, and the number itself is read from Postgres.
A vector index is an approximate structure by construction, which is exactly
right for finding passages and exactly wrong for a financial figure.

Point IDs are UUIDv5 of the chunk_id, so re-indexing the same corpus overwrites
in place instead of duplicating.

Two classes rather than one flag, because the collections differ structurally:
a dense-only collection has one unnamed vector, a hybrid one has named `dense`
and `sparse` vectors. Qdrant fixes that at creation time, so it cannot be a
runtime switch. Everything they share - payload, IDs, filters, hit parsing -
lives in the module-level helpers.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from fastembed.sparse.sparse_embedding_base import SparseEmbedding
from qdrant_client import QdrantClient, models

from analyst.chunking import Chunk

NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")
DENSE, SPARSE = "dense", "sparse"

# Fields we filter on. Indexing them lets Qdrant restrict the candidate set
# BEFORE scoring - cheaper and more accurate than filtering results afterwards.
INDEXED_PAYLOAD = {
    "ticker": models.PayloadSchemaType.KEYWORD,
    "type": models.PayloadSchemaType.KEYWORD,
    "document_id": models.PayloadSchemaType.KEYWORD,
    "fiscal_year": models.PayloadSchemaType.INTEGER,
}


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    element_ids: list[str]
    document_id: str
    ticker: str
    fiscal_year: int
    pages: list[int]
    type: str
    text: str
    score: float


def point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(NAMESPACE, chunk_id))


def _payload(c: Chunk) -> dict[str, object]:
    return {
        "chunk_id": c.chunk_id, "element_ids": c.element_ids,
        "document_id": c.document_id, "ticker": c.ticker,
        "fiscal_year": c.fiscal_year, "pages": c.pages,
        "type": c.type, "heading": c.heading, "text": c.text,
    }


def _to_hit(point: models.ScoredPoint) -> Hit:
    p = point.payload or {}
    return Hit(
        chunk_id=str(p.get("chunk_id", "")),
        element_ids=list(p.get("element_ids") or []),
        document_id=str(p.get("document_id", "")),
        ticker=str(p.get("ticker", "")),
        fiscal_year=int(p.get("fiscal_year") or 0),
        pages=list(p.get("pages") or []),
        type=str(p.get("type", "")),
        text=str(p.get("text", "")),
        score=float(point.score),
    )


def _filter(ticker: str | None, fiscal_year: int | None) -> models.Filter | None:
    conditions: list[models.Condition] = []
    if ticker:
        conditions.append(
            models.FieldCondition(key="ticker", match=models.MatchValue(value=ticker))
        )
    if fiscal_year:
        conditions.append(
            models.FieldCondition(key="fiscal_year", match=models.MatchValue(value=fiscal_year))
        )
    return models.Filter(must=conditions) if conditions else None


def _sparse(v: SparseEmbedding) -> models.SparseVector:
    return models.SparseVector(indices=v.indices.tolist(), values=v.values.tolist())


class _Base:
    """Collection lifecycle shared by both stores."""

    def __init__(self, url: str, collection: str, dim: int) -> None:
        self.client = QdrantClient(url=url, timeout=120)
        self.collection = collection
        self.dim = dim

    def exists(self) -> bool:
        return bool(self.client.collection_exists(self.collection))

    def count(self) -> int:
        return int(self.client.count(self.collection, exact=True).count)

    def _index_payload(self) -> None:
        for field, schema in INDEXED_PAYLOAD.items():
            self.client.create_payload_index(self.collection, field, field_schema=schema)

    def _drop(self) -> None:
        if self.exists():
            self.client.delete_collection(self.collection)


class VectorStore(_Base):
    """Dense only. One unnamed vector per point."""

    def recreate(self) -> None:
        self._drop()
        self.client.create_collection(
            collection_name=self.collection,
            # Cosine: BGE vectors are trained for angular similarity, and their
            # magnitude carries no meaning.
            vectors_config=models.VectorParams(size=self.dim, distance=models.Distance.COSINE),
        )
        self._index_payload()

    def upsert(self, chunks: Sequence[Chunk], vectors: Sequence[np.ndarray]) -> None:
        self.client.upsert(
            collection_name=self.collection,
            points=[
                models.PointStruct(id=point_id(c.chunk_id), vector=v.tolist(), payload=_payload(c))
                for c, v in zip(chunks, vectors, strict=True)
            ],
        )

    def search(
        self,
        vector: np.ndarray,
        limit: int = 10,
        ticker: str | None = None,
        fiscal_year: int | None = None,
    ) -> list[Hit]:
        result = self.client.query_points(
            collection_name=self.collection,
            query=vector.tolist(),
            limit=limit,
            query_filter=_filter(ticker, fiscal_year),
            with_payload=True,
        )
        return [_to_hit(p) for p in result.points]


class HybridStore(_Base):
    """Named `dense` + `sparse` vectors, fused server-side by RRF.

    Reciprocal Rank Fusion combines the two rankings by position, not by score,
    which is the point: a cosine similarity and a BM25 score are not on the same
    scale and normalising them is a fudge. RRF needs no tuning and no weights.
    """

    def recreate(self) -> None:
        self._drop()
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config={
                DENSE: models.VectorParams(size=self.dim, distance=models.Distance.COSINE)
            },
            sparse_vectors_config={SPARSE: models.SparseVectorParams()},
        )
        self._index_payload()

    def upsert(
        self,
        chunks: Sequence[Chunk],
        dense: Sequence[np.ndarray],
        sparse: Sequence[SparseEmbedding],
    ) -> None:
        self.client.upsert(
            collection_name=self.collection,
            points=[
                models.PointStruct(
                    id=point_id(c.chunk_id),
                    vector={DENSE: d.tolist(), SPARSE: _sparse(s)},
                    payload=_payload(c),
                )
                for c, d, s in zip(chunks, dense, sparse, strict=True)
            ],
        )

    def search(
        self,
        dense: np.ndarray,
        sparse: SparseEmbedding,
        limit: int = 10,
        ticker: str | None = None,
        fiscal_year: int | None = None,
        prefetch: int | None = None,
    ) -> list[Hit]:
        """`prefetch` is how deep each branch searches before fusion.

        Defaults to `limit`: RRF over two lists of that length can surface up to
        twice as many distinct chunks, which is where the recall gain comes from.
        """
        flt = _filter(ticker, fiscal_year)
        depth = prefetch or limit
        result = self.client.query_points(
            collection_name=self.collection,
            prefetch=[
                models.Prefetch(query=dense.tolist(), using=DENSE, limit=depth, filter=flt),
                models.Prefetch(query=_sparse(sparse), using=SPARSE, limit=depth, filter=flt),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            with_payload=True,
        )
        return [_to_hit(p) for p in result.points]

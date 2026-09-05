"""Qdrant wrapper.

The store holds vectors and a pointer. It never holds an authoritative value:
a hit gives back `element_ids`, and the number itself is read from Postgres.
A vector index is an approximate structure by construction, which is exactly
right for finding passages and exactly wrong for a financial figure.

Point IDs are UUIDv5 of the chunk_id, so re-indexing the same corpus overwrites
in place instead of duplicating.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from qdrant_client import QdrantClient, models

from analyst.chunking import Chunk

NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")

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


class VectorStore:
    def __init__(self, url: str, collection: str, dim: int) -> None:
        self.client = QdrantClient(url=url, timeout=120)
        self.collection = collection
        self.dim = dim

    def recreate(self) -> None:
        if self.client.collection_exists(self.collection):
            self.client.delete_collection(self.collection)
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=models.VectorParams(
                size=self.dim,
                # Cosine: BGE vectors are trained for angular similarity, and
                # their magnitude carries no meaning.
                distance=models.Distance.COSINE,
            ),
        )
        for field, schema in INDEXED_PAYLOAD.items():
            self.client.create_payload_index(self.collection, field, field_schema=schema)

    def upsert(self, chunks: Sequence[Chunk], vectors: Sequence[np.ndarray]) -> None:
        self.client.upsert(
            collection_name=self.collection,
            points=[
                models.PointStruct(
                    id=point_id(c.chunk_id),
                    vector=v.tolist(),
                    payload={
                        "chunk_id": c.chunk_id,
                        "element_ids": c.element_ids,
                        "document_id": c.document_id,
                        "ticker": c.ticker,
                        "fiscal_year": c.fiscal_year,
                        "pages": c.pages,
                        "type": c.type,
                        "heading": c.heading,
                        "text": c.text,
                    },
                )
                for c, v in zip(chunks, vectors, strict=True)
            ],
        )

    def count(self) -> int:
        return int(self.client.count(self.collection, exact=True).count)

    def search(
        self,
        vector: np.ndarray,
        limit: int = 10,
        ticker: str | None = None,
        fiscal_year: int | None = None,
    ) -> list[Hit]:
        conditions: list[models.Condition] = []
        if ticker:
            conditions.append(
                models.FieldCondition(key="ticker", match=models.MatchValue(value=ticker))
            )
        if fiscal_year:
            conditions.append(
                models.FieldCondition(
                    key="fiscal_year", match=models.MatchValue(value=fiscal_year)
                )
            )
        result = self.client.query_points(
            collection_name=self.collection,
            query=vector.tolist(),
            limit=limit,
            query_filter=models.Filter(must=conditions) if conditions else None,
            with_payload=True,
        )
        hits: list[Hit] = []
        for p in result.points:
            payload = p.payload or {}
            hits.append(
                Hit(
                    chunk_id=str(payload.get("chunk_id", "")),
                    element_ids=list(payload.get("element_ids") or []),
                    document_id=str(payload.get("document_id", "")),
                    ticker=str(payload.get("ticker", "")),
                    fiscal_year=int(payload.get("fiscal_year") or 0),
                    pages=list(payload.get("pages") or []),
                    type=str(payload.get("type", "")),
                    text=str(payload.get("text", "")),
                    score=float(p.score),
                )
            )
        return hits

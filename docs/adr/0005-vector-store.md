# ADR-005: Qdrant as the vector store

- **Status:** Accepted
- **Date:** 2026-09-05
- **Supersedes the open question in** [ADR-001](0001-domain-and-corpus.md) and
  [storage.md](../architecture/storage.md)

## Decision

**Qdrant**, run as a container alongside Postgres, holding one collection per
embedding model (`elements_<model-key>`).

Cosine distance. Payload-indexed on `ticker`, `fiscal_year`, `type` and
`document_id`. Point IDs are UUIDv5 of the chunk ID, so re-indexing overwrites
in place rather than duplicating.

**The store holds vectors and a pointer, never an authoritative value.** A hit
returns `element_ids`; the number itself is read from Postgres.

## Why

The deciding factor is Day 4, not Day 3.

Dense-only retrieval is the easy half. Financial questions lean heavily on exact
lexical tokens — a ticker, a fiscal year, a line-item name like "deferred tax
liabilities" — and dense vectors are systematically weak at exactly that.
Hybrid retrieval is therefore not a nice-to-have here; it is the main planned
quality lever.

Qdrant supports **named sparse vectors alongside dense ones in the same
collection, with server-side RRF fusion in a single query**. pgvector would mean
running a dense search and a Postgres full-text search separately and fusing
them in Python — more code, two round trips, and Postgres FTS is not BM25.

Two secondary reasons:

- **Payload filtering happens before scoring.** When a question names a company
  and a year, restricting the candidate set first is both faster and more
  accurate than filtering results afterwards.
- **`fastembed` is Qdrant's own library.** One dependency covers dense
  embeddings, sparse embeddings and the Day-4 cross-encoder reranker.

## Alternatives considered

| Option | Verdict |
|---|---|
| **pgvector** | Genuinely close, and the better choice if hybrid retrieval were not required: one fewer container, and transactional consistency between vectors and elements. Rejected because building hybrid search on it is materially more work for a worse result, and hybrid is a core Day-4 deliverable. |
| **Chroma** | Simplest to start, weakest filtering and hybrid story. Optimises the day we are already past. |
| **Milvus** | More capable at scale than either. Its scale is irrelevant at 46,000 elements, and its operational weight is not. |
| **Pinecone / Weaviate Cloud** | Managed and paid. Violates the ₹0 constraint, and hosting the index locally is part of the point. |

## Tradeoffs

- **Given up:** transactional consistency. A crash between writing `elements`
  and upserting to Qdrant leaves the index stale. Acceptable because the index
  is fully derived — `index_chunks.py` rebuilds it from Postgres in minutes,
  and Postgres remains the only source of truth.
- **Given up:** one fewer container. Real cost on a 15 GB laptop and on a
  free-tier EC2 instance; Qdrant's idle footprint is small enough to accept.
- **Accepted:** a second query language and client to learn.

## Consequences

- Postgres and Qdrant must be re-synchronised together. Re-parsing a document
  changes no element IDs (they are deterministic), so a stale index is
  *incomplete*, never *wrong*.
- The collection name carries the model key. Several embedding models can be
  indexed side by side and compared on the same benchmark, which is how
  [ADR-006](0006-embedding-model.md) was decided rather than argued.
- Deployment adds a Qdrant container and a volume. Vector data does not need
  backing up — it is rebuildable from `elements`.

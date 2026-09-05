# Storage architecture

What lives where, and why this is not one database.

**Status:** ✅ Postgres + filesystem built · 🔜 Qdrant designed (Day 3)

---

## The four stores

| Store | Holds | Owns | Size today |
|---|---|---|---|
| **PostgreSQL 17** | companies, prices, facts, documents, elements | **Truth** — exact values, joins, filters | 5 tables, ~70k rows |
| **Qdrant** 🔜 | chunk vectors + payload | **Findability** — approximate semantic search | — |
| **`data/raw/`** | 6 source PDFs | Reproducible input | ~68 MB |
| **`data/figures/`** | 418 extracted images | Vision Agent input | ~40 MB |

---

## Why not put everything in one database?

The honest question, since pgvector exists and would collapse two of these into one.

**Each store answers a different kind of question, and they have incompatible
correctness properties:**

| Question | Needs | Answered by |
|---|---|---|
| "What was Sun Pharma's FY25 revenue?" | An **exact** value | Postgres |
| "Which passages discuss margin pressure?" | **Approximate** similarity | Qdrant |
| "Show me the chart on page 14" | Bytes on disk | Filesystem |

The important word is **approximate**. A vector index is an ANN structure: it
trades recall for speed and is *designed* to return "close enough". That is
exactly right for finding passages and exactly wrong for a financial figure.

**So the rule is: Qdrant never stores an authoritative value.** It stores a
vector and an `element_id`. Retrieval says *where to look*; Postgres says *what
the value is*. If Qdrant were lost entirely, no data would be lost — only the
index, rebuildable from `elements`.

The filesystem holds PDFs and images because binaries do not belong in a
relational database or in git; the manifest checksum gives reproducibility
without vendoring 68 MB into the repo.

🧭 **Open — Qdrant vs pgvector.** pgvector would mean one fewer container and
transactional consistency between vectors and elements. Qdrant is planned for
native **sparse-vector support and RRF fusion**, which makes hybrid retrieval
(Day 4) substantially simpler. That will be settled in an ADR on Day 3 with a
measurement, not an opinion.

---

## PostgreSQL

Full reference: **[data/schema.md](../data/schema.md)** — generated from the
models, so it cannot drift.

Principles applied:

- **`Numeric(30,4)` for money, never `float`.** Reliance FY26 revenue is
  ~1.06 × 10¹³. Float arithmetic on money is wrong in ways nobody notices.
- **Absolute currency units at rest.** Crore/million scaling happens at read
  time, so no precision is lost at write time.
- **`unit` is part of a fact's identity** — `INR`, `USD`, `INR/share`, `shares`,
  `ratio`. Storing EPS as a currency amount silently corrupts every ratio
  downstream.
- **Alembic migrations, never `create_all()`.** `create_all` cannot `ALTER`; it
  sees a table exists, does nothing, and the schema silently drifts from the
  models until a query fails hours later.
- **Unique constraints make ingestion idempotent** — every acquisition script
  can be re-run safely.

Host port **5433**, not 5432, to avoid colliding with an existing local Postgres.

---

## Qdrant — how vectors will be stored 🔜

### Collection

| Property | Value | Why |
|---|---|---|
| Name | `elements` | one collection, filtered by payload |
| Distance | **Cosine** | BGE embeddings are trained for cosine; magnitude carries no meaning |
| Dense vector | `bge-*` output, 768-dim (model TBD Day 3) | fits 4 GB VRAM locally |
| Sparse vector 🔜 | lexical term weights | exact-term matching for tickers, years, line-item names |
| ID | UUIDv5 derived from `chunk_id` | deterministic — re-indexing overwrites rather than duplicating |

### Payload — what travels with every vector

```jsonc
{
  "chunk_id":     "SUNPHARMA-annual_report-FY2025-7cf1d4f4:p0259:e0003#0",
  "element_id":   "SUNPHARMA-annual_report-FY2025-7cf1d4f4:p0259:e0003",
  "document_id":  "SUNPHARMA-annual_report-FY2025-7cf1d4f4",
  "ticker":       "SUNPHARMA",
  "sector":       "Pharma",
  "fiscal_year":  2025,
  "page":         259,
  "type":         "table",
  "heading":      "Consolidated Statement of Profit and Loss",
  "text":         "…"           // for reranking and display, NOT for arithmetic
}
```

Indexed payload fields (`ticker`, `fiscal_year`, `type`, `sector`) exist so the
search can be **filtered before it is scored**. If a question names a company and
a year, there is no reason to search 46,000 elements when a few thousand qualify —
that is both faster and more accurate than filtering afterwards.

### Chunking rules 🔜

| Element type | Rule | Reason |
|---|---|---|
| `table` | **Never split.** One chunk per table. | A table cut in half loses its header and becomes unreadable to both the model and the reranker. |
| `text` | Group under the preceding `heading`, then split with overlap | A paragraph without its section title is ambiguous — "revenue grew 12%" for *which* segment? |
| `heading` | Not indexed alone; prepended to its children | A heading is context, not an answer. |
| `figure` | Indexed once the Vision Agent writes a description (Day 5) | Until then it is stored, not understood. |

### What Qdrant deliberately does not hold

- No authoritative numeric values — those come from `facts` or `table_json`.
- No PDF bytes and no images — those are on disk, referenced by path.
- No user data.

**Rebuild cost if the collection is lost:** re-embed 46,241 elements locally.
Minutes on the GPU, and zero data loss.

---

## Filesystem

```
data/                          # git-ignored in its entirety
├── raw/
│   ├── RELIANCE/RELIANCE_annual_report_FY2025.pdf
│   ├── SUNPHARMA/SUNPHARMA_annual_report_FY2025.pdf
│   └── …
└── figures/
    └── <document_id>/
        └── <document_id>_p0014_e0003.png
```

Figure filenames are the `element_id` with `:` replaced by `_` — Windows
forbids colons in paths. The element ID is therefore recoverable from the
filename alone, which matters when debugging a bad citation.

🔜 **On deployment:** `data/figures/` moves to S3, referenced by URL instead of
path. `data/raw/` does **not** need to ship — the manifest rebuilds it.

---

## Backup and recovery

| Loss | Recovery | Data lost |
|---|---|---|
| Qdrant collection | re-run indexing from `elements` | none |
| `data/raw/` | `uv run python scripts/download_docs.py` | none — checksums verify |
| `data/figures/` | `uv run python scripts/parse_documents.py` | none |
| `prices` / `facts` | re-run the acquisition scripts | none (vendor data may have been revised) |
| `elements` | re-parse; element IDs are deterministic | none |
| **`documents` + pinned checksums** | **from git** | — |

Everything except the manifest is derived state. **The manifest is the only
irreplaceable artifact, and it lives in git** — which is precisely why the
checksums are pinned into it rather than kept in a lockfile that could be
regenerated wrongly.

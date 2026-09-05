# Storage architecture

What lives where, and why this is not one database.

**Status:** ✅ Postgres, filesystem and Qdrant built

---

## The four stores

| Store | Holds | Owns | Size today |
|---|---|---|---|
| **PostgreSQL 17** | companies, prices, facts, documents, elements | **Truth** — exact values, joins, filters | 5 tables, ~70k rows |
| **Qdrant 1.12** | chunk vectors + payload | **Findability** — approximate semantic search | 9,982 points |
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

**Decided: Qdrant** — see [ADR-005](../adr/0005-vector-store.md). pgvector was
close, and would be the better choice if hybrid retrieval were not required: one
fewer container, and transactional consistency between vectors and elements.
Qdrant wins on Day 4's requirement — native sparse vectors alongside dense ones
in the same collection, with server-side RRF fusion in a single query.

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

## Qdrant — how vectors are stored ✅

### Collection

| Property | Value | Why |
|---|---|---|
| Name | `elements_<model-key>` | one collection per embedding model, so models can be compared on the same benchmark |
| Distance | **Cosine** | BGE embeddings are trained for cosine; magnitude carries no meaning |
| Dense vector | `bge-small-en-v1.5`, **384-dim** | 70 MB, runs on CPU via ONNX — the deployment target has no GPU |
| Sparse vector 🔜 (Day 4) | lexical term weights | exact-term matching for tickers, years, line-item names |
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

### Chunking rules ✅

| Element type | Rule | Reason |
|---|---|---|
| `table` | Split only when it must be, and **every slice repeats the header**. Packed to a 900-character budget. | A slice without its header is just digits. The budget is not cosmetic: before it existed the largest table chunk was 6,643 characters against an encoder limit of 512 tokens, so most of it was silently truncated and never embedded. |
| `text` | Group under the preceding `heading` (~1,200 chars, 200 overlap) | A paragraph without its section title is ambiguous — "revenue grew 12%" for *which* segment? |
| `heading` | Not indexed alone; prepended to its children | A heading is context, not an answer. |
| `figure` | Skipped until the Vision Agent writes a description (Day 5) | Until then it is stored, not understood. |

### What Qdrant deliberately does not hold

- No authoritative numeric values — those come from `facts` or `table_json`.
- No PDF bytes and no images — those are on disk, referenced by path.
- No user data.

**Rebuild cost if the collection is lost:** re-embed 9,982 chunks locally —
about 30 minutes on this CPU, and zero data loss.

### Embedding throughput, measured

| Configuration | chunks/sec |
|---|---:|
| default | 4.4 |
| `threads=16` (onnxruntime intra-op) | 4.1 |
| **`parallel=8`** (process-level) | **8.7** |

Intra-op threading does nothing — a single instance already saturates what it
can use. The model is small enough that more *copies* beat more threads per copy.
Defaulted to `parallel=4`: a `parallel=8` run died partway through a full index
on a machine with ~2 GB free RAM, and each worker loads its own copy of the model.

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
| `data/raw/` | run notebook `03_download_documents.ipynb` | none — checksums verify |
| `data/figures/` | run notebook `04_parse_documents.ipynb` | none |
| `prices` / `facts` | re-run notebooks `01` and `02` | none (vendor data may have been revised) |
| `elements` | re-parse; element IDs are deterministic | none |
| **`documents` + pinned checksums** | **from git** | — |

Everything except the manifest is derived state. **The manifest is the only
irreplaceable artifact, and it lives in git** — which is precisely why the
checksums are pinned into it rather than kept in a lockfile that could be
regenerated wrongly.

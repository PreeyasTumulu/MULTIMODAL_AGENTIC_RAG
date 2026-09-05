# Changelog

Notable changes per development day. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/).

---

## [Unreleased] — Day 4

Planned: hybrid dense + sparse retrieval, cross-encoder reranking, and the
measured improvement over the Day 3 baseline.

---

## Day 3 — 2026-09-05

### Changed — `scripts/` became `notebooks/`

Every pipeline entry point is now a numbered notebook under `notebooks/`, so the
pipeline **shows its output** instead of requiring a 30-minute run to see what
happened. Earlier entries in this file name `scripts/*.py` files that no longer
exist; the equivalents are listed in
[`notebooks/README.md`](../notebooks/README.md).

The split that makes this work:

- `src/analyst/*.py` keeps **all** reusable logic — importable, 37 unit tests,
  `mypy --strict` clean. A notebook cannot be imported, typed or tested.
- `notebooks/*.ipynb` orchestrate and display. Deliberately thin.
- `ruff` lints notebooks too; only file-level import rules (`E402`, `I001`) are
  relaxed there, because notebooks import per cell by design.
- `gen_schema_docs.py` moved into the library as `analyst.schema_docs.generate`,
  so a notebook and CI call the same code.

### Added

- `src/analyst/chunking.py` — heading-aware text chunks; tables never separated
  from their header.
- `src/analyst/embedding.py` — fastembed (ONNX, no torch). Query and document
  embeddings use different prefixes, which BGE requires.
- `src/analyst/vectorstore.py` — Qdrant wrapper. Deterministic UUIDv5 point IDs,
  payload-indexed on `ticker` / `fiscal_year` / `type` / `document_id`.
- `src/analyst/benchmark.py` — the auto-generated evaluation set.
- Qdrant added to `docker-compose.yml` (`:6333`).
- [ADR-005](adr/0005-vector-store.md) — Qdrant over pgvector.

### Fixed — two real defects found by measuring

- **Table chunks were being silently truncated.** The largest was 6,643
  characters against an encoder limit of 512 tokens, so most of the biggest
  tables was never embedded at all. Table rows are now packed to a character
  budget; p90 table chunk fell from 1,452 to 891 characters.
- **The benchmark's false-positive problem, fixed.** ADR-004 recorded raw oracle
  recall of 47–57% as a *ceiling*, not a score. A value is now accepted only when
  a label for its concept appears in the **same element**, plus a tolerant
  numeric pass within 0.5% — because the vendor and the filing rarely agree to
  the last rupee (HDFC Bank FY2025 net profit: ₹67,347.36 crore filed against
  ₹67,351 crore at the vendor). Tolerance took HDFCBANK from 0 anchored
  questions to 2, and the benchmark from 34 to 44.

### Measured

- **9,982 chunks** from 46,241 elements (2,751 table, 7,231 text).
- Embedding throughput: onnxruntime intra-op `threads=16` made things *worse*
  (4.1/sec against 4.4 default); process-level `parallel=8` doubled it to
  8.7/sec. Defaulted to `parallel=4` after a `parallel=8` run died partway
  through on a machine with ~2 GB free RAM.

---

## Day 2 — 2026-09-05

### Added
- **Document corpus.** `configs/documents.yaml`, a SHA-256-pinned manifest.
  6 annual reports, 2,056 pages, ~68 MB. Checksums are written back into the
  manifest on first fetch, preserving its comments and ordering.
- **`scripts/download_docs.py`.** Streamed downloads, content-type validation,
  `.part` files renamed only on completion, and a hard error (not a silent
  overwrite) when a checksum disagrees.
- **`fetch: manual` mode** for sources that block automated requests.
- **`scripts/benchmark_parsers.py`.** Scores parsers on **oracle recall** rather
  than characters per second.
- **`src/analyst/parsing.py`.** PDF → typed elements with page and bbox.
- **`src/analyst/numfmt.py`.** Generates every plausible Indian printed form of
  a value — 6 scales × 3 groupings × 3 precisions.
- **`documents` and `elements` tables** (migrations `f35f3fd5`, `e72036aa`).
- **`scripts/demo_oracle_link.py`.** Proves the structured/unstructured join.
- **Full documentation tree** under `docs/`, including a schema reference
  generated from the models by `scripts/gen_schema_docs.py`.
- [ADR-004](adr/0004-pdf-parser.md) — PyMuPDF.

### Measured
- **46,241 elements**: 37,675 text, 6,171 heading, 1,977 table, 418 figure.
- **PyMuPDF is 30–60× faster than pdfplumber** on identical 60-page subsets, for
  the same text (within 2%) and the same oracle recall (within 3 points).
- Full-document oracle recall **47–57%** — a raw match rate that includes false
  positives. Recorded as a ceiling, not a score.
- Oracle values located in real reports across three different printed scales:
  SUNPHARMA revenue `520,412.5` on p.259 (₹ million), SUNPHARMA net income
  `109,290` on p.6 (₹ million), ICICIBANK net income `510,291,955` on p.266
  (₹ thousand).

### Found
- **`tcs.com` and `infosys.com` return HTTP 403** to any scripted request, even
  with full browser headers and a `Referer`. Marked `fetch: manual` rather than
  worked around.
- **No OCR needed** — every corpus PDF carries a text layer at 2,400–7,000
  chars/page.

### Fixed
- `Fact.period_end` was compared against an f-string; psycopg refuses to compare
  `date` to `varchar`. Now a real `date()`.
- A "latest close" query keyed off a global `max(trade_date)` returned `NULL`
  for any ticker whose last bar was dropped — a query bug that looked like a
  data bug. Now `DISTINCT ON (ticker)`.

---

## Day 1 — 2026-09-05

### Added
- Project scaffold: uv, Ruff, mypy (strict), pytest, pre-commit.
- **Alembic from the first commit** — not `create_all()`, which cannot `ALTER`.
- `companies`, `prices`, `facts` tables (migrations `e11a2145`, `b1ae1176`).
- `src/analyst/provenance.py` — the `document_id / page / element_id / bbox`
  contract, with deterministic IDs. Written before it had a caller, because it
  is unrecoverable if skipped.
- `scripts/acquire_prices.py`, `scripts/acquire_facts.py`, `scripts/db_stats.py`.
- [ADR-001](adr/0001-domain-and-corpus.md) domain · [ADR-002](adr/0002-llm-provider-stack.md)
  LLM stack at ₹0 · [ADR-003](adr/0003-provenance-schema.md) provenance.

### Measured
- 12 companies across 4 sectors.
- **14,879** daily OHLCV rows (5 years).
- **8,532** financial facts, FY2022–FY2026 — the evaluation oracle.

### Found
- **INFY reports its statements in USD** while quoting in INR. Inferring
  currency from the exchange made Infosys look ~85× smaller than Wipro and would
  have made the benchmark search for `1,928` in a report printing
  `₹1,62,990 crore`. `companies.financial_currency` now carries it explicitly.
- **Yahoo returns a NaN close** for an in-progress session and occasionally for
  a completed one (DRREDDY, 2026-09-04). Guarded with a regression test.

### Infrastructure
- Postgres bound to host port **5433** — 5432 is occupied by another local
  Postgres on the development machine.

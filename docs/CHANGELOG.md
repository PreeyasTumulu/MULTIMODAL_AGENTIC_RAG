# Changelog

Notable changes per development day. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/).

---

## [Unreleased] — Day 3

Planned: chunking, BGE embeddings, Qdrant, the auto-generated benchmark, and
first baseline retrieval metrics.

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

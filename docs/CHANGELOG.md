# Changelog

Notable changes per development day. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/).

---

## [Unreleased]

### Added — the run ledger: measurements became records

Every metric this project had produced lived inside a notebook output cell. Fine
for one number, useless for a comparison: answering *"did hybrid beat dense, and
by how much"* meant re-running both. A claim you cannot diff is a claim you
cannot defend.

A run is now a **record**. `analyst.evaluation` writes each one to
`results/runs.jsonl` carrying the config that produced it, a content hash of the
benchmark it scored, and the git revision of the code — suffixed `-dirty` when
the tree was uncommitted, because that run is not reproducible and saying so
costs nothing. `results/leaderboard.md` regenerates from the ledger.

`results/` is committed, unlike `data/`. The corpus is reproducible from the
manifest; a measurement is not reproducible without the compute that made it.

- **The retriever is injected, not imported.** `evaluate()` takes a callable, so
  dense, hybrid and reranked retrieval are scored by identical code on identical
  questions — which is the only reason a delta means anything. It also lets the
  13 new tests run with a fake retriever, no Qdrant and no embeddings.
- `analyst.retrievers` holds one factory per strategy. Day 4's hybrid and
  reranked retrievers land beside `dense` without touching the scoring code.
- Notebook 07 now sweeps **one collection per model** and is **resumable** — a
  collection already at full point count is skipped, so a two-hour sweep does
  not restart from zero after one failure.
- Notebook 08 scores from the package instead of a notebook-local `evaluate()`,
  and the depth curve is finally reproducible code rather than prose in this file.
- [ADR-006](adr/0006-embedding-model.md) — **Proposed**, with the decision rule
  fixed *before* the sweep runs: highest Recall@5 wins, ties inside 0.02 go to
  the smaller model. The expectation is recorded too: given that 32 of 44
  questions have no correct element in the top 200, a bigger model in the same
  family is predicted to move little. Being wrong about that would be the
  interesting outcome.

Checks: **50 tests** (was 37), `ruff` clean, `mypy --strict` clean on 28 files.

> ⚠ Rewriting notebook 08 onto the ledger cleared its saved outputs, and two of
> notebook 07's. Both need one execution pass once the sweep has run; until then
> the only recorded numbers for Day 3 are the tables in this file.

### The Day 3 baseline — dense retrieval, and it is bad

The index is complete: `elements_bge-small` holds **9,982 of 9,982 points**,
rebuilt from scratch. Notebook 08 has run. This is the number every later change
is measured against, and it is not a good one.

44 benchmark questions, **zero LLM calls**:

| config | R@1 | R@5 | R@10 | MRR | pR@5 | p50 |
|---|---|---|---|---|---|---|
| `bge-small` + filters | 0.023 | **0.045** | 0.091 | 0.039 | 0.091 | 74 ms |
| `bge-small`, no filters | 0.023 | 0.045 | 0.091 | 0.035 | 0.091 | 74 ms |

**40 of 44 questions never retrieve the correct element in the top 10.** Growth
questions score 0.000 at every k. Metadata filtering changes MRR by 0.004, which
on four hits is noise — it has not yet earned its complexity, and saying so is
the point of measuring it.

### Verified before being believed

A number this bad is more likely to be a broken evaluator than a broken
retriever, so it was checked three ways before being recorded:

- **Element IDs match.** Expected and indexed IDs are the same `str` format — no
  type mismatch silently emptying the set intersection.
- **The retrievability ceiling is 100%.** All 54 expected element IDs are present
  in the index, across all 44 questions. Nothing was lost to chunking or the
  table budget. The evidence is there; the retriever fails to rank it.
- **It reproduces.** Two independent full drop-and-rebuild cycles produced
  identical metrics and an identical per-ticker miss breakdown.

The baseline is real.

### The measurement that reorders Day 4

Rank of the correct element, searching to depth 200:

| depth | 5 | 10 | 20 | 50 | 100 | 200 |
|---|---|---|---|---|---|---|
| recall | 0.045 | 0.091 | 0.136 | 0.182 | 0.273 | 0.273 |

**32 of 44 questions have no correct element anywhere in the top 200.** A
cross-encoder reranker only reorders what dense retrieval already surfaced, so on
this corpus **a reranker is capped at 0.273 recall no matter how good it is.**

Day 4 therefore leads with **hybrid sparse + dense retrieval**, and adds the
reranker second. These queries are numeric and entity-heavy — "net profit",
"FY2025", "HDFC Bank" — which is what lexical matching catches and what dense
embeddings blur across financial table rows that are mostly digits. Recall at
depth has to move before reranking has anything to work with.

> ⚠️ **Read the baseline with its caveat.** Ground truth is *single-anchor*: each
> question names one element that contains the answer. Retrieval that surfaces a
> different page also stating the answer scores as a miss. True quality is better
> than 0.045 — the metric is strict by construction. The Day 4 delta will be
> measured the same strict way, so the comparison is fair, but neither number
> should be quoted as absolute retrieval quality.

### Fixed — notebook outputs were mostly log noise

`configure_logging()` called `basicConfig(level="INFO")`, which sets the *root*
logger; `httpx` propagates to it. Every HTTP call became a saved output line —
~40 upserts per index run, ~90 searches per eval — burying the actual results.
`httpx`, `httpcore`, `urllib3` and `qdrant_client` are now pinned to `WARNING`,
behind a `quiet_third_party` flag so transport bugs stay debuggable. Notebook 07
shrank 36% and notebook 08 48%, all of it noise.

### Next

1. **Day 4**: hybrid sparse + dense, then the cross-encoder reranker, then re-run
   notebook 08. The delta is the deliverable, not the technique.
2. Execute notebooks 01–05 and 10 so they ship **with outputs** (06–09 have them).
3. Run the ADR-006 sweep (notebook 07 with `SWEEP = list(MODELS)`), then flip
   that ADR to Accepted with the winning row.
4. Flip the ✅/🔜 markers in `docs/`, regenerate `data/schema.md` via notebook 10.

### Open, not blocking

- **8,295 of 46,241 elements appear in no chunk.** Probably intentional
  header/footer/empty filtering, but it is unverified and undocumented.
- **`qdrant_client` 1.19.0 against server 1.12.4** — major-version skew warning on
  every connect. Works today; pin or bump.

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

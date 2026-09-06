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

**The retriever is injected, not imported.** `evaluate()` takes a callable, so
every configuration below was scored by identical code on identical questions.
The detail of what landed is in the Day 4 entry below.

### Day 4 — the sweep, and what it exposed

Four embedding models indexed in full and six retrieval configurations measured,
all in [`results/leaderboard.md`](../results/leaderboard.md). Two ADRs came out of
it: [ADR-006](adr/0006-embedding-model.md) (embedding model) and
[ADR-007](adr/0007-retrieval-strategy.md) (retrieval strategy).

#### The embedding model is not the bottleneck

`bge-base`, `arctic-s` and `minilm` were each indexed to the full 9,982 points and
scored on the same 44 questions. **The entire spread across four models is two
questions.** `bge-base` "won" R@5 at 0.091 (4 of 44) while finishing *last* on MRR
and R@1, missing a question `bge-small` finds, and costing 96 minutes to index
against 20-25. **38 of 44 questions are retrieved by no model at all.**

`bge-small` is retained. The 2.5 hours bought negative evidence, which was the
point: buying a bigger encoder is now a closed question rather than a hunch.

> The pre-registered decision rule picked `bge-base`, and following it would have
> been wrong. The tie-band was 0.02 on a 44-question benchmark where **one
> question is 0.023** — narrower than the smallest difference that can exist.
> Writing the rule down beforehand is what made that visible.

#### The real problem: the question and the filing use different words

**A question and the element answering it share a median of two words.** The
question asks for *total revenue in FY2024*; the filing prints *Revenue from
contracts with customers* under *Year ended March 31, 2024*.

`CONCEPT_ALIASES` already held the mapping — it is how notebook 06 anchored every
question — and the retriever had never used it at query time. Feeding those
labels plus the real date form into the query:

| retriever | R@5 | MRR | @50 | @100 | @200 |
|---|---|---|---|---|---|
| dense (baseline) | 0.045 | 0.039 | 0.227 | 0.273 | 0.432 |
| dense+expand | 0.068 | **0.056** | 0.364 | 0.477 | 0.682 |
| hybrid+expand | 0.068 | 0.054 | **0.477** | **0.614** | **0.727** |

**Recall at depth went 0.432 to 0.727** — 19 findable questions became 32.
SUNPHARMA went from 0 to 17 of 24; growth questions from 0 to 5 of 10.

#### Two predictions that were wrong, recorded as such

- **BM25 alone was predicted to be the Day 4 lever. It was not.** The argument was
  that `520,412.5` is a unique lexical token — but **0 of 44 questions contain the
  figure they ask for**, so BM25 had nothing to match. Alone it *lowered* the
  ceiling to 0.364. It only earns its place combined with expansion, where it
  gives the best pool at depth.
- **The reranker was predicted to pay off once the pool improved. It did not.**
  One question at R@5, a question *lost* at R@10, MRR down 0.056 to 0.046, and
  **60x the latency** (5,314 ms against 88 ms). `ms-marco-MiniLM-L-6-v2` is
  trained on web prose; our passages are grids of numbers. Kept in the package
  and tested, kept out of the default path.

#### Added

- `analyst.evaluation` — the run ledger. A run is a record: config, benchmark
  content-hash, git rev (`-dirty` when uncommitted), metrics, depth curve,
  appended to `results/runs.jsonl`. **The retriever is injected, not imported**, so
  every configuration above was scored by identical code on identical questions.
- `analyst.retrievers` — `dense`, `hybrid`, `expand_query`, `reranked`. Reranking
  composes over any retriever because they are all just a `SearchFn`.
- `analyst.embedding` — `SparseEmbedder` (BM25, 10 MB, statistical not neural)
  and `Reranker` (cross-encoder).
- `analyst.vectorstore.HybridStore` — named dense + sparse vectors, RRF fused
  server-side. RRF combines rankings by *position*, so there is no scale
  normalisation fudge and no weight to tune.
- Notebooks **11** (hybrid), **12** (query expansion), **13** (reranking).
- `RunConfig.filters` is a string, not a bool: three policies differing by 0.16
  recall at depth would otherwise have recorded as the same run.
- `RunConfig.points` records the index size scored, so a partial index can never
  look like a complete one.

#### Fixed

- **A second corpus tree at `notebooks/data/`.** `settings.data_dir` was
  CWD-relative and `nbconvert` runs notebooks with `CWD=notebooks/`, so a headless
  run wrote its own copy. Paths now anchor to the repo root, with a regression
  test that `chdir`s away. `schema_docs` had the same bug.
- **A stale throughput number.** `embedding.py` documented `parallel=8` at 8.7
  chunks/sec; two careful re-measurements say **6.2-6.3**. The 8.7 came from a
  short, badly sampled window.
- **The Day 3 depth curve was measured with the wrong retriever** — unfiltered,
  while the headline table beside it was filtered. Corrected below.

Checks: **68 tests**, `ruff` clean, `mypy --strict` clean on 29 files.

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

### The measurement that decides Day 4 — corrected

Rank of the correct element, searching to depth 200. **The filter policy moves
this curve more than anything else measured so far**, and the first reading of it
compared the wrong pair: the curve was measured *without* metadata filters while
the headline table above it is the *filtered* configuration. Two different
retrievers, one conclusion.

| policy | 5 | 10 | 20 | 50 | 100 | 200 |
|---|---|---|---|---|---|---|
| `none` — no filters | 0.045 | 0.091 | 0.136 | 0.182 | 0.273 | 0.273 |
| `ticker+year` — what the system uses | 0.045 | 0.091 | 0.136 | 0.227 | 0.273 | **0.432** |

The `none` row reproduces the originally recorded curve exactly, which is what
identified the mix-up. Every policy measured so far is **identical at k<=20**, so
the headline baseline is unaffected — they diverge only at depth, which is
precisely where the ceiling argument lives.

**The corrected ceiling: 0.432, not 0.273.** 19 of 44 questions have their answer
somewhere in the top 200, not 12; 25 have nothing there. A cross-encoder reranker
only reorders what retrieval surfaced, so 0.432 is its hard cap — still low, but
meaningfully less hopeless than recorded.

**Day 4 still leads with hybrid sparse retrieval.** A 0.432 ceiling does not
change the diagnosis: these queries are numeric and entity-heavy ("net profit",
"FY2025", "HDFC Bank"), which is what lexical matching catches and what dense
embeddings blur across table rows that are mostly digits. Recall at depth has to
move before reranking has much to work with. The reranker is now worth doing
*second* rather than not at all.

> `ticker` alone is not in the table because it has not been measured. Notebook
> 08 scores it; the row appears in `results/leaderboard.md` when it does.

### A finding worth not acting on

Forcing the year filter onto growth questions as well reaches **0.477**, beating
the principled policy. It should not be adopted. A growth question's evidence
spans two annual reports and scoring counts a hit on *either* anchor, so
narrowing to one year surfaces that year's element in a smaller pool while the
question — which needs both figures — remains unanswerable. That is the
benchmark being lenient about multi-document questions, not retrieval improving.
It is recorded here because the next person to see 0.477 will be tempted.

> ⚠ **Read the baseline with its caveat.** Ground truth is *single-anchor*: each
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

1. **Contextual chunk prefixes.** Query expansion fixed the *question* side of the
   vocabulary gap; the document side is untouched. The element answering a
   SUNPHARMA revenue question carries no company name, no fiscal year and no
   statement title. Prefixing each chunk with `SUNPHARMA FY2024 - Statement of
   Profit and Loss` gives both halves something to match. Needs a re-index.
2. Execute notebooks **01-05** so they ship with outputs. The only remaining gap.
3. Growth questions (10 of 44) stay at zero by construction - their evidence spans
   two annual reports, so no single chunk answers them. That is multi-document
   reasoning, an agent problem rather than a retrieval one.

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

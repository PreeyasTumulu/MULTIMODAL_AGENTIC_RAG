# Notebooks

The pipeline, in order, as runnable notebooks that **show their output**.

## Run order

| # | Notebook | What it does | Typical time |
|---|---|---|---|
| 01 | [Acquire market prices](01_acquire_prices.ipynb) | Companies + 5 years of daily OHLCV → `prices` | ~15 s |
| 02 | [Acquire financial facts](02_acquire_facts.ipynb) | Reported statements → `facts` — **the evaluation oracle** | ~30 s |
| 03 | [Download documents](03_download_documents.ipynb) | Annual report PDFs, SHA-256 verified → `documents` | ~2 min |
| 04 | [Parse documents](04_parse_documents.ipynb) | PDFs → typed elements with page/bbox → `elements` | ~5 min |
| 05 | [Benchmark parsers](05_benchmark_parsers.ipynb) | PyMuPDF vs pdfplumber, scored on **oracle recall** | ~4 min |
| 06 | [Build the benchmark](06_build_benchmark.ipynb) | Auto-generate `(question, answer, source page)` triples | ~15 s |
| 07 | [Chunk, embed, index](07_index_chunks.ipynb) | Chunks → embeddings → Qdrant, **one collection per model** | ~30 min/model |
| 08 | [Evaluate retrieval](08_evaluate_retrieval.ipynb) | Recall@k, MRR — appends to **`results/runs.jsonl`** | ~2 min |
| 09 | [Explore the corpus](09_explore_corpus.ipynb) | Read-only. Run any time | seconds |
| 10 | [Regenerate schema docs](10_generate_docs.ipynb) | Rewrites `docs/data/schema.md` | seconds |
| 11 | [Hybrid retrieval](11_hybrid_retrieval.ipynb) | BM25 + dense, fused by RRF | ~35 min |
| 12 | [Query expansion](12_query_expansion.ipynb) | Closes the question/filing vocabulary gap — **the real lever** | ~2 min |
| 13 | [Reranking](13_reranking.ipynb) | Cross-encoder over a shortlist — measured, not adopted | ~8 min |
| 14 | [Contextual chunk prefixes](14_contextual_chunks.ipynb) | The **document** side of the vocabulary gap — company + FY on every chunk | ~2 h |

01–08 are a dependency chain: each needs the ones before it to have run at least
once. 11 needs 01–06. 14 needs 01–06 and re-indexes into its own collections, so
it does not disturb 07's. 09 and 10 are safe at any point.

Everything is **idempotent** — re-running never duplicates data.

---

## Why notebooks here and a package there

| Lives in | What | Why |
|---|---|---|
| `src/analyst/*.py` | All reusable logic — parsing, chunking, embeddings, the oracle matcher, the vector store | Importable, unit-tested (37 tests), `mypy --strict` clean. A notebook cannot be imported, type-checked, or tested. |
| `notebooks/*.ipynb` | Orchestration and results | Shows its work. A reviewer sees the numbers without running anything. |

The notebooks are deliberately thin: they call into `analyst` and display what
comes back. If a cell starts growing real logic, that logic belongs in the
package with a test.

Lint applies to notebooks too — `uv run ruff check .` covers `.ipynb`. Only
file-level import rules are relaxed there (`E402`, `I001`), because notebooks
import per cell by design.

---

## Running

```bash
uv run jupyter lab                    # interactive
```

Headless, which also saves the outputs into the file:

```bash
uv run jupyter nbconvert --to notebook --execute --inplace \
  --ExecutePreprocessor.timeout=3600 notebooks/07_index_chunks.ipynb
```

**Currently carrying outputs:** 06, 07, 08, 09, 10, 11, 12, 13. **01-05 have never
been executed with outputs saved** — they are the acquisition and parsing steps, and
running them re-downloads and re-parses the corpus. That is the one remaining gap.

**Commit notebooks with their outputs.** The saved tables and numbers are the
point — a notebook stripped of outputs makes a reader run a 30-minute pipeline
just to see what happened.

---

## Prerequisites

```bash
cp .env.example .env
uv sync
docker compose up -d          # Postgres :5433, Qdrant :6333
uv run alembic upgrade head
```

Two documents (TCS, Infosys) must be downloaded by hand — their IR sites return
HTTP 403 to any scripted request. Notebook 03 prints the URLs and target paths.

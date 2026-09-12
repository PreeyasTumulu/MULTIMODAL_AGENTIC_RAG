# Multimodal Agentic RAG — Indian Equity Research Analyst

A question-answering system over Indian listed-company annual reports and share
prices that **will not state a figure it cannot find printed on the page it cites.**

A "chat with PDF" app has one path: embed the question, cosine-search, stuff the
chunks into a prompt, generate. That path answers *"what risks does the report
mention?"* and quietly fabricates *"what was revenue in FY25?"*, because nothing
checks the number against the document.

Here the language model routes the question and **points at** a figure. Plain Python
then checks that the figure is printed in the evidence the model cited, and does any
arithmetic. Anything that fails the check is refused.

| Question | Path |
|---|---|
| "What was ICICI Bank's net profit in FY2024?" | Retrieve → extract → **verify** the figure is printed on the cited page |
| "By what percentage did Sun Pharma's net profit change from FY2024 to FY2025?" | Two verified figures → growth computed in Python |
| "What does Sun Pharma say drove its specialty business?" | Retrieve → cited prose answer (its figures are verified; the prose is not) |
| "How has Reliance Industries traded over the last year?" | Fixed read-only price query → change computed in Python |
| "Should I buy HDFC Bank shares?" · "TCS's net profit in FY2025?" | Refused: advice / no TCS filing is indexed |

> **Status: Day 6.** Retrieval, answering, figure triage and the API + UI are built.
> Deployment is not. This README claims only what is built and measured — see
> [Results](#results) and [Limitations](#limitations).

---

## Why this is not a toy

1. **The LLM points; Python verifies and computes.** A figure is accepted only when it is
   printed in the evidence block the model cited; a unit only when that block prints it.
   Growth rates and price changes are computed in Python.
2. **Provenance is attached at extraction time.** Every element carries
   `document_id / page / element_id / bbox` from the moment it is parsed, so every
   answer cites a page. See [ADR-003](docs/adr/0003-provenance-schema.md).
3. **The benchmark is generated, not hand-written.** Reported financials act as an
   oracle: take a known fact, find that number in the parsed report in Indian formats
   (`9,64,693` / `964,693` / `96,469.3`), and you have a labelled
   `(question, answer, source page)` triple. See [ADR-001](docs/adr/0001-domain-and-corpus.md).
4. **Answers are graded without an LLM judge.** Every benchmark answer is a number with a
   known true value, so correctness is a comparison, not an opinion.

---

## Corpus

| | |
|---|---|
| Prices + reported financials | 12 companies, 4 sectors (TCS, INFY, WIPRO · HDFCBANK, ICICIBANK, BAJFINANCE · RELIANCE, NTPC, ONGC · SUNPHARMA, DRREDDY, CIPLA) |
| Annual reports parsed and indexed | **6 reports, 4 companies:** HDFC Bank FY25, ICICI Bank FY24–25, Reliance FY25, Sun Pharma FY24–25 — 2,056 pages, 46,241 elements |
| Figures extracted | 418 images, triaged by a local vision model |

TCS and Infosys block scripted downloads; their reports are a manual step. Scope lives in
[`configs/companies.yaml`](configs/companies.yaml) and
[`configs/documents.yaml`](configs/documents.yaml).

**No data is committed to this repository.** `data/` is git-ignored and rebuilt from the
notebooks; `results/` (the measurements) is committed.

---

## Quickstart

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker, and
[Ollama](https://ollama.com) with `llama3.2` pulled (answers run locally by default —
no API key needed).

```bash
git clone https://github.com/PreeyasTumulu/MULTIMODAL_AGENTIC_RAG.git
cd MULTIMODAL_AGENTIC_RAG
cp .env.example .env
uv sync
docker compose up -d          # Postgres :5433, Qdrant :6333
uv run alembic upgrade head
uv run jupyter lab            # then run notebooks/01 .. 16 in order
```

Serve it:

```bash
uv run uvicorn analyst.api:app --port 8400
uv run streamlit run src/analyst/ui.py
```

To answer with Groq instead, set `LLM_PROVIDER=groq`, `LLM_MODEL=openai/gpt-oss-120b` and
`GROQ_API_KEY` in `.env`.

The pipeline is a numbered set of notebooks — see
**[`notebooks/README.md`](notebooks/README.md)**. All reusable logic lives in
`src/analyst/`, unit-tested and `mypy --strict` clean; the notebooks orchestrate it and
show the results.

### Checks

```bash
uv run pytest          # 99 tests
uv run ruff check .    # covers notebooks too
uv run mypy            # strict, over src/ and tests/
```

---

## Architecture — as built

```
 Streamlit --> FastAPI /api/v1/ask --> agent.ask()   (plain Python)
                                           |
   route (LLM, JSON) --- checked against Postgres: company, filing years, concept
     |  price --> fixed READ ONLY query --> change computed in Python
     |  advice / no filing --> refuse
     v
   retrieve: Qdrant, dense bge-small + query expansion, filtered by ticker + year
     v
   extract (LLM, JSON): "this figure, as printed, is in evidence block [n]"
     v
   verify (Python): is it printed in block [n]? is the unit printed?
     |  no --> one wider retrieval (k=20) --> still no --> refuse
     v
   compute (Python) --> answer + citations (element, page) + trace
```

Ingestion: prices and financials (yfinance) and annual-report PDFs (sha256-pinned) →
PyMuPDF elements with provenance → Postgres → chunks with a company + fiscal-year prefix
→ `bge-small` embeddings → Qdrant. Figures → `gemma3:4b` kind triage → described charts,
tables, infographics and diagrams indexed beside the text.

Details: [architecture overview](docs/architecture/overview.md).

---

## Results

### Retrieval — 44 generated questions ([`results/leaderboard.md`](results/leaderboard.md))

| dense retrieval, `bge-small` | R@5 | MRR | recall@200 |
|---|---|---|---|
| Day 3 baseline | 0.045 | 0.039 | 0.432 |
| + query expansion ([ADR-007](docs/adr/0007-retrieval-strategy.md)) | 0.068 | 0.056 | 0.682 |
| + company/year chunk prefix ([ADR-008](docs/adr/0008-contextual-chunk-prefixes.md)) | **0.318** | **0.243** | **1.000** |

Measured and **rejected**: three larger embedding models (the whole spread was two
questions) and a cross-encoder reranker (R@5 fell from 0.318 to 0.204).

### Answers — the same 44 + 16 generated unanswerable ([`results/answers.md`](results/answers.md))

| LLM | accuracy | wrong | false refusal | refusal of unanswerable | calls / question | p50 |
|---|---|---|---|---|---|---|
| local `llama3.2` (3B) | 0.227 | **0.568** | 0.205 | **1.000** | 2.1 | 4.6 s |

Every figure shown was printed on its cited page, and every unanswerable question was
refused. But 25 of 44 answers were **real figures from the wrong line** — standalone
instead of consolidated, a neighbouring row — and in 9 of those the right table was
retrieved and cited. The small model reads the wrong cell. A Groq
(`openai/gpt-oss-120b`) run is the next measurement. See
[ADR-009](docs/adr/0009-answer-generation.md).

---

## Limitations

- **The benchmark is small and templated:** 44 questions (the ≥100 target is not met), one
  anchor element each, generated from fixed question templates — an easy test for the
  router.
- **The verifier cannot catch a printed figure from the wrong row or column.** That is the
  dominant failure today.
- **Only figures are verified.** Prose claims are not, and figures under 4 significant
  digits cannot be verified, so they are refused.
- Figures are checked against chunk text held in the Qdrant payload — a verbatim copy of
  the database text, but not re-read from Postgres.
- **Vector-drawn charts are not extracted at all**, and figure descriptions are written by a
  vision model, not quoted from the report.
- Financial data comes from Yahoo Finance, a *normalisation* of the filed statements. The
  benchmark generator discards facts it cannot locate in the source document, so
  disagreements reduce coverage rather than corrupt the metrics.
- Not investment advice. The system retrieves and computes over public filings; it refuses
  requests for recommendations.

---

## Roadmap

| Day | Scope | Status |
|---|---|---|
| 1 | Scaffold, migrations, corpus, prices, financial oracle | done |
| 2 | Parser benchmark, typed element store, table extraction | done |
| 3 | Chunking, embeddings, Qdrant, auto-generated benchmark, baseline metrics | done |
| 4 | Embedding sweep, hybrid retrieval, query expansion, reranking — measured | done |
| 5 | Contextual chunk prefixes: R@5 0.068 → 0.318 | done |
| 6 | Agent + verifier, answer evaluation, figure triage, FastAPI + Streamlit | done — Groq run pending |
| 7 | Docker, CI, AWS deployment | not started |

Deferred by decision, not oversight: semantic caching, full observability stack,
Next.js frontend, performance tuning.

---

## Documentation

Full documentation lives in **[`docs/`](docs/)** and is maintained alongside the
code — see [docs/README.md](docs/README.md) for the maintenance policy.

| Document | Answers |
|---|---|
| [PRD](docs/product/prd.md) | What are we building, and what counts as done? |
| [SRS](docs/product/srs.md) | Every requirement, with how it is verified |
| [Architecture overview](docs/architecture/overview.md) | Components and how they fit |
| **[Data flow](docs/architecture/data-flow.md)** | **Where every byte comes from, how it is processed, how it is used** |
| [Storage](docs/architecture/storage.md) | Postgres vs Qdrant vs disk — and how vectors are stored |
| [API](docs/architecture/api.md) | Endpoints, schemas — and what was built |
| [Data sources](docs/data/sources.md) | Provenance, licensing, reliability |
| [Database schema](docs/data/schema.md) | Generated from the models |
| [Runbook](docs/operations/runbook.md) | How to run, rebuild and debug |
| [Changelog](docs/CHANGELOG.md) | What changed, when |

## Decisions

Architecture decision records live in [`docs/adr/`](docs/adr/).

| ADR | Decision |
|---|---|
| [001](docs/adr/0001-domain-and-corpus.md) | Indian listed equities; why the oracle drives the domain choice |
| [002](docs/adr/0002-llm-provider-stack.md) | Groq, Ollama and OpenRouter behind one interface — at ₹0 |
| [003](docs/adr/0003-provenance-schema.md) | Provenance attached at extraction time |
| [004](docs/adr/0004-pdf-parser.md) | PyMuPDF over pdfplumber — 30-60x faster, same oracle recall |
| [005](docs/adr/0005-vector-store.md) | Qdrant over pgvector |
| [006](docs/adr/0006-embedding-model.md) | `bge-small` kept — the embedding model is not the bottleneck |
| [007](docs/adr/0007-retrieval-strategy.md) | Query expansion adopted; reranking measured and rejected |
| [008](docs/adr/0008-contextual-chunk-prefixes.md) | Company + fiscal-year prefix on every chunk |
| [009](docs/adr/0009-answer-generation.md) | The LLM points, Python verifies — answer generation and grading |
| [010](docs/adr/0010-figures.md) | Figures triaged by kind, described, indexed beside the text |

---

## Licence

Code is MIT. The corpus is not redistributed — only the notebooks that fetch it.

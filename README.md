# Multimodal Agentic RAG — Indian Equity Research Analyst

A question-answering system over Indian listed-company filings that decides
**what kind of question it is** before deciding **how to retrieve**.

A "chat with PDF" app has one path: embed the question, cosine-search, stuff the
chunks into a prompt, generate. That path answers *"what risks does the report
mention?"* and quietly fabricates *"what was revenue in FY25?"*, because text
similarity is a poor retrieval mechanism for an exact number.

This system routes instead:

| Question | Path |
|---|---|
| "What risks does TCS's FY25 report flag about attrition?" | Document RAG |
| "Operating margin: TCS vs Infosys vs Wipro, last 3 years" | SQL + deterministic calculation |
| "What trend does the revenue chart on page 14 show?" | Vision (VLM over the extracted figure) |
| "How has RELIANCE traded since its FY25 report was published?" | SQL over price series + filing date |
| "R&D spend grew faster than revenue — quantify it and explain why" | SQL + Calculator + Document RAG + synthesis |

> **Status: Day 2 of 7.** This README describes what is *built*, not what is
> planned. See [Roadmap](#roadmap) for the honest state of each subsystem.

---

## Why this is not a toy

Two design commitments, both made on Day 1 because neither can be retrofitted:

1. **Arithmetic is never done by the language model.** Exact values live in
   Postgres; the Calculator agent operates on them in Python. The LLM explains
   the result, it does not compute it.
2. **Provenance is attached at extraction time.** Every element carries
   `document_id / page / element_id / bbox` from the moment it is parsed.
   Citations, explainability and the evaluation harness all depend on it, and it
   is unrecoverable if skipped. See [ADR-003](docs/adr/0003-provenance-schema.md).

And one that makes the project measurable rather than demo-able:

3. **The benchmark is generated, not hand-written.** Reported financials act as
   an oracle: take a known fact, search the parsed report for that number in
   Indian formats (`9,64,693` / `964,693` / `96,469.3`), and if it is found on
   page 118 you have an auto-labelled `(question, answer, source page)` triple.
   Mismatches filter themselves out. See [ADR-001](docs/adr/0001-domain-and-corpus.md).

---

## Corpus

12 companies, 4 sectors — chosen so cross-sector questions exercise the router.

| Sector | Companies |
|---|---|
| IT | TCS, INFY, WIPRO |
| Banking / NBFC | HDFCBANK, ICICIBANK, BAJFINANCE |
| Energy | RELIANCE, NTPC, ONGC |
| Pharma | SUNPHARMA, DRREDDY, CIPLA |

Scope changes in one place: [`configs/companies.yaml`](configs/companies.yaml).

**No data is committed to this repository.** `data/` is git-ignored and rebuilt
from the acquisition scripts, so the corpus is reproducible rather than vendored.

---

## Quickstart

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and Docker.

```bash
git clone https://github.com/PreeyasTumulu/MULTIMODAL_AGENTIC_RAG.git
cd MULTIMODAL_AGENTIC_RAG
cp .env.example .env
uv sync
docker compose up -d
uv run alembic upgrade head
uv run python scripts/acquire_prices.py
uv run python scripts/acquire_facts.py
```

Postgres binds host port **5433** (not 5432) to avoid colliding with an existing
local Postgres.

### Checks

```bash
uv run pytest
uv run ruff check .
uv run mypy
```

---

## Architecture

Built so far — the structured half of the corpus:

```
configs/companies.yaml                    configs/documents.yaml
        |                                          |
        v                                          v
  acquire_prices.py --> prices              download_docs.py  (sha256-pinned)
  acquire_facts.py  --> facts  <-- ORACLE          |
        |                                          v
        |                                   parse_documents.py
        |                                          |
        |                            +-------------+-------------+
        |                            v             v             v
        |                          text/        tables        figures
        |                         headings    (structured)   (PNG on disk)
        |                            |             |             |
        +----------------------------+------ elements ----------+
                                     |
                              PostgreSQL :5433
```

Joined on `ticker` + fiscal year: `facts.period_end` year == `documents.fiscal_year`.

Target, by Day 7:

```
                      FastAPI (stream, auth, rate-limit)
                              |
                         LangGraph
                              |
                     ROUTER (structured output)
        +----------+----------+----------+----------+
        v          v          v          v          v
    Document    Table       SQL       Vision    Calculator
     Agent      Agent      Agent      Agent   (deterministic)
        |          |          |          |          |
     Qdrant   Qdrant+PG   Postgres    figures    Python
        +----------+-----+----+----------+----------+
                         v
                     RERANKER (cross-encoder)
                         v
                   CONTEXT BUILDER
                         v
                    SYNTHESIZER
                         v
                     VERIFIER --- fails ---> "insufficient evidence"
                         v
             ANSWER + citations + reasoning trace
```

---

## Roadmap

| Day | Scope | Status |
|---|---|---|
| 1 | Scaffold, migrations, corpus, prices, financial oracle | done |
| 2 | Parser benchmark, typed element store, table extraction | done |
| 3 | Chunking, embeddings, Qdrant, **auto-generated benchmark**, baseline metrics | not started |
| 4 | Hybrid retrieval, reranking, measured improvement over baseline | not started |
| 5 | SQL agent (read-only, validated), calculator, price tool, vision agent | not started |
| 6 | LangGraph orchestration, verifier, FastAPI, Streamlit | not started |
| 7 | Docker, CI, AWS deployment, benchmark report | not started |

Deferred by decision, not oversight: semantic caching, full observability stack,
Next.js frontend, performance tuning.

---

## Decisions

Architecture decision records live in [`docs/adr/`](docs/adr/).

| ADR | Decision |
|---|---|
| [001](docs/adr/0001-domain-and-corpus.md) | Indian listed equities; why the oracle drives the domain choice |
| [002](docs/adr/0002-llm-provider-stack.md) | Groq primary, Ollama local, OpenRouter benchmark — at ₹0 |
| [003](docs/adr/0003-provenance-schema.md) | Provenance attached at extraction time |
| [004](docs/adr/0004-pdf-parser.md) | PyMuPDF over pdfplumber — 30-60x faster, same oracle recall |

---

## Limitations

- Financial data comes from Yahoo Finance, which is a *normalisation* of the
  filed statements and can differ from the annual report. The benchmark
  generator discards facts it cannot locate in the source document, so
  disagreements reduce coverage rather than corrupt the metrics.
- Not investment advice. The system retrieves and computes over public filings;
  it does not make recommendations.

## Licence

Code is MIT. The corpus is not redistributed — only the scripts that fetch it.

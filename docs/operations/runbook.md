# Runbook

How to run, rebuild, migrate and debug this system.

**Status:** ✅ current as of Day 2

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.12+ | |
| [uv](https://docs.astral.sh/uv/) | 0.11+ | Package manager and runner — replaces pip/venv/poetry |
| Docker | with Compose v2 | Docker Desktop on Windows |
| Ollama | optional until Day 3 | Local embeddings and vision |

`make` is **not** required and is not installed on the development machine.
Every command goes through `uv run`.

---

## First run

```bash
git clone https://github.com/PreeyasTumulu/MULTIMODAL_AGENTIC_RAG.git
cd MULTIMODAL_AGENTIC_RAG
cp .env.example .env
uv sync
docker compose up -d
uv run alembic upgrade head
```

Then load the corpus, in this order (later steps depend on earlier ones):

```bash
uv run python scripts/acquire_prices.py     # ~15 s  -> companies + prices
uv run python scripts/acquire_facts.py      # ~30 s  -> facts (the oracle)
uv run python scripts/download_docs.py      # ~2 min -> data/raw + documents
uv run python scripts/parse_documents.py    # ~5 min -> elements + data/figures
uv run python scripts/db_stats.py           # verify
```

`download_docs.py` will print two documents it cannot fetch — see
[Manual downloads](#manual-downloads).

---

## Everyday commands

| Task | Command |
|---|---|
| Run tests | `uv run pytest` |
| Lint | `uv run ruff check .` |
| Auto-fix lint | `uv run ruff check . --fix` |
| Type check | `uv run mypy` |
| Corpus status | `uv run python scripts/db_stats.py` |
| Prove the oracle join | `uv run python scripts/demo_oracle_link.py SUNPHARMA 2025` |
| Benchmark parsers | `uv run python scripts/benchmark_parsers.py` |
| Regenerate schema docs | `uv run python scripts/gen_schema_docs.py` |
| Add a dependency | `uv add <package>` |

**Before every commit:** `uv run pytest && uv run ruff check . && uv run mypy`

---

## Database

Postgres binds **host port 5433**, not 5432 — port 5432 is already occupied on
the development machine by another local Postgres.

```bash
docker compose up -d                      # start
docker compose ps                         # status
docker compose logs -f postgres           # logs
docker compose down                       # stop, keep data
docker compose down -v                    # stop and DESTROY the volume
```

Connect with psql:

```bash
docker compose exec postgres psql -U analyst -d analyst
```

> ⚠️ `docker compose exec -T` consumes heredoc stdin. To run a multi-statement
> script, use a Python script through `uv run` rather than piping SQL in.

### Migrations

```bash
uv run alembic upgrade head                          # apply
uv run alembic revision --autogenerate -m "message"  # create after a model change
uv run alembic downgrade -1                          # roll back one
uv run alembic current                               # what is applied
uv run alembic history                               # all revisions
```

**Always review a generated migration before applying it.** Autogenerate detects
column and index changes reliably; it does not always get type changes or
renames right — a rename is usually detected as a drop plus an add, which loses
data.

> Never use `Base.metadata.create_all()`. It cannot `ALTER`. It sees a table
> exists, does nothing, and the schema silently drifts from the models until a
> query fails hours later.

---

## Rebuilding after data loss

Everything except the manifest is derived state.

| Lost | Recover with |
|---|---|
| Whole database | `docker compose up -d && uv run alembic upgrade head`, then re-run the four acquisition scripts |
| `data/raw/` | `uv run python scripts/download_docs.py` — checksums verify integrity |
| `data/figures/` | `uv run python scripts/parse_documents.py` |
| `elements` | Same — element IDs are deterministic, so any index stays valid |

Full-reset:

```bash
docker compose down -v
rm -rf data/
docker compose up -d
uv run alembic upgrade head
# then the four acquisition scripts
```

---

## Manual downloads

`tcs.com` and `infosys.com` return HTTP 403 to any scripted request (Akamai
challenge), including with full browser headers and a `Referer`. Download each
once in a browser:

| Ticker | URL | Save as |
|---|---|---|
| TCS | `https://www.tcs.com/content/dam/tcs/investor-relations/financial-statements/2024-25/ar/annual-report-2024-2025.pdf` | `data\raw\TCS\TCS_annual_report_FY2025.pdf` |
| INFY | `https://www.infosys.com/investors/reports-filings/annual-report/annual/documents/infosys-ar-25.pdf` | `data\raw\INFY\INFY_annual_report_FY2025.pdf` |

Then `uv run python scripts/download_docs.py` pins their checksums, and
`parse_documents.py` picks them up.

---

## Troubleshooting

### `could not connect to server` on port 5433

Docker Desktop is not running, or the container is unhealthy.

```bash
docker ps
docker inspect --format '{{.State.Health.Status}}' agentic_rag_pg
docker compose logs postgres
```

### `operator does not exist: date = character varying`

A Python `str` was passed where Postgres expects a `date`. psycopg does not
coerce. Use `datetime.date(2025, 3, 31)`, not `"2025-03-31"`.

### Checksum mismatch on a document

The publisher replaced the file. Verify the new one is the right report, then
clear the `sha256` for that entry in `configs/documents.yaml` and re-run
`download_docs.py` to re-pin. **Do not delete the check** — it is what makes the
corpus reproducible.

### A financial figure looks ~85× too small

The company reports in a currency other than INR. Check:

```sql
SELECT ticker, financial_currency FROM companies WHERE financial_currency <> 'INR';
```

INFY reports in USD. Never infer currency from the `.NS` suffix.

### Latest close is `NULL` for one ticker

That ticker's most recent bar had a NaN close and was correctly dropped. Query
per-ticker, not against a global max date:

```sql
SELECT DISTINCT ON (ticker) ticker, trade_date, close
FROM prices ORDER BY ticker, trade_date DESC;
```

### `import fitz` deprecation warning

Use `import pymupdf`. `fitz` is the legacy alias.

### mypy complains about untyped calls into PyMuPDF

Expected — PyMuPDF ships no type stubs. The relaxation is scoped to the two
modules that touch it in `pyproject.toml`. Do not weaken it project-wide.

### Git Bash mangles a Python edit

Heredocs eat backslash escapes, and `sed` destroys invisible Unicode such as
NBSP. For those edits write a real `.py` fixer file and run it, rather than
inlining the change in a shell command.

---

## Ports

| Port | Service | Note |
|---|---|---|
| 5432 | *(another local Postgres)* | Not ours — avoided |
| **5433** | Project Postgres | |
| 6333 | Qdrant | Day 3 |
| 8000 | FastAPI | Day 6 |
| 8501 | Streamlit | Day 6 |
| 11434 | Ollama | Native Windows install |

---

## Environment variables

Defined in `.env`, loaded through `src/analyst/config.py`. Nothing else reads
`os.environ`.

| Variable | Default | Purpose |
|---|---|---|
| `POSTGRES_HOST` | `localhost` | |
| `POSTGRES_PORT` | `5433` | |
| `POSTGRES_USER` / `_PASSWORD` / `_DB` | `analyst` | |
| `GROQ_API_KEY` | — | Day 3 |
| `OPENROUTER_API_KEY` | — | Benchmark comparison |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | |
| `LOG_LEVEL` | `INFO` | |

> ⚠️ **No inline comments after a value.** `POSTGRES_PORT=5433  # dev` is parsed
> by some dotenv readers as the literal string `5433  # dev`, producing a
> confusing type error at startup.

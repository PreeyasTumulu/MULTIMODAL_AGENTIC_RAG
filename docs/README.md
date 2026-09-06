# Documentation

Everything about this system that is not the code itself.

## Read in this order

| # | Document | What it answers |
|---|---|---|
| 1 | [Product Requirements (PRD)](product/prd.md) | What are we building, for whom, and what counts as done? |
| 2 | [Software Requirements (SRS)](product/srs.md) | Precisely what must the system do, and how is each requirement verified? |
| 3 | [Architecture overview](architecture/overview.md) | What are the components and how do they fit together? |
| 4 | **[Data flow](architecture/data-flow.md)** | **Where does every byte come from, how is it processed, and how is it used?** |
| 5 | [Storage architecture](architecture/storage.md) | What lives in Postgres, in Qdrant, on disk — and why not all in one place? |
| 6 | [Data sources](data/sources.md) | Provenance, licensing and reliability of each source |
| 7 | [Database schema](data/schema.md) | Every table, column, constraint and index *(generated)* |
| 8 | [API specification](architecture/api.md) | Endpoints, schemas, errors, streaming |
| 9 | [Runbook](operations/runbook.md) | How to run, rebuild, migrate and debug it |
| 10 | [Decision records](adr/) | Why each significant choice was made, and what was rejected |
| 11 | **[Retrieval leaderboard](../results/leaderboard.md)** | **Every measured run, generated from the ledger** |
| 11 | [Changelog](CHANGELOG.md) | What changed, when |

---

## Status conventions

Every document carries a status line. This project is built in phases and the
docs describe **both** what exists and what is designed but not yet built — so
each section is marked:

| Marker | Meaning |
|---|---|
| ✅ **Built** | Implemented, tested, and running. Numbers quoted are measured. |
| 🔜 **Designed** | Decided and specified, not yet implemented. |
| 🧭 **Open** | Known question, deliberately unresolved. |

A document that quietly presents a plan as a fact is worse than no document.
If you find one, that is a bug.

---

## Maintenance policy

**Generated docs — never edit by hand:**

| File | Regenerate with |
|---|---|
| [`data/schema.md`](data/schema.md) | run [`notebooks/10_generate_docs.ipynb`](../notebooks/10_generate_docs.ipynb) |
| [`results/leaderboard.md`](../results/leaderboard.md) | run [`notebooks/08_evaluate_retrieval.ipynb`](../notebooks/08_evaluate_retrieval.ipynb) |

**Written docs — update when the matching thing changes:**

| If you change… | Update… |
|---|---|
| a SQLAlchemy model | run notebook 10 to regenerate `schema.md` |
| an acquisition or parsing notebook | [data-flow.md](architecture/data-flow.md) |
| a data source, URL or licence | [data/sources.md](data/sources.md) |
| a component, or how components talk | [architecture/overview.md](architecture/overview.md) |
| where something is stored | [architecture/storage.md](architecture/storage.md) |
| an API route or schema | [architecture/api.md](architecture/api.md) |
| a command needed to run the system | [operations/runbook.md](operations/runbook.md) |
| a retriever, an embedding model, or the benchmark | re-run notebook 08; the ledger appends |
| **any significant technical choice** | **write a new [ADR](adr/)** |

**Every phase ends with:** regenerate `schema.md`, flip the affected ✅/🔜
markers, add a `CHANGELOG.md` entry.

### Writing an ADR

Copy the shape of an existing one. Required sections: **Decision**, **Why**,
**Alternatives considered** (with the reason each was rejected), **Tradeoffs**
(including what was given up), **Consequences**. Number sequentially. An ADR is
never deleted — if it is reversed, a later ADR supersedes it and says so.

# ADR-008: Contextual chunk prefixes — the document side of the vocabulary gap

- **Status:** Proposed
- **Date:** 2026-09-08
- **Follows** [ADR-007](0007-retrieval-strategy.md), which fixed the *question*
  side of the vocabulary gap and named this as the next lever
- **Evidence:** [`notebooks/14_contextual_chunks.ipynb`](../../notebooks/14_contextual_chunks.ipynb),
  [`results/leaderboard.md`](../../results/leaderboard.md)

## Context

ADR-007 closed with a prediction:

> The answer element carries no company name, no fiscal year, and no statement
> title — a chunk prefix of `SUNPHARMA FY2024 - Statement of Profit and Loss`
> would give both halves of the retriever something to match.

Measured against the corpus, **one of those three claims is wrong and one is
misleading**, so the prefix that gets built is not the prefix that was predicted.

| ADR-007 claimed the chunk lacks | measured | verdict |
|---|---|---|
| a company name | 8.0% of answer chunks name it | **true** |
| a fiscal year | 74.6% of answer chunks name it | **mostly false** |
| a statement title | 99.9% of chunks carry a `heading` | **true, but not for the stated reason** |

The heading slot is not empty — it is occupied by something worse than empty.

## Decision

**Prefix every chunk with the company and fiscal year, in both vocabularies.
Strip page-furniture headings. Do not attempt to recover statement titles.**

`analyst.chunking.DocContext.prefix`:

```
Sun Pharmaceutical Industries (SUNPHARMA) FY2024 year ended March 31, 2024
```

Both forms are deliberate: `FY2024` is what the question asks, `year ended
March 31, 2024` is what an Indian filing prints. `expand_query` already adds the
same date form on the query side, so the two halves now meet in the middle.

## Why

### The headings are running page bands, not section titles

2,290 distinct headings over 9,976 chunks, and the distribution is the finding:

| heading | chunks |
|---|---|
| `CONSOLIDATED FINANCIAL STATEMENTS OF ICICI BANK LIMITED` | 507 |
| `STANDALONE FINANCIAL STATEMENTS OF ICICI BANK LIMITED` | 380 |
| `226 / Statutory Reports / Corporate Overview / Financial Statements` | — one of many page bands |

A quarter of all chunks carried a band like the last one. A string printed
identically on hundreds of chunks cannot help tell them apart; it only pulls
every vector toward a shared direction and spends encoder budget doing it.
`clean_heading` drops them, matching **whole lines only** so that
`CONSOLIDATED FINANCIAL STATEMENTS OF ICICI BANK LIMITED` — which does name the
company — survives while a bare `Financial Statements` band does not.

### Statement-title recovery was measured and rejected

The obvious implementation of ADR-007's prediction is to scan backwards from
each element for the nearest statement title. It does not work:

- a title is found for only **65%** of answer elements;
- of those, **2.9%** are on the element's own page;
- median distance back is **21 elements**;
- and most matches are prose, not titles — *"Refer consolidated statement of
  changes in equity for detailed movement in..."*, *"Strong balance sheet
  imparts ability to undertake inorganic initiatives"*.

Shipping it would have attached confident, wrong context more often than right
context. The prefix therefore carries only what is derivable with certainty from
`documents` and `companies`.

### A prefix is only affordable if the budget is real

The prefix is embedded with the passage, so it spends the same 512 tokens. That
forced a check of the budget, which was not being kept: **160 chunks (1.6%)
exceeded it, the largest at 5,116 characters** — roughly four times what the
encoder would read.

Day 3 capped the row-packing path. Three other paths had no cap:

1. a table whose `table_json` has no rows, falling through to raw text;
2. a single text element larger than the whole target, never split;
3. **a table whose header is itself oversized** — the worst is 3,328 characters
   across 3 cells, an infographic page the table detector flattened. The header
   is repeated on every slice by design, so every slice of that table blew the
   limit no matter how few rows it held.

Fixed by giving every path the same budget, splitting on line boundaries, and
abandoning header-repetition when the header leaves no room for a row. This is
why the experiment has a `fix` arm: it holds the truncation fix constant so the
prefix is not credited with un-truncating 136 chunks.

## Results

| arm | budget fix | furniture stripped | context prefix |
|---|---|---|---|
| `elements_bge-small` (ADR-007) | no | no | no |
| `fix` | yes | no | no |
| `ctx` | yes | yes | yes |

_Numbers pending the indexing run; this ADR stays **Proposed** until they land._

## Tradeoffs

- **Accepted — the prefix is constant within a filtered pool.** Under the default
  `ticker+year` policy the candidate set is already scoped to one company and one
  document-year, so the prefix adds the same string to every candidate and cannot
  discriminate between them. Its upside is concentrated where the filter is not
  doing that work: growth questions (which are deliberately not year-filtered)
  and any production query arriving without metadata. **There is a real
  possibility this measures flat or slightly negative at `ticker+year`, and that
  is a result, not a failure of the experiment.**
- **Accepted — dropping headings loses real titles too.** The furniture filter is
  a line-anchored allowlist-by-exclusion, not a classifier. It is tuned to be
  conservative, but it will occasionally drop a genuine one-word section title.
- **Given up — statement titles.** The most informative context available is
  still not attached to chunks. Recovering it properly needs layout-aware
  parsing (a table-of-contents pass, or font-size heuristics on the heading
  elements), which is out of scope for this build.
- **Cost:** a full re-index per arm, ~30 minutes each on this machine.

## Consequences

- `Chunk` grows `context`, and `Chunk.embed_text` is what gets embedded while
  `Chunk.text` stays the verbatim passage. Citations quote the document, never
  the prefix we assembled — the prefix must not leak into provenance.
- `chunk_document` takes `context` and `strip_furniture`, both defaulting to the
  pre-ADR-008 behaviour, so the baseline arm is reproducible by construction.
- Collections gain a `variant` segment (`elements_ctx_bge-small`). Existing
  collection names are unchanged when no variant is given.
- The parser flattening an infographic page into a 3-cell table with a 3,328
  character header is a **data-quality bug in `analyst.parsing`**, worked around
  here rather than fixed. Worth its own look.

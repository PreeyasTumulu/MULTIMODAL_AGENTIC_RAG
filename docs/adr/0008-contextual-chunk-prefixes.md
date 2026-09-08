# ADR-008: Contextual chunk prefixes — the document side of the vocabulary gap

- **Status:** Accepted
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

Three arms, `bge-small`, `ticker+year`, query expansion on everywhere, the same
44 questions (`bench_sha 2c4aedf3dcb75f7e` on all six runs):

| arm | budget fix | furniture stripped | context prefix |
|---|---|---|---|
| `elements_bge-small` (ADR-007) | no | no | no |
| `fix` | yes | no | no |
| `ctx` | yes | yes | yes |

| retriever | R@1 | R@5 | R@10 | MRR | @50 | @100 | **@200** | p50 |
|---|---|---|---|---|---|---|---|---|
| dense+expand (ADR-007) | 0.045 | 0.068 | 0.114 | 0.056 | 0.364 | 0.477 | 0.682 | 88 ms |
| dense+expand `[fix]` | 0.045 | 0.068 | 0.114 | 0.056 | 0.364 | 0.455 | 0.682 | 94 ms |
| **dense+expand `[ctx]`** | **0.182** | **0.318** | **0.455** | **0.243** | 0.795 | 0.841 | **1.000** | 101 ms |
| hybrid+expand (ADR-007) | 0.045 | 0.068 | 0.091 | 0.054 | 0.477 | 0.614 | 0.727 | 91 ms |
| hybrid+expand `[fix]` | 0.045 | 0.068 | 0.091 | 0.054 | 0.455 | 0.614 | 0.727 | 99 ms |
| hybrid+expand `[ctx]` | 0.159 | 0.341 | 0.409 | 0.229 | 0.795 | 0.864 | 0.977 | 99 ms |

**The control arm did its job and reported nothing.** `fix` is identical to
ADR-007 on every headline metric — the encoder-budget bug was real, but fixing
160 truncated chunks moved no number. That is what makes the rest attributable.

**`ctx` is the largest movement measured in this project.** R@5 0.068 -> 0.318,
MRR 0.056 -> 0.243, and **recall at depth 200 reaches 1.000** — every one of the
44 answer elements is now retrieved. Growth questions, unsolved since Day 4, go
**5/10 -> 10/10**; value lookups 33/34.

Note dense now beats hybrid at depth (1.000 vs 0.977) and on MRR, reversing
ADR-007. RRF at a fixed cut can still drop a deep dense hit, and with the pool
this good that costs more than the lexical half adds.

### Why it worked — not the reason ADR-007 assumed

ADR-007 expected the prefix to *add* a matching signal. What actually dominated
is that furniture stripping *removed a distractor*. The canonical question,
top 5, before and after:

```
fix : 0.832  Consolidated Statement of Cash Flow | for the year ended March 31, 2024 | Sun Pharmaceutical Indus...
      0.831  for the year ended March 31, 2024 | 6 | 541.8 | ... Sun Pharmaceutical Industries (Aus...
      0.823  Notes to the Consolidated Financial Statements | for the year ended March 31, 2024 | Sun Pharmaceu...

ctx : 0.936  | Year ended | March 31, 2024 | Year ended | March 31, 2023 | Revenue from contracts with customers   <== CORRECT
```

`expand_query` appends the company name and `year ended March 31, <fy>`. Those
are exactly the words printed in the running page bands — so the furniture was
manufacturing high-scoring false positives on hundreds of irrelevant pages, and
the more the query was expanded the better the furniture scored. **Query
expansion and page furniture were interacting badly, and ADR-007's headline gain
was being suppressed by it.**

⚠️ **This experiment does not separate the two changes.** `ctx` strips furniture
*and* adds the prefix; there is no arm with one and not the other. The evidence
above points strongly at stripping, but pointing strongly is not measuring. A
`strip` arm (furniture removed, no prefix) would settle it and costs one
dense re-index (~25 min). **Until that runs, the honest claim is "the pair is
worth +0.25 R@5", not "the prefix is."**

## Tradeoffs

- **A prediction recorded here before the run was wrong.** It argued that under
  `ticker+year` the pool is already one company and one document-year, so a
  constant prefix cannot discriminate and the result would likely be "flat or
  slightly negative". The reasoning about the prefix was sound as far as it went;
  it missed that the other half of the change — stripping furniture — is *not*
  constant across the pool, and that it removes an active distractor rather than
  adding a signal. The measured jump is the largest in the project.
  **This is the second time on this project that predicting the mechanism went
  wrong while measuring it went right** (see ADR-007 on BM25 and reranking).
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

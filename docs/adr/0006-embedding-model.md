# ADR-006: Choosing the embedding model by measurement

- **Status:** Proposed — the decision rule below is fixed; the sweep has not run yet
- **Date:** 2026-09-06
- **Resolves the forward reference in** [ADR-005](0005-vector-store.md)

## Decision

**The decision rule is recorded before the numbers, not after.** Every candidate
in `analyst.embedding.MODELS` is indexed as its own collection and scored on the
same 44 questions. The winner is the model with the highest **Recall@5**; ties
inside ±0.02 (one question on a 44-question benchmark) go to the smaller model,
because the deployment target has no GPU.

Runs append to `results/runs.jsonl` and the table regenerates into
`results/leaderboard.md`, so this ADR cites a file rather than a screenshot.

| candidate | dim | size | why it is here |
|---|---|---|---|
| `bge-small-en-v1.5` | 384 | 0.07 GB | Day 3 baseline. R@5 **0.045** |
| `bge-base-en-v1.5` | 768 | 0.21 GB | Same family, ~2× bigger. Isolates *capacity* |
| `snowflake-arctic-embed-s` | 384 | 0.13 GB | Different family, tuned for retrieval |
| `all-MiniLM-L6-v2` | 384 | 0.09 GB | The common default. Included to be beaten |

## Why measure at all, given the baseline

The Day 3 depth curve is the reason to keep expectations low, and to run the
sweep anyway.

**25 of 44 questions have no correct element anywhere in the top 200** (recall
0.432 at depth, corrected — the figure first recorded, 0.273, came from an
unfiltered run compared against a filtered headline; see the CHANGELOG). The
failure is not ranking; it is that near-identical numeric table rows collapse
together in embedding space. A larger model in the same family reshuffles ranks
— it does not obviously fix that. So this sweep is expected to produce a *small*
delta, and hybrid sparse retrieval remains the main Day 4 lever.

Recording that expectation now is the point. If `bge-base` does move recall
materially, the prediction was wrong in an interesting way; if it does not, the
project has evidence for its model choice instead of a preference.

Two questions the sweep answers either way:

- **Does dimension buy recall here?** 384 → 768 doubles index size and query
  cost. On this corpus it may buy nothing.
- **Is the family or the size doing the work?** `arctic-s` is a different family
  at the same 384 dimensions, which separates the two.

## Alternatives considered

| Option | Verdict |
|---|---|
| **Pick by MTEB leaderboard** | Rejected — MTEB is not Indian annual reports, and the failure mode here is numeric tables, which no general benchmark measures. Cheap and unjustifiable. |
| **BGE-M3 / e5-large** | Rejected for now. Strong models, but 2+ GB and slow on CPU; the AWS free-tier target has no GPU, so a model that cannot be deployed is not a candidate. |
| **A financial-domain fine-tune** | Out of scope in a one-week build. Worth revisiting once hybrid retrieval sets an honest ceiling. |
| **Skip the sweep, go straight to hybrid** | Tempting, and defensible on expected payoff. Rejected because the sweep is ~30 min per model of *unattended* compute and the cost is attention, not time — and an unmeasured model choice is the exact thing this project exists to avoid. |

## Tradeoffs

- **Given up:** ~2 hours of unattended indexing and roughly 1 GB of disk across
  four collections.
- **Given up:** breadth. Only CPU-deployable models are tested, so the sweep
  cannot say what the best available embedding model is — only the best one that
  can actually ship here.
- **Accepted:** the benchmark is single-anchor, so all four models are scored
  strictly and identically. The ranking is trustworthy; the absolute numbers are
  a floor.

## Consequences

- `analyst.embedding.DEFAULT_MODEL` changes only if the sweep says so, and this
  ADR is updated to **Accepted** with the winning row.
- Losing collections are dropped after the decision. The ledger keeps the
  evidence, so nothing is lost by deleting the vectors.
- The same ledger measures Day 4's hybrid and reranked retrievers, which is what
  makes "hybrid beat dense by X" a comparison rather than an assertion.

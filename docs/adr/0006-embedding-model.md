# ADR-006: Choosing the embedding model by measurement

- **Status:** Accepted — sweep run 2026-09-06; **`bge-small` retained**
- **Date:** 2026-09-06
- **Resolves the forward reference in** [ADR-005](0005-vector-store.md)
- **Evidence:** [`results/leaderboard.md`](../../results/leaderboard.md), generated from
  [`results/runs.jsonl`](../../results/runs.jsonl)

## Decision

**Keep `bge-small-en-v1.5`.** All four candidates were indexed as full 9,982-point
collections and scored on the same 44 questions. Nothing beat the incumbent by a
margin this benchmark can resolve.

| model | dim | R@1 | R@5 | R@10 | MRR | p50 | index time |
|---|---|---|---|---|---|---|---|
| `bge-base` | 768 | 0.000 | **0.091** | 0.114 | 0.030 | 396 ms | **96 min** |
| `minilm` | 384 | **0.045** | 0.068 | 0.114 | **0.056** | 20 ms | ~25 min |
| **`bge-small`** | 384 | 0.023 | 0.045 | 0.091 | 0.039 | 85 ms | ~30 min |
| `arctic-s` | 384 | 0.023 | 0.045 | 0.045 | 0.034 | 14 ms | **20 min** |

## Why not `bge-base`, which "won"

**The pre-registered rule picks `bge-base`. Following it would have been wrong,
and the rule was the thing at fault.**

The rule said *highest Recall@5 wins, ties inside 0.02 go to the smaller model*.
On 44 questions **one question is worth 0.023**, so the tie-band was narrower
than the smallest difference that can exist. It could not help but declare a
winner. That is a flaw in how the rule was written, not a finding — and writing
it down beforehand is what made the flaw visible instead of invisible.

The evidence against acting on it:

- **The whole spread is two questions.** R@5 of 0.091 is 4 questions of 44;
  0.045 is 2. Every 95% interval overlaps every other: `bge-base`
  [0.006, 0.176] against `bge-small` [0.000, 0.107].
- **The hits do not nest.** `bge-base` found 3 questions `bge-small` missed and
  *missed one `bge-small` found*. A genuinely better model would be close to a
  superset. This is reshuffling.
- **It wins the chosen metric and loses the others.** `bge-base` is last on MRR
  (0.030) and last on R@1 (**0.000** — it never ranks a correct answer first).
  That pattern is the signature of noise.
- **It costs 3-5x more.** 96 minutes to index against 20-25, and 396 ms per
  query against 14-20, on a deploy target with no GPU.

## The result that actually mattered

**38 of 44 questions are retrieved by no model at all.** The union of all four
is 6 questions. Every hit belongs to RELIANCE or ICICIBANK; **SUNPHARMA supplies
24 of the 44 questions and scores zero on every model.**

So the sweep's real value is negative evidence, and that was worth 2.5 hours:
**the embedding model is not the bottleneck.** It closes off buying a bigger
encoder — the obvious, expensive next move — before a week goes into it. The
cause turned out to be a vocabulary mismatch between question and filing, which
[ADR-007](0007-retrieval-strategy.md) addresses.

## Alternatives considered

| Option | Verdict |
|---|---|
| **Adopt `bge-base` per the rule** | Rejected. Two questions, non-nesting, worse on MRR and R@1, 5x the index cost. Following a rule whose premise has failed is not rigour. |
| **Adopt `minilm`** | Genuinely tempting — best MRR (0.056), best R@1, 20 ms queries. Rejected on the same logic: one question of separation is not evidence. Revisit if the benchmark grows. |
| **Pick by MTEB leaderboard** | Rejected before the sweep and vindicated by it. MTEB is not Indian annual reports, and the failure here is numeric tables, which no general benchmark measures. |
| **BGE-M3 / e5-large** | Rejected: 2+ GB, slow on CPU, and the free-tier target has no GPU. A model that cannot deploy is not a candidate. |

## Tradeoffs

- **Given up:** ~2.5 hours of unattended indexing and ~1 GB across four
  collections, to learn that the variable does not matter. That is a real cost
  and the right trade — the alternative was guessing.
- **Given up:** breadth. Only CPU-deployable models were tested, so this says
  nothing about the best embedding model in general — only the best one that can
  ship here.
- **Accepted:** a 44-question benchmark cannot resolve differences smaller than
  ~0.05 recall. Any future model comparison needs either a bigger benchmark or a
  much larger effect.

## Consequences

- `analyst.embedding.DEFAULT_MODEL` stays `bge-small`.
- The losing collections can be dropped; the ledger keeps the evidence, so
  deleting the vectors loses nothing.
- **Any future "should we swap the model?" question is already answered** unless
  the benchmark grows or retrieval quality changes character.
- The next ADR takes up what the sweep exposed: the question and the filing do
  not use the same words.

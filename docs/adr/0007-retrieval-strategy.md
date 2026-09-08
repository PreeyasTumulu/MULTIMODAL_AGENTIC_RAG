# ADR-007: Retrieval strategy — query expansion in, reranking out

- **Status:** Accepted
- **Date:** 2026-09-06
- **Follows** [ADR-006](0006-embedding-model.md), which established that the
  embedding model is not the bottleneck
- **Evidence:** [`results/leaderboard.md`](../../results/leaderboard.md)

## Decision

**Adopt query expansion. Keep hybrid sparse only in combination with it. Do not
ship the cross-encoder reranker.**

All measured on `bge-small`, `ticker+year` filters, the same 44 questions:

| retriever | R@5 | R@10 | MRR | @50 | @100 | **@200** | p50 |
|---|---|---|---|---|---|---|---|
| dense (baseline) | 0.045 | 0.091 | 0.039 | 0.227 | 0.273 | 0.432 | 85 ms |
| hybrid | 0.068 | 0.114 | 0.045 | 0.205 | 0.273 | 0.364 | 90 ms |
| dense+expand | 0.068 | **0.114** | **0.056** | 0.364 | 0.477 | 0.682 | 88 ms |
| hybrid+expand | 0.068 | 0.091 | 0.054 | **0.477** | **0.614** | **0.727** | 91 ms |
| dense+expand+rerank | **0.091** | 0.091 | 0.046 | — | — | — | 5,314 ms |
| hybrid+expand+rerank | **0.091** | 0.091 | 0.046 | — | — | — | 5,381 ms |

## Why

### The diagnosis: a vocabulary gap, not a retrieval failure

Four embedding models failed at the same place, which is the clue — when
changing the technique changes nothing, the technique is not the problem.

**A question and the element answering it share a median of two words.**

- Question: *"What was Sun Pharmaceutical Industries's total revenue in FY2024?"*
- Answer element: `| Year ended | March 31, 2024 | Revenue from contracts with
  customers (Refer note 53) | 477,584.5 | ...`

No retriever bridges that, dense or lexical, because the words are genuinely
different. `CONCEPT_ALIASES` in `analyst/benchmark.py` already held the mapping —
it is how notebook 06 located every anchor — and the retriever had never used it
at query time. Expansion adds those labels plus `year ended March 31, <fy>`,
because an Indian filing never prints the string "FY2024".

**Recall at depth 200 went 0.432 to 0.727.** 19 findable questions became 32.
SUNPHARMA went from 0 to 17 of 24; growth questions from 0 to 5 of 10. Nothing
else tried in this project moved a number that far.

### Why hybrid only in combination

Sparse retrieval alone **lowered** the ceiling (0.432 to 0.364). The argument
for BM25 had been that a figure like `520,412.5` is a unique token — but
**0 of 44 questions contain the figure they ask for.** The number exists only in
the document, so BM25 had almost nothing to match, and RRF fusion at a fixed cut
pushed genuine deep dense hits out of the list.

With expansion supplying real vocabulary, the lexical half finally has words to
grip, and hybrid gives the best pool at depth (0.727 against 0.682). It earns
its place only in that combination.

### Why the reranker does not ship

A cross-encoder was the obvious next step: the pool is now rich (61% of answers
inside the top 100) and ranking is the weak part. It did not work.

It gains one question at R@5, **loses** one at R@10, **drops MRR** (0.056 to
0.046), and costs **60x the latency** (5,314 ms against 88 ms).

The cause is domain, not capability: `ms-marco-MiniLM-L-6-v2` is trained on
MS MARCO web prose, and our passages are grids of numbers. A general reranker
has nothing useful to say about `| Year ended | March 31, 2024 | 477,584.5 |`.

### Re-measured after ADR-008 — the decision holds, and hardens

This rejection was made when recall@100 was 0.477, and the stated reason to
revisit it was that a cross-encoder is capped by recall at the shortlist depth.
[ADR-008](0008-contextual-chunk-prefixes.md) moved recall@100 to 0.841, so the
reranker was re-run on that index (`notebooks/13_reranking.ipynb`, depth 100):

| inner retriever | R@5 | R@10 | MRR |
|---|---|---|---|
| dense+expand (this ADR) | 0.068 -> 0.091 **(+0.023)** | 0.114 -> 0.091 (-0.023) | 0.056 -> 0.046 |
| hybrid+expand (this ADR) | 0.068 -> 0.091 **(+0.023)** | 0.091 -> 0.091 (0.000) | 0.054 -> 0.046 |
| dense+expand `[ctx]` | 0.318 -> 0.204 **(-0.114)** | 0.455 -> 0.341 (-0.114) | 0.243 -> 0.097 |
| hybrid+expand `[ctx]` | 0.341 -> 0.114 **(-0.227)** | 0.409 -> 0.182 (-0.227) | 0.209 -> 0.061 |

**A better pool made the reranker worse, not better.** The hypothesis behind
re-testing — raise the ceiling and the reranker starts paying — was wrong.

The reason is visible in the reranked column alone: 0.091, 0.091, 0.204, 0.114
at R@5 and 0.046, 0.046, 0.097, 0.061 at MRR. **The reranked result barely
depends on what it was given.** A cross-encoder does not refine an ordering, it
*replaces* it, so what it is worth is `reranker quality - retriever quality`.
Against near-random retrieval its own noise was roughly break-even; against a
retriever that now works it destroys real signal, costing up to ten questions
at R@5 and more than half the MRR.

**Recall at shortlist depth was never the binding constraint — the reranker's own
domain competence was.** That reframes the open option below: `bge-reranker-base`
is not "the same idea but bigger", it is a bet on the one variable that actually
matters, and a general-purpose reranker of any size is the thing in doubt.

(Latency also improved, 5,314 ms -> 4,029 ms, because ADR-008's chunks are
shorter on average. Still ~44x un-reranked, and still irrelevant given the
accuracy went backwards.)

## Alternatives considered

| Option | Verdict |
|---|---|
| **Ship the reranker anyway** | Rejected. 60x latency for one question, with MRR going the wrong way. |
| **`bge-reranker-base`** | Plausibly better and 1 GB — too large for the GPU-less target, and the domain objection likely still applies. Open, not chosen. |
| **Tune RRF weights / prefetch depth** | Deferred. Real headroom, but tuning a fusion knob is worth less than fixing the chunks (below). |
| **A financial-domain reranker fine-tune** | Out of scope for a one-week build. The honest option if reranking is revisited. |

## Tradeoffs

- **Given up:** the reranker's index-time-free accuracy. Reranking stays in the
  package (`analyst.retrievers.reranked`, tested) but is not in the default path.
- **Accepted:** expansion is **benchmark-shaped**. It uses `CONCEPT_ALIASES`,
  which exist because the benchmark needed them. A free-text user question has
  no `concept` field, so production needs the aliases chosen by a classifier or
  an LLM — cheap, but it is work, and it is not what was measured here.
  **This is the most important caveat in this ADR.**
- **Accepted:** absolute quality is still poor. R@5 of 0.091 is 4 questions of
  44. The pool improved dramatically; shallow ranking did not.

## Consequences

- Default retrieval becomes **hybrid + query expansion**.
- **The next lever is the chunks, not the query.** Expansion fixed the question
  side of the vocabulary gap; the document side is untouched. The answer element
  above carries no company name, no fiscal year, and no statement title — a
  chunk prefix of `SUNPHARMA FY2024 - Statement of Profit and Loss` would give
  both halves of the retriever something to match. That needs a re-index and is
  the first thing to try next.
- Growth questions remain unsolved by construction: their evidence spans two
  annual reports, and no single chunk contains the answer. That is multi-document
  reasoning, an agent problem rather than a retrieval one.

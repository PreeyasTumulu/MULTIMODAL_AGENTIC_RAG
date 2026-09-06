# Retrieval leaderboard

Generated from `results/runs.jsonl` by `analyst.evaluation`. Never edit by hand.

> Ground truth is **single-anchor**: each question names one element holding the
> answer, so a different page that also states it scores as a miss. Every row is
> strict the same way, so the deltas are fair; no number here is absolute quality.

| run | retriever | model | filters | R@1 | R@3 | R@5 | R@10 | MRR | pR@5 | p50 ms | bench | git |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dense-bge-base-b8c50be6 | dense | `bge-base` | `ticker+year` | 0.000 | 0.045 | 0.091 | 0.114 | 0.030 | 0.159 | 396 | `2c4aedf3` | `3e65907-dirty` |
| dense-minilm-d66ffa93 | dense | `minilm` | `ticker+year` | 0.045 | 0.045 | 0.068 | 0.114 | 0.056 | 0.114 | 20 | `2c4aedf3` | `3e65907-dirty` |
| hybrid-bge-small-ee1a298f | hybrid | `bge-small` | `ticker+year` | 0.023 | 0.068 | 0.068 | 0.114 | 0.045 | 0.114 | 90 | `2c4aedf3` | `3e65907-dirty` |
| dense-bge-small-02c4b4ed | dense | `bge-small` | `ticker+year` | 0.023 | 0.045 | 0.045 | 0.091 | 0.039 | 0.091 | 85 | `2c4aedf3` | `3e65907-dirty` |
| dense-bge-small-6cbee6af | dense | `bge-small` | `none` | 0.023 | 0.045 | 0.045 | 0.091 | 0.035 | 0.091 | 85 | `2c4aedf3` | `3e65907-dirty` |
| dense-bge-small-73d5667f | dense | `bge-small` | `ticker` | 0.023 | 0.045 | 0.045 | 0.091 | 0.035 | 0.091 | 88 | `2c4aedf3` | `3e65907-dirty` |
| dense-arctic-s-d7b2c355 | dense | `arctic-s` | `ticker+year` | 0.023 | 0.045 | 0.045 | 0.045 | 0.034 | 0.045 | 14 | `2c4aedf3` | `3e65907-dirty` |

## Recall by search depth

Where this flattens is the ceiling for anything that only reorders results.

| run | 1 | 5 | 10 | 20 | 50 | 100 | 200 |
|---|---|---|---|---|---|---|---|
| dense-bge-small-02c4b4ed | 0.023 | 0.045 | 0.091 | 0.136 | 0.227 | 0.273 | 0.432 |
| dense-bge-small-6cbee6af | 0.023 | 0.045 | 0.091 | 0.136 | 0.182 | 0.273 | 0.273 |
| dense-bge-small-73d5667f | 0.023 | 0.045 | 0.091 | 0.136 | 0.182 | 0.273 | 0.273 |
| dense-bge-base-b8c50be6 | 0.000 | 0.091 | 0.114 | 0.182 | 0.182 | 0.227 | 0.432 |
| dense-arctic-s-d7b2c355 | 0.023 | 0.045 | 0.045 | 0.045 | 0.091 | 0.159 | 0.341 |
| dense-minilm-d66ffa93 | 0.045 | 0.068 | 0.114 | 0.136 | 0.227 | 0.227 | 0.318 |
| hybrid-bge-small-ee1a298f | 0.023 | 0.091 | 0.114 | 0.114 | 0.204 | 0.273 | 0.364 |

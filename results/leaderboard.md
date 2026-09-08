# Retrieval leaderboard

Generated from `results/runs.jsonl` by `analyst.evaluation`. Never edit by hand.

> Ground truth is **single-anchor**: each question names one element holding the
> answer, so a different page that also states it scores as a miss. Every row is
> strict the same way, so the deltas are fair; no number here is absolute quality.

| run | retriever | model | filters | R@1 | R@3 | R@5 | R@10 | MRR | pR@5 | p50 ms | bench | git |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hybrid+expand[ctx]-bge-small-8cefefeb | hybrid+expand[ctx] | `bge-small` | `ticker+year` | 0.159 | 0.250 | 0.341 | 0.409 | 0.229 | 0.364 | 99 | `2c4aedf3` | `917bfe7-dirty` |
| hybrid+expand[ctx]-bge-small-21b256e5 | hybrid+expand[ctx] | `bge-small` | `ticker+year` | 0.114 | 0.273 | 0.341 | 0.409 | 0.209 | 0.364 | 90 | `2c4aedf3` | `a715497-dirty` |
| dense+expand[ctx]-bge-small-1ba71392 | dense+expand[ctx] | `bge-small` | `ticker+year` | 0.182 | 0.227 | 0.318 | 0.455 | 0.243 | 0.364 | 101 | `2c4aedf3` | `917bfe7-dirty` |
| dense+expand[ctx]-bge-small-f1b65882 | dense+expand[ctx] | `bge-small` | `ticker+year` | 0.182 | 0.227 | 0.318 | 0.455 | 0.243 | 0.364 | 92 | `2c4aedf3` | `a715497-dirty` |
| dense-bge-base-b8c50be6 | dense | `bge-base` | `ticker+year` | 0.000 | 0.045 | 0.091 | 0.114 | 0.030 | 0.159 | 396 | `2c4aedf3` | `3e65907-dirty` |
| dense+expand+rerank-bge-small-b261fe8f | dense+expand+rerank | `bge-small` | `ticker+year` | 0.023 | 0.068 | 0.091 | 0.091 | 0.046 | 0.136 | 5314 | `2c4aedf3` | `2f3c9a3-dirty` |
| hybrid+expand+rerank-bge-small-51aef45a | hybrid+expand+rerank | `bge-small` | `ticker+year` | 0.023 | 0.068 | 0.091 | 0.091 | 0.046 | 0.136 | 5381 | `2c4aedf3` | `2f3c9a3-dirty` |
| dense-minilm-d66ffa93 | dense | `minilm` | `ticker+year` | 0.045 | 0.045 | 0.068 | 0.114 | 0.056 | 0.114 | 20 | `2c4aedf3` | `3e65907-dirty` |
| hybrid-bge-small-ee1a298f | hybrid | `bge-small` | `ticker+year` | 0.023 | 0.068 | 0.068 | 0.114 | 0.045 | 0.114 | 90 | `2c4aedf3` | `3e65907-dirty` |
| dense+expand-bge-small-b60d0b39 | dense+expand | `bge-small` | `ticker+year` | 0.045 | 0.045 | 0.068 | 0.114 | 0.056 | 0.136 | 88 | `2c4aedf3` | `2f3c9a3-dirty` |
| hybrid+expand-bge-small-6510b044 | hybrid+expand | `bge-small` | `ticker+year` | 0.045 | 0.045 | 0.068 | 0.091 | 0.054 | 0.114 | 91 | `2c4aedf3` | `2f3c9a3-dirty` |
| dense+expand[fix]-bge-small-372bacbe | dense+expand[fix] | `bge-small` | `ticker+year` | 0.045 | 0.045 | 0.068 | 0.114 | 0.056 | 0.136 | 94 | `2c4aedf3` | `917bfe7` |
| hybrid+expand[fix]-bge-small-81fcddac | hybrid+expand[fix] | `bge-small` | `ticker+year` | 0.045 | 0.045 | 0.068 | 0.091 | 0.054 | 0.114 | 99 | `2c4aedf3` | `917bfe7-dirty` |
| dense+expand[fix]-bge-small-21c3af53 | dense+expand[fix] | `bge-small` | `ticker+year` | 0.045 | 0.045 | 0.068 | 0.114 | 0.056 | 0.136 | 90 | `2c4aedf3` | `a715497-dirty` |
| hybrid+expand[fix]-bge-small-163a5715 | hybrid+expand[fix] | `bge-small` | `ticker+year` | 0.045 | 0.045 | 0.068 | 0.091 | 0.055 | 0.114 | 92 | `2c4aedf3` | `a715497-dirty` |
| dense-bge-small-02c4b4ed | dense | `bge-small` | `ticker+year` | 0.023 | 0.045 | 0.045 | 0.091 | 0.039 | 0.091 | 85 | `2c4aedf3` | `3e65907-dirty` |
| dense-bge-small-6cbee6af | dense | `bge-small` | `none` | 0.023 | 0.045 | 0.045 | 0.091 | 0.035 | 0.091 | 85 | `2c4aedf3` | `3e65907-dirty` |
| dense-bge-small-73d5667f | dense | `bge-small` | `ticker` | 0.023 | 0.045 | 0.045 | 0.091 | 0.035 | 0.091 | 88 | `2c4aedf3` | `3e65907-dirty` |
| dense-arctic-s-d7b2c355 | dense | `arctic-s` | `ticker+year` | 0.023 | 0.045 | 0.045 | 0.045 | 0.034 | 0.045 | 14 | `2c4aedf3` | `3e65907-dirty` |
| dense+expand[strip]-bge-small-cc4276b5 | dense+expand[strip] | `bge-small` | `ticker+year` | 0.045 | 0.045 | 0.045 | 0.091 | 0.050 | 0.114 | 90 | `2c4aedf3` | `a715497-dirty` |

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
| dense+expand-bge-small-b60d0b39 | 0.045 | 0.068 | 0.114 | 0.159 | 0.364 | 0.477 | 0.682 |
| hybrid+expand-bge-small-6510b044 | 0.000 | 0.045 | 0.114 | 0.159 | 0.477 | 0.614 | 0.727 |
| dense+expand[fix]-bge-small-372bacbe | 0.045 | 0.068 | 0.114 | 0.159 | 0.364 | 0.455 | 0.682 |
| hybrid+expand[fix]-bge-small-81fcddac | 0.023 | 0.045 | 0.091 | 0.159 | 0.455 | 0.614 | 0.727 |
| dense+expand[ctx]-bge-small-1ba71392 | 0.182 | 0.318 | 0.455 | 0.636 | 0.795 | 0.841 | 1.000 |
| hybrid+expand[ctx]-bge-small-8cefefeb | 0.136 | 0.341 | 0.455 | 0.614 | 0.795 | 0.864 | 0.977 |
| dense+expand[fix]-bge-small-21c3af53 | 0.045 | 0.068 | 0.114 | 0.159 | 0.364 | 0.455 | 0.682 |
| hybrid+expand[fix]-bge-small-163a5715 | 0.000 | 0.045 | 0.091 | 0.159 | 0.455 | 0.614 | 0.727 |
| dense+expand[ctx]-bge-small-f1b65882 | 0.182 | 0.318 | 0.455 | 0.636 | 0.795 | 0.841 | 1.000 |
| hybrid+expand[ctx]-bge-small-21b256e5 | 0.159 | 0.341 | 0.455 | 0.614 | 0.795 | 0.864 | 0.977 |
| dense+expand[strip]-bge-small-cc4276b5 | 0.045 | 0.045 | 0.091 | 0.204 | 0.409 | 0.523 | 0.727 |

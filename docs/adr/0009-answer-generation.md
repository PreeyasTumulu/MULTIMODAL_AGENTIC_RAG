# ADR-009: Answer generation — the LLM points, Python verifies

- **Status:** Accepted
- **Date:** 2026-09-12
- **Follows** [ADR-002](0002-llm-provider-stack.md) (providers), [ADR-003](0003-provenance-schema.md)
  (provenance), [ADR-008](0008-contextual-chunk-prefixes.md) (the index it reads)
- **Evidence:** [`notebooks/15_answering.ipynb`](../../notebooks/15_answering.ipynb),
  [`results/answers.md`](../../results/answers.md)

## Context

Days 1–5 built retrieval and measured it: the correct element is somewhere in the top 200
for every benchmark question, but only 32% of the time in the top 5. Nothing yet turned a
chunk into an answer. The project name promises an agent. The architecture overview
promises something stricter: **the LLM is the least trusted component. It receives values;
it does not produce them.**

## Decision

```
question → route (LLM) → retrieve (Qdrant) → extract (LLM) → verify (Python) → compute (Python)
                                                                   └── fails → one wider retry → refuse
```

| Step | Owner | Rule |
|---|---|---|
| Route | LLM, then Python | Intent, company, years and concept come from the LLM. **All of it is checked against the database** before use. |
| Retrieve | Qdrant | Dense + expansion over the `ctx` index. That config leads the leaderboard. |
| Extract | LLM | Names a figure *as printed* and the numbered evidence block it came from. |
| Verify | Python | The figure, and every other figure in the sentence, must be **printed in the evidence the model cited**. Otherwise: one retry at k=20, then refuse. |
| Compute | Python | Growth rates, price changes. The model never does arithmetic. |
| Prices | Python | A fixed, parametrised, READ ONLY query. The LLM supplies a ticker and dates, never SQL. |

Orchestration is **plain Python** (`analyst/agent.py`), chosen over LangGraph by the owner.
The flow is a fixed sequence with one bounded retry, and a graph framework would hide the
control flow this project exists to explain.

## Why

### Verification is string matching, not a second LLM call

A "judge" LLM that asks *is this answer supported?* costs a call and can itself be wrong.
The claim that matters here is checkable by string matching: a figure is either printed in
the cited evidence or it is not. Figures are compared as values, so `9,64,693` equals
`964,693`. That uses `numfmt`, the same code that built the benchmark.

⚠️ **What this does not catch:** a figure that *is* printed but sits in the wrong row or
column, such as standalone profit where consolidated was asked. The first live run showed it
on Reliance: `35,262` (standalone) was verified, cited, and wrong. That is why the
evaluation reports **wrong** separately from **refused**.

### A unit is a multiplier, so it is verified too

Reports print ₹ crore, ₹ million or ₹ '000. ICICI Bank's FY2024 profit and loss prints
`442,563,735` with no unit anywhere on the page. In the first live run the model labelled
two ICICI figures "million" and "crore", and the conversion reported **+1,129.6%** growth.
A unit is now applied only when the model names it **and** the cited evidence prints it.
Otherwise the two figures are compared as printed.

### Ollama is called through its native API

Ollama's OpenAI-compatible endpoint cannot set the context window. Measured: an
11,021-token prompt arrived as **2,050 tokens**, with no error, and the model answered `{}`.
The native `/api/chat` with `num_ctx` received all 11,021 and answered correctly. A 10-chunk
evidence prompt would otherwise have been silently cut down.

### The free tier's binding limit moved from requests to tokens

ADR-002 budgeted *requests* per day for Llama 3.x on Groq. As of 2026-09-12 those models
are gone from Groq's free-tier table. The free models (`openai/gpt-oss-120b`, `gpt-oss-20b`)
allow **8K tokens per minute and 200K per day**. A request larger than 8K tokens can never
succeed however long it waits, so the retry is capped at 20 chunks (`RETRY_K`). An evaluation
run must fit the daily token budget. The disk cache (`data/llm_cache.sqlite`) makes a re-run
free.

### No LLM judge in the evaluation either

Every benchmark answer is a number with a true value. Correct means the true figure at any
printed scale (exactly how notebook 06 located it), or a growth rate within 1 point. That
tolerance allows for two vendor-vs-filing differences of up to 0.5% each. Refusal is
measured on generated unanswerable questions: companies with no indexed report, a future
fiscal year, and investment advice.

## Alternatives considered

| Option | Rejected because |
|---|---|
| **LangGraph** | Earns its keep with cycles, checkpointing and human-in-the-loop. This is a fixed flow with one retry. |
| **Text-to-SQL for prices** | The SRS safety rules (FR-5.4–5.6) would need validation code. With fixed queries they hold by construction. |
| **Letting the agent read `facts`** | `facts` is the evaluation oracle. A system that can read the answer key scores 100% and proves nothing. |
| **Trusting the model's `value` field only** | llama3.2 routinely wrote the figure into its sentence and left `value` null. The figure is taken from either and verified the same way. |
| **LLM-as-judge grading** | Costs quota, adds a second fallible model, and is unnecessary when the answer is a number. |
| **Native function calling** | Not reliable across all three providers and small local models. JSON mode plus validation is. |

## Consequences

- **The Day 3–5 retrieval scores are an upper bound.** Every leaderboard row filtered and
  expanded queries with the benchmark's own ticker, year and concept labels. End to end
  those come from the router. Notebook 15 measures both and records the router's run in the
  retrieval ledger.
- Narrative answers are verified for their **figures only**. A vague or wrong prose claim
  with no figure in it passes. Claim-level entailment is out of scope for v1.
- Figures shorter than `MIN_DIGITS` (4 significant digits) cannot be verified, so they are
  refused. That is the rule the oracle already follows.
- Citations are narrowed by Python to the evidence blocks that actually print the figure,
  not every block the model listed.
- **`cited_expected` does not separate "retrieval never found the anchor" from "a
  plausible wrong-table figure passed the tolerant numeric check."** Both show up as
  `cited_expected=False`. Telling them apart needs a per-question diff against the
  retrieval ledger's ranks, not the answer ledger alone — not built for v1.

## Results

### Baseline — local `ollama/llama3.2` (3B), k=10, bench `2c4aedf3`

| metric | value |
|---|---|
| accuracy, 44 answerable | **0.227** (10) |
| value lookups / growth | 0.235 (8 of 34) / 0.200 (2 of 10) |
| **wrong answer** (answered, incorrect) | **0.568** (25) |
| false refusal | 0.205 (9) |
| refusal, 16 generated unanswerable | **1.000** (16) |
| a citation names the benchmark anchor | 0.318 |
| LLM calls / tokens per question | 2.1 / 2,909 |
| latency p50 | 4.6 s — 60 questions in 295 s |

**Reading it.**

- **Refusal works.** All 16 unanswerable questions were refused. None of them cost an
  extraction call: companies without a filing, future years and advice are all caught at
  the route step.
- **Every figure shown was printed in its cited evidence**, by construction. The failure
  mode left over is the one this design cannot see: **25 real figures from the wrong line.**
  Reliance's standalone profit (35,262) was given for the consolidated one (69,648). Sun
  Pharma's FY2024 revenue came back as ₹484,968.5 million, which is ₹48,497 crore against the
  oracle's ₹47,758 crore: 1.5% off, a neighbouring line.
- **In 9 of the 25 wrong answers the anchor element itself was retrieved and cited.** The
  3B model had the right table and read the wrong cell. That is a reading failure, not a
  retrieval failure, and it is the case for measuring a larger model before anything else.
- **The one retry** fired on 19 of 60 questions: 4 ended correct, 6 wrong, 9 refused.
  Widening the evidence rescues some answers and misleads on more.

### Router output vs benchmark labels — the "upper bound" measured

Same retriever and index, filtered and expanded with what `llama3.2` routed rather than the
benchmark's stored labels (recorded as `dense+expand[ctx]+router` in `results/runs.jsonl`):

| filters from | @1 | @5 | @10 | @20 | @50 | @100 | @200 |
|---|---|---|---|---|---|---|---|
| benchmark labels | .182 | .318 | .455 | .636 | .795 | .841 | 1.000 |
| the router | .182 | .386 | .455 | .659 | .773 | .841 | 1.000 |

The two curves are within about one question of each other at every depth. 9 of 44 routes
disagreed with the labels, mostly `Operating Revenue` read as `Total Revenue`, whose aliases
overlap. ⚠️ The benchmark questions are **templated**, so this is still an easy test for a
router. Paraphrased questions would be the honest next test.

### Groq `openai/gpt-oss-120b`, k=10, bench `2c4aedf3` (same bench as baseline)

| metric | value |
|---|---|
| accuracy, 44 answerable | **0.386** (17) |
| value lookups / growth | 0.382 (13 of 34) / 0.400 (4 of 10) |
| **wrong answer** (answered, incorrect) | **0.614** (27) |
| false refusal | **0.000** (0) |
| refusal, 16 generated unanswerable | **1.000** (16) |
| a citation names the benchmark anchor | 0.295 |
| LLM calls / tokens per question | 1.9 / 2,594 |
| latency p50 | 5.5 s — 60 questions in 812 s |

**Reading it.**

- **Accuracy nearly doubled (0.227 → 0.386) and false refusal went to zero.** The 9
  questions llama3.2 falsely refused were all attempted this time: 4 came back correct,
  5 wrong. Nothing about the retrieval or verification pipeline changed between runs —
  only the model doing the routing and extraction did.
- **Reading errors did not go away, they concentrated.** Of the 27 wrong answers, 5 had
  the correct anchor element retrieved *and* cited — all 5 are Sun Pharma questions
  (`TotalRevenue`, `StockholdersEquity`, `TotalExpenses`, and both growth pairs). The
  other 22 wrong answers cited a different element than the benchmark anchor: either a
  genuine retrieval miss, or (per the tolerant numeric match) a plausible-looking figure
  from the wrong table that the verifier accepted. This run does not distinguish the two;
  see Consequences below.
- **calls/tokens per question dropped slightly versus llama3.2** (1.9 vs 2.1 calls, 2,594
  vs 2,909 tokens) — `gpt-oss-120b`'s hidden reasoning tokens, the pre-run concern, did
  not inflate usage. The full 60-question run used ~156K of Groq's 200K-token daily
  budget.
- **wrong_answer rose in relative terms (0.568 → 0.614)** only because false refusals
  fell to zero and were reclassified as attempts — in raw counts, wrong answers rose by
  just 2 (25 → 27) while correct answers rose by 7 (10 → 17). Read the pair together, not
  either number alone.

# ADR-002: LLM provider stack — Groq primary, Ollama local, OpenRouter benchmark

- **Status:** Accepted
- **Date:** 2026-09-05

## Decision

| Role | Provider | Limits (verified 2026-09-05) |
|---|---|---|
| **Orchestration / synthesis** | **Groq** free tier | 30 RPM; 14,400 req/day (Llama 3.1 8B), 1,000 req/day (Llama 3.3 70B, GPT-OSS 120B). No credit card. |
| **Embeddings, reranking, vision** | **Ollama**, local | Unlimited. Already installed (`qwen3-vl`, `gemma3:4b`, `llama3.2`). |
| **Benchmark row + fallback** | **OpenRouter** free | 20 RPM, **50 req/day** unfunded. |

Total spend: **₹0**.

All three sit behind one interface, selected by config. Implemented on Day 3,
when the first call is actually made — the seam is designed now, the code is
written when it has a caller.

## Why

The project constraint is zero cost. The binding limit is not price, it is
**requests per day**, and the arithmetic decides the architecture:

```
one agentic query   ~=   5 LLM calls
100-question eval   ~= 500 LLM calls

OpenRouter free  50/day  ->  one eval run takes 10 DAYS   -> unusable
Groq free     1,000/day  ->  two eval runs per day        -> workable
Ollama local   unlimited ->  slow, but free and unmetered
```

Groq gives ~20x OpenRouter's daily allowance on a comparable model, with no card.

### The eval split that makes ₹0 viable

- **Retrieval metrics (Recall@k, MRR, nDCG) need ZERO LLM calls.** Pure
  computation against the oracle. Days 3–4 — the most iterative days of the
  project — cost no quota at all.
- **Generation metrics (faithfulness, answer relevance) cost ~2 calls/question.**
  100 questions = 200 calls, comfortably inside Groq's daily budget.

## Alternatives considered

| Option | Rejected because |
|---|---|
| **Gemini free tier** (~1,500 req/day) | Comparable limits and a strong candidate. Excluded on the owner's explicit preference to avoid a Google API for this project. |
| **OpenRouter as primary** | 50 req/day would make the evaluation harness — the whole point of the project — impossible to iterate on. |
| **Paid API** | Violates the ₹0 constraint. |
| **vLLM local** | Needs ≥16 GB VRAM to beat Ollama; this machine has 4 GB. Configuration effort, no learning payoff. |
| **Local model as primary generator** | 7–8B spills out of 4 GB VRAM to CPU at ~6–12 tok/s. At 5 calls per query that is 90–150 s per question: the dev loop and the demo both die. |

## Hardware constraint driving this

Measured on the dev machine: RTX 3050 Laptop, **4 GB VRAM**; 15.3 GB RAM.

| Workload | Fits 4 GB? |
|---|---|
| BGE embeddings (109M) | yes, comfortably |
| `bge-reranker-v2-m3` (568M) | yes |
| `gemma3:4b` / `llama3.2:3b` | yes, ~25–40 tok/s |
| `qwen3-vl` (6.1 GB) | no — spills to CPU; acceptable for offline batch vision |
| 14B+ | no — 2–4 tok/s, unusable |

**The GPU's job is embeddings, reranking and vision — not generation.**

## Consequences

- The AWS deployment target has **no GPU**, so the deployed configuration is
  API-inference-only. The provider must therefore be swappable by configuration,
  not by code change. This is why the abstraction is non-negotiable.
- Local models are a **benchmark artifact** ("quality/latency/cost across three
  providers on our own eval set"), not a deployment dependency. Claiming
  otherwise in the README would be false.
- A response cache is not decoration: without it, iterating on the eval harness
  does not fit inside free quota. That is the measured justification for the
  caching work, deferred to Week 2.

# Product Requirements Document

**Product:** Multimodal Agentic RAG — Indian Equity Research Analyst
**Owner:** Preeyas Tumulu
**Version:** 0.2 · 2026-09-05
**Status:** Active — Day 2 of a 7-day v1

---

## 1. Problem

An Indian listed company's annual report is 150–600 pages of prose, financial
tables and charts. Answering a real analyst question usually requires more than
one of those at once:

> *"Sun Pharma's revenue grew in FY2025 — by how much, and what does management
> say drove it?"*

That is an exact number **and** a passage of narrative. A conventional
"chat with PDF" system has a single retrieval path — embed, cosine-search,
generate — which handles the narrative and **fabricates the number**, because
text similarity is a poor mechanism for retrieving an exact figure and a
language model will happily produce a plausible one.

The gap is not better search. It is **deciding what kind of question this is
before deciding how to answer it**, and then refusing to answer when the
evidence is not there.

---

## 2. Users

| User | Needs | Success looks like |
|---|---|---|
| **Primary — the author** | Practical, demonstrable experience across RAG, agents, evaluation, and deployment | Can explain and defend every technical decision in an interview |
| **Secondary — a reviewer or interviewer** | Evidence of engineering judgement, not tool-name collection | Reads the ADRs and benchmark table and sees decisions made on measurement |
| **Illustrative — a retail investor or analyst** | Fast, *cited* answers over annual reports | Every claim traceable to a page |

This is a portfolio-grade engineering project, not a commercial product. That
shapes priorities: **measurement and honesty outrank feature count.**

---

## 3. Goals

| # | Goal | Measure |
|---|---|---|
| G1 | Route a question to the right retrieval mechanism | Router accuracy on a labelled question set |
| G2 | Answer exact-value questions **exactly** | Numeric answers come from Postgres, never generation |
| G3 | Cite every claim to a page | 100% of numeric claims carry a resolvable `element_id` |
| G4 | Refuse when evidence is missing | Abstention rate on deliberately unanswerable questions |
| G5 | Measure retrieval quality, not vibes | Recall@k / MRR against a generated benchmark |
| G6 | Show measured improvement | Baseline → hybrid → reranked, as a published table |
| G7 | Run at ₹0 | No paid API or service anywhere in the stack |
| G8 | Deploy publicly | A reachable URL with CI |

---

## 4. Non-goals

Named explicitly so scope creep is a decision, not an accident.

| Not doing | Why |
|---|---|
| Investment advice or buy/sell signals | Out of scope, and not something this system should produce |
| Real-time / intraday data | Daily bars are sufficient; intraday adds cost and no learning |
| Every listed Indian company | 12 companies across 4 sectors is enough to exercise routing |
| Fine-tuning any model | Retrieval quality is the bottleneck, not model weights |
| A production SPA frontend | Streamlit is adequate; Next.js is already on the author's CV |
| Multi-user auth, billing, tenancy | No users to isolate |
| OCR | All corpus PDFs carry a real text layer — [ADR-004](../adr/0004-pdf-parser.md) |

---

## 5. Scope — v1 (7 days)

### In

- 12 companies, 4 sectors; annual report PDFs, reported financials, daily prices
- Reproducible, checksum-verified ingestion
- Parsing to typed elements with page/bbox provenance
- Hybrid retrieval with reranking
- Document, Table, SQL, Vision and Calculator agents behind a router
- Auto-generated evaluation benchmark with retrieval and generation metrics
- Groundedness verification and explicit abstention
- FastAPI + Streamlit, Docker, CI, AWS deployment

### Deferred (decided, not forgotten)

| Item | Why deferred | Revisit |
|---|---|---|
| Semantic caching | Needs a working system to measure benefit against | Week 2 |
| Full observability stack (Phoenix/OTel) | Structured logging covers ~70% of the value at ~20% of the cost | Week 2 |
| Next.js frontend | Worst hours-to-value ratio for an AI role | Not planned |
| Performance tuning | Optimising before measuring is the classic mistake | Week 2 |

---

## 6. Success criteria

v1 is done when **all** of these hold:

| # | Criterion | Verified by |
|---|---|---|
| S1 | Corpus rebuilds from a clean clone with no manual steps except the two bot-blocked PDFs | Fresh-clone run |
| S2 | A published benchmark of ≥100 auto-generated questions with ground-truth sources | `docs/` benchmark report |
| S3 | Baseline vs. improved retrieval shown as measured numbers | Benchmark table |
| S4 | Every numeric answer traceable to an element | Citation validity check |
| S5 | Unanswerable questions produce abstention, not invention | Adversarial question set |
| S6 | Deployed and reachable | Public URL |
| S7 | Total spend ₹0 | Billing pages |
| S8 | README claims only what was measured | Self-review against this document |

**S8 is the one that matters most.** A project that overstates what it does
fails at exactly the moment it is supposed to help — an interview.

---

## 7. Risks

| Risk | Impact | Mitigation | Status |
|---|---|---|---|
| Free-tier rate limits block evaluation | Fatal — evaluation is the point | Retrieval metrics need **zero** LLM calls; Groq gives ~20× OpenRouter's daily budget | Handled ([ADR-002](../adr/0002-llm-provider-stack.md)) |
| Oracle disagrees with the filings | Corrupts the benchmark | Unlocatable facts are discarded, not scored as failures | Handled |
| False positives inflate oracle recall | Overstates quality | Recorded as an open question; tighten on Day 3 and re-measure | 🧭 Open |
| IR sites block downloads | Corpus gaps | `fetch: manual` path; checksum preserves reproducibility | Handled |
| 4 GB VRAM cannot serve a strong LLM | Unusable latency | Local GPU does embeddings/rerank/vision; API does generation | Handled |
| 7-day budget vs. 22-phase ambition | Half-finished everything | Breadth cut (12 companies, 6 documents), pipeline depth kept | Handled |
| Vendor API breakage (yfinance) | Ingestion stops | Pinned versions; ingestion is idempotent and re-runnable | Accepted |

---

## 8. Open questions

| # | Question | Decide by |
|---|---|---|
| Q1 | Qdrant or pgvector? | Day 3, with a measurement |
| Q2 | Which embedding model — BGE-M3 vs bge-base vs e5? | Day 3, benchmarked |
| Q3 | How to eliminate false-positive oracle matches | Day 3 |
| Q4 | Is a cross-encoder reranker worth its latency here? | Day 4, measured |

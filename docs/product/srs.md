# Software Requirements Specification

**System:** Multimodal Agentic RAG — Indian Equity Research Analyst
**Version:** 0.2 · 2026-09-05
**Companion to:** [PRD](prd.md)

Each requirement has an ID, a status, and a **verification method** — how you
would prove it holds. A requirement with no verification method is a wish.

Status: ✅ built and verified · 🔜 specified, not built · 🧭 open

---

## 1. Scope

The system ingests Indian listed-company annual reports, reported financials and
daily market prices; answers natural-language questions over them by routing to
the appropriate retrieval mechanism; and returns answers with page-level
citations, or an explicit refusal when evidence is insufficient.

**Environment:** Python 3.12, PostgreSQL 17, Docker, Windows 11 development host
(RTX 3050 4 GB), Linux deployment target without GPU.

---

## 2. Functional requirements

### 2.1 Data acquisition

| ID | Requirement | Status | Verification |
|---|---|---|---|
| FR-1.1 | Acquire daily OHLCV for every configured company | ✅ | 14,879 rows across 12 companies |
| FR-1.2 | Discard price bars with no close value | ✅ | `test_prices.py`; fired on DRREDDY 2026-09-04 |
| FR-1.3 | Acquire reported financial statements for ≥5 fiscal years | ✅ | 8,532 facts, FY2022–FY2026 |
| FR-1.4 | Record each company's reporting currency from the vendor, not the exchange | ✅ | `companies.financial_currency`; INFY = USD |
| FR-1.5 | Represent absent values as absent, never as zero | ✅ | `test_facts.py::test_melt_drops_nan_instead_of_writing_zero` |
| FR-1.6 | Download source PDFs from a declarative manifest | ✅ | 6 documents, 2,056 pages |
| FR-1.7 | Verify every downloaded document against a pinned SHA-256 | ✅ | Checksum mismatch exits non-zero |
| FR-1.8 | Support a manual-fetch path for sources that block automation | ✅ | TCS, INFY marked `fetch: manual` |
| FR-1.9 | All acquisition is idempotent | ✅ | `ON CONFLICT` on every insert; re-run adds no duplicates |
| FR-1.10 | No corpus data is committed to version control | ✅ | `data/` git-ignored; `git check-ignore` |

### 2.2 Document processing

| ID | Requirement | Status | Verification |
|---|---|---|---|
| FR-2.1 | Extract text, headings, tables and figures as typed elements | ✅ | 46,241 elements across 6 documents |
| FR-2.2 | Every element carries `document_id`, `page`, `seq`, and `bbox` where available | ✅ | `elements` schema; `test_provenance.py` |
| FR-2.3 | Element IDs are deterministic across re-parses | ✅ | `test_provenance.py::test_document_id_is_deterministic` |
| FR-2.4 | Element IDs sort into document order lexically | ✅ | `test_provenance.py::test_element_id_sorts_in_document_order` |
| FR-2.5 | Tables retain exact values separately from their embeddable text | ✅ | `elements.table_json` vs `elements.text` |
| FR-2.6 | A value inside a table is not also emitted as loose text | ✅ | Table regions claimed before text extraction |
| FR-2.7 | Figures are written to disk and linked to their element | ✅ | 418 images under `data/figures/` |
| FR-2.8 | Parsing is re-runnable without duplicating elements | ✅ | Upsert on `element_id` |

### 2.3 Oracle and benchmark

| ID | Requirement | Status | Verification |
|---|---|---|---|
| FR-3.1 | Generate every plausible Indian printed form of a value | ✅ | `numfmt.py`; 6 scales × 3 groupings × 3 precisions |
| FR-3.2 | Match values despite whitespace inserted by PDF extraction | ✅ | `test_numfmt.py`; handles NBSP and thin space |
| FR-3.3 | Reject figures too short to match uniquely | ✅ | `MIN_DIGITS = 4` |
| FR-3.4 | Locate an oracle value on a specific page of its source document | ✅ | `demo_oracle_link.py`: 3 companies, 3 different scales |
| FR-3.5 | Discard facts that cannot be located rather than scoring them as failures | ✅ | Verified on SUNPHARMA Gross Profit |
| FR-3.6 | Generate ≥100 benchmark questions with ground-truth answer and source | 🔜 | Day 3 |
| FR-3.7 | Eliminate coincidental matches by requiring concept-label proximity | 🧭 | Day 3 — current 47–57% is a ceiling, not a score |

### 2.4 Indexing and retrieval

| ID | Requirement | Status | Verification |
|---|---|---|---|
| FR-4.1 | Chunk elements without splitting any table | 🔜 | Day 3 |
| FR-4.2 | Embed chunks locally on GPU | 🔜 | Day 3 |
| FR-4.3 | Every vector payload carries enough metadata to filter and to cite | 🔜 | Day 3 |
| FR-4.4 | Apply metadata filters before vector scoring | 🔜 | Day 3 |
| FR-4.5 | Combine dense and sparse retrieval | 🔜 | Day 4 |
| FR-4.6 | Rerank candidates with a cross-encoder | 🔜 | Day 4 |
| FR-4.7 | Report Recall@k and MRR against the benchmark **without any LLM call** | 🔜 | Day 3 |

### 2.5 Reasoning agents

| ID | Requirement | Status | Verification |
|---|---|---|---|
| FR-5.1 | Classify each question and select the agent set, with a stated reason | 🔜 | Day 6 |
| FR-5.2 | Document Agent retrieves passages and returns citable elements | 🔜 | Day 5 |
| FR-5.3 | Table Agent reads exact values from `table_json`, never from text | 🔜 | Day 5 |
| FR-5.4 | SQL Agent connects as a read-only role | 🔜 | Day 5 |
| FR-5.5 | SQL Agent enforces row limits and a statement timeout | 🔜 | Day 5 |
| FR-5.6 | SQL Agent rejects any non-`SELECT` statement before execution | 🔜 | Day 5 |
| FR-5.7 | Vision Agent describes figures and links each to its source page | 🔜 | Day 5 |
| FR-5.8 | **All arithmetic is performed in Python, never by the model** | 🔜 | Day 5 |

### 2.6 Answering

| ID | Requirement | Status | Verification |
|---|---|---|---|
| FR-6.1 | Every numeric claim carries a resolvable `element_id` | 🔜 | Day 6 |
| FR-6.2 | Verify each claim is grounded in retrieved context before answering | 🔜 | Day 6 |
| FR-6.3 | Abstain explicitly when evidence is insufficient | 🔜 | Day 6 |
| FR-6.4 | Expose which agents ran, why, which sources were used, and what was computed | 🔜 | Day 6 |
| FR-6.5 | Never expose raw chain-of-thought — only auditable traces | 🔜 | Day 6 |

---

## 3. Non-functional requirements

### 3.1 Correctness

| ID | Requirement | Status | Verification |
|---|---|---|---|
| NFR-1.1 | Monetary values stored with exact decimal precision | ✅ | `Numeric(30,4)`; no float anywhere in the money path |
| NFR-1.2 | Currency and unit are part of a fact's identity | ✅ | `facts.unit`; `test_facts.py` |
| NFR-1.3 | Schema changes applied by migration, never `create_all()` | ✅ | 4 Alembic migrations |
| NFR-1.4 | Vector search never supplies an authoritative value | 🔜 | Qdrant payload carries `element_id`, not truth |

### 3.2 Security

| ID | Requirement | Status | Verification |
|---|---|---|---|
| NFR-2.1 | No secret is committed | ✅ | `.env` git-ignored; `.env.example` has no values |
| NFR-2.2 | Secrets never enter logs or serialised models | ✅ | `SecretStr`; `database_url` is a property, not a `computed_field` |
| NFR-2.3 | Retrieved document content is treated as data, never as instructions | 🔜 | Day 6 — prompt-injection defence |
| NFR-2.4 | Database access for agents is read-only | 🔜 | Day 5 |
| NFR-2.5 | Uploaded/downloaded files validated by content type and checksum | ✅ | `download_docs.py` rejects non-PDF responses |

### 3.3 Reliability

| ID | Requirement | Status | Verification |
|---|---|---|---|
| NFR-3.1 | Network calls retry with exponential backoff | ✅ | `tenacity` on every vendor call |
| NFR-3.2 | An interrupted download never leaves a file that looks complete | ✅ | `.part` file renamed only on success |
| NFR-3.3 | All derived state is rebuildable from the manifest and scripts | ✅ | See [storage.md](../architecture/storage.md#backup-and-recovery) |

### 3.4 Performance

| ID | Requirement | Status | Verification |
|---|---|---|---|
| NFR-4.1 | Parse a 300-page report in under 60 s | ✅ | ~50 s including figure extraction |
| NFR-4.2 | Text extraction under 2 s per document | ✅ | 0.7–1.4 s measured ([ADR-004](../adr/0004-pdf-parser.md)) |
| NFR-4.3 | End-to-end query latency under 15 s | 🔜 | Day 6 |

### 3.5 Cost

| ID | Requirement | Status | Verification |
|---|---|---|---|
| NFR-5.1 | Zero rupees of paid API or service spend | ✅ | No paid dependency in `pyproject.toml` or infrastructure |
| NFR-5.2 | Retrieval evaluation consumes no LLM quota | 🔜 | Day 3 — metrics are pure computation |
| NFR-5.3 | Deployment fits inside available AWS credits | 🔜 | Day 7 |

### 3.6 Maintainability

| ID | Requirement | Status | Verification |
|---|---|---|---|
| NFR-6.1 | `mypy --strict` clean across src, scripts and tests | ✅ | 25 source files, zero errors |
| NFR-6.2 | `ruff` clean | ✅ | Zero findings |
| NFR-6.3 | Business logic is unit-testable without network or database | ✅ | `numfmt`, `facts`, `prices`, `provenance` all pure |
| NFR-6.4 | Every significant decision recorded as an ADR | ✅ | ADR-001…004 |
| NFR-6.5 | Schema documentation generated, not hand-written | ✅ | `gen_schema_docs.py` |
| NFR-6.6 | Automated tests run in CI on every push | 🔜 | Day 7 |

---

## 4. Constraints

| ID | Constraint | Source |
|---|---|---|
| C1 | Total budget ₹0 | Owner |
| C2 | 4 GB VRAM on the development machine | Hardware |
| C3 | No GPU on the deployment target | AWS free tier |
| C4 | Windows 11 + Docker Desktop for development | Owner preference |
| C5 | 7-day v1, ~4 h/day | Owner |
| C6 | `tcs.com` and `infosys.com` refuse automated requests | Verified 2026-09-05 |
| C7 | Financial data is a vendor normalisation, not the filed statements | Yahoo Finance |

---

## 5. Traceability

| PRD goal | Requirements |
|---|---|
| G1 Route correctly | FR-5.1 |
| G2 Exact values | FR-5.3, FR-5.8, NFR-1.1, NFR-1.4 |
| G3 Cite everything | FR-2.2, FR-6.1 |
| G4 Refuse when unsure | FR-6.2, FR-6.3 |
| G5 Measure retrieval | FR-3.6, FR-4.7 |
| G6 Show improvement | FR-4.5, FR-4.6 |
| G7 Zero cost | NFR-5.1, NFR-5.2 |
| G8 Deploy | NFR-5.3, NFR-6.6 |

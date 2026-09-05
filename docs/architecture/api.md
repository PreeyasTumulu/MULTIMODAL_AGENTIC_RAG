# API specification

**Status:** 🔜 **Designed, not built.** Implementation is Day 6.
This document is the contract the implementation must satisfy — it is written
now so the agent and orchestration work has a target shape.

**Framework:** FastAPI · **Base path:** `/api/v1` · **Content type:** `application/json`

---

## Design principles

1. **Every answer carries its evidence.** There is no endpoint that returns a
   claim without the sources that support it.
2. **Abstention is a success, not an error.** `answer: null` with
   `abstained: true` is HTTP 200. Refusing to guess is correct behaviour.
3. **The trace is part of the response, not a debug flag.** Explainability is a
   product requirement (PRD G3), so it ships in the normal payload.
4. **Never expose raw chain-of-thought.** The trace is auditable structure —
   which agents ran, what was retrieved, what was computed — not model
   monologue.

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/ask` | Ask a question, get a cited answer |
| `POST` | `/api/v1/ask/stream` | Same, streamed as Server-Sent Events |
| `GET` | `/api/v1/companies` | List the corpus |
| `GET` | `/api/v1/documents` | List source documents |
| `GET` | `/api/v1/elements/{element_id}` | Resolve a citation |
| `GET` | `/api/v1/figures/{element_id}` | Fetch a figure image |
| `GET` | `/health` | Liveness + dependency status |
| `GET` | `/docs` | OpenAPI UI (FastAPI built-in) |

---

## `POST /api/v1/ask`

### Request

```jsonc
{
  "question": "How much did Sun Pharma's revenue grow in FY2025?",
  "filters": {                    // optional — narrows retrieval before scoring
    "tickers":      ["SUNPHARMA"],
    "fiscal_years": [2025, 2024]
  },
  "max_sources": 8,               // default 8, max 20
  "include_trace": true           // default true
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `question` | string | yes | 3–500 characters |
| `filters.tickers` | string[] | no | Must exist in `companies` |
| `filters.fiscal_years` | int[] | no | |
| `max_sources` | int | no | 1–20, default 8 |
| `include_trace` | bool | no | default `true` |

### Response — 200, answered

```jsonc
{
  "answer": "Sun Pharma's total revenue grew 18.6% in FY2025, from ₹43,886 crore to ₹52,041 crore.",
  "abstained": false,
  "confidence": "high",
  "citations": [
    {
      "element_id":  "SUNPHARMA-annual_report-FY2025-7cf1d4f4:p0259:e0003",
      "document_id": "SUNPHARMA-annual_report-FY2025-7cf1d4f4",
      "title":       "Annual Report 2024-25",
      "ticker":      "SUNPHARMA",
      "page":        259,
      "type":        "table",
      "bbox":        [72.0, 310.4, 523.8, 588.2],
      "snippet":     "Revenue from operations … 520,412.5"
    }
  ],
  "computations": [
    {
      "expression": "(52041 - 43886) / 43886 * 100",
      "result":     18.6,
      "unit":       "percent",
      "inputs": [
        { "source": "facts", "ticker": "SUNPHARMA", "concept": "Total Revenue",
          "period_end": "2025-03-31", "value": "520412500000", "unit": "INR" }
      ]
    }
  ],
  "trace": {
    "route":        ["sql_agent", "calculator", "document_agent"],
    "route_reason": "Question asks for a quantity and an explanation, so it needs both an exact value and narrative context.",
    "steps": [
      { "agent": "sql_agent",       "ms": 41,   "result_rows": 2 },
      { "agent": "calculator",      "ms": 1,    "result": 18.6 },
      { "agent": "document_agent",  "ms": 380,  "candidates": 40, "after_rerank": 8 },
      { "agent": "verifier",        "ms": 210,  "grounded": true }
    ],
    "tokens": { "prompt": 3140, "completion": 190 },
    "model":  "groq/llama-3.3-70b-versatile"
  },
  "latency_ms": 2180
}
```

**`computations` is the part that matters.** Every number in `answer` traces to
an entry here, and every entry traces to a row in `facts` or a `table_json`
cell. Nothing numeric originates in the language model.

### Response — 200, abstained

```jsonc
{
  "answer": null,
  "abstained": true,
  "abstain_reason": "insufficient_evidence",
  "message": "I don't have enough evidence in the available sources to answer this reliably.",
  "citations": [],
  "computations": [],
  "trace": { "route": ["document_agent"], "steps": [ /* … */ ] },
  "latency_ms": 940
}
```

| `abstain_reason` | Meaning |
|---|---|
| `insufficient_evidence` | Retrieval returned nothing above the relevance threshold |
| `not_grounded` | A draft answer contained claims not supported by retrieved context |
| `out_of_corpus` | The question names a company or year not in the corpus |
| `unsupported_question` | Not answerable from filings — e.g. a request for investment advice |

---

## `POST /api/v1/ask/stream`

Same request body. Responds `text/event-stream`, so the user sees routing and
retrieval progress rather than a spinner.

```
event: route
data: {"agents":["sql_agent","document_agent"],"reason":"…"}

event: step
data: {"agent":"sql_agent","status":"complete","ms":41}

event: citation
data: {"element_id":"…:p0259:e0003","page":259}

event: token
data: {"text":"Sun Pharma's total revenue"}

event: done
data: {"abstained":false,"latency_ms":2180}
```

Verification runs **before** tokens stream, so a non-grounded answer is never
partially shown and then retracted.

---

## Read endpoints

### `GET /api/v1/companies`

```jsonc
[ { "ticker": "SUNPHARMA", "name": "Sun Pharmaceutical Industries",
    "sector": "Pharma", "financial_currency": "INR",
    "documents": 2, "facts": 753, "price_from": "2021-09-06", "price_to": "2026-09-04" } ]
```

### `GET /api/v1/elements/{element_id}`

Resolves a citation to its full content — the endpoint the UI calls when a user
clicks a source.

```jsonc
{
  "element_id": "SUNPHARMA-annual_report-FY2025-7cf1d4f4:p0259:e0003",
  "document":   { "document_id": "…", "title": "Annual Report 2024-25",
                  "ticker": "SUNPHARMA", "fiscal_year": 2025, "n_pages": 326 },
  "page": 259, "type": "table", "bbox": [72.0, 310.4, 523.8, 588.2],
  "text": "…",
  "table_json": { "header": ["Particulars","FY2025","FY2024"],
                  "rows": [["Revenue from operations","520,412.5","438,860.1"]],
                  "n_rows": 24 }
}
```

### `GET /health`

```jsonc
{ "status": "ok", "version": "0.1.0",
  "dependencies": { "postgres": "ok", "qdrant": "ok", "llm_provider": "ok" },
  "corpus": { "companies": 12, "documents": 6, "elements": 46241, "facts": 8532 } }
```

Returns `503` if any dependency is down.

---

## Errors

Uniform shape, no stack traces, no SQL, no internal paths.

```jsonc
{ "error": { "code": "validation_error",
             "message": "question must be between 3 and 500 characters",
             "field": "question" } }
```

| Status | Code | When |
|---|---|---|
| 400 | `validation_error` | Malformed request |
| 404 | `not_found` | Unknown `element_id` or ticker |
| 422 | `unprocessable` | Well-formed but unanswerable request shape |
| 429 | `rate_limited` | Client quota exceeded — includes `Retry-After` |
| 503 | `dependency_unavailable` | Postgres, Qdrant or the LLM provider is down |
| 504 | `timeout` | Exceeded the request budget |

An **upstream LLM rate limit** is reported as `503 dependency_unavailable`, not
`429` — the client did nothing wrong, and the distinction matters given the free
tiers this runs on.

---

## Cross-cutting

| Concern | Approach |
|---|---|
| Auth | API key in `X-API-Key`. Single key for v1 — there are no users to isolate. |
| Rate limiting | Per-key token bucket, sized under the LLM provider's own daily quota |
| Request budget | Hard timeout; partial work is discarded rather than returned |
| Validation | Pydantic v2 models; FastAPI generates OpenAPI from them |
| CORS | Streamlit origin only |
| Logging | One structured event per stage, correlated by `request_id` |
| Prompt injection | Retrieved text is passed as data, never concatenated into the instruction section of a prompt |
| Versioning | Path-versioned `/api/v1`; breaking changes get `/v2` |

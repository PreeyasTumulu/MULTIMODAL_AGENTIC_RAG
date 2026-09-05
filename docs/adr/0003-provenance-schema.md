# ADR-003: Provenance is attached at extraction time, not reconstructed

- **Status:** Accepted
- **Date:** 2026-09-05

## Decision

Every extracted unit of a document carries, from the moment it is parsed:

```
document_id  ->  stable, human-readable:  TCS-annual_report-FY2025-deadbeef
page         ->  1-indexed, as a human reads it
element_id   ->  document_id:p0042:e0001   (zero-padded: lexical sort == doc order)
bbox         ->  (x0, y0, x1, y1) in PDF points
```

IDs are **deterministic**: re-parsing the same file yields identical IDs, so the
index can be rebuilt without invalidating an existing evaluation set.

Defined in `src/analyst/provenance.py`. This is the one piece of Day-1 code
written ahead of its caller — deliberately, because it is the contract every
later subsystem is built against.

## Why

Provenance cannot be recovered after the fact. Once a PDF has been flattened into
a list of strings, "which page was this on?" is unanswerable. Everything the
project promises depends on that answer:

- **Citations** — the UI renders `SourceRef`
- **Explainability (§20)** — which pages, tables and figures supported the answer
- **The evaluation harness** — retrieval metrics compare *retrieved* element IDs
  against *expected* element IDs; without stable IDs there is no Recall@k
- **Hallucination control** — a claim with no resolvable source is a claim to
  refuse

Retrofitting this on Day 5 would mean re-parsing the entire corpus and
regenerating the benchmark.

## Alternatives considered

| Option | Rejected because |
|---|---|
| **Chunk text only, attach metadata later** | The common shortcut. Page and bbox are gone by then; citations degrade to "somewhere in this document". |
| **UUID element IDs** | Not deterministic — re-parsing invalidates the eval set. Also unreadable in a failure log, where `TCS-...-FY2025:p0118:e0003` tells you where to look immediately. |
| **Page-level granularity only** | Enough for citations, not enough to highlight the table a number came from, and too coarse for element-level retrieval metrics. |

## Tradeoffs

- **Accepted:** bbox is parser-dependent and will be `None` for some elements.
  Modelled as optional rather than pretended to be universal.
- **Accepted:** a table is stored three ways — `text` (linearised, for
  embedding), `table_json` (exact values, for arithmetic), and `bbox`/page (for
  citation). More storage, more code. The alternative is doing arithmetic on a
  language model's reading of a number, which is the single largest source of
  wrong answers in financial RAG.

## Consequences

- `Element.text` is what gets embedded; `Element.table_json` is what gets
  computed on. The Calculator agent never reads from `text`.
- Day 2's parser must emit `Element` objects, not strings. Any parser that cannot
  provide page numbers is disqualified before benchmarking begins — that is a
  hard filter on the ADR-004 parser choice.
- Elements are frozen (immutable) so a retrieved element cannot be mutated
  between retrieval and citation rendering.

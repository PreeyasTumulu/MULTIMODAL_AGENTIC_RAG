# ADR-004: PyMuPDF for text and layout extraction

- **Status:** Accepted
- **Date:** 2026-09-05

## Decision

**PyMuPDF** is the parser for text, headings, tables and figure extraction.

## How it was decided

Not by reputation. The usual parser comparison measures characters per second,
which is the wrong metric here — a parser that extracts plenty of prose but
mangles the digits inside a financial table is worse than useless for this
project.

So the benchmark measures **oracle recall**: of the financial facts we already
know to be true for a company and fiscal year, what fraction can be located in
the text the parser produced? It predicts directly how many benchmark questions
Day 3 will be able to generate, and it costs zero LLM calls.
See notebook `05_benchmark_parsers.ipynb`.

### Identical 60-page subsets, six real annual reports

| Document | Parser | sec | kchars | Oracle recall |
|---|---|---:|---:|---:|
| HDFCBANK FY25 | pymupdf | **0.2** | 163 | 2/151 |
| HDFCBANK FY25 | pdfplumber | 7.5 | 160 | 3/151 |
| ICICIBANK FY25 | pymupdf | **0.4** | 167 | 4/131 |
| ICICIBANK FY25 | pdfplumber | 25.6 | 163 | 3/131 |
| ICICIBANK FY24 | pymupdf | **0.2** | 158 | 2/131 |
| ICICIBANK FY24 | pdfplumber | 7.0 | 154 | 3/131 |
| RELIANCE FY25 | pymupdf | **0.7** | 426 | 30/159 |
| RELIANCE FY25 | pdfplumber | 22.5 | 440 | 28/159 |
| SUNPHARMA FY25 | pymupdf | **0.2** | 176 | 31/176 |
| SUNPHARMA FY25 | pdfplumber | 7.2 | 173 | 27/176 |
| SUNPHARMA FY24 | pymupdf | **0.2** | 187 | 29/176 |
| SUNPHARMA FY24 | pdfplumber | 7.3 | 184 | 29/176 |

**Result: 30–60x faster, same text (within 2%), same oracle recall (within 3
points).** pdfplumber costs an order of magnitude more time for no measurable
gain on this corpus.

### Full-document oracle recall (PyMuPDF, all pages)

| Document | Pages | Sec | Oracle recall |
|---|---:|---:|---:|
| HDFCBANK FY25 | 590 | 1.4 | 71/151 (47%) |
| ICICIBANK FY25 | 341 | 0.9 | 72/131 (55%) |
| ICICIBANK FY24 | 341 | 0.7 | 73/131 (56%) |
| RELIANCE FY25 | 146 | 1.4 | 88/159 (55%) |
| SUNPHARMA FY25 | 326 | 0.8 | 101/176 (57%) |
| SUNPHARMA FY24 | 312 | 0.8 | 84/176 (48%) |

## Alternatives considered

| Option | Verdict |
|---|---|
| **pdfplumber** | Benchmarked and rejected on the numbers above. Its real strength is `extract_tables()` structure, which this benchmark does not measure — see Open questions. |
| **Docling** | Installed and available in an ephemeral environment. Deferred: it pulls torch plus layout models, and PyMuPDF's table extraction has not yet been shown to be the bottleneck. Revisit if table fidelity limits Day 3's benchmark coverage. |
| **Unstructured** | Same weight class as Docling, less table-focused. Not benchmarked. |
| **OCR (Tesseract / Surya)** | **Not needed.** All six PDFs carry a real text layer at 2,400–7,000 chars/page. OCR would add minutes per document and cost accuracy. |

## Consequences

- Tables are located **first** and their page regions claimed; text blocks
  overlapping a claimed region are skipped. Without that, every figure in every
  table appears twice — once as a structured cell, once as loose text — and the
  retriever ranks the mangled copy above the structured one.
- Headings are detected by font size relative to the page median (1.15x), not by
  an absolute point size: annual report typography varies far too much between
  designers to hardcode.
- Figures below 120 px on a side, or under 40,000 px², are discarded as
  decorative rules and bullets.

## Open questions

- **Oracle recall of ~50% is a raw match rate and includes false positives.** A
  4-digit figure can collide by chance in a 300-page document. Day 3 must
  tighten this — likely by requiring the matched number to co-occur with its
  concept label nearby — and re-measure. The current number is a ceiling, not a
  score.
- Table *structure* fidelity is untested. The benchmark above measures whether
  numbers survive into text, not whether rows and columns are correctly
  associated. That is the question that would justify revisiting Docling.

# ADR-001: Domain and corpus — Indian listed equities

- **Status:** Accepted
- **Date:** 2026-09-05

## Decision

The corpus is **12 Indian listed companies across 4 sectors** (IT, Banking/NBFC,
Energy, Pharma), combining four data layers:

| Layer | Source | Modality | Serves |
|---|---|---|---|
| Annual report PDFs | Company investor-relations pages | Text + tables + charts | Document Agent, Table Agent, Vision Agent |
| Investor presentations | Company IR pages | Charts | Vision Agent |
| Reported financials | `yfinance` fundamentals | Structured | SQL Agent + **evaluation oracle** |
| Daily OHLCV | `yfinance` `.NS` | Time series | SQL Agent |

## Why

1. **It has an oracle.** `yfinance` exposes 5 fiscal years x ~174 line items per
   company (income 50, balance 77, cashflow 47) — roughly 10,000 verifiable facts
   across the corpus. Verified live on 2026-09-05: RELIANCE FY26 revenue
   ₹10,57,219 Cr, FY25 ₹9,64,693 Cr, FY24 ₹9,01,064 Cr.
2. **The oracle builds the benchmark automatically.** Take a known fact, search
   the parsed report text for that number in every Indian format
   (`964,693` / `9,64,693` / `964693` / `96,469.3`). Found on page 118 → an
   auto-labelled `(question, answer, source page)` triple. Not found → discard.
   Yahoo-vs-PDF disagreements filter themselves out instead of producing false
   RAG failures.
3. **Indian annual reports are the most chart-dense documents available for free**,
   which is what the Vision Agent needs.
4. **Cross-sector questions are the sharpest test of the router** — "compare
   operating margin, IT vs Pharma" cannot be answered by one retrieval path.

## Alternatives considered

| Option | Rejected because |
|---|---|
| **SEC EDGAR (US filings)** | Stronger oracle (XBRL: 27,114 facts for NVIDIA alone, each carrying the filing accession number) and better reproducibility. Rejected on the owner's preference for Indian markets, which was reaffirmed after the tradeoff was presented. Remains the best fallback if the IR-page approach proves too manual. |
| **Screener.in scraping** | Their value *is* the aggregated data; a scraper in a public repo is a liability to the repo and the account. Used manually as a research tool instead. |
| **BSE/NSE portals** | Cookie-gated, finicky, fragile. Same PDFs are on the companies' own IR pages. |
| **Research papers (arXiv/PMC)** | No numeric ground truth — every eval question hand-written. Also the most crowded portfolio project in existence. |
| **Energy/climate (IRENA + OWID)** | Genuinely strong runner-up, better charts. No live market dimension. |

## Tradeoffs

- **Accepted:** the oracle is Yahoo's *normalisation* of the filing, not the filed
  number, so it can disagree with the PDF. Mitigated by the self-filtering search
  above — a mismatch drops the question rather than failing the system.
- **Accepted:** document URLs need one-time manual curation into a manifest
  (~30 min) because there is no bulk API. After that, downloads are scripted and
  reproducible via checksums.
- **Given up:** the filing-accession-level provenance that SEC XBRL provides.

## Consequences

- `configs/companies.yaml` is the single place scope changes.
- The corpus must never enter git; `data/` is ignored and reconstructed from
  scripts plus a manifest.
- Day 3's benchmark generator depends on Indian number formatting (lakh/crore
  grouping) — that string-matching is load-bearing, not a detail.

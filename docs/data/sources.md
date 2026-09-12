# Data sources

Provenance, licensing and reliability of every byte in the system.

**Status:** ✅ all sources live and verified 2026-09-05

---

## Summary

| Source | Provides | Access | Cost | Reliability |
|---|---|---|---|---|
| Yahoo Finance (`yfinance`) | Daily OHLCV, `.NS` symbols | Unofficial Python client | ₹0 | Medium — unofficial |
| Yahoo Finance (`yfinance`) | Reported financial statements | Same | ₹0 | Medium — vendor normalisation |
| Company IR pages | Annual report PDFs | Direct HTTPS | ₹0 | High — but 2 of 12 bot-block |

---

## 1. Market prices — Yahoo Finance

**Accessed by:** `scripts/acquire_prices.py` via `yfinance`
**Symbols:** NSE tickers with a `.NS` suffix (`RELIANCE.NS`)
**Window:** 5 years of daily bars
**Volume:** 14,879 rows across 12 companies
**Verified:** 2026-09-05 — RELIANCE ₹1,302.50 close, live ₹1,322.00; TCS ₹2,320.10

### Known behaviour

| Behaviour | Consequence | Handling |
|---|---|---|
| A session in progress returns Open/High/Low/Volume with **`Close` = NaN** | `df.iloc[-1]["Close"]` is NaN, intermittently and only during market hours | `prices.drop_partial_bar()` |
| A *completed* session can also carry a NaN close | Same, but not reproducible by time of day | Same guard — observed on DRREDDY, 2026-09-04 |
| `.BO` (BSE) data is thinner than `.NS` | Fewer bars | `.NS` used throughout |

### Reliability

`yfinance` is an unofficial client for an undocumented endpoint. It breaks
occasionally when Yahoo changes its API. Mitigated by pinning the version and by
ingestion being idempotent — a failed run is retried, not repaired by hand.

🧭 **If it breaks permanently:** NSE publishes daily Bhavcopy files. Stooq was
evaluated and rejected — it now sits behind a JavaScript proof-of-work challenge
and returns an HTML shim to any scripted request (verified 2026-09-05).

---

## 2. Reported financials — Yahoo Finance

**Accessed by:** `scripts/acquire_facts.py`
**Statements:** `income_stmt`, `balance_sheet`, `cashflow`
**Coverage:** 5 fiscal years × ~174 line items per company
**Volume:** 8,532 facts, FY2022–FY2026

### This is the evaluation oracle

Every row is a verifiable `(question, answer)` pair. Day 3 searches the parsed
reports for these values to auto-label which page contains each answer — see
[data-flow.md](../architecture/data-flow.md#the-number-bridge).

### The currency trap

**`financialCurrency` is not the quote currency.** Verified across all 12:

| Reporting currency | Companies |
|---|---|
| INR | 11 |
| **USD** | **INFY** |

Infosys quotes in rupees on the NSE and publishes its statements in dollars.
Inferring currency from the exchange suffix made Infosys appear ~85× smaller
than Wipro, and would have made the benchmark search for `1,928` in a document
printing `₹1,62,990 crore` — a silent, total failure for that company.

Handled: `companies.financial_currency` is read from the vendor and flows into
every fact's `unit`.

### Accuracy caveat — read this before trusting a number

These are **Yahoo's normalisation** of the filed statements, not the filed
statements themselves. Line-item names are Yahoo's taxonomy (`Total Revenue`,
`Diluted NI Availto Com Stockholders`), not the company's. Values can differ
from the annual report through different consolidation or restatement.

**This is why the benchmark generator discards facts it cannot locate in the
source document.** A vendor/filing disagreement reduces coverage; it never
corrupts the metric. See [ADR-001](../adr/0001-domain-and-corpus.md).

---

## 3. Annual report PDFs — company investor-relations pages

**Accessed by:** `scripts/download_docs.py` from `configs/documents.yaml`
**Volume:** 6 documents, 2,056 pages, ~68 MB

| Ticker | FY | Host | Pages | Fetch |
|---|---:|---|---:|---|
| RELIANCE | 2025 | ril.com | 146 | ✅ auto |
| SUNPHARMA | 2025 | sunpharma.com | 326 | ✅ auto |
| SUNPHARMA | 2024 | sunpharma.com | 312 | ✅ auto |
| HDFCBANK | 2025 | hdfc.bank.in | 590 | ✅ auto |
| ICICIBANK | 2025 | icici.bank.in | 341 | ✅ auto |
| ICICIBANK | 2024 | icicibank.com | 341 | ✅ auto |
| TCS | 2025 | tcs.com | — | ⚠️ **manual** |
| INFY | 2025 | infosys.com | — | ⚠️ **manual** |

### Bot protection

Verified 2026-09-05: `tcs.com` and `infosys.com` return **HTTP 403** with an
HTML challenge page to any scripted request — including with a full browser
User-Agent, `Accept-Language`, and a matching `Referer`.

**These are not worked around.** They are marked `fetch: manual`: the script
prints the URL and target path, the file is downloaded once in a browser, and
the SHA-256 checksum still guarantees every copy of the corpus is identical.
Reproducibility is preserved without defeating a site's access controls.

### Licensing

Annual reports are published by the companies for public access. They are
**downloaded, not redistributed** — no PDF is committed to this repository. The
repository contains only URLs and checksums, so anyone can reconstruct the same
corpus from the original sources.

### Why not Screener.in or the exchange portals

| Source | Why not |
|---|---|
| **Screener.in** | Its value *is* the aggregated data. A scraper for it in a public repository is a liability to both the repository and the account. Excellent as a manual research tool — used that way. |
| **BSE / NSE portals** | Cookie-gated and fragile. The same PDFs are on the companies' own servers. |

---

## 4. What was evaluated and rejected

| Candidate | Verdict |
|---|---|
| **SEC EDGAR** (US filings) | Stronger oracle — XBRL gives 27,114 facts for NVIDIA alone, each carrying the filing accession number — and better reproducibility. Rejected on the owner's preference for Indian markets, reaffirmed after the tradeoff was presented. Best fallback if IR-page curation becomes unsustainable. |
| **Stooq** | Dead as a scripted source — JavaScript proof-of-work challenge. |
| **Alpha Vantage** | Free tier too restrictive for bulk history. |
| **arXiv / PubMed** | No numeric ground truth; every eval question would be hand-written. |
| **IRENA / Our World in Data** | Strong runner-up, better charts, but no live market dimension. |

---

## 5. Refresh

| Data | Cadence | Command |
|---|---|---|
| Prices | Daily | notebook `01_acquire_prices.ipynb` |
| Financials | Quarterly | notebook `02_acquire_facts.ipynb` |
| Documents | Annually | edit `configs/documents.yaml`, then notebook `03` |
| Elements | After any document change | notebook `04_parse_documents.ipynb` |

All four are idempotent and safe to re-run.

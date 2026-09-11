# 📊 Bull AI Research Report Generator

## ⚡ Quick Summary

This project takes a company name and an uploaded financial document (PDF, CSV, or TXT) and
returns a downloadable PDF research report matching the layout of a professional equity-research
report. The layout was rebuilt from scratch to match the structure and format of a reference
sample — no third-party content is reproduced (see `ENGINEERING_REPORT.md`, ADR-0004). A single
FastAPI endpoint runs the whole pipeline synchronously: ingest the document, extract structured
data with Claude, build charts, map fields with a strict no-fabrication policy, and render the
final PDF.

It was built as a take-home engineering assessment for [Bull AI](https://bull-ai.in), whose own
product performs AI-driven equity research at scale across thousands of stocks. This project
mirrors that same problem — arbitrary, inconsistently structured company filings in, a trustworthy
analyst-style report out — at MVP scope.

### One pipeline, one upload, one PDF — extraction that never guesses when the source document doesn't say

---

## 🏷️ Project Badges

[![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Anthropic Claude](https://img.shields.io/badge/Anthropic-Claude-D97757?style=for-the-badge&logo=anthropic&logoColor=white)](https://www.anthropic.com/)
[![Tests](https://img.shields.io/badge/Tests-84_passed-success?style=for-the-badge&logo=pytest&logoColor=white)](https://github.com/deepan-mehta-analytics/bull-ai-research-report-generator)
[![Status](https://img.shields.io/badge/Status-Complete-brightgreen?style=for-the-badge)](https://github.com/deepan-mehta-analytics/bull-ai-research-report-generator)
[![Live Market Data](https://img.shields.io/badge/Live_Data-Yahoo_Finance-orange?style=for-the-badge)](https://github.com/deepan-mehta-analytics/bull-ai-research-report-generator)

---

## 📌 Project Overview

This project implements **an end-to-end pipeline that turns one uploaded financial document into
one downloadable, analyst-styled PDF report — with no fabricated data and no client-side
JavaScript.**

It implements:

- **Zero-JS upload flow** — a plain HTML form (company name + PDF/CSV/TXT file) posts directly to
  `POST /generate`, which returns the PDF as a file download; no frontend framework, no client
  JavaScript at all (`app/main.py`).
- **LLM-driven structured extraction** — Anthropic Claude (`claude-opus-5` by default, overridable
  via the `ANTHROPIC_MODEL` env var) extracts a validated schema from raw document text
  (`app/extraction/extractor.py`). Extraction is schema-flexible rather than rules-per-sector: the
  real test documents this was built against (a bank, a power company, and others) share no common
  metric set, so per-sector rule tables would have broken on the second document. See
  `ENGINEERING_REPORT.md` for the ADR trail.
- **Universal missing-field policy** — every field, table row, and chart independently renders
  "Not available in source document" instead of being invented or silently dropped
  (`app/mapping/mapper.py`, `app/mapping/field_map.yaml`).
- **Live market-data enrichment** — Rating, CMP, Target Price, Market Cap, and Sector, almost never
  present in an arbitrary uploaded document, are filled from live Yahoo Finance data as a second,
  independent, clearly-labeled source — never merged with document-extracted content, never
  guessed, and never able to block or break the underlying report if the lookup fails
  (`app/market_data/`, see ADR-0005).
- **Matplotlib dual-axis chart rendering** — chart series from the extracted data are rendered as
  bar charts, with a growth-% line overlay computed arithmetically from the already-extracted values
  (never requested from Claude) when a series' periods share one consistent format, and embedded
  directly in the PDF as base64 PNG data URIs, with no external image hosting
  (`app/charts/chart_builder.py`, see ADR-0006).
- **Jinja2 + WeasyPrint PDF rendering** — the mapped context is rendered to HTML and converted to a
  paginated PDF without a headless browser (`app/render/`).
- **Reproducible sample generation** — `scripts/generate_samples.py` is a CLI that regenerates
  example PDFs from any local source document and company name; it hardcodes no document or
  company names, by design (see `ENGINEERING_REPORT.md`).

---

## ⚙️ Tech Stack

| Layer | Tool | Purpose |
|---|---|---|
| Language | Python 3.11 | Pipeline and API implementation |
| Web framework | FastAPI + uvicorn | Serves the upload form and the `/generate` endpoint |
| Form parsing | python-multipart | Parses the multipart form upload (company name + file) |
| LLM extraction | Anthropic SDK | Structured extraction via `client.messages.stream` + `output_format` |
| Schema validation | Pydantic | Defines and validates the extracted report schema (`app/extraction/schema.py`) |
| Document ingestion | pdfplumber + pandas | Parses PDF text/tables and CSV data (`app/ingestion/loaders.py`) |
| Table formatting | tabulate | Formats tabular data during ingestion/mapping |
| Config | PyYAML | Loads the field-mapping config (`field_map.yaml`) |
| Charting | matplotlib (Agg backend) | Renders chart series to PNG images |
| Live market data | yfinance | Fetches live rating/price/market-cap data from Yahoo Finance (`app/market_data/`) |
| Rendering | Jinja2 + WeasyPrint | Renders the HTML report template and converts it to PDF |
| Testing | pytest + httpx (`TestClient`) | Unit and API-level test suite |

---

## 🎯 Business Problem

Bull AI's own product performs AI-powered equity research that reads company filings and refreshes
analyst-grade narratives across thousands of stocks — including many with inconsistent, sparse, or
unusually structured disclosures. A rules-based extraction pipeline breaks the moment the second
document doesn't share the first document's fields. The harder, more valuable problem is a pipeline
that stays correct under that inconsistency instead of failing silently.

> Can one pipeline turn an arbitrary, inconsistently structured company filing into an
> analyst-grade PDF report without a human in the loop — and fail honestly instead of guessing when
> data is missing?

---

## 🏗️ Architecture

```
[Upload: PDF/CSV/TXT]
        │
        ▼
[load_document]  ── app/ingestion/          normalize the uploaded file into plain text
        │
        ▼
[extract_report_data]  ── app/extraction/   Claude structured extraction → validated ReportData
        │
        ▼
[get_market_data]  ── app/market_data/      best-effort live Yahoo Finance lookup, never blocks/breaks the report
        │
        ▼
[build_charts]  ── app/charts/              render chart series to base64 PNG data URIs
        │
        ▼
[map_to_template_context]  ── app/mapping/  missing-field-safe mapping to template context
        │
        ▼
[render_pdf]  ── app/render/                Jinja2 HTML render → WeasyPrint PDF conversion
        │
        ▼
[PDF download]
```

| Component | Package | Purpose |
|---|---|---|
| API / form | `app/main.py` | Serves the upload form, orchestrates the pipeline, returns the PDF |
| Ingestion | `app/ingestion/` | Turns PDF/CSV/TXT bytes into plain text |
| Extraction | `app/extraction/` | Calls Claude to extract a validated `ReportData` schema |
| Charts | `app/charts/` | Renders numeric chart series to embeddable PNG images |
| Market data | `app/market_data/` | Best-effort live Yahoo Finance lookup for Rating/CMP/Target Price/Market Cap/Sector |
| Mapping | `app/mapping/` | Maps extracted data to template fields with a missing-field policy |
| Render | `app/render/` | Renders the Jinja2 HTML template and converts it to PDF via WeasyPrint |

---

## 📁 Repository Structure

```
bull-ai-research-report-generator/
│
├── app/
│   ├── main.py                          ← FastAPI app: form route + /generate pipeline orchestration
│   ├── ingestion/
│   │   └── loaders.py                   ← PDF/CSV/TXT → plain text
│   ├── extraction/
│   │   ├── extractor.py                 ← Claude structured-extraction call
│   │   └── schema.py                    ← Pydantic ReportData schema
│   ├── mapping/
│   │   ├── mapper.py                    ← ReportData → template context, missing-field policy
│   │   └── field_map.yaml               ← field mapping configuration
│   ├── charts/
│   │   └── chart_builder.py             ← chart series → base64 PNG data URIs
│   ├── market_data/
│   │   ├── schema.py                    ← MarketDataResult model
│   │   ├── formatting.py                ← price/market-cap/rating formatting helpers
│   │   └── lookup.py                    ← ticker resolution + timeout-bounded Yahoo Finance fetch
│   └── render/
│       ├── renderer.py                  ← Jinja2 HTML render + WeasyPrint PDF conversion
│       └── templates/
│           ├── form.html                ← upload form template
│           └── report.html              ← report layout template
│
├── docs/
│   └── decisions/
│       ├── ADR-0001-no-rag.md           ← why no retrieval layer
│       ├── ADR-0002-weasyprint-matplotlib.md   ← why this PDF/chart toolchain
│       ├── ADR-0003-plain-html-frontend.md     ← why zero client JavaScript
│       ├── ADR-0004-full-template-fidelity.md  ← template fidelity + missing-field policy
│       └── ADR-0005-live-market-data-enrichment.md  ← live market data as a second, independent source
│
├── examples/
│   ├── jsw_energy_report.pdf            ← sample report: fully populated fields path
│   └── icici_bank_report.pdf            ← sample report: graceful-degradation path
│
├── scripts/
│   └── generate_samples.py              ← CLI to regenerate example PDFs from any local document
│
├── tests/
│   ├── test_api.py                      ← /generate route, success + error paths
│   ├── test_charts.py                   ← chart series → PNG rendering
│   ├── test_extraction_schema.py        ← ReportData schema validation and defaults
│   ├── test_extractor.py                ← Claude extraction call, mocked
│   ├── test_ingestion.py                ← PDF/CSV/TXT loaders
│   ├── test_mapping.py                  ← missing-field mapping behavior
│   ├── test_market_data.py              ← market-data schema + formatting helpers
│   ├── test_market_data_lookup.py       ← ticker resolution, fetch, timeout, ticker-typo fallback
│   └── test_renderer.py                 ← HTML render + PDF conversion
│
└── requirements.txt                     ← pinned Python dependencies
```

---

## ▶️ How to Run

1. Create and activate a virtual environment, then install dependencies:
   ```
   python -m venv .venv
   source .venv/Scripts/activate      # Windows Git Bash; .venv/bin/activate on macOS/Linux
   pip install -r requirements.txt
   ```
2. Set your Anthropic API key:
   ```
   export ANTHROPIC_API_KEY=your-key-here
   ```
3. Start the server:
   ```
   uvicorn app.main:app --reload
   ```
4. Open `http://127.0.0.1:8000`, enter a company name, upload a PDF/CSV/TXT document, and click
   "Generate report" to download the PDF.
5. Optionally enter a stock ticker (e.g. `JSWENERGY.NS`) to include live market data in the report,
   or leave it blank to auto-match from the company name.

**Windows note:** WeasyPrint needs the GTK3 runtime libraries discoverable on Windows. If
`import weasyprint` fails with a `cannot load library` `OSError`, install the GTK3 runtime (e.g.
from the `tschoonj/GTK-for-Windows-Runtime-Environment-Installer` releases) and set the
`WEASYPRINT_DLL_DIRECTORY` environment variable to its `bin/` directory before running —
`app/render/renderer.py` picks this up automatically on `sys.platform == "win32"`; it's a no-op on
macOS/Linux.

To regenerate the example PDFs: `python scripts/generate_samples.py --help` for usage (it takes
the company name, source document path, and output filename as CLI arguments — no document names
are hardcoded).

### ☁️ CI

Tests run automatically on every push/PR via GitHub Actions — see
`.github/workflows/tests.yml`.

---

## 🧪 Tests

```
pytest
```

**84 passed**, 0 failed (verified against `main`, with `WEASYPRINT_DLL_DIRECTORY` set on Windows).
The suite is fully mocked against the Anthropic API and against Yahoo Finance (`yfinance`) — no
network access or API key is required to run it. CI (`.github/workflows/tests.yml`) runs the same
suite on every push/PR.

| Test file | Covers |
|---|---|
| `test_extraction_schema.py` | `ReportData` schema validation and field defaults |
| `test_ingestion.py` | PDF/CSV/TXT → plain text loaders |
| `test_extractor.py` | Claude extraction call (mocked) |
| `test_mapping.py` | Missing-field mapping behavior and null-safety |
| `test_charts.py` | Chart series → base64 PNG rendering |
| `test_market_data.py` | Market-data schema defaults and price/market-cap/rating formatting |
| `test_market_data_lookup.py` | Ticker resolution, fetch, the 8s timeout guarantee, ticker-typo fallback |
| `test_renderer.py` | Jinja2 HTML render + WeasyPrint PDF conversion |
| `test_api.py` | `/generate` route, success and error paths |

---

## 📊 Results / Performance

This project has no benchmark metrics — it isn't an ML model, so there's no accuracy/latency table
to report. What does exist is two real example reports in `examples/`, generated against the real
Anthropic API from real financial documents:

- `jsw_energy_report.pdf` — demonstrates the **populated-fields path**: a power company's own
  quarterly results deck yields a full financial table with period columns, YoY figures, and charts.
- `icici_bank_report.pdf` — demonstrates the **graceful-degradation path**: the source document
  doesn't support every field (no Rating/CMP/Target Price/Market Cap of its own), so those cells
  show "Not available in source document" instead of being fabricated — while the financial table,
  highlights, and outlook are fully populated from the document's real figures.

Both examples were regenerated with a real ticker (`JSWENERGY.NS`, `ICICIBANK.NS`) and show a
populated Live Market Data section sourced independently from Yahoo Finance.

---

## ⚠️ Known Limitations

- No authentication or rate limiting on `/generate`.
- Single-document-per-request only — no batch processing.
- The growth-line overlay only renders when a chart's category labels all share one consistent
  period format (all-quarter, all-half-year, or all-year); a series mixing formats falls back to a
  plain bar with no growth line, by design — confirmed real on this project's own JSW Energy example.
- Growth is computed as plain index-adjacent arithmetic on already-extracted values, not verified
  against true chronological adjacency — a series whose consecutive categories skip periods
  (confirmed real on the ICICI example) still shows a real, arithmetically-correct growth number for
  that step, just not a clean "one period later" comparison.
- Dual-axis (two independently-scaled y-axes) is a deliberate exception to general dataviz best
  practice, made for sample-fidelity and domain-convention reasons — see ADR-0006.
- At most 3 distinct bar colors are used even though up to 4 charts can render per report; a 4th
  chart's bar color repeats the 1st chart's — each chart's own title remains the real identity
  channel. See ADR-0006.
- At most 4 charts per report — extraction can surface many more series than fit the layout, so the
  first 4 (in the order the model returns them) are kept and the rest are dropped.
- Wide tables shrink rather than paginate: when a document supplies more than ~6 distinct period
  labels, the financial tables step down to a denser type size to stay inside the page margins. At
  that density, a very tall row (many wrapped "Not available in source document" cells) can still
  split across a PDF page boundary, detaching the row's label from part of its data visually — no
  data is lost or misordered, but it's a known cosmetic gap (`tr { page-break-inside: avoid }`
  would fix it).
- No async job queue — the request/response is synchronous, so large documents or slow API
  responses block the request.
- A broad `except Exception` around the pipeline swallows tracebacks server-side with no logging
  (acceptable for MVP scope, noted here as a gap).
- No upload file-size cap.
- Live market-data enrichment depends on an unofficial Yahoo Finance client (`yfinance`); coverage
  and availability aren't guaranteed to stay stable over time, and the feature degrades to "not
  available" rather than erroring when it isn't.
- Acronym-only company names (e.g. querying just "LTTS" instead of the full registered name) may
  fail to auto-match a ticker even when one legitimately exists — intentional, not a bug; type the
  ticker directly in that case.
- The two committed example PDFs show live market data as of their generation time, which will look
  "stale" against the real market within days — inherent to what "live" means, made explicit by the
  caption's own timestamp.

---

## 🔜 Roadmap

- React/Vite frontend with drag-and-drop upload
- Async job queue with live pipeline-stage progress (Reading → Extracting → Charting → Rendering)
- Post-generation on-screen metrics/highlights preview before download
- Additional input formats (DOCX, XLSX)
- Multi-company batch processing, report history/persistence, authentication
- A vector-store/RAG layer for cross-report comparison (e.g. tracking guidance vs. actuals across a
  company's own report history)
- Provider-agnostic LLM extraction (any provider's API key, not just Anthropic's) — see
  `ENGINEERING_REPORT.md` for why this was descoped

---

## 📂 Dataset

This project does not ship a dataset. The two sample PDFs in `examples/` were generated from real
financial documents supplied as part of a take-home assessment. Those source documents are not
included in this repository for confidentiality reasons; `scripts/generate_samples.py` can
regenerate equivalent output from any company document you provide locally.

---

## 👤 Author

**Deepan Mehta**

- Data Analytics → Data Engineering → AI/ML Engineering
- Focused on building end-to-end data and ML systems combining analytics, automation, and
  deployment
- Experience in ETL pipelines, predictive modelling, and analytical databases

🔗 GitHub: [deepan-mehta-analytics](https://github.com/deepan-mehta-analytics)

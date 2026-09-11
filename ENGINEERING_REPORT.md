# Engineering Report

## Summary

Built per `docs/superpowers/specs/2026-09-10-research-report-generator-design.md`. This document
rolls up the architecture decisions (full ADRs in `docs/decisions/`) and records what was
deliberately left out of scope, per the assessment's own "minimal web app" framing and this
project's line-by-line PRD compliance pass (spec Appendix B).

## Decision log

- **ADR-0001 — No RAG.** One document per request fits comfortably in Claude's context window;
  structured multi-field extraction needs the whole document in view, not similarity-retrieved
  fragments that risk splitting a table across a chunk boundary.
- **ADR-0002 — WeasyPrint + matplotlib, not Playwright or ReportLab.** Pure-Python, no browser
  binary to manage under deadline pressure, sufficient CSS support for this layout.
- **ADR-0003 — Plain server-rendered HTML, zero client JavaScript.** The PRD specifies exactly two
  inputs and one output control; a multipart form POST returning a PDF with
  `Content-Disposition: attachment` downloads natively with no JS at all.
- **ADR-0004 — Full template fidelity, universal missing-field handling, no fabricated advice.**
  Every section of the sample is rebuilt; every field/row/chart independently renders "Not
  available in source document" rather than being invented or dropped; the disclaimer section
  contains generic, honest text instead of reproducing the original sample's actual regulatory
  filing content.

## Alignment with Bull AI's own product

Bull AI's own site (bull-ai.in) describes "AI-powered equity research that reads filings... and
refreshes analyst-grade narratives... with zero human prompting" across 3000+ stocks, including
many obscure micro-caps with inconsistent disclosure quality — confirmed directly by the test
documents used during development, which span a bank's NII/NIM-based investor deck, a power
company's MW/PLF-based results deck, and others, none sharing a common metric set. This is why
extraction here is fully LLM-driven and schema-flexible rather than rules-per-sector, and why the
missing-field policy refuses to guess: a hallucinated number is a worse failure than a visibly
absent one for a product whose own positioning is "fast enough for markets, calm enough for
conviction."

## Possible extensions if scope allowed

Considered during design, deliberately not built (see spec Section 8):

- React/Vite frontend with drag-and-drop upload
- Async job queue with live pipeline-stage progress (Reading -> Extracting -> Charting -> Rendering)
- Post-generation on-screen metrics/highlights preview before download
- Additional input formats (DOCX, XLSX)
- Multi-company batch processing, report history/persistence, authentication
- A vector-store/RAG layer for cross-report comparison (e.g. tracking guidance vs. actuals across
  a company's own report history — directly analogous to Bull AI's own "Guidance vs. Actuals"
  feature)
- Dual-axis bar+line charts (value + growth %) matching the sample's exact chart style, instead of
  v1's bar-only charts
- **Provider-agnostic LLM extraction.** Considered supporting any LLM provider's API key, not just
  Anthropic's. Descoped: Anthropic's `client.messages.parse(output_format=ReportData)` is a
  convenience wrapper with automatic schema validation against the Pydantic model; a
  provider-agnostic version (e.g. via `litellm`) would lose that guarantee and require hand-rolled
  JSON-schema prompting, manual parsing, and retry logic per provider — a new
  `app/extraction/providers/` module, a new ADR, and rework of the already-reviewed extractor, none
  of which the assessment's scope called for.

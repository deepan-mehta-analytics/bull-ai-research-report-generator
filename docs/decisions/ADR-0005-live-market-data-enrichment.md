# ADR-0005: Live market-data enrichment as a second, independent data source

## Context
ADR-0004 established that every report field is either extracted from the uploaded document or
marked "Not available in source document" - never fabricated. In practice, 5 CompanyData fields
(sector, rating, target price, CMP, market cap) almost never populate this way: a company's own
filing almost never states its own analyst rating or target price, since those are sell-side
research artifacts, not something a company reports about itself.

## Decision
Add a second, completely independent data source - live market data from Yahoo Finance
(`yfinance`) - scoped to exactly those 5 fields. It is never merged visually with document-extracted
content: it renders in its own section, with its own caption stating it is live data "not from the
uploaded document," and its own distinct missing-field marker (`MARKET_DATA_MISSING_TEXT`, never
the same string as `MISSING_TEXT`) so a field this source doesn't cover can never contradict its
own section's provenance claim.

The lookup is strictly best-effort: it can never block the pipeline longer than a hard 8-second
timeout, and it can never prevent the underlying document-based report from generating, even on
total failure. Auto-matching a company name to a ticker (when no ticker is typed) never accepts an
ambiguous result - exactly one unambiguous, name-overlapping match, or "not available." A
typo'd/wrong manually-typed ticker falls back to auto-match rather than simply failing.

## Consequences
- ADR-0004's no-fabrication guarantee is preserved for document-extracted content - this is a new,
  honestly-labeled source, not the extraction pipeline pretending to know things the document
  didn't say.
- New external dependency (`yfinance`, an unofficial Yahoo Finance client) and a new failure
  surface, fully isolated: every failure mode degrades to "not available," never an exception, never
  wrong data under the right company's name.
- Live data reflects the moment a report is generated, not a fixed point in time - documented as a
  known, accepted characteristic (see README Known Limitations), not a bug.
- Charts remain v1 bar-only in this same release - richer charts (dual-axis, per-series color,
  wiring `yoy_growth`/`qoq_growth` into visuals) were explicitly scoped out given the deadline and
  moved to Roadmap, not built alongside this feature.

# ADR-0002: WeasyPrint + matplotlib for PDF generation

## Context
The PDF must reproduce the sample's boxed/tabular layout, colored section
bands, bordered tables, and bar+line-style charts, built under a hard
34-hour deadline.

## Decision
Render the report as Jinja2-templated HTML/CSS, convert to PDF with
WeasyPrint (pure Python, no browser binary). Render charts as static PNGs
with matplotlib, embedded as base64 data URIs in the HTML before conversion.

## Consequences
- `pip install` only — no headless Chromium, no Node/JS toolchain, no
  Chart.js dependency to wire up.
- WeasyPrint's CSS support (borders, background colors, standard box model,
  `<table>`) is sufficient for this layout; avoided modern flexbox/grid in
  the template to reduce rendering-quirk risk.
- Slightly less pixel-perfect than a headless-Chromium render of live
  Chart.js canvases. Charts started bar-only in v1 (no dual-axis
  growth-percentage line overlay like the sample) as a documented, considered
  trade-off in ENGINEERING_REPORT.md, not a limitation discovered late;
  dual-axis growth overlays shipped in a later pass — see ADR-0006 for why
  a dual-axis chart was chosen despite general dataviz best-practice
  guidance against it.

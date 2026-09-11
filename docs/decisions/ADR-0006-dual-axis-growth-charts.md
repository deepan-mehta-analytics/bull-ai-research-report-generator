# ADR-0006: Dual-axis growth-line charts as a deliberate dataviz exception

## Context
The `dataviz` skill's non-negotiable rule states dual-axis (two y-scales) charts are "the #1 chart
mistake" for general-purpose dashboards, because arbitrary independent axis scaling can visually
imply a false correlation between two unrelated-scale series. This directly conflicts with README/
ADR-0002/ADR-0005's existing description of the richer-charts feature and with ADR-0004's fidelity
mandate: the reference sample itself uses a dual-axis bar+line value/growth-% chart, a completely
standard convention in equity research (Bloomberg, FactSet, and sell-side research notes use it
constantly).

## Decision
Proceed with dual-axis bar+growth-line charts, as a deliberate, explicitly-documented domain
exception - not a silent deviation from the `dataviz` skill's general guidance. Equity research is a
specific domain where this encoding is the accepted reader convention, and ADR-0004 already commits
this project to sample fidelity over generic convention.

## Consequences
- Charts now carry two independently-scaled axes, mitigated by: a legend on every dual-axis chart
  (dataviz skill: ">=2 encoded series always gets a legend"); a growth line rendered in a fixed,
  non-competing color (`#0b0b0b`, this project's text-primary token) rather than a bright hue that
  could be mistaken for a third bar-series color; and this ADR itself, so a future reader sees the
  trade-off was considered, not missed.
- Growth is computed arithmetically from already-extracted `ChartSeries.values`, never requested
  from Claude - the real source documents this project was built against (ICICI, JSW Energy, LTTS,
  POCL, all in `local-input/`) only ever state a single current-period growth figure per metric,
  never a full per-period series, so asking Claude to extract that data would rarely populate.
- The growth line only renders when a chart's categories all share one consistent period format
  (all-quarter, all-half-year, or all-year) - confirmed real on this project's own shipped examples
  that categories can mix formats (JSW Energy) or skip periods within one format (ICICI). A mixed
  series falls back to a plain bar with no growth line, by design.
- Bar colors are capped at 3 distinct validated hues even though `MAX_CHART_SERIES` allows 4 charts
  - a 4-hue all-pairs-safe categorical set does not exist in this palette at this chart count; each
  chart's own title remains the true identity channel across charts, not color.

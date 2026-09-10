# ADR-0004: Full template fidelity, universal missing-field handling, no fabricated advice

## Context
The PRD's "What to build" section says to recreate the sample "same
layout/sections/fields & tables," and the acceptance criteria say the
template must match the sample "closely (layout + section order)." The
sample also contains fields no arbitrary uploaded document will ever supply
(an analyst's BUY/HOLD rating, a target price, three years of prior rating
history) and a page of the reference sample's own SEBI registration number,
named compliance officer, and analyst certification.

## Decision
Rebuild every section of the sample, not a curated subset. Every field,
table row, and chart is independently null-safe: when extraction doesn't
support a value, the template renders the literal text "Not available in
source document" rather than omitting the section or inventing a value.
The disclaimer section keeps its position in the layout but contains
generic, honest, self-referential text (this is an AI-assisted extraction
tool, not a registered research entity) instead of the reference sample's
actual regulatory content, since reproducing that verbatim would misrepresent this
tool as SEBI-registered, which is false.

## Consequences
- Two PRD requirements ("same layout/sections" and "handles missing fields
  gracefully") are satisfied by one mechanism instead of being treated as
  separate problems.
- The rating/target-price box and the historical-ratings section will show
  "Not available in source document" for effectively every test document,
  which is the correct, honest behavior — not a bug to fix later.
- More Jinja2/CSS template surface to build than a 2-page curated version
  would have needed; accepted as the actual, not reduced, scope.

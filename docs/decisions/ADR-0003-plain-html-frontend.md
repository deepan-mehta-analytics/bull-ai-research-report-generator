# ADR-0003: Plain server-rendered HTML frontend, zero client JavaScript

## Context
The PRD specifies exactly two inputs (company name, file) and one output
control (a download button) — literally "Simple UI." An earlier design pass
proposed React/Vite, drag-and-drop, an async job queue with live
pipeline-stage progress polling, and a post-generation metrics-preview
screen.

## Decision
Ship a single Jinja2-rendered HTML page with a plain `<form>` (text input +
file input + submit button). The form POSTs as multipart/form-data directly
to `/generate`, which runs the pipeline synchronously and returns one of two
plain HTML pages — no JavaScript at all, no new endpoint, no server-side
storage of the generated file:
- **Success:** a confirmation page naming the company, with the generated PDF
  embedded as a `data:application/pdf;base64,...` download link (click-through,
  not auto-triggered — an explicit click is a clearer, more reliable
  confirmation than an auto-download that browsers may silently block) and a
  link back to the form.
- **Failure:** the same form re-rendered with an inline, plain-language error
  message — a small mapping in `app/main.py` translates known exception types
  (Anthropic API errors, schema-validation errors) into actionable text;
  anything unmapped falls through to its own message unchanged.

## Consequences
- No build step, no Node dependency, nothing beyond the two PRD-specified
  controls for a reviewer to evaluate.
- No async job infrastructure (no job-status store, no polling endpoint) —
  the request is synchronous; the user's browser shows its native "waiting
  for response" state during the ~10-30 second pipeline run.
- Embedding the PDF as a data: URI avoids adding any transient server-side
  storage (a token store, a TTL/eviction policy) just to let a follow-up
  request re-fetch the same file — at the cost of ~33% response-size
  inflation from base64 encoding, negligible for the report sizes this
  pipeline produces.
- The rejected alternative (React, drag-and-drop, live stage progress,
  metrics preview) is recorded in ENGINEERING_REPORT.md as "possible if
  scope allowed," not silently dropped.

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
to `/generate`, which returns the PDF with a `Content-Disposition: attachment`
header — the browser downloads the file natively with no JavaScript at all.
On error, the same route re-renders the form with an inline message.

## Consequences
- No build step, no Node dependency, nothing beyond the two PRD-specified
  controls for a reviewer to evaluate.
- No async job infrastructure (no job-status store, no polling endpoint) —
  the request is synchronous; the user's browser shows its native "waiting
  for response" state during the ~10-30 second pipeline run.
- The rejected alternative (React, drag-and-drop, live stage progress,
  metrics preview) is recorded in ENGINEERING_REPORT.md as "possible if
  scope allowed," not silently dropped.

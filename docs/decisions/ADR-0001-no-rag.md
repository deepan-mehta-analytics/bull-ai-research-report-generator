# ADR-0001: No RAG for extraction

## Context
Each report generation processes exactly one uploaded document. The largest
test document (a 58-page investor deck) extracts to roughly 15-20K tokens of
text, well inside Claude's context window. Extraction must populate 15-20
schema fields that can be scattered anywhere in the document, including
inside tables.

## Decision
Use full-document-in-context, single-shot structured extraction: normalize
the uploaded file to plain text, send the whole text to Claude in one call,
get back schema-validated JSON. No chunking, no embeddings, no vector store,
no similarity retrieval.

## Consequences
- Simpler pipeline: one module (`extraction/`), one API call per report.
- No risk of a table being split across chunk boundaries and losing
  row/column alignment.
- Does not scale to documents that exceed the context window (multi-hundred
  page annual reports with appendices) — out of scope for this project.
- Does not support cross-report comparison (e.g. "how does this compare to
  the last 8 quarters we've generated for this company") — a v2 feature that
  would justify a vector store over an archive of past extractions.

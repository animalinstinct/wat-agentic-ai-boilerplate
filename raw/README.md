# Raw Sources

This directory holds curated source material for the LLM wiki.

## Rules

- Treat files here as immutable source of truth. Read them, cite them, and summarize them, but do not rewrite their contents during wiki maintenance.
- Treat the top level of `raw/` as the ingestion inbox. After a source is ingested, move it to `raw/ingested/`.
- Put downloaded or clipped images in `raw/assets/` and reference them from source notes when useful.
- Do not store secrets here. Credentials still belong only in `.env`, `credentials.json`, or `token.json`.
- Prefer stable, descriptive filenames: `2026-06-12-topic-source-title.md`.

When a source has been processed, create or update a corresponding page under `wiki/sources/`, update `wiki/index.md`, append to `wiki/log.md`, then run `python3 tools/wiki.py archive-source raw/path.md`.

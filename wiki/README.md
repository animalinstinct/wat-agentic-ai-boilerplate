# LLM Wiki

This is the persistent knowledge layer for the WAT system.

The wiki is generated and maintained by the agent. Humans curate sources and steer the analysis; the agent keeps the markdown knowledge base current.

## Layers

- `raw/`: immutable curated sources.
- `wiki/`: generated markdown pages, summaries, entity pages, concept pages, syntheses, and saved query outputs.
- `CLAUDE.md`: the schema and operating contract that tells agents how to maintain the wiki.

## Required Files

- `index.md`: content-oriented catalog. Read it first when answering wiki questions.
- `log.md`: append-only timeline of ingests, queries, lint passes, and maintenance.

Use `python3 tools/wiki.py status` to inspect the wiki and `python3 tools/wiki.py lint` before finishing wiki maintenance work.

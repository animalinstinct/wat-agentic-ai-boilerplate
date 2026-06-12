# Workflow: Lint The LLM Wiki

## Objective

Health-check the wiki so it remains navigable, current, and internally consistent.

## Required Inputs

- None, unless the user asks for a targeted audit

## Tools

- `python3 tools/wiki.py status`
- `python3 tools/wiki.py lint --strict`
- `rg "\[\[" wiki`

## Procedure

1. Run `python3 tools/wiki.py status` to inspect counts, recent activity, pending raw inbox sources, and archived ingested sources.
2. Run `python3 tools/wiki.py lint --strict`.
3. Fix broken links, missing index entries, malformed log headings, and missing frontmatter.
4. Search for concepts repeatedly mentioned but lacking dedicated pages.
5. Look for stale claims, contradictions, orphan pages, and pages that should be cross-linked.
6. Update affected pages and `wiki/index.md`.
7. Append a lint entry to `wiki/log.md` summarizing what changed.
8. Re-run lint and report remaining warnings or risks.

## Expected Output

- Passing strict lint where feasible
- Updated links, index entries, and pages
- Appended `wiki/log.md` entry

## Edge Cases

- If a warning requires domain judgment, leave a clear note in the relevant page and ask the user how to resolve it.
- If a source is missing or private, do not invent evidence. Mark the gap.

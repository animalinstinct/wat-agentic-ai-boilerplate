#!/usr/bin/env python3
"""Small deterministic helpers for the WAT LLM wiki."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw"
INGESTED_DIR = RAW_DIR / "ingested"
WIKI_DIR = ROOT / "wiki"
INDEX_PATH = WIKI_DIR / "index.md"
LOG_PATH = WIKI_DIR / "log.md"

PAGE_TYPES = {
    "source": "sources",
    "entity": "entities",
    "concept": "concepts",
    "synthesis": "syntheses",
    "query": "queries",
}

LOG_HEADING_RE = re.compile(
    r"^## \[\d{4}-\d{2}-\d{2}\] (ingest|query|lint|maintenance|note) \| .+"
)
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
MDLINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


@dataclass
class Issue:
    level: str
    message: str


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def wiki_markdown_files(include_templates: bool = False) -> list[Path]:
    if not WIKI_DIR.exists():
        return []
    files = sorted(WIKI_DIR.rglob("*.md"))
    if include_templates:
        return files
    return [path for path in files if "_templates" not in path.parts]


def content_pages() -> list[Path]:
    excluded = {INDEX_PATH, LOG_PATH, WIKI_DIR / "README.md"}
    return [path for path in wiki_markdown_files() if path not in excluded]


def raw_source_files(include_ingested: bool = False) -> list[Path]:
    if not RAW_DIR.exists():
        return []
    files: list[Path] = []
    for path in sorted(RAW_DIR.rglob("*")):
        if not path.is_file():
            continue
        if path.name in {".gitkeep", "README.md"}:
            continue
        parts = path.relative_to(RAW_DIR).parts
        if parts and parts[0] == "assets":
            continue
        if not include_ingested and parts and parts[0] == "ingested":
            continue
        files.append(path)
    return files


def ingested_source_files() -> list[Path]:
    return [
        path
        for path in raw_source_files(include_ingested=True)
        if path.relative_to(RAW_DIR).parts[0] == "ingested"
    ]


def source_page_text() -> str:
    source_dir = WIKI_DIR / "sources"
    if not source_dir.exists():
        return ""
    return "\n".join(read_text(path) for path in sorted(source_dir.glob("*.md")))


def slugify(title: str) -> str:
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "untitled"


def has_frontmatter(text: str) -> bool:
    if not text.startswith("---\n"):
        return False
    return "\n---\n" in text[4:]


def parse_frontmatter(text: str) -> dict[str, str]:
    if not has_frontmatter(text):
        return {}
    block = text.split("\n---\n", 1)[0].removeprefix("---\n")
    data: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data


def page_targets() -> dict[str, Path]:
    targets: dict[str, Path] = {}
    for path in wiki_markdown_files(include_templates=False):
        if path == LOG_PATH:
            continue
        wiki_rel = path.relative_to(WIKI_DIR).with_suffix("").as_posix()
        targets[wiki_rel.lower()] = path
        targets[path.stem.lower()] = path
    return targets


def resolve_wikilink(target: str, targets: dict[str, Path]) -> Path | None:
    target = target.split("|", 1)[0].split("#", 1)[0].strip()
    if not target:
        return None
    normalized = target.removesuffix(".md").strip("/").lower()
    if normalized in targets:
        return targets[normalized]
    slug = slugify(Path(normalized).name)
    return targets.get(slug)


def is_external_link(target: str) -> bool:
    return bool(re.match(r"^[a-z][a-z0-9+.-]*:", target)) or target.startswith("#")


def resolve_raw_inbox_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()

    try:
        path.relative_to(RAW_DIR.resolve())
    except ValueError:
        raise ValueError(f"Source must be under {rel(RAW_DIR)}: {raw_path}") from None

    try:
        path.relative_to(INGESTED_DIR.resolve())
    except ValueError:
        pass
    else:
        raise ValueError(f"Source is already under {rel(INGESTED_DIR)}: {raw_path}")

    parts = path.relative_to(RAW_DIR.resolve()).parts
    if parts and parts[0] == "assets":
        raise ValueError(f"Source assets are not archived by this command: {raw_path}")

    if not path.exists():
        raise FileNotFoundError(f"Source does not exist: {raw_path}")
    if not path.is_file():
        raise ValueError(f"Source must be a file: {raw_path}")
    return path


def unique_destination(path: Path) -> Path:
    relative = path.relative_to(RAW_DIR.resolve())
    destination = INGESTED_DIR / relative
    if not destination.exists():
        return destination

    stem = destination.stem
    suffix = destination.suffix
    parent = destination.parent
    counter = 2
    while True:
        candidate = parent / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def replace_wiki_source_references(old_rel: str, new_rel: str) -> list[Path]:
    changed: list[Path] = []
    for path in wiki_markdown_files(include_templates=False):
        text = read_text(path)
        updated = text.replace(old_rel, new_rel)
        if updated == text:
            continue
        path.write_text(updated, encoding="utf-8")
        changed.append(path)
    return changed


def lint(strict: bool = False) -> list[Issue]:
    issues: list[Issue] = []
    required_paths = [RAW_DIR, INGESTED_DIR, WIKI_DIR, INDEX_PATH, LOG_PATH]
    for path in required_paths:
        if not path.exists():
            issues.append(Issue("ERROR", f"Missing required path: {rel(path)}"))

    if not WIKI_DIR.exists():
        return issues

    index_text = read_text(INDEX_PATH) if INDEX_PATH.exists() else ""
    targets = page_targets()

    for path in content_pages():
        text = read_text(path)
        metadata = parse_frontmatter(text)
        if not metadata:
            issues.append(Issue("WARN", f"Missing frontmatter: {rel(path)}"))
        else:
            for field in ("title", "type", "status", "updated"):
                if field not in metadata:
                    issues.append(Issue("WARN", f"Missing `{field}` in frontmatter: {rel(path)}"))

        page_ref = path.relative_to(WIKI_DIR).as_posix()
        wikilink_ref = page_ref.removesuffix(".md")
        if page_ref not in index_text and f"[[{wikilink_ref}" not in index_text:
            issues.append(Issue("WARN", f"Page is not listed in wiki/index.md: {rel(path)}"))

        for raw_target in WIKILINK_RE.findall(text):
            if resolve_wikilink(raw_target, targets) is None:
                issues.append(Issue("ERROR", f"Broken wiki link in {rel(path)}: [[{raw_target}]]"))

        for raw_target in MDLINK_RE.findall(text):
            target = raw_target.split("#", 1)[0]
            if not target or is_external_link(target):
                continue
            candidate = (path.parent / target).resolve()
            if not candidate.exists():
                issues.append(Issue("ERROR", f"Broken markdown link in {rel(path)}: {raw_target}"))

    if LOG_PATH.exists():
        for line_number, line in enumerate(read_text(LOG_PATH).splitlines(), start=1):
            if line.startswith("## [") and not LOG_HEADING_RE.match(line):
                issues.append(Issue("ERROR", f"Malformed log heading at {rel(LOG_PATH)}:{line_number}"))

    processed_text = source_page_text()
    for path in raw_source_files():
        raw_rel = path.relative_to(ROOT).as_posix()
        if raw_rel not in processed_text and path.name not in processed_text:
            issues.append(Issue("WARN", f"Raw inbox source has no matching source page: {raw_rel}"))

    for path in ingested_source_files():
        raw_rel = path.relative_to(ROOT).as_posix()
        if raw_rel not in processed_text and path.name not in processed_text:
            issues.append(Issue("WARN", f"Ingested source has no matching source page: {raw_rel}"))

    if strict:
        issues = [Issue("ERROR" if issue.level == "WARN" else issue.level, issue.message) for issue in issues]
    return issues


def command_status(_: argparse.Namespace) -> int:
    pages = content_pages()
    raw_files = raw_source_files()
    ingested_files = ingested_source_files()
    print("LLM Wiki Status")
    print(f"- Raw inbox sources: {len(raw_files)}")
    print(f"- Archived ingested sources: {len(ingested_files)}")
    print(f"- Wiki content pages: {len(pages)}")
    print(f"- Index: {'present' if INDEX_PATH.exists() else 'missing'}")
    print(f"- Log: {'present' if LOG_PATH.exists() else 'missing'}")

    if LOG_PATH.exists():
        headings = [line for line in read_text(LOG_PATH).splitlines() if line.startswith("## [")]
        print("- Recent log entries:")
        for heading in headings[-5:]:
            print(f"  {heading}")
        if not headings:
            print("  None")

    processed_text = source_page_text()
    unprocessed = [
        path.relative_to(ROOT).as_posix()
        for path in raw_files
        if path.relative_to(ROOT).as_posix() not in processed_text and path.name not in processed_text
    ]
    if unprocessed:
        print("- Unprocessed raw inbox sources:")
        for item in unprocessed:
            print(f"  {item}")
    return 0


def command_lint(args: argparse.Namespace) -> int:
    issues = lint(strict=args.strict)
    if not issues:
        print("Wiki lint passed.")
        return 0

    for issue in issues:
        print(f"{issue.level}: {issue.message}")

    return 1 if any(issue.level == "ERROR" for issue in issues) else 0


def command_log(args: argparse.Namespace) -> int:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary = args.summary.strip() if args.summary else "No summary provided."
    entry = f"\n## [{date.today().isoformat()}] {args.type} | {args.title}\n\n- {summary}\n"
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(entry)
    print(f"Appended log entry to {rel(LOG_PATH)}")
    return 0


def command_new_page(args: argparse.Namespace) -> int:
    page_type = args.type
    directory = WIKI_DIR / PAGE_TYPES[page_type]
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{slugify(args.title)}.md"
    if path.exists() and not args.force:
        print(f"Refusing to overwrite existing page: {rel(path)}", file=sys.stderr)
        return 1

    today = date.today().isoformat()
    extra = f'source_path: {args.source}\n' if args.source else ""
    content = (
        "---\n"
        f'title: "{args.title}"\n'
        f"type: {page_type}\n"
        "status: draft\n"
        f"created: {today}\n"
        f"updated: {today}\n"
        f"{extra}"
        "---\n\n"
        f"# {args.title}\n\n"
        "## Summary\n\n"
        "Draft this page from source evidence and wiki context.\n\n"
        "## Evidence\n\n"
        "- Add links to source pages, raw source paths, or related wiki pages.\n\n"
        "## Open Questions\n\n"
        "- Add unresolved questions or gaps.\n"
    )
    path.write_text(content, encoding="utf-8")
    print(f"Created {rel(path)}")
    return 0


def command_archive_source(args: argparse.Namespace) -> int:
    try:
        source = resolve_raw_inbox_path(args.source)
    except (FileNotFoundError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1

    destination = unique_destination(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    old_rel = source.relative_to(ROOT).as_posix()
    source.rename(destination)
    new_rel = destination.relative_to(ROOT).as_posix()
    changed = replace_wiki_source_references(old_rel, new_rel)

    print(f"Moved {old_rel} -> {new_rel}")
    if changed:
        print("Updated wiki references:")
        for path in changed:
            print(f"  {rel(path)}")
    else:
        print("No wiki references needed updates.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Show wiki counts and recent activity")
    status_parser.set_defaults(func=command_status)

    lint_parser = subparsers.add_parser("lint", help="Check wiki structure and links")
    lint_parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    lint_parser.set_defaults(func=command_lint)

    log_parser = subparsers.add_parser("log", help="Append an entry to wiki/log.md")
    log_parser.add_argument("type", choices=["ingest", "query", "lint", "maintenance", "note"])
    log_parser.add_argument("title")
    log_parser.add_argument("--summary", default="")
    log_parser.set_defaults(func=command_log)

    new_page_parser = subparsers.add_parser("new-page", help="Create a draft wiki page")
    new_page_parser.add_argument("type", choices=sorted(PAGE_TYPES))
    new_page_parser.add_argument("title")
    new_page_parser.add_argument("--source", help="Raw source path for source pages")
    new_page_parser.add_argument("--force", action="store_true", help="Overwrite an existing page")
    new_page_parser.set_defaults(func=command_new_page)

    archive_parser = subparsers.add_parser(
        "archive-source", help="Move an ingested raw source into raw/ingested/"
    )
    archive_parser.add_argument("source", help="Path to a source file under raw/")
    archive_parser.set_defaults(func=command_archive_source)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

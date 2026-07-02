#!/usr/bin/env python3
"""Validate PeakGuard Wiki structure, metadata, links, and catalog coverage."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

REQUIRED_FIELDS = {"id", "title", "type", "status"}
ALLOWED_TYPES = {
    "index",
    "status",
    "architecture",
    "operations",
    "concept",
    "reference",
    "roadmap",
    "proposal",
    "decision",
    "runbook",
    "work-note",
    "meta",
    "template",
}
ALLOWED_STATUSES = {"active", "proposed", "accepted", "archived", "superseded"}
DEPRECATED_PATHS = {
    "docs/meta/knowledge-graph.md",
    "docs/meta/writing-guide.md",
}
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)#]+\.md)(?:#[^)]+)?\)")


def parse_frontmatter(path: Path) -> tuple[dict[str, object], str]:
    """Return parsed YAML frontmatter and Markdown body."""
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---\n"):
        raise ValueError("missing opening frontmatter delimiter")

    parts = content.split("---\n", maxsplit=2)
    if len(parts) != 3:
        raise ValueError("missing closing frontmatter delimiter")

    data = yaml.safe_load(parts[1])
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a YAML mapping")
    return data, parts[2]


def repository_root(explicit_root: Path | None) -> Path:
    """Resolve the repository root from an argument or this script's location."""
    if explicit_root is not None:
        return explicit_root.resolve()
    return Path(__file__).resolve().parents[4]


def validate(root: Path) -> list[str]:
    """Collect Wiki validation errors without mutating the repository."""
    docs = root / "docs"
    errors: list[str] = []
    if not docs.is_dir():
        return [f"missing docs directory: {docs}"]

    for deprecated in sorted(DEPRECATED_PATHS):
        if (root / deprecated).exists():
            errors.append(f"deprecated Wiki file exists: {deprecated}")

    pages = sorted(path for path in docs.rglob("*.md") if path.name != "AGENTS.md")
    ids: dict[str, Path] = {}
    catalog_targets: set[Path] = set()
    index_path = docs / "index.md"

    for path in pages:
        relative = path.relative_to(root)
        try:
            metadata, body = parse_frontmatter(path)
        except (OSError, UnicodeError, yaml.YAMLError, ValueError) as exc:
            errors.append(f"{relative}: {exc}")
            continue

        missing = REQUIRED_FIELDS - metadata.keys()
        if missing:
            errors.append(f"{relative}: missing fields {sorted(missing)}")

        page_id = metadata.get("id")
        if not isinstance(page_id, str) or not page_id.strip():
            errors.append(f"{relative}: id must be a non-empty string")
        elif page_id in ids:
            errors.append(
                f"{relative}: duplicate id '{page_id}' also used by "
                f"{ids[page_id].relative_to(root)}"
            )
        else:
            ids[page_id] = path

        if metadata.get("type") not in ALLOWED_TYPES:
            errors.append(f"{relative}: unsupported type '{metadata.get('type')}'")
        if metadata.get("status") not in ALLOWED_STATUSES:
            errors.append(f"{relative}: unsupported status '{metadata.get('status')}'")

        related = metadata.get("related", [])
        if not isinstance(related, list):
            errors.append(f"{relative}: related must be a list")
        else:
            for target_value in related:
                if not isinstance(target_value, str):
                    errors.append(f"{relative}: related entries must be strings")
                    continue
                target = (path.parent / target_value).resolve()
                if not target.is_file():
                    errors.append(f"{relative}: broken related path '{target_value}'")
                elif docs.resolve() not in target.parents and target != docs.resolve():
                    errors.append(
                        f"{relative}: related path leaves docs/ '{target_value}'"
                    )

        for field in ("code", "tests"):
            values = metadata.get(field, [])
            if not isinstance(values, list):
                errors.append(f"{relative}: {field} must be a list")
                continue
            for target_value in values:
                if not isinstance(target_value, str):
                    errors.append(f"{relative}: {field} entries must be strings")
                    continue
                if not (root / target_value).exists():
                    errors.append(f"{relative}: missing {field} path '{target_value}'")

        for target_value in MARKDOWN_LINK.findall(body):
            target = (path.parent / target_value).resolve()
            if not target.is_file():
                errors.append(f"{relative}: broken Markdown link '{target_value}'")
            if path == index_path and target.is_file():
                catalog_targets.add(target)

    if index_path not in pages:
        errors.append("missing docs/index.md")
    else:
        expected = set(pages) - {index_path}
        for missing_page in sorted(expected - catalog_targets):
            errors.append(
                "docs/index.md: missing catalog entry for "
                f"{missing_page.relative_to(docs)}"
            )

    return errors


def main() -> int:
    """Run validation and return a shell-friendly exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="PeakGuard repository root")
    args = parser.parse_args()

    root = repository_root(args.root)
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"Wiki validation failed with {len(errors)} error(s).")
        return 1

    page_count = len(list((root / "docs").rglob("*.md"))) - 1
    print(f"Wiki validation passed for {page_count} document(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

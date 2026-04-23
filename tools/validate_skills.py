#!/usr/bin/env python3
"""Validate SKILL.md frontmatter across repository.

Checks:
- Frontmatter block exists (`--- ... ---`)
- YAML is parseable
- Required keys: `name`, `description`
- Reject known bad args pattern: `args: [..] [..]`
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml


FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?", re.S)
BAD_ARGS_PATTERN = re.compile(r"^args:\s*\[[^\]]*\]\s*\[", re.M)


def iter_skill_files(root: Path) -> list[Path]:
    return sorted(root.rglob("SKILL.md"))


def validate_file(path: Path) -> list[str]:
    issues: list[str] = []
    text = path.read_text(encoding="utf-8")

    m = FRONTMATTER_RE.match(text)
    if not m:
        return ["missing YAML frontmatter block"]

    frontmatter_raw = m.group(1)
    if BAD_ARGS_PATTERN.search(frontmatter_raw):
        issues.append("invalid args syntax: use YAML list, not consecutive [] blocks")

    try:
        data = yaml.safe_load(frontmatter_raw)
    except Exception as exc:  # pragma: no cover - parser detail
        return [f"invalid YAML: {exc}"]

    if not isinstance(data, dict):
        return ["frontmatter must be a YAML mapping/object"]

    for key in ("name", "description"):
        if key not in data:
            issues.append(f"missing required key: {key}")
        elif not isinstance(data[key], str) or not data[key].strip():
            issues.append(f"key `{key}` must be a non-empty string")

    if "args" in data and not isinstance(data["args"], (str, list)):
        issues.append("`args` must be string or list")

    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Repository root (default: current directory)",
    )
    args = parser.parse_args()
    root = args.root.resolve()

    files = iter_skill_files(root)
    if not files:
        print("No SKILL.md files found.")
        return 0

    failed = 0
    for path in files:
        issues = validate_file(path)
        if issues:
            failed += 1
            rel = path.relative_to(root)
            for issue in issues:
                print(f"[FAIL] {rel}: {issue}")

    if failed:
        print(f"\nValidation failed: {failed}/{len(files)} SKILL.md file(s) have issues.")
        return 1

    print(f"Validation passed: {len(files)} SKILL.md files are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


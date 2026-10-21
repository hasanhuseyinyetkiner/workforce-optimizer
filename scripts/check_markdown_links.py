#!/usr/bin/env python3
"""Validate local Markdown links (paths, directories, assets, and heading anchors).

Skips http(s)/mailto/data URLs. Exit 1 on any broken local target or missing anchor.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIR_PARTS = {
    ".git",
    "node_modules",
    ".venv",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    "test-results",
    "playwright-report",
}
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)|!\[([^\]]*)\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def should_skip(path: Path) -> bool:
    return any(part in SKIP_DIR_PARTS for part in path.parts)


def github_slug(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text)
    return text.strip("-")


def heading_slugs(path: Path) -> set[str]:
    slugs: set[str] = set()
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return slugs
    for line in content.splitlines():
        match = HEADING_RE.match(line)
        if match:
            slugs.add(github_slug(match.group(2)))
    return slugs


def iter_markdown_files() -> list[Path]:
    return sorted(
        p for p in ROOT.rglob("*.md") if p.is_file() and not should_skip(p.relative_to(ROOT))
    )


def extract_targets(text: str) -> list[str]:
    targets: list[str] = []
    for match in LINK_RE.finditer(text):
        url = match.group(1) or match.group(3)
        if not url:
            continue
        url = url.strip().strip("<>").split()[0]
        targets.append(url)
    return targets


def main() -> int:
    errors: list[str] = []
    checked = 0

    for md_path in iter_markdown_files():
        rel_md = md_path.relative_to(ROOT).as_posix()
        text = md_path.read_text(encoding="utf-8")
        for raw in extract_targets(text):
            if re.match(r"^(https?://|mailto:|data:)", raw, flags=re.IGNORECASE):
                continue

            path_part, _, fragment = raw.partition("#")
            if not path_part:
                target = md_path
            else:
                target = (md_path.parent / path_part).resolve()
                try:
                    target.relative_to(ROOT.resolve())
                except ValueError:
                    errors.append(f"{rel_md}: escapes repo root -> {raw}")
                    continue
                if not target.exists():
                    errors.append(f"{rel_md}: missing path -> {raw}")
                    continue

            checked += 1
            if fragment:
                if target.is_dir():
                    errors.append(f"{rel_md}: fragment on directory -> {raw}")
                    continue
                if target.suffix.lower() != ".md":
                    continue
                slugs = heading_slugs(target)
                if github_slug(fragment) not in slugs and fragment not in slugs:
                    errors.append(f"{rel_md}: missing anchor -> {raw}")

    if errors:
        print(f"Markdown link check FAILED ({len(errors)} issue(s), {checked} local link(s) checked)")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"Markdown link check OK ({checked} local link(s) across {len(iter_markdown_files())} file(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())

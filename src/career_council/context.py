"""Materials-context gathering for non-grounded (provider) backends.

Cursor-backed personas read the materials folder themselves. Provider backends
(OpenAI/Anthropic/Google) are plain chat calls, so we capture a snapshot of the
candidate's materials (resume, job description, notes) in `cwd` and prepend it to
their prompt.

`--cwd` for a career council is normally an ordinary folder of documents, not a
git repo, so we read text files directly from disk. (If it happens to be a git
repo we still fall back to a file listing.) The snapshot is bounded so we never
blow up a provider context window.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

_MAX_TOTAL_CHARS = 60_000
_MAX_FILE_CHARS = 20_000
_MAX_FILES = 25
# Text formats a resume / JD / notes realistically live in. Binary formats
# (.pdf/.docx) are skipped here — ask the user to export to text, or rely on the
# grounded Cursor backend which can open them.
_TEXT_SUFFIXES = {
    ".txt", ".md", ".markdown", ".rst", ".json", ".yaml", ".yml",
    ".csv", ".tsv", ".html", ".htm", ".tex", ".text", ".log",
}
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".idea", ".vscode"}


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated, {len(text) - limit} more chars] ..."


def _gather_from_filesystem(cwd: str) -> List[str]:
    """Read bounded text content from the materials folder (non-git path)."""

    root = Path(cwd)
    if not root.is_dir():
        return []

    sections: List[str] = []
    total = 0
    count = 0
    for path in sorted(root.rglob("*")):
        if count >= _MAX_FILES or total >= _MAX_TOTAL_CHARS:
            break
        if path.is_dir():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="replace").strip()
        except (OSError, ValueError):
            continue
        if not body:
            continue
        rel = path.relative_to(root).as_posix()
        chunk = _truncate(body, _MAX_FILE_CHARS)
        sections.append(f"### {rel}\n```\n{chunk}\n```")
        total += len(chunk)
        count += 1
    return sections


def gather_repo_context(cwd: str, diff_scope: Optional[str] = None) -> str:
    """Build a bounded text snapshot of the candidate's materials for prompt
    injection into non-grounded (provider) backends.

    Reads text files under `cwd` (resume, JD, notes). Returns "" when there is
    nothing to ground in, so the caller can warn.
    """

    sections: List[str] = []
    if diff_scope:
        sections.append(f"## Focus\n{diff_scope.strip()}")

    materials = _gather_from_filesystem(cwd)
    if materials:
        sections.append("## Candidate materials (ground every claim in these)\n" + "\n\n".join(materials))

    if not sections:
        return ""
    header = (
        "You cannot browse the materials folder directly. The material below is your "
        "only evidence; ground every claim in it and never invent anything not shown.\n\n"
    )
    return header + "\n\n".join(sections)

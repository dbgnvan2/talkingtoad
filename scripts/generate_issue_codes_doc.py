#!/usr/bin/env python3
"""Generate ``docs/issue-codes.md`` from the issue catalogue (v2.3 Cycle B).

The hand-maintained ``docs/issue-codes.md`` had a long history of drifting
from the actual ``_CATALOGUE`` in ``api/crawler/issue_checker.py`` — thresholds
mismatched, codes appeared in one and not the other, severities went stale.

This script eliminates the drift by emitting the doc from the same constants
the runtime uses:

  - ``_CATALOGUE``                  — code -> spec (category, severity, etc.)
  - ``_ISSUE_SCORING``              — code -> (impact, effort)
  - ``_AI_READINESS_CONFIDENCE``    — code -> Established | Reasonable proxy | Heuristic

Run modes:

  python scripts/generate_issue_codes_doc.py              # write doc to disk
  python scripts/generate_issue_codes_doc.py --check      # CI: fail if doc out of sync
  python scripts/generate_issue_codes_doc.py --stdout     # print to stdout

The ``--check`` mode is what CI runs. If anyone hand-edits issue-codes.md, the
CI build fails with a clear "regenerate the doc" message — keeping the doc and
the catalogue in lockstep forever.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Run from the project root so the import resolves.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.crawler.issue_checker import (  # noqa: E402
    _AI_READINESS_CONFIDENCE,
    _CATALOGUE,
    _ISSUE_SCORING,
)


DOC_PATH = PROJECT_ROOT / "docs" / "issue-codes.md"


SEVERITY_ICONS = {
    "critical": "🔴",
    "warning": "🟡",
    "info": "🔵",
}


# Order categories so the generated doc is stable and readable. Anything not
# in this list falls to the end alphabetically.
CATEGORY_ORDER = [
    "metadata",
    "heading",
    "broken_link",
    "redirect",
    "crawlability",
    "duplicate",
    "sitemap",
    "security",
    "url_structure",
    "image",
    "ai_readiness",
]


CATEGORY_BLURBS = {
    "metadata":     "Title, meta description, OG tags, canonical, favicon.",
    "heading":      "H1 presence and uniqueness, heading hierarchy, empty headings.",
    "broken_link":  "Internal and external links returning 4xx/5xx, login redirects.",
    "redirect":     "Redirect chains, loops, and per-status-code findings.",
    "crawlability": "robots.txt blocks, noindex directives, thin content, orphan pages.",
    "duplicate":    "Cross-page title / meta description / title+meta pair duplicates.",
    "sitemap":      "Sitemap presence and per-URL coverage.",
    "security":     "HTTPS, HSTS, mixed content, unsafe cross-origin links.",
    "url_structure":"URL format: uppercase, spaces, underscores, length.",
    "image":        "Image accessibility, performance, format, srcset, and content checks.",
    "ai_readiness": (
        "Site readiness for AI search engines (Google AI Overviews, ChatGPT, "
        "Perplexity, etc.). Every code in this category carries a confidence "
        "label per the v2.0 spec: **Established** (vendor-confirmed effect), "
        "**Reasonable proxy** (industry consensus + Google's published best "
        "practices), **Heuristic** (industry consensus only, no vendor "
        "confirmation)."
    ),
}


def _sort_key_for_category(cat: str) -> tuple[int, str]:
    """Stable ordering: known categories in declared order, rest alphabetical."""
    if cat in CATEGORY_ORDER:
        return (CATEGORY_ORDER.index(cat), cat)
    return (len(CATEGORY_ORDER), cat)


def _group_by_category() -> dict[str, list[str]]:
    """Return {category: [code, code, ...]} sorted by category order then code name."""
    groups: dict[str, list[str]] = {}
    for code, spec in _CATALOGUE.items():
        groups.setdefault(spec.category, []).append(code)
    for codes in groups.values():
        codes.sort()
    return dict(sorted(groups.items(), key=lambda kv: _sort_key_for_category(kv[0])))


def _render_code_entry(code: str) -> str:
    """Render a single issue code as a doc section."""
    spec = _CATALOGUE[code]
    impact, effort = _ISSUE_SCORING.get(code, (0, 0))
    confidence = _AI_READINESS_CONFIDENCE.get(code)

    severity_icon = SEVERITY_ICONS.get(spec.severity, "⚪")
    pieces = [
        f"**Severity:** {severity_icon} {spec.severity}",
        f"**Impact:** {impact}",
        f"**Effort:** {effort}",
    ]
    if confidence:
        pieces.insert(1, f"**Confidence:** {confidence}")
    if spec.fixability and spec.fixability != "developer_needed":
        pieces.append(f"**Fixability:** {spec.fixability}")

    header_line = " | ".join(pieces)

    body_parts: list[str] = []
    if spec.what_it_is:
        body_parts.append(f"**What it is**\n{spec.what_it_is}")
    elif spec.description:
        body_parts.append(spec.description)

    if spec.impact_desc:
        body_parts.append(f"**Why it matters**\n{spec.impact_desc}")

    if spec.how_to_fix:
        body_parts.append(f"**How to fix**\n{spec.how_to_fix}")
    elif spec.recommendation and not spec.what_it_is:
        # If no separate how_to_fix, fall back to the short recommendation
        body_parts.append(f"**Recommendation:** {spec.recommendation}")

    if spec.human_description:
        body_parts.append(f"**Plain-English:** {spec.human_description}")

    body = "\n\n".join(body_parts) if body_parts else ""

    return f"### {code}\n{header_line}\n\n{body}".rstrip() + "\n"


def _render_doc() -> str:
    """Render the full markdown doc as a string."""
    groups = _group_by_category()
    total_codes = sum(len(v) for v in groups.values())

    lines: list[str] = []
    lines.append("---")
    lines.append("status: current")
    lines.append("auto_generated: true")
    lines.append("generator: scripts/generate_issue_codes_doc.py")
    lines.append("---")
    lines.append("")
    lines.append("# Issue Codes Reference")
    lines.append("")
    lines.append(
        "> **This file is auto-generated.** Do not edit by hand — your changes "
        "will be overwritten the next time the generator runs. To update an "
        "issue code, edit `api/crawler/issue_checker.py` (`_CATALOGUE`, "
        "`_ISSUE_SCORING`, `_AI_READINESS_CONFIDENCE`) and re-run "
        "`python scripts/generate_issue_codes_doc.py`."
    )
    lines.append("")
    lines.append(
        f"**{total_codes} issue codes** across {len(groups)} categories."
    )
    lines.append("")

    # Per-category Table of Contents
    lines.append("## Table of contents")
    lines.append("")
    for cat, codes in groups.items():
        lines.append(f"- [{cat.upper()}](#{cat}) ({len(codes)})")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Sections
    for cat, codes in groups.items():
        lines.append(f'<a id="{cat}"></a>')
        lines.append(f"## {cat.upper()}")
        lines.append("")
        blurb = CATEGORY_BLURBS.get(cat)
        if blurb:
            lines.append(blurb)
            lines.append("")
        lines.append(f"_{len(codes)} codes in this category._")
        lines.append("")
        for code in codes:
            lines.append(_render_code_entry(code))
            lines.append("---")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate docs/issue-codes.md from the issue catalogue.")
    parser.add_argument("--check", action="store_true",
                        help="CI mode: exit 1 if doc on disk differs from generated.")
    parser.add_argument("--stdout", action="store_true",
                        help="Print to stdout instead of writing.")
    args = parser.parse_args()

    generated = _render_doc()

    if args.stdout:
        print(generated)
        return 0

    if args.check:
        if not DOC_PATH.exists():
            print(
                f"ERROR: {DOC_PATH} doesn't exist. Run "
                "`python scripts/generate_issue_codes_doc.py` to create it.",
                file=sys.stderr,
            )
            return 1
        existing = DOC_PATH.read_text()
        if existing != generated:
            print(
                f"ERROR: {DOC_PATH} is out of sync with the catalogue. "
                "Run `python scripts/generate_issue_codes_doc.py` to regenerate, "
                "then commit the updated doc.",
                file=sys.stderr,
            )
            # Show the first 20 lines of diff for context
            import difflib
            diff = list(difflib.unified_diff(
                existing.splitlines(keepends=True),
                generated.splitlines(keepends=True),
                fromfile=str(DOC_PATH),
                tofile="generated",
                n=2,
            ))
            sys.stderr.writelines(diff[:60])
            return 1
        print(f"OK: {DOC_PATH} is in sync with the catalogue.")
        return 0

    DOC_PATH.write_text(generated)
    print(f"Wrote {DOC_PATH} ({len(generated.splitlines())} lines, "
          f"{sum(len(v) for v in _group_by_category().values())} codes).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

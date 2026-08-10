"""Frontend ↔ backend issue-code-set parity.

The frontend hand-mirrors two backend code sets. When §7 merged/deleted codes on
the Python side, the JS copies drifted (merged code lost its AI-suggestion + fix
buttons; a vitest test broke) and pytest never noticed. These tests make that
class of drift fail in CI.
"""

import re
from pathlib import Path

from api.routers.ai import _AI_TEXT_SUGGESTION_CODES
from api.services.wp_shared import _CODE_TO_FIELD

_ROOT = Path(__file__).resolve().parent.parent
_RESULTS = _ROOT / "frontend" / "src" / "pages" / "Results.jsx"
_FIXPANEL = _ROOT / "frontend" / "src" / "components" / "FixInlinePanel.jsx"
_SUMMARY = _ROOT / "frontend" / "src" / "components" / "SummaryPanel.jsx"
_PDF_REPORT = _ROOT / "api" / "services" / "report_generator.py"

# Codes deleted/merged in §7 — must not linger in any frontend code-set.
_DELETED_OR_MERGED = {
    "SCHEMA_MISSING", "TITLE_META_DUPLICATE_PAIR",
    "OG_TITLE_MISSING", "OG_DESC_MISSING", "OG_IMAGE_MISSING", "TWITTER_CARD_MISSING",
}


def _js_set(text: str, name: str) -> set[str]:
    """Extract the string literals from `const NAME = new Set([ ... ])`."""
    m = re.search(name + r"\s*=\s*new Set\(\[(.*?)\]\)", text, re.S)
    assert m, f"{name} not found"
    return set(re.findall(r"['\"]([A-Z0-9_]+)['\"]", m.group(1)))


def _js_object_keys(text: str, name: str) -> set[str]:
    """Extract the keys from `const NAME = { KEY: 'x', ... }`."""
    m = re.search(name + r"\s*=\s*\{(.*?)\}", text, re.S)
    assert m, f"{name} not found"
    return set(re.findall(r"^\s*([A-Z0-9_]+)\s*:", m.group(1), re.M))


def test_ai_suggestion_codes_match_backend():
    js = _js_set(_RESULTS.read_text(), "AI_TEXT_SUGGESTION_CODES")
    assert js == set(_AI_TEXT_SUGGESTION_CODES), (
        "Results.jsx AI_TEXT_SUGGESTION_CODES drifted from ai.py "
        f"_AI_TEXT_SUGGESTION_CODES.\n  only in frontend: {js - set(_AI_TEXT_SUGGESTION_CODES)}"
        f"\n  only in backend:  {set(_AI_TEXT_SUGGESTION_CODES) - js}"
    )


def test_inline_fix_codes_are_backend_fixable():
    """Every code the inline panel offers to fix must exist in the backend
    _CODE_TO_FIELD (else the fix call fails)."""
    js = _js_object_keys(_FIXPANEL.read_text(), "CODE_TO_FIELD")
    missing = js - set(_CODE_TO_FIELD)
    # TITLE_H1_MISMATCH is a pre-existing frontend-only entry (tracked in TODO,
    # not introduced here) — exclude it so this test guards NEW drift only.
    missing.discard("TITLE_H1_MISMATCH")
    assert not missing, (
        f"FixInlinePanel CODE_TO_FIELD offers codes the backend can't fix: {missing}"
    )


def test_no_deleted_codes_linger_in_frontend():
    for path in (_RESULTS, _FIXPANEL):
        present = _DELETED_OR_MERGED & set(re.findall(r"[A-Z0-9_]+", path.read_text()))
        assert not present, f"{path.name} still references deleted/merged codes: {present}"


# ── Category display/ordering lists ↔ backend categories ─────────────────────
# The set of issue categories is hand-mirrored in THREE hardcoded display lists:
# the Results.jsx category tabs, the SummaryPanel.jsx "Issues by Category" grid,
# and the PDF report's cat_list. Adding a new backend category (e.g. `analytics`,
# 2026-08-06) without updating all three makes it silently vanish from the UI and
# the audit PDF — exactly what happened to `analytics`, `rendering`, and
# `semantic_html`. This test makes that class of omission fail in CI.

def _js_category_keys(text: str) -> set[str]:
    """Extract the `key: 'x'` slugs from a `const CATEGORIES = [ ... ]` array."""
    m = re.search(r"CATEGORIES\s*=\s*\[(.*?)\]", text, re.S)
    assert m, "CATEGORIES array not found"
    return set(re.findall(r"key:\s*'([a-z_]+)'", m.group(1)))


def _pdf_category_keys(text: str) -> set[str]:
    """Extract the slug (2nd tuple element) from the PDF `cat_list = [ ... ]`."""
    m = re.search(r"cat_list\s*=\s*\[(.*?)\]", text, re.S)
    assert m, "cat_list not found"
    return set(re.findall(r'"[^"]+"\s*,\s*"([a-z_]+)"', m.group(1)))


def test_category_display_lists_cover_every_backend_category():
    """CLN1.2: each display list's category key set EQUALS the backend set —
    no missing (silently vanished from UI) and no extra (a dead tile that can
    only ever show 0, e.g. the former `duplicate`)."""
    from api.crawler.checkers.registry import _CATALOGUE

    backend = {spec.category for spec in _CATALOGUE.values()}
    lists = {
        "Results.jsx CATEGORIES tabs": _js_category_keys(_RESULTS.read_text()),
        "SummaryPanel.jsx category grid": _js_category_keys(_SUMMARY.read_text()),
        "report_generator.py PDF cat_list": _pdf_category_keys(_PDF_REPORT.read_text()),
    }
    for name, keys in lists.items():
        missing = backend - keys
        assert not missing, (
            f"{name} is missing backend issue categories: {sorted(missing)}. "
            "Every category in registry._CATALOGUE must appear in this display list."
        )
        extra = keys - backend
        assert not extra, (
            f"{name} has category keys no _CATALOGUE code emits: {sorted(extra)}. "
            "A dead category tile/row can only ever show 0 — remove it or wire a "
            "code to that category."
        )


def test_cln1_1_no_dead_duplicate_category():
    """CLN1.1: no issue spec emits `category='duplicate'` (the premise for
    dropping the dead Duplicates tile). Duplicate detection lives under the real
    categories — TITLE_DUPLICATE/META_DESC_DUPLICATE (metadata), etc."""
    from api.crawler.checkers.registry import _CATALOGUE

    assert "duplicate" not in {spec.category for spec in _CATALOGUE.values()}

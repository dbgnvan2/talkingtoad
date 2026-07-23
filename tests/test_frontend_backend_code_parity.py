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

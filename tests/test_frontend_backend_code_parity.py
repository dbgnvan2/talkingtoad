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
    return set(_js_object_map(text, name))


def _js_object_map(text: str, name: str) -> dict[str, str]:
    """Extract the full key→value map from `const NAME = { KEY: 'value', ... }`."""
    m = re.search(name + r"\s*=\s*\{(.*?)\}", text, re.S)
    assert m, f"{name} not found"
    return dict(re.findall(r"^\s*([A-Z0-9_]+)\s*:\s*['\"]([a-z0-9_]+)['\"]",
                           m.group(1), re.M))


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
    # CLN6: TITLE_H1_MISMATCH exclusion removed — it is now in the backend map.
    assert not missing, (
        f"FixInlinePanel CODE_TO_FIELD offers codes the backend can't fix: {missing}"
    )


def test_cln6_1_title_h1_mismatch_is_backend_fixable():
    """CLN6.1: TITLE_H1_MISMATCH (catalogued wp_fixable) resolves to the seo_title
    field in the backend map, so the inline-fix button actually works."""
    from api.services.wp_shared import _CODE_TO_FIELD, get_fixable_codes

    assert _CODE_TO_FIELD.get("TITLE_H1_MISMATCH") == "seo_title"
    assert "TITLE_H1_MISMATCH" in get_fixable_codes()


def test_inline_fix_field_VALUES_match_the_backend_map():
    """The mapped field, not just the key, must agree with `_CODE_TO_FIELD`.

    `apply-one` now derives the field server-side and ignores any `field` in the
    body, so the WRITE side cannot be misled by a stale client. The READ side still
    can: `FixInlinePanel` puts its own `CODE_TO_FIELD[code]` in the
    `/api/fixes/wp-value?field=` query string. With only the key set compared, a
    frontend entry of `META_DESC_TOO_LONG: 'og_description'` passes — the panel then
    shows the social-share text, trims it to 157 chars, and `apply-one` writes that
    into the meta description. Silent, and it looks like the fix worked.
    """
    js = _js_object_map(_FIXPANEL.read_text(), "CODE_TO_FIELD")
    assert js, "CODE_TO_FIELD parsed as empty — the regex no longer matches the file"
    drift = {code: (field, _CODE_TO_FIELD.get(code))
             for code, field in js.items() if _CODE_TO_FIELD.get(code) != field}
    assert not drift, (
        "FixInlinePanel CODE_TO_FIELD maps codes to different fields than the "
        f"backend. {{code: (frontend, backend)}} = {drift}"
    )


def test_inline_fix_fields_are_real_backend_fields():
    """Every field the panel names must exist in `_FIELD_SPECS`.

    /api/fixes/wp-value returns 400 UNKNOWN_FIELD for anything else, so a typo here
    is a fix panel that can only ever show an error.
    """
    from api.services.wp_shared import _FIELD_SPECS

    js = _js_object_map(_FIXPANEL.read_text(), "CODE_TO_FIELD")
    unknown = {c: f for c, f in js.items() if f not in _FIELD_SPECS}
    assert not unknown, f"FixInlinePanel names fields the backend does not have: {unknown}"


def test_no_deleted_codes_linger_in_frontend():
    for path in (_RESULTS, _FIXPANEL):
        present = _DELETED_OR_MERGED & set(re.findall(r"[A-Z0-9_]+", path.read_text()))
        assert not present, f"{path.name} still references deleted/merged codes: {present}"


# ── Category display list ↔ backend categories (CLN1 / CLN2) ─────────────────
# The category set + labels + order live in ONE place — registry.CATEGORY_DISPLAY
# — projected to frontend/src/data/categories.generated.json (imported by the
# frontend) and read directly by the PDF report. Previously they were
# hand-mirrored in 3 places, which silently dropped `analytics`, `rendering`, and
# `semantic_html` from surfaces. These tests guard the single source against the
# crawler's actual categories, and that no hand-mirrored copy sneaks back in.

def test_category_display_is_single_source_of_truth():
    """CLN1.2/CLN2: registry.CATEGORY_DISPLAY's key set EQUALS the set of
    categories _CATALOGUE emits — no missing (would vanish from every surface),
    no extra (a dead tile that can only show 0, e.g. the former `duplicate`)."""
    from api.crawler.checkers.registry import CATEGORY_DISPLAY, _CATALOGUE

    display = {key for key, _label in CATEGORY_DISPLAY}
    backend = {spec.category for spec in _CATALOGUE.values()}
    assert display == backend, (
        "CATEGORY_DISPLAY drifted from the catalogue categories: "
        f"missing={sorted(backend - display)} extra={sorted(display - backend)}"
    )
    keys = [key for key, _ in CATEGORY_DISPLAY]
    assert len(keys) == len(set(keys)), "CATEGORY_DISPLAY has duplicate keys"


def test_no_hand_mirrored_category_lists_remain():
    """CLN2.2: the frontend imports the generated JSON and the PDF derives its
    list from CATEGORY_DISPLAY — no file re-declares the category list by hand."""
    for path in (_RESULTS, _SUMMARY):
        text = path.read_text()
        assert "categories.generated.json" in text, (
            f"{path.name} must import CATEGORIES from categories.generated.json"
        )
        assert not re.search(r"const\s+CATEGORIES\s*=\s*\[", text), (
            f"{path.name} still hand-declares a CATEGORIES array — use the import"
        )
    assert "CATEGORY_DISPLAY" in _PDF_REPORT.read_text(), (
        "report_generator.py PDF cat_list must derive from CATEGORY_DISPLAY"
    )


def test_cln1_1_no_dead_duplicate_category():
    """CLN1.1: no issue spec emits `category='duplicate'` (the premise for
    dropping the dead Duplicates tile). Duplicate detection lives under the real
    categories — TITLE_DUPLICATE/META_DESC_DUPLICATE (metadata), etc."""
    from api.crawler.checkers.registry import _CATALOGUE

    assert "duplicate" not in {spec.category for spec in _CATALOGUE.values()}

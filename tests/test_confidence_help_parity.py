"""The help drawer must not contradict the API about how far to trust a finding.

Spec:  docs/functional-specification.md (V1.1 — the confidence label is derived)
Tests: this file

The label had four homes, not three. Removing the backend duplicates left
frontend/src/data/issueHelp.js — the surface a user actually reads — still
carrying its own copy, drifted the same way:

  ENTITY_HOURS_DEFAULT      API "Heuristic",        help "Established"
  AI_HIGH_VALUE_UNCITED     API "Heuristic",        help "Reasonable proxy"
  CONTACT_INFO_NOT_IN_HTML  API "Reasonable proxy", help "Heuristic"

ENTITY_HOURS_DEFAULT is the sharpest case: it was downgraded precisely because
no vendor has confirmed it, and the drawer went on telling the user one had.
A severity parity test existed and caught the severity half of the same edit;
nothing checked confidence, so the confidence half shipped.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from api.crawler.checkers.registry import _AI_READINESS_CONFIDENCE

HELP = Path(__file__).parent.parent / "frontend/src/data/issueHelp.js"
API_TAXONOMY = frozenset({"Established", "Reasonable proxy", "Heuristic"})

# Entries whose `confidence:` is written in an OLDER, different vocabulary
# ("Mechanistic" / "Empirical" / "Conventional"), which predates the v2.0
# taxonomy the API uses. They are not drift — they answer a different question,
# and V1's authority record now answers it properly. Reconciling them is an
# editorial decision for the owner, tracked in TODO.md; they are named here
# rather than skipped by a pattern so the list cannot quietly grow.
LEGACY_VOCABULARY = {
    "AUTHOR_BYLINE_MISSING", "AI_TXT_MISSING", "CENTRAL_CLAIM_BURIED",
    "CHUNKS_NOT_SELF_CONTAINED", "CODE_BLOCK_MISSING_TECHNICAL",
    "COMPARISON_TABLE_MISSING", "CONTENT_CLOAKING_DETECTED",
    "DATE_MODIFIED_MISSING", "DATE_PUBLISHED_MISSING", "EXTERNAL_CITATIONS_LOW",
    "FAQ_SCHEMA_MISSING", "FIRST_VIEWPORT_NO_ANSWER", "JSON_LD_INVALID",
    "JS_RENDERED_CONTENT_DIFFERS", "LINK_PROFILE_PROMOTIONAL",
    "ORPHAN_CLAIM_TECHNICAL", "PROMOTIONAL_CONTENT_INTERRUPTS",
    "QUERY_COVERAGE_WEAK", "QUOTATIONS_MISSING", "RAW_HTML_JS_DEPENDENT",
    "SECTION_CROSS_REFERENCES", "SECTION_VAGUE_OPENER", "STATISTICS_COUNT_LOW",
    "STRUCTURED_ELEMENTS_LOW", "UA_CONTENT_DIFFERS",
}

_ENTRY = re.compile(r'^  ([A-Z][A-Z0-9_]*): \{(.*?)^  \},', re.S | re.M)


def _help_confidence() -> dict[str, str]:
    out = {}
    for m in _ENTRY.finditer(HELP.read_text(encoding="utf-8")):
        c = re.search(r'confidence: "([^"]*)"', m.group(2))
        if c:
            out[m.group(1)] = c.group(1)
    return out


def test_v11_help_confidence_matches_the_api_for_every_shared_code():
    help_conf = _help_confidence()
    assert help_conf, "parsed no confidence values — the parser has drifted"
    bad = []
    for code, label in help_conf.items():
        if code in LEGACY_VOCABULARY or code not in _AI_READINESS_CONFIDENCE:
            continue
        api = _AI_READINESS_CONFIDENCE[code]
        if label != api:
            bad.append(f"{code}: API says {api!r}, help drawer says {label!r}")
    assert not bad, (
        "the help drawer contradicts the API about how far to trust a "
        "finding:\n  " + "\n  ".join(bad))


def test_v11_legacy_vocabulary_list_is_exact():
    """P29 — a named exclusion list must not silently absorb new drift.

    Asserted as an exact set, so a code leaving the old vocabulary (or a new
    entry joining it) is a deliberate edit rather than an unnoticed pass.
    """
    help_conf = _help_confidence()
    actual = {c for c, v in help_conf.items()
              if v not in API_TAXONOMY and c in _AI_READINESS_CONFIDENCE}
    assert actual == LEGACY_VOCABULARY, (
        f"the legacy-vocabulary set changed.\n"
        f"  newly non-taxonomy: {sorted(actual - LEGACY_VOCABULARY)}\n"
        f"  no longer present:  {sorted(LEGACY_VOCABULARY - actual)}")


@pytest.mark.parametrize("code", ["ENTITY_HOURS_DEFAULT",
                                  "AI_HIGH_VALUE_UNCITED",
                                  "CONTACT_INFO_NOT_IN_HTML"])
def test_v11_the_three_drifted_codes_agree_on_both_surfaces(code):
    """Named individually: these are the three that actually shipped wrong."""
    assert _help_confidence()[code] == _AI_READINESS_CONFIDENCE[code]

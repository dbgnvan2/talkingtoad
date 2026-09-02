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

from pathlib import Path

import pytest

from api.crawler.checkers.registry import _AI_READINESS_CONFIDENCE

HELP = Path(__file__).parent.parent / "frontend/src/data/issueHelp.json"
API_TAXONOMY = frozenset({"Established", "Reasonable proxy", "Heuristic"})

# Phase 2 (2026-09-02): the 25 entries that carried the retired vocabulary
# ("Mechanistic" / "Empirical" / "Conventional") were rewritten to the API's
# labels, so the exclusion list is EMPTY and asserted so — a code re-entering
# the old vocabulary is a deliberate edit that has to touch this line.
LEGACY_VOCABULARY: set[str] = set()


def _help_confidence() -> dict[str, str]:
    import json
    data = json.loads(HELP.read_text(encoding="utf-8"))
    return {code: e["confidence"] for code, e in data.items() if e.get("confidence")}


def test_v11_help_confidence_matches_the_api_for_every_shared_code():
    help_conf = _help_confidence()
    assert help_conf, "parsed no confidence values — the source has moved"
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
    """P29 — the retired vocabulary must stay gone."""
    help_conf = _help_confidence()
    actual = {c for c, v in help_conf.items()
              if v not in API_TAXONOMY and c in _AI_READINESS_CONFIDENCE}
    assert actual == LEGACY_VOCABULARY, (
        f"codes using a non-API confidence label: {sorted(actual)}")


@pytest.mark.parametrize("code", ["ENTITY_HOURS_DEFAULT",
                                  "AI_HIGH_VALUE_UNCITED",
                                  "CONTACT_INFO_NOT_IN_HTML"])
def test_v11_the_three_drifted_codes_agree_on_both_surfaces(code):
    """Named individually: these are the three that actually shipped wrong."""
    assert _help_confidence()[code] == _AI_READINESS_CONFIDENCE[code]

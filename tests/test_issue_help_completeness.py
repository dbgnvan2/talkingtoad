"""Every issue code teaches — the seven-field explainer is complete, honest and in parity.

Spec:  docs/pending/2026-09-02_phase2-education-layer.md#E2.3,
       docs/explanation-style-guide.md
Tests: this file

The test that matters most is ``test_caveat_has_substance``: a
``how_it_can_mislead`` that says only "results may vary" satisfies a presence
check and teaches nothing. The caveat is the trust-builder, so it must name the
tier and a way the check is wrong.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from api.crawler.checkers.authority import authority_for
from api.crawler.checkers.registry import (
    _AI_READINESS_CONFIDENCE,
    _CATALOGUE,
    derive_impact,
    severity_from_impact,
)

ROOT = Path(__file__).resolve().parent.parent
HELP = json.loads((ROOT / "frontend/src/data/issueHelp.json").read_text(encoding="utf-8"))

REQUIRED = ("title", "mission_impact", "definition", "impact", "good_vs_bad",
            "how_it_can_mislead", "fix", "confidence")
AI_TIERS = {"Established", "Reasonable proxy", "Heuristic"}
BASIS_TIER = {"citation": "Established", "observation": "Measured", "heuristic": "Heuristic"}
CODES = sorted(_CATALOGUE)


def test_every_code_has_an_entry_and_every_entry_is_a_code():
    assert set(HELP) == set(_CATALOGUE), (
        f"missing: {sorted(set(_CATALOGUE) - set(HELP))}; stale: {sorted(set(HELP) - set(_CATALOGUE))}")


@pytest.mark.parametrize("code", CODES)
def test_all_seven_fields_present_and_non_empty(code):
    e = HELP[code]
    for f in REQUIRED:
        assert e.get(f), f"{code} is missing {f}"
    gb = e["good_vs_bad"]
    assert isinstance(gb, dict) and gb.get("good") and gb.get("bad"), f"{code} good_vs_bad must be {{good, bad}}"
    assert len(e["title"]) <= 60, f"{code} title is {len(e['title'])} chars"


@pytest.mark.parametrize("code", CODES)
def test_category_and_severity_match_the_registry(code):
    e = HELP[code]
    assert e["category"] == _CATALOGUE[code].category, code
    assert e["severity"] == severity_from_impact(derive_impact(code)), (
        f"{code}: help says {e['severity']}, registry derives {severity_from_impact(derive_impact(code))}")


@pytest.mark.parametrize("code", CODES)
def test_confidence_is_the_derived_tier(code):
    e = HELP[code]
    if code in _AI_READINESS_CONFIDENCE:
        expected = _AI_READINESS_CONFIDENCE[code]
    else:
        expected = BASIS_TIER[authority_for(code)["basis"]]
    assert e["confidence"] == expected, f"{code}: help says {e['confidence']!r}, derived {expected!r}"


@pytest.mark.parametrize("code", CODES)
def test_caveat_names_its_tier_first(code):
    e = HELP[code]
    m = re.match(r"Evidence tier: (Established|Reasonable proxy|Heuristic|Measured)\.", e["how_it_can_mislead"])
    assert m, f"{code}: how_it_can_mislead must begin 'Evidence tier: <tier>.'"
    assert m.group(1) == e["confidence"], f"{code}: caveat tier {m.group(1)} != confidence {e['confidence']}"


# A caveat has substance when it names a concrete way the check is wrong. These
# are the phrases the style guide asks for (a false positive / negative, or the
# correct-looking-but-wrong result), not common English words.
_SUBSTANCE = ("false positive", "false negative", "false-positive", "false-negative",
              "correct-looking", "wrong", "flagged anyway", "is flagged", "still flag",
              "passes", "pass ", "misfire", "misses", "missed", "not flagged", "never flagged",
              "cannot tell", "can't tell")


def caveat_has_substance(text: str) -> bool:
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]
    if len(sentences) < 3:
        return False
    body = text.lower()
    return any(p in body for p in _SUBSTANCE)


@pytest.mark.parametrize("code", CODES)
def test_caveat_has_substance(code):
    assert caveat_has_substance(HELP[code]["how_it_can_mislead"]), (
        f"{code}: the caveat does not name a way the check is wrong")


@pytest.mark.parametrize("text", [
    "Evidence tier: Heuristic. Results may vary.",
    "Evidence tier: Heuristic. It only looks at HTML. It cannot see everything.",
    "Evidence tier: Established. This check is reliable. Trust it. It is well tested.",
])
def test_the_adversarial_caveat_fails(text):
    """The guard must reject the vacuous caveats it exists to catch (P27)."""
    assert caveat_has_substance(text) is False

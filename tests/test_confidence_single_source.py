"""The AI-readiness confidence label has exactly one source of truth.

Spec:  docs/functional-specification.md (V1 — evidence basis)
Tests: this file

Until 2026-08-30 the label lived in two places: a ``confidence_label`` field on
``_IssueSpec`` and the ``_AI_READINESS_CONFIDENCE`` dict. ``make_issue`` read
``spec.confidence_label or _AI_READINESS_CONFIDENCE.get(code)``, so the field
silently won — and the two had drifted apart on two codes:

  AI_HIGH_VALUE_UNCITED     API said "Reasonable proxy", docs said "Heuristic"
  CONTACT_INFO_NOT_IN_HTML  API said "Heuristic", docs said "Reasonable proxy"

docs/issue-codes.md generates from the dict, so the published documentation and
the running product disagreed about how far a user should trust those findings.
Five further overrides were exact duplicates — carrying the same risk without
the symptom. The field is gone; the dict is the single source.
"""
from __future__ import annotations

import dataclasses

from api.crawler.checkers.registry import (_AI_READINESS_CONFIDENCE, _CATALOGUE,
                                           make_issue)


def test_v1_issuespec_carries_no_confidence_field():
    """A second home for the label must not come back."""
    names = {f.name for f in dataclasses.fields(_CATALOGUE["TITLE_MISSING"])}
    assert "confidence_label" not in names, (
        "_IssueSpec has a confidence_label field again. The label belongs in "
        "_AI_READINESS_CONFIDENCE only — a per-spec override silently wins "
        "over the dict that docs/issue-codes.md is generated from, so the "
        "product and its documentation drift apart unnoticed."
    )


def test_v1_every_ai_readiness_code_labelled_from_the_dict():
    ai = {c for c, s in _CATALOGUE.items() if s.category == "ai_readiness"}
    assert ai, "no ai_readiness codes found — the check would be vacuous"
    missing = sorted(c for c in ai if c not in _AI_READINESS_CONFIDENCE)
    assert not missing, f"ai_readiness codes with no confidence label: {missing}"


def test_v1_make_issue_serves_the_dict_value_for_the_drifted_codes():
    """The two codes that disagreed now report the dict's value, which is also
    what docs/issue-codes.md publishes."""
    for code in ("AI_HIGH_VALUE_UNCITED", "CONTACT_INFO_NOT_IN_HTML"):
        issue = make_issue(code, "https://example.test/", job_id="j")
        assert issue.confidence_label == _AI_READINESS_CONFIDENCE[code], (
            f"{code}: make_issue served {issue.confidence_label!r} but the "
            f"single source says {_AI_READINESS_CONFIDENCE[code]!r}"
        )


def test_v1_non_ai_codes_get_no_confidence_label():
    """The label means something specific to AI readiness; it must not leak
    onto codes the taxonomy does not apply to."""
    for code, spec in _CATALOGUE.items():
        if spec.category != "ai_readiness":
            issue = make_issue(code, "https://example.test/", job_id="j")
            assert issue.confidence_label is None, (
                f"{code} is {spec.category}, not ai_readiness, yet carries "
                f"confidence_label={issue.confidence_label!r}"
            )

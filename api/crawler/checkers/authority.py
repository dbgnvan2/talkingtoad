"""V1 — the evidence basis behind every issue code TalkingToad scores.

Purpose: expose, per code, whether a finding rests on a published source or on
         TalkingToad's own judgement — and say which, in the product.
Spec:    docs/functional-specification.md (V1 — evidence basis)
Tests:   tests/test_authority.py

Every scored code makes a claim about a site. Until now the product gave a user
no way to tell a claim backed by a W3C success criterion from one resting on a
convention we chose, and it stated both in the same voice. A 60-character title
limit reads as Google's rule; Google publishes no such limit. This module makes
the difference legible.

The record itself is YAML (editorial content belongs in config, not in Python
source), and every cited URL was fetched — see data/url_verification.yaml.
"""
from __future__ import annotations

import functools
from pathlib import Path
from typing import Literal

import yaml

_DATA = Path(__file__).parent / "data"
_AUTHORITY_FILE = _DATA / "authority.yaml"
_VERIFICATION_FILE = _DATA / "url_verification.yaml"

Basis = Literal["citation", "heuristic", "observation"]
SOURCE_TYPES = frozenset({"vendor", "standard", "research", "industry"})


@functools.lru_cache(maxsize=1)
def _load() -> dict[str, dict]:
    with _AUTHORITY_FILE.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@functools.lru_cache(maxsize=1)
def _verification() -> dict[str, dict]:
    with _VERIFICATION_FILE.open(encoding="utf-8") as fh:
        return (yaml.safe_load(fh) or {}).get("urls", {}) or {}


def authority_for(code: str) -> dict | None:
    """Return the evidence record for *code*, or None if it has none.

    None is a real answer and must be surfaced as "no basis recorded", never
    rendered as though the finding were cited. test_authority.py asserts that
    no catalogue code returns None, so a None in production means a code was
    added without one.
    """
    entry = _load().get(code)
    return dict(entry) if entry else None


def is_heuristic(code: str) -> bool:
    """True when the finding rests on TalkingToad's judgement.

    A direct observation is NOT a heuristic — it is a recorded measurement —
    so this is False for basis "observation" as well as for "citation". Use
    ``authority_for(code)["basis"]`` when the three-way distinction matters.

    An unknown code returns True: a code with no recorded basis has no
    published source and no recorded measurement behind it, and the
    conservative answer is the one that claims less.
    """
    entry = _load().get(code)
    return not entry or entry.get("basis") == "heuristic"


def url_verification(url: str) -> dict | None:
    """What happened when this URL was last actually fetched."""
    rec = _verification().get(url)
    return dict(rec) if rec else None


def all_codes() -> frozenset[str]:
    return frozenset(_load())

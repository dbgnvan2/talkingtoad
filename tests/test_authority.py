"""V1 — every scored code declares its evidence basis, and the record holds up.

Spec:  docs/functional-specification.md (V1 — evidence basis)
Tests: this file

TalkingToad scores 170 codes and states all of them in the same voice. A user
had no way to tell "W3C requires a text alternative" from "we picked 60
characters". Worse, several checks cite a real source for the SUBJECT while
firing on a THRESHOLD that source does not publish — Google documents the title
link and publishes no length limit — so a house convention reads as somebody
else's rule. These tests hold the record to what it can actually support.
"""
from __future__ import annotations

import pytest
import yaml

from api.crawler.checkers.authority import (SOURCE_TYPES, _AUTHORITY_FILE,
                                            all_codes, authority_for,
                                            is_heuristic, url_verification)
from api.crawler.checkers.registry import (_AI_READINESS_CONFIDENCE, _CATALOGUE,
                                           _ISSUE_SCORING)


class TestCoverage:
    def test_v1_every_catalogue_code_declares_a_basis(self):
        missing = sorted(set(_CATALOGUE) - all_codes())
        assert not missing, (
            f"{len(missing)} codes score a site with no recorded evidence "
            f"basis: {missing}"
        )

    def test_v1_every_scored_code_declares_a_basis(self):
        """_ISSUE_SCORING is what charges a site's health score."""
        missing = sorted(set(_ISSUE_SCORING) - all_codes())
        assert not missing, f"scored codes with no basis: {missing}"

    def test_v1_record_invents_no_codes(self):
        """A basis for a code that does not exist is dead editorial content
        that will be believed."""
        extra = sorted(all_codes() - set(_CATALOGUE))
        assert not extra, f"authority.yaml describes non-existent codes: {extra}"


class TestSchema:
    @pytest.mark.parametrize("code", sorted(_CATALOGUE))
    def test_v1_entry_is_well_formed(self, code):
        entry = authority_for(code)
        assert entry is not None, f"{code} has no entry"
        basis = entry.get("basis")
        assert basis in ("citation", "heuristic", "observation"), (
            f"{code}: basis must be citation, heuristic or observation, "
            f"got {basis!r}")

        if basis == "citation":
            for field in ("source", "source_type", "url", "claim"):
                assert entry.get(field), f"{code}: citation missing {field}"
            assert entry["source_type"] in SOURCE_TYPES, (
                f"{code}: unknown source_type {entry['source_type']!r}")
            assert entry["url"].startswith("https://"), (
                f"{code}: citation URL must be https")
            assert not (entry.get("threshold_note")
                        and entry.get("threshold_published_by_source")), (
                f"{code}: claims the threshold is both ours and the source's")
        elif basis == "observation":
            method = entry.get("method", "")
            assert len(method) >= 60, (
                f"{code}: an observation must say what was measured and what "
                f"it does NOT establish. Got {len(method)} chars: {method!r}")
            assert "url" not in entry, (
                f"{code}: an observation cites nothing — it records what this "
                f"crawl saw. A URL here would dress a measurement as a source")
        else:
            rationale = entry.get("rationale", "")
            assert len(rationale) >= 60, (
                f"{code}: a heuristic must say what we believe and why. "
                f"Got {len(rationale)} chars: {rationale!r}")
            assert "url" not in entry, (
                f"{code}: basis is heuristic but a URL is attached — pick one")


class TestUrlsWereActuallyFetched:
    def test_v1_every_citation_url_was_actually_fetched(self):
        """The record claims these sources exist. That claim is checked, not
        asserted: scripts/verify_authority_urls.py fetches every URL and writes
        the result. Three URLs in the first draft of this record did not exist —
        they were plausible and wrong — which is why this test is here."""
        unverified = []
        for code in sorted(_CATALOGUE):
            entry = authority_for(code)
            url = entry.get("url")
            if not url:
                continue
            record = url_verification(url)
            if not record:
                unverified.append(f"{code}: {url} — never fetched")
            elif record.get("status") != 200:
                unverified.append(
                    f"{code}: {url} — last fetch returned "
                    f"{record.get('status') or record.get('error')}")
        assert not unverified, (
            "citations pointing at URLs that were not confirmed to resolve:\n  "
            + "\n  ".join(unverified)
            + "\nRun scripts/verify_authority_urls.py and fix or repoint them.")


class TestReconcilesWithTheConfidenceLabel:
    """The AI-readiness confidence label and the evidence basis are two
    statements about the same thing. If they disagree, one of them is wrong."""

    def test_v1_established_codes_carry_a_citation(self):
        """'Established' means vendor-confirmed. It cannot rest on judgement."""
        bad = []
        for code, label in _AI_READINESS_CONFIDENCE.items():
            if label != "Established":
                continue
            entry = authority_for(code) or {}
            if entry.get("basis") == "observation":
                continue        # a measurement is at least as established
            if entry.get("basis") != "citation":
                bad.append(f"{code}: labelled Established, basis is "
                           f"{entry.get('basis')!r}")
            elif entry.get("source_type") not in ("vendor", "standard"):
                bad.append(f"{code}: labelled Established but its source is "
                           f"{entry.get('source_type')!r} — neither the "
                           f"operator of the system nor a normative spec")
        assert not bad, "\n".join(bad)

    def test_v1_heuristic_codes_do_not_claim_vendor_confirmation(self):
        """The converse: a code labelled Heuristic that turns out to have a
        vendor source is under-claiming, and the label should be raised."""
        bad = []
        for code, label in _AI_READINESS_CONFIDENCE.items():
            if label != "Heuristic":
                continue
            entry = authority_for(code) or {}
            if (entry.get("basis") == "citation"
                    and entry.get("source_type") == "vendor"
                    and not entry.get("threshold_note")):
                bad.append(
                    f"{code}: labelled Heuristic yet cites the vendor "
                    f"({entry.get('source')}) with no threshold_note "
                    f"explaining what the citation does NOT cover")
        assert not bad, "\n".join(bad)


class TestThresholdHonesty:
    """The failure this pass exists to prevent: citing a real source for the
    subject while the check fires on a number that source never published."""

    # Checks whose trigger is a number of TalkingToad's choosing. Each must
    # either be a heuristic or carry a threshold_note disclaiming the number.
    NUMERIC_TRIGGER_CODES = [
        "TITLE_TOO_LONG", "TITLE_TOO_SHORT", "META_DESC_TOO_LONG",
        "META_DESC_TOO_SHORT", "URL_TOO_LONG", "THIN_CONTENT", "CONTENT_THIN",
        "PARA_TOO_LONG", "IMG_ALT_TOO_LONG", "IMG_ALT_TOO_SHORT",
        "IMG_OVERSIZED", "IMG_OVERSCALED", "IMG_SLOW_LOAD", "PDF_TOO_LARGE",
        "PAGE_SIZE_LARGE", "HIGH_CRAWL_DEPTH", "REDIRECT_CHAIN",
        "SEMANTIC_DENSITY_LOW", "AI_MAIN_CONTENT_LOW_RATIO",
        "IMG_POOR_COMPRESSION", "NEAR_DUPLICATE_BODY",
        # Added after a cold review found them missing: both fire on
        # js_renderer._DIFF_THRESHOLD = 0.20, both cite Google, and neither
        # carried a threshold_note — precisely the failure this class names.
        # A hand-written list cannot police a class it does not enumerate,
        # which is why the guard below now derives instead of sampling.
        "JS_RENDERED_CONTENT_DIFFERS", "UA_CONTENT_DIFFERS",
    ]

    @pytest.mark.parametrize("code", NUMERIC_TRIGGER_CODES)
    def test_v1_a_number_we_chose_is_never_presented_as_a_published_rule(self, code):
        entry = authority_for(code)
        assert entry, f"{code} has no entry"
        if entry["basis"] == "citation":
            note = entry.get("threshold_note", "")
            assert len(note) >= 30, (
                f"{code} fires on a threshold TalkingToad chose, and cites "
                f"{entry['source']}. Without a threshold_note the citation "
                f"reads as though the source published the number. Either add "
                f"one or declare the code heuristic.")

    def test_v1_the_numeric_trigger_list_still_matches_the_catalogue(self):
        """P29 — a list of known-hard cases is worthless if its members quietly
        stop existing. Assert membership exactly, not a floor."""
        gone = sorted(set(self.NUMERIC_TRIGGER_CODES) - set(_CATALOGUE))
        assert not gone, (
            f"these codes no longer exist, so the honesty check above is not "
            f"testing anything: {gone}")

    def test_v1_every_citation_naming_a_threshold_declares_whose_it_is(self):
        """The list above is hand-written, so it can only police the codes
        somebody remembered to add. This derives instead: any citation whose
        own claim talks about a specific number must say whose number it is.

        A cold review found two codes missing from the hand-written list
        (JS_RENDERED_CONTENT_DIFFERS, UA_CONTENT_DIFFERS) — a sampled check
        policing a class it did not enumerate.
        """
        import re
        offenders = []
        for code in sorted(_CATALOGUE):
            entry = authority_for(code) or {}
            if entry.get("basis") != "citation":
                continue
            if entry.get("threshold_note"):
                continue
            if entry.get("threshold_published_by_source"):
                # The opposite case, stated explicitly: Google does publish the
                # Core Web Vitals bands, so quoting 4s or 500ms is reporting
                # the source's own figure, not dressing ours as theirs.
                continue
            # A claim that quotes a figure while the source is a vendor is the
            # risky shape: it reads as though the vendor published the figure.
            claim = entry.get("claim", "")
            if entry.get("source_type") == "vendor" and re.search(
                    r"\b\d+\s*(%|characters|seconds|ms|KB|MB|words|px)\b", claim):
                offenders.append(f"{code}: {claim[:70]}")
        assert not offenders, (
            "a vendor citation quotes a figure with no threshold_note saying "
            "whether the figure is the vendor's or ours:\n  "
            + "\n  ".join(offenders))


class TestTheRecordIsUsable:
    def test_v1_is_heuristic_agrees_with_the_record(self):
        raw = yaml.safe_load(_AUTHORITY_FILE.read_text(encoding="utf-8"))
        for code, entry in raw.items():
            assert is_heuristic(code) is (entry["basis"] == "heuristic"), code

    def test_v1_an_observation_is_not_reported_as_a_guess(self):
        """A measurement TalkingToad made is not judgement. Filing it as a
        heuristic understates it, and giving it a citation overstates it —
        the first draft of this record did both."""
        for code in ("AI_CITED_PAGE", "PAGE_TIMEOUT", "EXTERNAL_LINK_SKIPPED"):
            entry = authority_for(code)
            assert entry["basis"] == "observation", code
            assert is_heuristic(code) is False, (
                f"{code} is a recorded measurement, not a guess")

    def test_v1_unknown_code_claims_nothing(self):
        """An unrecorded code must not read as cited."""
        assert authority_for("NOT_A_REAL_CODE_XYZ") is None
        assert is_heuristic("NOT_A_REAL_CODE_XYZ") is True

    def test_v1_a_meaningful_share_of_codes_are_honestly_heuristic(self):
        """If nearly everything claimed a citation, the record would be doing
        what it exists to prevent. This is a smoke check on the record's
        honesty, not a target to tune."""
        heuristics = sum(1 for c in _CATALOGUE if is_heuristic(c))
        assert 30 <= heuristics <= 140, (
            f"{heuristics} of {len(_CATALOGUE)} codes are heuristic. Outside "
            f"this band the record is probably mis-stating one way or the "
            f"other — check it by hand rather than adjusting this bound.")

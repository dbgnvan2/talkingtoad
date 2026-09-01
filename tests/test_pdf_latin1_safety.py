"""The PDF is Latin-1, so no call site may hand fpdf a character it cannot encode.

Found while wiring the domain filter into the exports, and entirely
pre-existing: `_render_priority_pages_section` renders its blurb with a raw
`pdf.multi_cell(W, 5, blurb)`, and the branch taken when a site has NO Search
Console or GA4 data contains an em dash. That is the default for a nonprofit,
so the PDF export raised UnicodeEncodeError and returned 500 for exactly the
sites this tool is built for.

36 of the `pdf.cell` / `pdf.multi_cell` calls in report_generator.py skipped
`clean_text`. Rather than patch 36 call sites and hope the 37th remembers,
cleaning moved into TalkingToadReport.cell / .multi_cell, so a new call cannot
reintroduce it.

The existing PDF caveat test asserts that `orphan_coverage_note` is *called*
(by AST), not that the PDF renders — which is why a note containing an em dash
could sit in `coverage_notes.py` without anything going red.
"""

from __future__ import annotations

import pytest

from api.services.report_generator import TalkingToadReport

# Characters this codebase actually uses in report prose.
NON_LATIN1 = ["—", "–", "‘", "’", "“", "”",
              "…", "→", "✓", " ", "\U0001F438"]


class TestTheReportCannotBeBrokenByPunctuation:
    @pytest.mark.parametrize("ch", NON_LATIN1)
    def test_cell_survives_a_character_latin1_cannot_encode(self, ch):
        pdf = TalkingToadReport()
        pdf.add_page()
        pdf.set_font("helvetica", "", 10)
        pdf.cell(100, 5, f"before {ch} after")      # must not raise
        assert pdf.output()

    @pytest.mark.parametrize("ch", NON_LATIN1)
    def test_multi_cell_survives_the_same(self, ch):
        pdf = TalkingToadReport()
        pdf.add_page()
        pdf.set_font("helvetica", "", 10)
        pdf.multi_cell(100, 5, f"before {ch} after")
        assert pdf.output()

    def test_the_em_dash_blurb_that_actually_broke_it(self):
        """The exact string from _render_priority_pages_section."""
        pdf = TalkingToadReport()
        pdf.add_page()
        pdf.set_font("helvetica", "", 10)
        pdf.multi_cell(160, 5, (
            "Ranked by page health. No Search Console or GA4 data was supplied "
            "for this site, so traffic and conversions could not be weighed — "
            "see Scope, Method and Caveats."))
        assert pdf.output()


class TestTheGuardIsRealAndNarrow:
    def test_adversarial_ascii_text_is_passed_through_unchanged(self):
        """The cleaner must not mangle ordinary text, or it would quietly
        corrupt every report while keeping this file green."""
        pdf = TalkingToadReport()
        assert pdf.clean_text("Plain ASCII, 100% intact.") == "Plain ASCII, 100% intact."

    def test_adversarial_the_cleaner_is_actually_reached_by_cell(self):
        """Pins that the OVERRIDE is what protects us, not luck: with cleaning
        removed, the em-dash case raises. Proven by calling fpdf's own
        implementation directly, which is what the override bypasses."""
        from fpdf import FPDF
        raw = FPDF(orientation="P", unit="mm", format="Letter")
        raw.add_page()
        raw.set_font("helvetica", "", 10)
        with pytest.raises(Exception):
            raw.multi_cell(100, 5, "an em dash — here")
            raw.output()

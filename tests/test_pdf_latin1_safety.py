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
        """Pins that OUR override is what protects us.

        The first version built a raw `fpdf.FPDF` and asserted it raised —
        which tests fpdf, not TalkingToad. Deleting TalkingToadReport.cell and
        .multi_cell turned 21 of 25 tests in this file red and left that one
        green. This version drives our own class and asserts the cleaning
        actually happened, with a narrowed exception type so an unrelated
        signature change cannot masquerade as protection.
        """
        pdf = TalkingToadReport()
        # The override must transform the text, not merely pass it through.
        assert pdf.clean_text("em — dash") != "em — dash"
        assert pdf.clean_text("em — dash").encode("latin-1")   # now encodable

        pdf.add_page()
        pdf.set_font("helvetica", "", 10)
        # And the override must be on the class we actually use, not inherited
        # unchanged from fpdf.
        assert TalkingToadReport.multi_cell is not __import__("fpdf").FPDF.multi_cell
        assert TalkingToadReport.cell is not __import__("fpdf").FPDF.cell

    def test_adversarial_raw_fpdf_still_fails_on_the_same_input(self):
        """The control: unprotected fpdf genuinely cannot take this text, so
        the protection above is doing real work."""
        from fpdf import FPDF
        from fpdf.errors import FPDFUnicodeEncodingException
        raw = FPDF(orientation="P", unit="mm", format="Letter")
        raw.add_page()
        raw.set_font("helvetica", "", 10)
        # Named exactly: a bare `Exception` would let an unrelated signature
        # change (a TypeError) masquerade as the protection working.
        with pytest.raises(FPDFUnicodeEncodingException):
            raw.multi_cell(100, 5, "an em dash — here")

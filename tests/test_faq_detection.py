"""FAQ detection hardening — accordion-aware detection (A) + AI-visibility check (B).

Spec: docs/pending/OLD/2026-07-04_faq-detection-accordion-aivisibility.md
Origin: page-by-page accuracy audit of livingsystems.ca (Elementor nested-accordion FAQ)
        where FAQ_SCHEMA_MISSING reported `question_headings: 0` despite 7 real questions.
"""

from bs4 import BeautifulSoup

from api.crawler.parser import _extract_faq_blocks
from api.crawler.checkers.registry import derive_impact, severity_from_impact, _CATALOGUE
from tests.test_issue_checker import _page
from api.crawler.issue_checker import check_page


# ── A1/A2: parser extracts accordion Q&A into faq_blocks ──────────────────────
def _q(blocks):
    return {b["question"] for b in blocks}


def test_faq_extract_details_summary():
    """Native <details>/<summary> FAQ with answer text present in source."""
    html = """
    <section>
      <details><summary>Who is counselling for?</summary>
        <p>Counselling can help anyone facing life's challenges, no referral needed.</p>
      </details>
      <details><summary>How much does it cost?</summary>
        <p>We offer a regular rate and a low-cost sliding scale for those in need.</p>
      </details>
    </section>"""
    blocks = _extract_faq_blocks(BeautifulSoup(html, "lxml"))
    assert _q(blocks) == {"Who is counselling for?", "How much does it cost?"}
    assert all(b["answer_char_count"] >= 40 for b in blocks)
    assert all(b["container"] == "details" for b in blocks)


def test_faq_extract_elementor_nested_accordion():
    """Elementor nested-accordion titles (.e-n-accordion-item-title-text)."""
    html = """
    <div class="e-n-accordion-item">
      <span class="e-n-accordion-item-title-text">Are sessions available online?</span>
      <div class="e-n-accordion-item-content"><p>Yes — sessions are available online and in person depending on your therapist.</p></div>
    </div>"""
    blocks = _extract_faq_blocks(BeautifulSoup(html, "lxml"))
    assert "Are sessions available online?" in _q(blocks)
    assert blocks[0]["answer_char_count"] >= 40


def test_faq_dedupes_mobile_desktop_duplicates():
    """Elementor emits a mobile + desktop copy of each question — count once."""
    html = """
    <div class="e-n-accordion-item"><span class="e-n-accordion-item-title-text">How do I get started?</span>
      <div><p>Complete the intake form and we'll match you with a therapist within days.</p></div></div>
    <div class="e-n-accordion-item"><span class="e-n-accordion-item-title-text">How do I get started?</span>
      <div><p>Complete the intake form and we'll match you with a therapist within days.</p></div></div>"""
    blocks = _extract_faq_blocks(BeautifulSoup(html, "lxml"))
    assert len([b for b in blocks if b["question"] == "How do I get started?"]) == 1


def test_faq_extract_ignores_non_question_accordion():
    """A non-FAQ accordion (feature titles, no '?') is NOT collected as FAQ."""
    html = """
    <div class="e-n-accordion-item"><span class="e-n-accordion-item-title-text">Fast, secure hosting</span>
      <div><p>Our platform is fast and secure.</p></div></div>
    <details><summary>Free migration included</summary><p>We migrate your site for free.</p></details>"""
    blocks = _extract_faq_blocks(BeautifulSoup(html, "lxml"))
    assert blocks == []


# ── A3: FAQ_SCHEMA_MISSING fires on accordion FAQ with NO literal "FAQ" heading ─
def _faq_page(html_body, schema_types=None):
    """Build a ParsedPage with faq_blocks populated from the given body HTML."""
    page = _page(url="https://wp.example/counselling/", schema_types=schema_types or [])
    page.faq_blocks = _extract_faq_blocks(BeautifulSoup(html_body, "lxml"))
    page.word_count = 800
    return page


def test_faq_schema_missing_fires_on_accordion_without_faq_heading():
    """The exact false-negative the audit found: accordion FAQ, no <h?>FAQ</h?>,
    no FAQPage schema -> must still fire FAQ_SCHEMA_MISSING (was silently missed)."""
    html = """
      <details><summary>Who is counselling for?</summary><p>Anyone facing challenges can benefit greatly.</p></details>
      <details><summary>How do I get started?</summary><p>Complete the intake form to begin your journey.</p></details>
      <details><summary>Is it covered by insurance?</summary><p>Many extended health plans provide coverage here.</p></details>"""
    page = _faq_page(html)
    codes = {i.code for i in check_page(page)}
    assert "FAQ_SCHEMA_MISSING" in codes


def test_faq_extra_reports_accurate_question_count():
    """The misleading `question_headings: 0` is replaced by an accurate count."""
    html = """
      <details><summary>Who is counselling for?</summary><p>Anyone facing challenges can benefit greatly.</p></details>
      <details><summary>How do I get started?</summary><p>Complete the intake form to begin your journey.</p></details>
      <details><summary>Is it covered by insurance?</summary><p>Many extended health plans provide coverage here.</p></details>"""
    page = _faq_page(html)
    faq = next(i for i in check_page(page) if i.code == "FAQ_SCHEMA_MISSING")
    assert faq.extra.get("question_count") == 3


def test_faq_schema_missing_not_fired_when_schema_present():
    html = "<details><summary>Who is counselling for?</summary><p>Anyone facing life's challenges here.</p></details>"
    page = _faq_page(html, schema_types=["FAQPage"])
    assert "FAQ_SCHEMA_MISSING" not in {i.code for i in check_page(page)}


def test_non_question_accordion_not_flagged():
    """P7 adversarial: a feature/spec accordion must NOT trigger FAQ_SCHEMA_MISSING."""
    html = """
      <div class="e-n-accordion-item"><span class="e-n-accordion-item-title-text">Fast hosting</span><div><p>Speedy.</p></div></div>
      <div class="e-n-accordion-item"><span class="e-n-accordion-item-title-text">Secure by default</span><div><p>Safe.</p></div></div>
      <div class="e-n-accordion-item"><span class="e-n-accordion-item-title-text">Free migration</span><div><p>Included.</p></div></div>"""
    page = _faq_page(html)
    assert "FAQ_SCHEMA_MISSING" not in {i.code for i in check_page(page)}


# ── B: FAQ_ANSWERS_NOT_IN_HTML — answers absent from raw HTML (JS-hydrated) ────
def test_faq_answers_js_only_flagged():
    """Question titles present but answer bodies empty in raw HTML -> AI-invisible."""
    html = """
      <details><summary>Who is counselling for?</summary></details>
      <details><summary>How do I get started?</summary></details>
      <details><summary>Is it covered by insurance?</summary></details>"""
    page = _faq_page(html)
    faq = check_page(page)
    codes = {i.code for i in faq}
    assert "FAQ_ANSWERS_NOT_IN_HTML" in codes
    issue = next(i for i in faq if i.code == "FAQ_ANSWERS_NOT_IN_HTML")
    assert issue.extra["affected"] >= 2


def test_faq_answers_present_not_flagged():
    """livingsystems.ca-style: answers present in HTML -> B does NOT fire."""
    html = """
      <details><summary>Who is counselling for?</summary><p>Counselling can help anyone facing difficulties, no referral needed at all.</p></details>
      <details><summary>How do I get started?</summary><p>The first step is completing the intake form so we can match you well.</p></details>"""
    page = _faq_page(html)
    assert "FAQ_ANSWERS_NOT_IN_HTML" not in {i.code for i in check_page(page)}


# ── Registry parity for the new code ──────────────────────────────────────────
def test_new_code_registered_and_consistent():
    assert "FAQ_ANSWERS_NOT_IN_HTML" in _CATALOGUE
    impact = derive_impact("FAQ_ANSWERS_NOT_IN_HTML")
    assert impact == 4  # Reasonable proxy x moderate
    assert _CATALOGUE["FAQ_ANSWERS_NOT_IN_HTML"].severity == severity_from_impact(impact)
    assert _CATALOGUE["FAQ_ANSWERS_NOT_IN_HTML"].confidence_label is not None

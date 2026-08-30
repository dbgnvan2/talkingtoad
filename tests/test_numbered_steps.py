"""AF7b — CODE_BLOCK_MISSING_TECHNICAL must be able to fire.

Spec:  docs/pending/2026-08-30_audit-fixes.md#AF7
Audit: docs/audit/2026-08-30_full-check-audit.md (F17)

The gate `_has_numbered_steps(headings, page)` ignored its `headings` argument
entirely (AST-proven) and grepped a LINE-ANCHORED regex (`^\\d+[.)]` with re.M)
against `first_200_words` — which is space-joined and holds zero newlines, so
`^` could only match at position 0. Verified unreachable against `<ol><li>`,
"1. " in paragraphs, and inline "1. 2. 3.". 0 firings in 156 jobs.
"""
from __future__ import annotations

from api.crawler.checkers.ai_readiness import _has_numbered_steps
from api.crawler.fetcher import FetchResult
from api.crawler.issue_checker import check_page
from api.crawler.parser import parse_page

BASE = "https://example.com/"
_FILLER = " ".join(["word"] * 300)
_TECH = ("<script type='application/ld+json'>"
         '{"@context":"https://schema.org","@type":"TechArticle","headline":"X"}'
         "</script>")


def _page(body, head="", url="https://example.com/tutorial/setup"):
    html = ("<!DOCTYPE html><html lang='en'><head><title>A Setup Guide With A Long Title</title>"
            "<meta name='description' content='A description long enough to pass the checks here.'>"
            f"{head}</head><body>{body}<p>{_FILLER}</p></body></html>")
    return parse_page(
        FetchResult(url=url, final_url=url, status_code=200, headers={},
                    html=html, content_type="text/html"), BASE)


class TestNumberedStepDetection:
    def test_af7b_ordered_list_counts_as_numbered_steps(self):
        """The canonical shape, and the one that produced NO digits in the text."""
        p = _page("<h1>Setup</h1><ol><li>Install</li><li>Configure</li><li>Run</li></ol>")
        assert p.ordered_list_item_count == 3
        assert _has_numbered_steps(p.headings_outline, p) is True

    def test_af7b_step_headings_count(self):
        p = _page("<h1>Setup</h1><h2>Step 1: Install</h2><h2>Step 2: Configure</h2>")
        assert _has_numbered_steps(p.headings_outline, p) is True

    def test_af7b_numbered_headings_count(self):
        p = _page("<h1>Setup</h1><h2>1. Install</h2><h2>2. Configure</h2>")
        assert _has_numbered_steps(p.headings_outline, p) is True

    def test_af7b_inline_numbering_in_prose_counts(self):
        p = _page("<h1>Setup</h1><p>1. Install the SDK 2. Configure the key 3. Run it</p>")
        assert _has_numbered_steps(p.headings_outline, p) is True

    def test_af7b_a_single_numbered_item_is_not_a_procedure(self):
        """Adversarial: one '1.' is a footnote, not a sequence."""
        p = _page("<h1>About</h1><p>1. A lone numbered note appears here.</p>")
        assert _has_numbered_steps(p.headings_outline, p) is False

    def test_af7b_ordinary_prose_is_not_a_procedure(self):
        """Adversarial: the fix must not make every page look like a tutorial."""
        p = _page("<h1>About Us</h1><h2>Our History</h2><h2>Our Team</h2>")
        assert _has_numbered_steps(p.headings_outline, p) is False


class TestCodeBlockMissingTechnical:
    def test_af7b_technical_page_with_steps_and_no_code_fires(self):
        p = _page("<h1>Setup</h1><ol><li>Install the SDK</li><li>Set the API key</li></ol>",
                  head=_TECH)
        assert any(i.code == "CODE_BLOCK_MISSING_TECHNICAL" for i in check_page(p))

    def test_af7b_technical_page_with_code_does_not_fire(self):
        """Adversarial: a page that HAS code blocks must stay clean."""
        p = _page("<h1>Setup</h1><ol><li>Install</li><li>Configure</li></ol>"
                  "<pre><code>pip install thing</code></pre>", head=_TECH)
        assert not any(i.code == "CODE_BLOCK_MISSING_TECHNICAL" for i in check_page(p))

    def test_af7b_non_technical_page_with_steps_does_not_fire(self):
        """Adversarial: a recipe-shaped charity page is not a technical doc."""
        p = _page("<h1>How to donate</h1><ol><li>Visit the page</li><li>Enter an amount</li></ol>",
                  url="https://example.com/donate")
        assert not any(i.code == "CODE_BLOCK_MISSING_TECHNICAL" for i in check_page(p))

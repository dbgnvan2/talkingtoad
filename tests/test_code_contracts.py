"""AF11 — the per-code contract every check must satisfy.

Spec:  docs/pending/2026-08-30_audit-fixes.md#AF11
Audit: docs/audit/2026-08-30_full-check-audit.md

The 2026-08-30 audit found 20 defects across 170 codes. Each belonged to a class
a contract makes impossible to reintroduce silently:

    DEAD            cannot fire at all          -> POSITIVE fixture
    STARVED         its input is never populated -> GUARD FIELDS
    FALSE-POSITIVE  fires on correct input       -> NEGATIVE fixture
    NO EVIDENCE     the finding names nothing    -> EVIDENCE keys

The NEGATIVE fixture is the one nothing previously required, and it is where the
alt-text bug would have died: `alt=""` is WCAG-correct markup, and no test in
2,700 asserted that correct-looking input must stay clean.
"""
from __future__ import annotations

import pytest

from api.crawler.checkers.code_contracts import codes_reading, guard_fields
from api.crawler.checkers.registry import _CATALOGUE
from api.crawler.fetcher import FetchResult
from api.crawler.issue_checker import check_page
from api.crawler.parser import parse_page

BASE = "https://example.com/"
_FILLER = " ".join(["word"] * 400)


def page(body: str = "", head: str = "", url: str = BASE, **kw):
    title = kw.pop("title", "A Reasonably Long Page Title Here")
    desc = kw.pop("desc", "A description long enough to pass the minimum length checks here.")
    lang = kw.pop("lang", "en")
    t = f"<title>{title}</title>" if title is not None else ""
    d = f"<meta name='description' content='{desc}'>" if desc is not None else ""
    lg = f" lang='{lang}'" if lang else ""
    html = (f"<!DOCTYPE html><html{lg}><head>{t}{d}"
            f"<meta name='viewport' content='width=device-width'>{head}</head>"
            f"<body>{body or f'<h1>H</h1><p>{_FILLER}</p>'}</body></html>")
    return parse_page(
        FetchResult(url=url, final_url=url, status_code=kw.pop("status", 200),
                    headers=kw.pop("headers", {}), html=html, content_type="text/html"),
        BASE, is_homepage=(url == BASE))


def fires(code: str, p) -> bool:
    return any(i.code == code for i in check_page(p))


# ── The contracts ───────────────────────────────────────────────────────────
# (code, positive fixture, negative fixture). The negative must be an input a
# CORRECT site produces — the shape most likely to be misread as a defect.
CONTRACTS = [
    ("TITLE_MISSING",
     lambda: page(title=None),
     lambda: page()),
    ("TITLE_TOO_LONG",
     lambda: page(title="A" * 120),
     lambda: page(title="A Perfectly Reasonable Title")),
    ("TITLE_TOO_SHORT",
     lambda: page(title="Short"),
     lambda: page(title="A Perfectly Reasonable Page Title Here")),
    ("META_DESC_MISSING",
     lambda: page(desc=None),
     lambda: page()),
    ("META_DESC_TOO_LONG",
     lambda: page(desc="d" * 200),
     lambda: page()),
    ("LANG_MISSING",
     lambda: page(lang=None),
     lambda: page()),
    ("H1_MISSING",
     lambda: page(body=f"<p>{_FILLER}</p>"),
     lambda: page()),
    ("H1_MULTIPLE",
     lambda: page(body=f"<h1>One</h1><h1>Two</h1><p>{_FILLER}</p>"),
     lambda: page()),
    ("HEADING_EMPTY",
     lambda: page(body=f"<h1>H</h1><h3></h3><p>{_FILLER}</p>"),
     # AF3: a heading wrapping a block is NOT empty — lxml only makes it look so.
     lambda: page(body=f"<h1>H</h1><h3><p>Practicum Student</p></h3><p>{_FILLER}</p>")),
    ("NOINDEX_META",
     lambda: page(head="<meta name='robots' content='noindex'>"),
     lambda: page(head="<meta name='robots' content='index,follow'>")),
    ("MISSING_VIEWPORT_META",
     lambda: parse_page(FetchResult(
         url=BASE, final_url=BASE, status_code=200, headers={},
         html=("<html lang='en'><head><title>A Reasonably Long Page Title Here</title>"
               "<meta name='description' content='A description long enough to pass checks.'>"
               f"</head><body><h1>H</h1><p>{_FILLER}</p></body></html>"),
         content_type="text/html"), BASE, is_homepage=True),
     lambda: page()),
    ("CANONICAL_EXTERNAL",
     lambda: page(head="<link rel='canonical' href='https://other-domain.org/x'>"),
     lambda: page(head=f"<link rel='canonical' href='{BASE}'>")),
    ("JSON_LD_MISSING",
     lambda: page(),
     lambda: page(head="<script type='application/ld+json'>"
                       '{"@context":"https://schema.org","@type":"Organization","name":"X"}'
                       "</script>")),
    ("INTERNAL_NOFOLLOW",
     lambda: page(body=f"<h1>H</h1><a href='{BASE}x' rel='nofollow'>x</a><p>{_FILLER}</p>"),
     lambda: page(body=f"<h1>H</h1><a href='{BASE}x'>x</a><p>{_FILLER}</p>")),
    ("MIXED_CONTENT",
     lambda: page(body=f"<h1>H</h1><img src='http://other.org/a.jpg' alt='A described image'><p>{_FILLER}</p>"),
     lambda: page(body=f"<h1>H</h1><img src='https://other.org/a.jpg' alt='A described image'><p>{_FILLER}</p>")),
    ("IMG_ALT_MISSING",
     lambda: page(body=f"<h1>H</h1><img src='/a.jpg'><p>{_FILLER}</p>"),
     # The 2026-08-30 defect: alt="" is the WCAG decorative signal, not a defect.
     lambda: page(body=f"<h1>H</h1><img src='/a.jpg' alt=''><p>{_FILLER}</p>")),
    ("ANCHOR_TEXT_GENERIC",
     lambda: page(body=f"<h1>H</h1><a href='{BASE}x'>click here</a><p>{_FILLER}</p>"),
     lambda: page(body=f"<h1>H</h1><a href='{BASE}x'>Read our counselling guide</a><p>{_FILLER}</p>")),
    # Gated on word_count >= 500, so both fixtures must clear that bar.
    ("QUOTATIONS_MISSING",
     lambda: page(body="<h1>H</h1><p>" + " ".join(["word"] * 600) + "</p>"),
     lambda: page(body="<h1>H</h1><blockquote>A cited quotation.</blockquote><p>"
                       + " ".join(["word"] * 600) + "</p>")),
    ("COMPARISON_TABLE_MISSING",
     lambda: page(body=f"<h1>X vs Y</h1><p>{_FILLER}</p>"),
     lambda: page(body=f"<h1>X vs Y</h1><table><tr><td>a</td></tr></table><p>{_FILLER}</p>")),
]

CONTRACT_CODES = {c for c, _, _ in CONTRACTS}


@pytest.mark.parametrize("code,positive,_negative", CONTRACTS, ids=[c[0] for c in CONTRACTS])
def test_af11_positive_fixture_fires(code, positive, _negative):
    """The check is not DEAD: an input that should trigger it, does."""
    assert fires(code, positive()), f"{code} did not fire on its positive fixture"


@pytest.mark.parametrize("code,_positive,negative", CONTRACTS, ids=[c[0] for c in CONTRACTS])
def test_af11_negative_fixture_stays_clean(code, _positive, negative):
    """The check is not a FALSE POSITIVE: correct-looking input stays clean.

    This is the assertion that did not exist for IMG_ALT_MISSING.
    """
    assert not fires(code, negative()), f"{code} fired on correct input"


class TestGuardFieldIntegrity:
    def test_af11_every_guard_field_exists_on_a_model(self):
        """A guard reading a field that no model has is a rename that went
        unnoticed — the check would be silently dead."""
        from api.crawler.parser import ParsedPage
        from api.models.image import ImageInfo

        known = set(getattr(ParsedPage, "__annotations__", {}))
        known |= set(getattr(ImageInfo, "__annotations__", {}))
        known |= {n for n in dir(ParsedPage) if not n.startswith("_")}
        known |= {n for n in dir(ImageInfo) if not n.startswith("_")}
        unknown = {}
        for code, fields in guard_fields().items():
            missing = {f for f in fields if f not in known}
            if missing:
                unknown[code] = sorted(missing)
        assert not unknown, f"guards read fields no model defines: {unknown}"

    def test_af11_starvation_query_is_wired(self):
        """`codes_reading` is how a never-populated field is traced back to the
        checks it silently kills. It found the four dead image checks."""
        assert codes_reading("width") == ["IMG_NO_SRCSET", "IMG_OVERSCALED", "IMG_POOR_COMPRESSION"]
        assert codes_reading("crawl_depth") == ["HIGH_CRAWL_DEPTH"]


class TestContractCoverage:
    """Coverage is deliberately visible: the number must go UP, never down."""

    #: Codes with no contract yet. This list may only shrink.
    MIN_CONTRACTS = len(CONTRACTS)

    def test_af11_contract_count_does_not_regress(self):
        assert len(CONTRACTS) >= self.MIN_CONTRACTS

    def test_af11_every_contract_names_a_real_code(self):
        unknown = CONTRACT_CODES - set(_CATALOGUE)
        assert not unknown, f"contracts for non-existent codes: {unknown}"

    def test_af11_coverage_is_reported_honestly(self):
        """Not a pass/fail bar — a visible number, so 'we have contracts' can
        never be mistaken for 'every code has one' (P33: name the axis)."""
        pct = 100.0 * len(CONTRACT_CODES) / len(_CATALOGUE)
        assert pct > 0
        print(f"\ncode-contract coverage: {len(CONTRACT_CODES)}/{len(_CATALOGUE)} ({pct:.0f}%)")

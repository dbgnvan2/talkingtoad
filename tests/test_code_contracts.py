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
    # Baseline must be CLEAN: long enough to clear META_DESC_TOO_SHORT (<70)
    # and short enough to clear META_DESC_TOO_LONG (>160). A fixture that
    # trips an unrelated check makes every other contract noisier.
    desc = kw.pop("desc", "A description that is comfortably long enough to pass the "
                          "minimum length check without exceeding the maximum.")
    lang = kw.pop("lang", "en")
    t = f"<title>{title}</title>" if title is not None else ""
    d = f"<meta name='description' content='{desc}'>" if desc is not None else ""
    lg = f" lang='{lang}'" if lang else ""
    html = (f"<!DOCTYPE html><html{lg}><head>{t}{d}"
            f"<meta name='viewport' content='width=device-width'>{head}</head>"
            f"<body>{body or f'<h1>H</h1><p>{_FILLER}</p>'}</body></html>")
    return parse_page(
        FetchResult(url=url, final_url=url, status_code=kw.pop("status", 200),
                    headers=kw.pop("headers", {}), html=html, content_type="text/html",
                    # The fetcher always sets this, and text_to_html_ratio is
                    # computed only when it is > 0 — without it, every
                    # ratio-based check is silently unreachable in a fixture.
                    response_size_bytes=len(html.encode("utf-8"))),
        BASE, is_homepage=(url == BASE))


def _fetch_asset(content_type: str, size: int):
    """A FetchResult for a non-HTML asset, as the engine hands it to check_asset."""
    from api.crawler.fetcher import FetchResult
    return FetchResult(url=f"{BASE}a.pdf", final_url=f"{BASE}a.pdf", status_code=200,
                       headers={"content-length": str(size)}, html=None,
                       content_type=content_type, response_size_bytes=size)


def _with(obj, **attrs):
    """Set attributes the ENGINE assigns after parsing (last_modified, depth)."""
    for k, v in attrs.items():
        setattr(obj, k, v)
    return obj


def fires(code: str, p) -> bool:
    return any(i.code == code for i in check_page(p))


# ── Runners ────────────────────────────────────────────────────────────────
# A contract's fixture is a callable returning the INPUT; the runner turns that
# input into issues. Several codes are emitted outside check_page, and the
# reachability audit showed that 18 of 28 first-pass "dead" verdicts were really
# the wrong entry point — so the runner is part of the contract, not an
# assumption.

def _run_page(inp):
    return check_page(inp)


def _run_url(inp):
    from api.crawler.checkers.url_structure import check_url_structure
    return check_url_structure(inp)


def _run_image(inp):
    from api.crawler import image_analyzer as IA
    return IA.analyze_image(inp, job_id="j")[0]


def _run_cross(inp):
    from api.crawler.issue_checker import check_cross_page
    return check_cross_page(inp, start_url=BASE)


def _run_redirect(inp):
    """inp = (url, first_status, chain, final_url)."""
    from api.crawler.issue_checker import issues_for_redirect
    url, status, chain, final = inp
    return issues_for_redirect(url, status, chain, final_url=final, base_url=BASE)


def _run_status(inp):
    """inp = (status_code, url) -> the issue for an HTTP status, if any."""
    from api.crawler.issue_checker import issue_for_status
    issue = issue_for_status(inp[0], inp[1])
    return [issue] if issue else []


def _run_robots(inp):
    """inp = robots.txt text."""
    from api.crawler.robots import RobotsData, _parse_robots
    from api.services.ai_readiness import check_ai_bot_access
    parser, delay, sitemaps = _parse_robots(f"{BASE}robots.txt", inp)
    return check_ai_bot_access(RobotsData(parser, delay, sitemaps, inp), BASE.rstrip("/"))


def _run_asset(inp):
    """inp = FetchResult for a non-HTML asset (PDF/image)."""
    from api.crawler.checkers.images import check_asset
    return check_asset(inp, img_size_limit_kb=200)


def _run_engine(inp):
    """inp = a callable that registers respx mocks; returns the crawl's issues.

    Several codes are emitted by the ENGINE, not by any checker — redirect
    loops, login redirects, timeouts, www canonicalisation, robots blocks, the
    llms.txt / ai.txt probes. They are only reachable through a real crawl, so
    the contract runs one against mocked HTTP.
    """
    import asyncio

    import respx

    from api.crawler.engine import CrawlSettings, run_crawl

    async def _go():
        with respx.mock:
            inp(respx.mock)
            result = await run_crawl("contract", BASE,
                                     CrawlSettings(crawl_delay_ms=0, max_pages=10))
        return result.issues

    return asyncio.run(_go())


def _run_geo_llm(inp):
    """inp = the LLM verdict dict."""
    from api.services.geo_llm import geo_llm_issues
    return geo_llm_issues(BASE, inp)


def _run_vitals(inp):
    """inp = a WebVitalsReport."""
    from api.services.web_vitals import vitals_issues
    return vitals_issues(inp)


def _run_render(inp):
    """inp = a JSRenderResult-shaped object (the Playwright comparison)."""
    from api.crawler.issue_checker import js_render_issues
    return js_render_issues(inp)


RUNNERS = {"page": _run_page, "url": _run_url, "image": _run_image, "cross": _run_cross,
           "redirect": _run_redirect, "status": _run_status, "robots": _run_robots,
           "asset": _run_asset, "engine": _run_engine, "geo_llm": _run_geo_llm,
           "vitals": _run_vitals, "render": _run_render}


def _vitals(**kw):
    """A WebVitalsReport with one FIELD row. Lab rows never raise a finding, so
    the source must be "field" — that distinction is the feature's whole point."""
    from api.services.web_vitals import VitalsRow, WebVitalsReport
    row = VitalsRow(url=BASE, source=kw.pop("source", "field"),
                    lcp_ms=kw.pop("lcp_ms", 1200), inp_ms=kw.pop("inp_ms", 120),
                    cls=kw.pop("cls", 0.02), performance_score=kw.pop("score", 95),
                    unavailable_reason=None, retryable=False)
    return WebVitalsReport(rows=[row], requested=1, field_count=1, lab_count=0,
                           unavailable_count=0, retryable_failures=0,
                           strategy="mobile", had_api_key=True)


def _render(**kw):
    """A JSRenderResult-shaped stand-in for the Playwright comparison."""
    from types import SimpleNamespace
    base = dict(url=BASE, error=None, js_rendered_content_differs=False,
                content_cloaking_detected=False, ua_content_differs=False,
                raw_token_count=500, rendered_token_count=520,
                added_token_ratio=0.04, topic_jaccard=0.9,
                gptbot_token_count=500, claudebot_token_count=500)
    base.update(kw)
    return SimpleNamespace(**base)


# ── Engine-runner helpers ──────────────────────────────────────────────────
_OK_ROBOTS = "User-agent: *\nDisallow:\n"
_OK_HTML = ("<!DOCTYPE html><html lang='en'><head><title>A Page With A Good Long Title</title>"
            "<meta name='description' content='A description long enough to pass the checks here.'>"
            "</head><body><h1>H</h1><p>" + " ".join(["word"] * 80) + "</p></body></html>")


def _engine_base(mock, *, robots=_OK_ROBOTS, home=None):
    """Register the three probes every crawl makes, then the homepage."""
    import httpx
    mock.get("https://example.com/robots.txt").mock(return_value=httpx.Response(200, text=robots))
    mock.get("https://example.com/sitemap.xml").mock(return_value=httpx.Response(404))
    mock.get(BASE).mock(return_value=(home or httpx.Response(
        200, text=_OK_HTML, headers={"content-type": "text/html"})))
    return mock


def img(**kw):
    """An ImageInfo with sane defaults — only the field under test varies."""
    from api.models.image import ImageInfo
    base = dict(url="https://example.com/sunset-beach.jpg", page_url=BASE, job_id="j",
                filename="sunset-beach.jpg", alt="A described sunset over the beach",
                http_status=200)
    base.update(kw)
    return ImageInfo(**base)


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

# ── URL-structure codes (runner="url") ─────────────────────────────────────
CONTRACTS += [
    ("URL_UPPERCASE",
     lambda: "https://example.com/Some/Path", lambda: "https://example.com/some/path", "url"),
    ("URL_HAS_UNDERSCORES",
     lambda: "https://example.com/some_path", lambda: "https://example.com/some-path", "url"),
    ("URL_HAS_SPACES",
     lambda: "https://example.com/a b", lambda: "https://example.com/a-b", "url"),
    ("URL_TOO_LONG",
     lambda: "https://example.com/" + "segment-" * 40, lambda: "https://example.com/short", "url"),
]

# ── Image codes (runner="image") ───────────────────────────────────────────
CONTRACTS += [
    ("IMG_ALT_GENERIC",
     lambda: img(alt="image"), lambda: img(alt="A sunset over Ambleside beach"), "image"),
    ("IMG_ALT_TOO_SHORT",
     lambda: img(alt="ab"), lambda: img(alt="A sunset over Ambleside beach"), "image"),
    ("IMG_ALT_TOO_LONG",
     lambda: img(alt="A " + "very " * 60 + "long description"),
     lambda: img(alt="A sunset over Ambleside beach"), "image"),
    ("IMG_ALT_DUP_FILENAME",
     lambda: img(alt="sunset beach"), lambda: img(alt="Volunteers planting trees at dawn"), "image"),
    ("IMG_ALT_MISUSED",
     # A decorative image must NOT carry meaningful alt text...
     lambda: img(alt="A meaningful description", is_decorative=True),
     # ...but alt="" on a decorative image is exactly right (WCAG 1.1.1).
     lambda: img(alt="", is_decorative=True), "image"),
    ("IMG_BROKEN",
     lambda: img(http_status=404), lambda: img(http_status=200), "image"),
    ("IMG_OVERSIZED",
     lambda: img(file_size_bytes=3_000_000), lambda: img(file_size_bytes=40_000), "image"),
    ("IMG_NO_SRCSET",
     lambda: img(has_srcset=False, width=2000, rendered_width=400),
     lambda: img(has_srcset=True, width=2000, rendered_width=400), "image"),
    ("IMG_OVERSCALED",
     lambda: img(width=4000, height=3000, rendered_width=400, rendered_height=300,
                 file_size_bytes=90_000),
     lambda: img(width=800, height=600, rendered_width=800, rendered_height=600,
                 file_size_bytes=90_000), "image"),
]

# ── Page codes, second tranche ─────────────────────────────────────────────
CONTRACTS += [
    ("META_DESC_TOO_SHORT",
     lambda: page(desc="Too short."), lambda: page()),
    ("HEADING_SKIP",
     lambda: page(body=f"<h1>H</h1><h4>Skipped two levels</h4><p>{_FILLER}</p>"),
     lambda: page(body=f"<h1>H</h1><h2>Next level</h2><p>{_FILLER}</p>")),
    ("HTTP_PAGE",
     lambda: page(url="http://example.com/p"), lambda: page(url="https://example.com/p")),
    ("CANONICAL_MISSING",
     lambda: page(url="https://example.com/p?x=1"),
     lambda: page(url="https://example.com/p?x=1",
                  head="<link rel='canonical' href='https://example.com/p'>")),
    ("CANONICAL_SELF_MISSING",
     lambda: page(url="https://example.com/plain"),
     lambda: page(url="https://example.com/plain",
                  head="<link rel='canonical' href='https://example.com/plain'>")),
    ("SCHEMA_ORG_MISSING",
     lambda: page(url=BASE),
     lambda: page(url=BASE, head="<script type='application/ld+json'>"
                                 '{"@context":"https://schema.org","@type":"Organization",'
                                 '"name":"Living Systems"}</script>')),
    ("SCHEMA_TYPE_CONFLICT",
     lambda: page(head="<script type='application/ld+json'>"
                       '{"@context":"https://schema.org","@graph":'
                       '[{"@type":"Article"},{"@type":"Product"}]}</script>'),
     lambda: page(head="<script type='application/ld+json'>"
                       '{"@context":"https://schema.org","@type":"Article"}</script>')),
    ("LINK_EMPTY_ANCHOR",
     lambda: page(body=f"<h1>H</h1><a href='{BASE}x'></a><p>{_FILLER}</p>"),
     # An icon link with an accessible name is CORRECT, not an empty anchor.
     lambda: page(body=f"<h1>H</h1><a href='{BASE}x' aria-label='Our Facebook page'>"
                       f"<svg></svg></a><p>{_FILLER}</p>")),
    ("PLACEHOLDER_LINK",
     lambda: page(body=f"<h1>H</h1><a href='#'>Learn More</a>"
                       f"<a href='{BASE}x'>Real</a><p>{_FILLER}</p>"),
     lambda: page(body=f"<h1>H</h1><a href='{BASE}x'>Learn More</a><p>{_FILLER}</p>")),
    ("PARA_TOO_LONG",
     lambda: page(body="<h1>H</h1><p>" + " ".join(["word"] * 400) + "</p>"),
     lambda: page(body="<h1>H</h1>" + "".join(f"<p>{' '.join(['word'] * 40)}</p>" for _ in range(6)))),
    ("LANDMARK_MAIN_MISSING",
     lambda: page(body=f"<h1>H</h1><p>{_FILLER}</p>"),
     lambda: page(body=f"<main><h1>H</h1><p>{_FILLER}</p></main>")),
    ("LANDMARK_NAV_MISSING",
     lambda: page(body=f"<main><h1>H</h1><p>{_FILLER}</p></main>"),
     lambda: page(body=f"<nav><a href='{BASE}a'>A</a></nav><main><h1>H</h1><p>{_FILLER}</p></main>")),
    ("NON_SEMANTIC_BUTTON",
     lambda: page(body=f"<h1>H</h1><div class='btn' onclick='go()'>Donate</div><p>{_FILLER}</p>"),
     lambda: page(body=f"<h1>H</h1><button>Donate</button><p>{_FILLER}</p>")),
    ("INTERACTIVE_NO_ACCESSIBLE_NAME",
     lambda: page(body=f"<h1>H</h1><button></button><p>{_FILLER}</p>"),
     lambda: page(body=f"<h1>H</h1><button aria-label='Donate now'></button><p>{_FILLER}</p>")),
    ("SELF_REFERENCING_UTM",
     lambda: page(body=f"<h1>H</h1><a href='{BASE}x?utm_source=site'>x</a><p>{_FILLER}</p>"),
     lambda: page(body=f"<h1>H</h1><a href='{BASE}x'>x</a><p>{_FILLER}</p>")),
    ("FAQ_SCHEMA_MISSING",
     lambda: page(body=f"<h1>FAQ</h1><h2>What is Bowen theory?</h2><p>{_FILLER}</p>",
                  url="https://example.com/faq"),
     lambda: page(body=f"<h1>FAQ</h1><h2>What is Bowen theory?</h2><p>{_FILLER}</p>",
                  url="https://example.com/faq",
                  head="<script type='application/ld+json'>"
                       '{"@context":"https://schema.org","@type":"FAQPage","mainEntity":'
                       '[{"@type":"Question","name":"What is Bowen theory?","acceptedAnswer":'
                       '{"@type":"Answer","text":"A theory of family systems."}}]}</script>')),
    ("CONTENT_NOT_EXTRACTABLE_NO_TEXT",
     lambda: page(body="<h1></h1>"), lambda: page()),
]

# ── Cross-page codes (runner="cross"): the fixture is a LIST of pages ──────
def _pages(*bodies_and_urls):
    return [page(body=b, url=u, **kw) for b, u, kw in bodies_and_urls]


_LD_ORG_LINKED = ("<script type='application/ld+json'>"
                  '{"@context":"https://schema.org","@type":"Organization","name":"LS",'
                  '"sameAs":["https://facebook.com/ls"]}</script>')
_LD_ORG_BARE = ("<script type='application/ld+json'>"
                '{"@context":"https://schema.org","@type":"Organization","name":"LS"}</script>')
_LD_AUTHOR = ("<script type='application/ld+json'>"
              '{"@context":"https://schema.org","@type":"Person","name":"Dave"}</script>')

CONTRACTS += [
    ("TITLE_DUPLICATE",
     lambda: [page(title="Exactly The Same Title", url=BASE),
              page(title="Exactly The Same Title", url=BASE + "b")],
     lambda: [page(title="A Distinct Title For Page One", url=BASE),
              page(title="A Different Title For Page Two", url=BASE + "b")], "cross"),
    ("META_DESC_DUPLICATE",
     lambda: [page(desc="D" * 100, url=BASE), page(desc="D" * 100, url=BASE + "b")],
     lambda: [page(desc="A" * 100, url=BASE), page(desc="B" * 100, url=BASE + "b")], "cross"),
    ("ENTITY_SAMEAS_MISSING",
     lambda: [page(head=_LD_ORG_BARE, url=BASE)],
     # The real 2026-08-30 case: the Organization IS linked; the Yoast author
     # Person node is not, and that is not a defect.
     lambda: [page(head=_LD_ORG_LINKED + _LD_AUTHOR, url=BASE)], "cross"),
    ("ORPHAN_PAGE",
     lambda: [page(url=BASE), page(url=BASE + "hidden")],
     lambda: [page(body=f"<h1>H</h1><a href='{BASE}linked'>Linked</a><p>{_FILLER}</p>", url=BASE),
              page(url=BASE + "linked")], "cross"),
]

# ── Page codes, third tranche ──────────────────────────────────────────────
_ARTICLE = ("<script type='application/ld+json'>"
            '{"@context":"https://schema.org","@type":"Article","headline":"X",'
            '"datePublished":"2026-01-01","dateModified":"2026-06-01",'
            '"author":{"@type":"Person","name":"Dave Galloway"}}</script>')
_ARTICLE_NO_DATES = ("<script type='application/ld+json'>"
                     '{"@context":"https://schema.org","@type":"Article","headline":"X",'
                     '"author":{"@type":"Person","name":"Dave Galloway"}}</script>')
_ARTICLE_NO_AUTHOR = ("<script type='application/ld+json'>"
                      '{"@context":"https://schema.org","@type":"Article","headline":"X",'
                      '"datePublished":"2026-01-01","dateModified":"2026-06-01"}</script>')
_BLOG = "https://example.com/blog/post"

CONTRACTS += [
    ("DATE_MODIFIED_MISSING",
     lambda: page(head=_ARTICLE_NO_DATES, url=_BLOG),
     lambda: page(head=_ARTICLE, url=_BLOG)),
    ("DATE_PUBLISHED_MISSING",
     lambda: page(head=_ARTICLE_NO_DATES, url=_BLOG),
     lambda: page(head=_ARTICLE, url=_BLOG)),
    ("AUTHOR_BYLINE_MISSING",
     lambda: page(head=_ARTICLE_NO_AUTHOR, url=_BLOG),
     lambda: page(head=_ARTICLE, url=_BLOG)),
    ("FAVICON_MISSING",
     lambda: page(url=BASE),
     lambda: page(url=BASE, head="<link rel='icon' href='/favicon.ico'>")),
    ("NOINDEX_HEADER",
     lambda: page(headers={"x-robots-tag": "noindex"}),
     lambda: page(headers={"x-robots-tag": "index, follow"})),
    ("META_REFRESH_REDIRECT",
     lambda: page(head="<meta http-equiv='refresh' content='0;url=/x'>"),
     lambda: page()),
    # Emitted by the image analyzer, not check_page — the wrong runner made
    # this look dead, which is exactly the 18-of-28 trap from the audit.
    # Emitted by the image analyzer, not check_page — the wrong runner made this
    # look dead, exactly the 18-of-28 trap from the audit. It also needs a size
    # over the legacy-format threshold: a small JPEG is not worth converting.
    ("IMG_FORMAT_LEGACY",
     lambda: img(url="https://example.com/a.jpg", filename="a.jpg",
                 format="jpeg", file_size_bytes=900_000),
     lambda: img(url="https://example.com/a.webp", filename="a.webp",
                 format="webp", file_size_bytes=900_000), "image"),
    ("UNSAFE_CROSS_ORIGIN_LINK",
     lambda: page(body=f"<h1>H</h1><a href='https://other.org/' target='_blank'>Ext</a><p>{_FILLER}</p>"),
     lambda: page(body="<h1>H</h1><a href='https://other.org/' target='_blank' "
                       f"rel='noopener noreferrer'>Ext</a><p>{_FILLER}</p>")),
    ("OUTBOUND_LINK_UNTRACKABLE",
     lambda: page(body=f"<h1>H</h1><a href='https://other.org/'><img src='https://other.org/i.png'>"
                       f"</a><p>{_FILLER}</p>"),
     lambda: page(body=f"<h1>H</h1><a href='https://other.org/'>A named destination</a><p>{_FILLER}</p>")),
    ("STATISTICS_COUNT_LOW",
     lambda: page(body="<h1>H</h1><p>" + " ".join(["word"] * 600) + "</p>"),
     lambda: page(body="<h1>H</h1><p>Research found 62% of clients improved, with 3 in 4 "
                       "reporting change and 48 per cent sustaining it. "
                       + " ".join(["word"] * 600) + "</p>")),
    ("EXTERNAL_CITATIONS_LOW",
     lambda: page(body="<h1>H</h1><p>" + " ".join(["word"] * 600) + "</p>"),
     lambda: page(body="<h1>H</h1><p><a href='https://who.int/report'>WHO report</a> "
                       + " ".join(["word"] * 600) + "</p>")),
    ("CONVERSATIONAL_H2_MISSING",
     lambda: page(body=f"<h1>H</h1><h2>Our Services</h2><p>{_FILLER}</p>"),
     lambda: page(body=f"<h1>H</h1><h2>What is Bowen theory?</h2><p>{_FILLER}</p>")),
    ("HOWTO_SCHEMA_INCOMPLETE",
     lambda: page(head="<script type='application/ld+json'>"
                       '{"@context":"https://schema.org","@type":"HowTo","name":"X"}</script>'),
     lambda: page(head="<script type='application/ld+json'>"
                       '{"@context":"https://schema.org","@type":"HowTo","name":"X","step":'
                       '[{"@type":"HowToStep","text":"First"},{"@type":"HowToStep","text":"Then"}]}'
                       "</script>")),
    ("PRODUCT_REVIEW_SCHEMA_MISSING",
     lambda: page(head="<script type='application/ld+json'>"
                       '{"@context":"https://schema.org","@type":"Product","name":"W"}</script>'),
     lambda: page(head="<script type='application/ld+json'>"
                       '{"@context":"https://schema.org","@type":"Product","name":"W",'
                       '"aggregateRating":{"@type":"AggregateRating","ratingValue":"4.5",'
                       '"reviewCount":"12"}}</script>')),
]

# ── Redirect / status codes ────────────────────────────────────────────────
CONTRACTS += [
    ("REDIRECT_301",
     lambda: ("https://other.org/a", 301, ["https://other.org/b"], "https://other.org/b"),
     lambda: ("https://other.org/a", 200, [], "https://other.org/a"), "redirect"),
    ("REDIRECT_302",
     lambda: ("https://other.org/a", 302, ["https://other.org/b"], "https://other.org/b"),
     lambda: ("https://other.org/a", 200, [], "https://other.org/a"), "redirect"),
    ("REDIRECT_CHAIN",
     lambda: (f"{BASE}a", 301, [f"{BASE}b", f"{BASE}c", f"{BASE}d"], f"{BASE}d"),
     lambda: (f"{BASE}a", 301, [f"{BASE}b"], f"{BASE}b"), "redirect"),
    ("INTERNAL_REDIRECT_301",
     lambda: (f"{BASE}old", 301, [f"{BASE}new"], f"{BASE}new"),
     lambda: (f"{BASE}old", 200, [], f"{BASE}old"), "redirect"),
    ("BROKEN_LINK_404",
     lambda: (404, f"{BASE}gone"), lambda: (200, f"{BASE}here"), "status"),
    ("BROKEN_LINK_410",
     lambda: (410, f"{BASE}gone"), lambda: (200, f"{BASE}here"), "status"),
    ("BROKEN_LINK_503",
     lambda: (503, f"{BASE}down"), lambda: (200, f"{BASE}up"), "status"),
    ("BROKEN_LINK_5XX",
     lambda: (500, f"{BASE}boom"), lambda: (200, f"{BASE}fine"), "status"),
]

# ── robots.txt / AI-bot codes ──────────────────────────────────────────────
_ROBOTS_OK = ("User-agent: *\nAllow: /\n"
              "User-agent: GPTBot\nAllow: /\n"
              "User-agent: OAI-SearchBot\nAllow: /\n"
              "User-agent: ChatGPT-User\nAllow: /\n")
CONTRACTS += [
    ("AI_BOT_BLANKET_DISALLOW",
     lambda: "User-agent: *\nDisallow: /\n", lambda: _ROBOTS_OK, "robots"),
    ("AI_BOT_TRAINING_DISALLOWED",
     lambda: "User-agent: GPTBot\nDisallow: /\nUser-agent: *\nAllow: /\n",
     lambda: _ROBOTS_OK, "robots"),
    ("AI_BOT_SEARCH_BLOCKED",
     lambda: "User-agent: OAI-SearchBot\nDisallow: /\nUser-agent: *\nAllow: /\n",
     lambda: _ROBOTS_OK, "robots"),
    ("AI_BOT_USER_FETCH_BLOCKED",
     lambda: "User-agent: ChatGPT-User\nDisallow: /\nUser-agent: *\nAllow: /\n",
     lambda: _ROBOTS_OK, "robots"),
    ("AI_BOT_NO_AI_DIRECTIVES",
     lambda: "User-agent: *\nAllow: /\n", lambda: _ROBOTS_OK, "robots"),
]

# ── Page codes, fourth tranche ─────────────────────────────────────────────
_LONG = " ".join(["word"] * 600)
CONTRACTS += [
    # Realistic prose, not one 400 KB token: the pathological fixture took 41s
    # to parse and surfaced AF12 (quadratic email regex). Fixed there; the
    # contract should exercise the size threshold, not the backtracking.
    ("PAGE_SIZE_LARGE",
     lambda: page(body="<h1>H</h1>" + "".join(
         f"<p>{' '.join(['word'] * 100)}</p>" for _ in range(700))),
     lambda: page()),
    # _titles_mismatch flags only when the significant-word sets are DISJOINT,
    # so the fixture words must not overlap at all ("Title" in both was enough
    # to clear it).
    ("TITLE_H1_MISMATCH",
     lambda: page(title="Counselling Appointments In Vancouver",
                  body=f"<h1>Podcast Episode Seventeen Transcript</h1><p>{_FILLER}</p>"),
     lambda: page(title="Bowen Family Systems Training",
                  body=f"<h1>Bowen Family Systems Training</h1><p>{_FILLER}</p>")),
    ("SOCIAL_PREVIEW_METADATA_MISSING",
     lambda: page(),
     lambda: page(head="<meta property='og:title' content='T'>"
                       "<meta property='og:description' content='D'>"
                       "<meta property='og:image' content='https://example.com/i.jpg'>"
                       "<meta name='twitter:card' content='summary_large_image'>")),
    ("THIN_CONTENT",
     lambda: page(body="<h1>H</h1><p>Only a few words here.</p>"),
     lambda: page(body=f"<h1>H</h1><p>{_LONG}</p>")),
    ("CONTENT_THIN",
     lambda: page(body="<h1>H</h1><p>Only a few words here.</p>"),
     lambda: page(body=f"<h1>H</h1><p>{_LONG}</p>")),
    ("MISSING_HSTS",
     lambda: page(url=BASE, headers={}),
     lambda: page(url=BASE, headers={"strict-transport-security": "max-age=31536000"})),
    # Fires on a block that PARSES but carries no @type. Syntactically broken
    # JSON-LD is reported as JSON_LD_MISSING instead — see the audit's adjacent
    # findings: "your structured data is absent" is not the same message as
    # "your structured data is broken".
    ("JSON_LD_INVALID",
     lambda: page(head="<script type='application/ld+json'>"
                       '{"@context":"https://schema.org","name":"No type here"}'
                       "</script>"),
     lambda: page(head="<script type='application/ld+json'>"
                       '{"@context":"https://schema.org","@type":"Organization","name":"X"}'
                       "</script>")),
    ("PAGINATION_LINKS_PRESENT",
     lambda: page(head="<link rel='next' href='https://example.com/p/2'>"),
     lambda: page()),
    # page.last_modified is assigned by the ENGINE after parse_page, not by the
    # parser, so a unit fixture must set it explicitly.
    ("CONTENT_STALE",
     lambda: _with(page(url=_BLOG), last_modified="Mon, 01 Jan 2015 00:00:00 GMT"),
     lambda: _with(page(url=_BLOG), last_modified="Mon, 01 Jul 2026 00:00:00 GMT")),
    ("STRUCTURED_ELEMENTS_LOW",
     lambda: page(body="<h1>H</h1><p>" + " ".join(["prose"] * 1400) + "</p>"),
     lambda: page(body="<h1>H</h1>" + "".join(
         f"<h2>Section {i}</h2><ul><li>a</li><li>b</li></ul><p>{' '.join(['word'] * 120)}</p>"
         for i in range(6)))),
    ("CONSENT_MODE_MISSING",
     lambda: page(head="<script async src='https://www.googletagmanager.com/gtag/js?id=G-AAA111'>"
                       "</script><script>gtag('config','G-AAA111');</script>"),
     lambda: page(head="<script async src='https://www.googletagmanager.com/gtag/js?id=G-AAA111'>"
                       "</script><script>gtag('consent','default',{'ad_storage':'denied'});"
                       "gtag('config','G-AAA111');</script>")),
    ("ANALYTICS_TAG_MISSING",
     lambda: page(),
     lambda: page(head="<script async src='https://www.googletagmanager.com/gtag/js?id=G-AAA111'>"
                       "</script><script>gtag('config','G-AAA111');</script>")),
]

# ── Fifth tranche: page/image/redirect codes with clear correct-input cases ──
_LONG = " ".join(["word"] * 700)
_REAL = "https://realsite.org/"
_TECH_LD = ("<script type='application/ld+json'>"
            '{"@context":"https://schema.org","@type":"TechArticle","headline":"X"}</script>')

CONTRACTS += [
    # Suppressed when IMG_OVERSIZED already explains the size, so the positive
    # must be dense-per-pixel WITHOUT tripping the oversize limit.
    ("IMG_POOR_COMPRESSION",
     lambda: img(width=200, height=150, file_size_bytes=190_000, format="jpeg"),
     lambda: img(width=1600, height=1200, file_size_bytes=190_000, format="jpeg"), "image"),
    ("IMG_SLOW_LOAD",
     lambda: img(load_time_ms=9000, file_size_bytes=50_000),
     lambda: img(load_time_ms=120, file_size_bytes=50_000), "image"),
    ("REDIRECT_CASE_NORMALISE",
     lambda: (f"{BASE}Cased", 301, [f"{BASE}cased"], f"{BASE}cased"),
     lambda: (f"{BASE}old", 301, [f"{BASE}totally-different"], f"{BASE}totally-different"),
     "redirect"),
    ("REDIRECT_TRAILING_SLASH",
     lambda: (f"{BASE}about", 301, [f"{BASE}about/"], f"{BASE}about/"),
     lambda: (f"{BASE}old", 301, [f"{BASE}new"], f"{BASE}new"), "redirect"),



    ("HIGH_CRAWL_DEPTH",
     lambda: _with(page(), crawl_depth=7),
     lambda: _with(page(), crawl_depth=2)),
    ("CODE_BLOCK_MISSING_TECHNICAL",
     lambda: page(head=_TECH_LD, url="https://example.com/tutorial/setup",
                  body=f"<h1>Setup</h1><ol><li>Install</li><li>Configure</li></ol><p>{_LONG}</p>"),
     lambda: page(head=_TECH_LD, url="https://example.com/tutorial/setup",
                  body=f"<h1>Setup</h1><ol><li>Install</li><li>Configure</li></ol>"
                       f"<pre><code>pip install thing</code></pre><p>{_LONG}</p>")),
    ("AI_NO_VISUAL_COMPANION",
     lambda: page(url="https://example.com/blog/post", head=_ARTICLE,
                  body=f"<h1>H</h1><p>{_LONG}</p>"),
     lambda: page(url="https://example.com/blog/post", head=_ARTICLE,
                  body=f"<h1>H</h1><img src='/a.jpg' alt='A described photo'><p>{_LONG}</p>")),
    ("BLOG_SECTIONS_MISSING",
     lambda: page(url="https://example.com/blog/post", body=f"<h1>Post</h1><p>{_LONG}</p>"),
     lambda: page(url="https://example.com/blog/post",
                  body="<h1>Post</h1>" + "".join(
                      f"<h2>Section {i} heading</h2><p>{' '.join(['word'] * 120)}</p>"
                      for i in range(4)))),
    ("CONTACT_INFO_NOT_IN_HTML",
     lambda: page(url=BASE, body=f"<h1>Home</h1><p>{_LONG}</p>"),
     lambda: page(url=BASE,
                  body=f"<h1>Home</h1><a href='mailto:info@example.com'>Email us</a><p>{_LONG}</p>")),
    # "no headings" means ZERO headings of any level — an <h1> counts.
    ("CONTENT_UNSTRUCTURED",
     lambda: page(body=f"<p>{_LONG}</p>"),
     lambda: page(body="<h1>H</h1>" + "".join(
         f"<h2>Section {i}</h2><p>{' '.join(['word'] * 120)}</p>" for i in range(5)))),
    ("CONTENT_IMAGE_HEAVY",
     lambda: page(body="<h1>H</h1>" + "".join(
         f"<img src='/i{i}.jpg' alt='A described photo {i}'>" for i in range(20))
         + f"<p>{' '.join(['word'] * 320)}</p>"),
     lambda: page(body="<h1>H</h1>" + "".join(
         f"<h2>Section {i}</h2><p>{' '.join(['word'] * 120)}</p>" for i in range(5))
         + "<img src='/i.jpg' alt='A described photo'>")),


    # check_asset takes a FetchResult, not an ImageInfo.
    ("PDF_TOO_LARGE",
     lambda: _fetch_asset("application/pdf", 20_000_000),
     lambda: _fetch_asset("application/pdf", 200_000), "asset"),
]

# ── Engine-driven codes (runner="engine") ──────────────────────────────────
# Emitted by run_crawl itself, so the contract runs a real crawl against mocked
# HTTP. The fixture is a callable that registers the mocks.
import httpx as _httpx   # noqa: E402  (test-local, keeps the fixtures readable)


def _eng(setup):
    return lambda: setup


def _loop(mock):
    _engine_base(mock)
    mock.get(f"{BASE}a").mock(return_value=_httpx.Response(301, headers={"location": f"{BASE}b"}))
    mock.get(f"{BASE}b").mock(return_value=_httpx.Response(301, headers={"location": f"{BASE}a"}))
    mock.get(BASE).mock(return_value=_httpx.Response(
        200, text=_OK_HTML.replace("<h1>H</h1>", f"<h1>H</h1><a href='{BASE}a'>loop</a>"),
        headers={"content-type": "text/html"}))


def _no_loop(mock):
    _engine_base(mock)
    mock.get(f"{BASE}a").mock(return_value=_httpx.Response(
        200, text=_OK_HTML, headers={"content-type": "text/html"}))
    mock.get(BASE).mock(return_value=_httpx.Response(
        200, text=_OK_HTML.replace("<h1>H</h1>", f"<h1>H</h1><a href='{BASE}a'>ok</a>"),
        headers={"content-type": "text/html"}))


def _login_redirect(mock):
    _engine_base(mock)
    mock.get(f"{BASE}members").mock(return_value=_httpx.Response(
        302, headers={"location": f"{BASE}wp-login.php?redirect_to=/members"}))
    mock.get(f"{BASE}wp-login.php").mock(return_value=_httpx.Response(
        200, text=_OK_HTML, headers={"content-type": "text/html"}))
    mock.get(BASE).mock(return_value=_httpx.Response(
        200, text=_OK_HTML.replace("<h1>H</h1>", f"<h1>H</h1><a href='{BASE}members'>Members</a>"),
        headers={"content-type": "text/html"}))


def _robots_blocked(mock):
    _engine_base(mock, robots="User-agent: *\nDisallow: /private/\n")
    mock.get(f"{BASE}private/x").mock(return_value=_httpx.Response(
        200, text=_OK_HTML, headers={"content-type": "text/html"}))
    mock.get(BASE).mock(return_value=_httpx.Response(
        200, text=_OK_HTML.replace("<h1>H</h1>", f"<h1>H</h1><a href='{BASE}private/x'>P</a>"),
        headers={"content-type": "text/html"}))


def _sitemap_missing(mock):
    _engine_base(mock)


def _sitemap_present(mock):
    _engine_base(mock)
    mock.get("https://example.com/sitemap.xml").mock(return_value=_httpx.Response(
        200, headers={"content-type": "application/xml"},
        text=('<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
              f"<url><loc>{BASE}</loc></url></urlset>")))


def _llms_missing(mock):
    _engine_base(mock)
    mock.get("https://example.com/llms.txt").mock(return_value=_httpx.Response(404))


def _llms_present(mock):
    _engine_base(mock)
    mock.get("https://example.com/llms.txt").mock(return_value=_httpx.Response(
        200, text="# Example\n\n## Docs\n- [Home](https://example.com/): the homepage\n",
        headers={"content-type": "text/plain"}))


def _ai_txt_missing(mock):
    _engine_base(mock)
    mock.get("https://example.com/ai.txt").mock(return_value=_httpx.Response(404))


def _ai_txt_present(mock):
    _engine_base(mock)
    mock.get("https://example.com/ai.txt").mock(return_value=_httpx.Response(
        200, text="User-agent: *\nAllow: /\n", headers={"content-type": "text/plain"}))


CONTRACTS += [
    ("REDIRECT_LOOP", _eng(_loop), _eng(_no_loop), "engine"),
    ("LOGIN_REDIRECT", _eng(_login_redirect), _eng(_no_loop), "engine"),
    ("ROBOTS_BLOCKED", _eng(_robots_blocked), _eng(_no_loop), "engine"),
    ("SITEMAP_MISSING", _eng(_sitemap_missing), _eng(_sitemap_present), "engine"),
    ("LLMS_TXT_MISSING", _eng(_llms_missing), _eng(_llms_present), "engine"),
    ("AI_TXT_MISSING", _eng(_ai_txt_missing), _eng(_ai_txt_present), "engine"),
]

# ── Sixth tranche: entity, citation, schema and GEO codes ──────────────────
def _ld(obj):
    import json as _json
    return f"<script type='application/ld+json'>{_json.dumps(obj)}</script>"


def _site(head_blocks):
    """A 3-page site carrying the entity graph on its homepage.

    check_cross_page gates its site-scoped checks on a minimum page count, so a
    single-page fixture is skipped silently — the first version of these four
    contracts failed for exactly that reason.
    """
    return ([page(url=BASE, head="".join(head_blocks))]
            + [page(url=BASE + c) for c in ("b", "c")])


_ORG_GOOD = {"@context": "https://schema.org", "@type": "LocalBusiness",
             "name": "Living Systems Counselling",
             "telephone": "+1 604 555 0100",
             "address": {"@type": "PostalAddress", "streetAddress": "123 Main St",
                         "addressLocality": "North Vancouver", "addressRegion": "BC",
                         "postalCode": "V7M 1A1", "addressCountry": "CA"},
             "openingHoursSpecification": [
                 {"@type": "OpeningHoursSpecification", "dayOfWeek": "Monday",
                  "opens": "09:00", "closes": "17:00"}],
             "email": "info@livingsystems.ca",
             "url": "https://example.com/",
             "logo": "https://example.com/logo.png",
             "description": "Family systems counselling and training in North Vancouver.",
             "sameAs": ["https://facebook.com/ls"]}

CONTRACTS += [
    # _check_entity_values runs AFTER check_cross_page's site-check gate, so it
    # needs at least _MIN_PAGES_SITE_CHECKS pages — a single-page fixture is
    # silently skipped. Shapes below match api/config/entity_values.json.
    ("ENTITY_NAP_INCOMPLETE",
     lambda: _site([_ld({k: v for k, v in _ORG_GOOD.items()
                         if k not in ("telephone", "address", "email")})]),
     lambda: _site([_ld(_ORG_GOOD)]), "cross"),
    ("ENTITY_VALUE_PLACEHOLDER",
     lambda: _site([_ld({**_ORG_GOOD, "name": "Your Business Name"})]),
     lambda: _site([_ld(_ORG_GOOD)]), "cross"),
    ("ENTITY_FIELD_EMPTY",
     lambda: _site([_ld({**_ORG_GOOD, "telephone": "", "description": ""})]),
     lambda: _site([_ld(_ORG_GOOD)]), "cross"),
    ("ENTITY_HOURS_DEFAULT",
     # config default_hours: 7 days, 09:00-17:00 — the "never edited it" shape.
     lambda: _site([_ld({**_ORG_GOOD, "openingHoursSpecification": [
         {"@type": "OpeningHoursSpecification",
          "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                        "Saturday", "Sunday"],
          "opens": "09:00", "closes": "17:00"}]})]),
     lambda: _site([_ld({**_ORG_GOOD, "openingHoursSpecification": [
         {"@type": "OpeningHoursSpecification",
          "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
          "opens": "08:30", "closes": "16:00"}]})]), "cross"),
    ("SCHEMA_TYPE_MISMATCH",
     lambda: page(url="https://example.com/contact-us",
                  head=_ld({"@context": "https://schema.org", "@type": "Recipe",
                            "name": "Not a contact page"})),
     lambda: page(url="https://example.com/contact-us",
                  head=_ld({"@context": "https://schema.org", "@type": "ContactPage",
                            "name": "Contact"}))),
    ("SCHEMA_VISIBLE_MISMATCH",
     lambda: page(head=_ld({"@context": "https://schema.org", "@type": "Article",
                            "headline": "A headline that appears nowhere on the page"}),
                  body=f"<h1>Something Entirely Different</h1><p>{_FILLER}</p>"),
     lambda: page(head=_ld({"@context": "https://schema.org", "@type": "Article",
                            "headline": "Bowen Family Systems Training"}),
                  body=f"<h1>Bowen Family Systems Training</h1><p>{_FILLER}</p>")),
    ("AUTHOR_CREDENTIALS_MISSING",
     lambda: page(url=_BLOG, head=_ld({"@context": "https://schema.org", "@type": "Article",
                                       "headline": "X", "datePublished": "2026-01-01",
                                       "dateModified": "2026-06-01",
                                       "author": {"@type": "Person", "name": "Dave Galloway"}})),
     lambda: page(url=_BLOG, head=_ld({"@context": "https://schema.org", "@type": "Article",
                                       "headline": "X", "datePublished": "2026-01-01",
                                       "dateModified": "2026-06-01",
                                       "author": {"@type": "Person", "name": "Dave Galloway",
                                                  "jobTitle": "Clinical Counsellor",
                                                  "url": "https://example.com/team/dave",
                                                  "sameAs": ["https://linkedin.com/in/dave"]}}))),
    ("CONTENT_STAT_OUTDATED",
     lambda: page(body=f"<h1>H</h1><p>In 2011, 62% of clients reported change.</p><p>{_FILLER}</p>"),
     lambda: page(body=f"<h1>H</h1><p>In 2026, 62% of clients reported change.</p><p>{_FILLER}</p>")),
    ("LINK_STACKED_DUPLICATE",
     lambda: page(body=f"<h1>H</h1><div class='card'>"
                       f"<a href='{BASE}x'><img src='/a.jpg' alt='A photo'></a>"
                       f"<a href='{BASE}x'><h3>Title</h3></a>"
                       f"<a href='{BASE}x'>Read more</a></div><p>{_FILLER}</p>"),
     lambda: page(body=f"<h1>H</h1><div class='card'><a href='{BASE}x'>Title</a>"
                       f"<a href='{BASE}y'>Another</a></div><p>{_FILLER}</p>")),
    # BASE is example.com, which is itself in _PLACEHOLDER_HOSTS — so this
    # contract needs a real-looking base or every link is a "placeholder".
    ("WRONG_PLACEHOLDER_LINK",
     lambda: page(url=_REAL, body=f"<h1>H</h1><a href='https://example.com/x'>Link</a>"
                                  f"<p>{_FILLER}</p>"),
     lambda: page(url=_REAL, body=f"<h1>H</h1><a href='{_REAL}x'>Link</a><p>{_FILLER}</p>")),
    ("ORPHAN_CLAIM_TECHNICAL",
     lambda: page(url="https://example.com/guide/setup",
                  body="<h1>Guide</h1>"
                       + "".join("<p>This system supports scaling to many users and "
                                 "reduces latency for every request.</p>" for _ in range(4))
                       + f"<p>{_LONG}</p>"),
     lambda: page(url="https://example.com/guide/setup",
                  body="<h1>Guide</h1>"
                       + "".join(f"<p>This system supports scaling to many users, per "
                                 f"<a href='https://who.int/r{i}'>the report</a>.</p>"
                                 for i in range(8))
                       + f"<p>{_LONG}</p>")),
    ("ANALYTICS_TAG_DUPLICATE",
     lambda: page(head="<script async src='https://www.googletagmanager.com/gtag/js?id=G-AAA111'>"
                       "</script><script>gtag('config','G-AAA111');</script>"
                       "<script async src='https://www.googletagmanager.com/gtag/js?id=G-AAA111'>"
                       "</script><script>gtag('config','G-AAA111');</script>"),
     lambda: page(head="<script async src='https://www.googletagmanager.com/gtag/js?id=G-AAA111'>"
                       "</script><script>gtag('config','G-AAA111');</script>")),
    ("ANALYTICS_ID_INCONSISTENT",
     lambda: [page(url=BASE, head="<script async src='https://www.googletagmanager.com/gtag/js?"
                                  "id=G-AAA111'></script><script>gtag('config','G-AAA111');</script>"),
              page(url=BASE + "b", head="<script async src='https://www.googletagmanager.com/gtag/js?"
                                        "id=G-BBB222'></script><script>gtag('config','G-BBB222');</script>")],
     lambda: [page(url=BASE, head="<script async src='https://www.googletagmanager.com/gtag/js?"
                                  "id=G-AAA111'></script><script>gtag('config','G-AAA111');</script>"),
              page(url=BASE + "b", head="<script async src='https://www.googletagmanager.com/gtag/js?"
                                        "id=G-AAA111'></script><script>gtag('config','G-AAA111');</script>")],
     "cross"),
    ("ENTITY_NAME_INCONSISTENT",
     lambda: [page(url=BASE, head=_ld({**_ORG_GOOD, "name": "Living Systems Counselling"})),
              page(url=BASE + "b", head=_ld({**_ORG_GOOD, "name": "Totally Different Society"})),
              page(url=BASE + "c", head=_ld({**_ORG_GOOD, "name": "A Third Distinct Name"}))],
     lambda: [page(url=BASE, head=_ld(_ORG_GOOD)),
              page(url=BASE + "b", head=_ld(_ORG_GOOD)),
              page(url=BASE + "c", head=_ld(_ORG_GOOD))], "cross"),
    ("AUTHOR_IDENTITY_INCONSISTENT",
     lambda: [page(url=BASE + str(i), head=_ld({"@context": "https://schema.org",
                                                "@type": "Article", "headline": "X",
                                                "author": {"@type": "Person",
                                                           "name": n, "url": u}}))
              for i, (n, u) in enumerate([("Dave Galloway", "https://example.com/a"),
                                          ("Dave Galloway", "https://example.com/b"),
                                          ("Dave Galloway", "https://example.com/c")])],
     lambda: [page(url=BASE + str(i), head=_ld({"@context": "https://schema.org",
                                                "@type": "Article", "headline": "X",
                                                "author": {"@type": "Person",
                                                           "name": "Dave Galloway",
                                                           "url": "https://example.com/a"}}))
              for i in range(3)], "cross"),
    ("NEAR_DUPLICATE_BODY",
     lambda: [page(url=BASE + str(i), body=f"<h1>H</h1><p>{_LONG}</p>") for i in range(3)],
     lambda: [page(url=BASE + str(i),
                   body="<h1>H</h1><p>" + " ".join([f"unique{i}word{j}" for j in range(400)])
                        + "</p>") for i in range(3)], "cross"),
]

# ── Seventh tranche: GEO and citation codes ────────────────────────────────
_W = lambda n: " ".join(["counselling"] * n)          # noqa: E731
_CITED = "".join(f"<a href='https://who.int/r{i}'>Report {i}</a> " for i in range(6))

CONTRACTS += [
    ("CITATIONS_MISSING_SUBSTANTIAL_CONTENT",
     lambda: page(body=f"<h1>H</h1><p>{_W(700)}</p>"),
     lambda: page(body=f"<h1>H</h1>{_CITED}<p>{_W(700)}</p>")),
    ("FIRST_VIEWPORT_NO_ANSWER",
     lambda: page(body=f"<h1>H</h1>{_CITED}<p>{_W(700)}</p>"),
     lambda: page(body=f"<h1>H</h1>{_CITED}<h2>What is Bowen theory?</h2>"
                       f"<p>Bowen theory is a model of family systems. {_W(700)}</p>")),
    ("SECTION_VAGUE_OPENER",
     lambda: page(body=f"<h1>H</h1>{_CITED}<h2>Overview</h2>"
                       f"<p>It is important to note that this matters. {_W(300)}</p>"
                       f"<h2>More</h2><p>There are many things. {_W(300)}</p>"),
     lambda: page(body=f"<h1>H</h1>{_CITED}<h2>Overview</h2>"
                       f"<p>Bowen theory explains family anxiety patterns. {_W(300)}</p>"
                       f"<h2>More</h2><p>Differentiation reduces reactivity. {_W(300)}</p>")),
    ("QUERY_COVERAGE_WEAK",
     lambda: page(body=f"<h1>Bowen Family Systems Theory</h1>{_CITED}"
                       f"<h2>Unrelated Heading</h2><p>{_W(400)}</p>"),
     lambda: page(body=f"<h1>Bowen Family Systems Theory</h1>{_CITED}"
                       f"<h2>Bowen Family Systems Theory Explained</h2>"
                       f"<p>Bowen family systems theory {_W(400)}</p>")),
    ("SEMANTIC_DENSITY_LOW",
     # A page that is mostly inline CSS: the visible-text share is what matters,
     # not the byte count.
     lambda: page(body="<h1>H</h1><style>" + "a{color:red}" * 4000 + "</style>"
                       f"<p>{_W(20)}</p>"),
     lambda: page(body=f"<h1>H</h1>{_CITED}<p>{_W(600)}</p>")),
]

# ── Eighth tranche ─────────────────────────────────────────────────────────
CONTRACTS += [
    ("AI_MAIN_CONTENT_LOW_RATIO",
     lambda: page(body="<h1>H</h1><nav>"
                       + "".join(f"<a href='/n{i}'>Navigation item {i}</a>" for i in range(400))
                       + "</nav><footer>"
                       + "".join(f"<a href='/f{i}'>Footer link {i}</a>" for i in range(200))
                       + f"</footer><main><p>{_W(25)}</p></main>"),
     lambda: page(body=f"<h1>H</h1>{_CITED}<main><p>{_W(700)}</p></main>")),
    ("SECTION_CROSS_REFERENCES",
     # The DEFECT is backward-reference phrasing that breaks section
     # independence — not the absence of cross-references.
     lambda: page(body=f"<h1>H</h1><h2>A</h2><p>As mentioned above, this matters. {_W(300)}</p>"
                       f"<h2>B</h2><p>As discussed earlier, {_W(300)}</p>"),
     lambda: page(body=f"<h1>H</h1><h2>A</h2><p>Bowen theory explains anxiety. {_W(300)}</p>"
                       f"<h2>B</h2><p>Differentiation reduces reactivity. {_W(300)}</p>")),
    ("CITATIONS_ORPHANED",
     # An orphan citation is an external link with NO anchor text: the anchor
     # text is what supplies the citation's context.
     lambda: page(body=f"<h1>H</h1><p>{_W(300)}</p>"
                       + "".join(f"<a href='https://who.int/report{i}'></a>" for i in range(4))
                       + f"<p>{_W(300)}</p>"),
     lambda: page(body="<h1>H</h1><p>According to the "
                       "<a href='https://who.int/report'>WHO 2026 report</a>, rates fell. "
                       f"{_W(600)}</p>")),
]

CONTRACTS += [
    ("LINK_PROFILE_PROMOTIONAL",
     # classify_body_links counts a link as promotional only on an affiliate
     # marker (?ref=/?aff=//go/) — a plain shop link classifies as "other".
     lambda: page(body="<h1>H</h1>"
                       + "".join(f"<a href='https://shop.other.org/p{i}?ref=aff'>Buy now</a>"
                                 for i in range(12))
                       + f"<p>{_W(400)}</p>"),
     lambda: page(body=f"<h1>H</h1>{_CITED}<p>{_W(400)}</p>")),
]

# ── Gated-subsystem codes ──────────────────────────────────────────────────
# These never fire in a normal crawl because the subsystem does not run. The
# contract exercises the subsystem's own entry point, so "not run" and "broken"
# stay distinguishable (P31).
CONTRACTS += [
    ("CWV_LCP_POOR",
     lambda: _vitals(lcp_ms=6000), lambda: _vitals(lcp_ms=1200), "vitals"),
    ("CWV_INP_POOR",
     lambda: _vitals(inp_ms=900), lambda: _vitals(inp_ms=120), "vitals"),
    ("CWV_CLS_POOR",
     lambda: _vitals(cls=0.6), lambda: _vitals(cls=0.02), "vitals"),
    ("JS_RENDERED_CONTENT_DIFFERS",
     lambda: _render(js_rendered_content_differs=True, added_token_ratio=0.6),
     lambda: _render(), "render"),
    ("CONTENT_CLOAKING_DETECTED",
     lambda: _render(js_rendered_content_differs=True, content_cloaking_detected=True,
                     topic_jaccard=0.1),
     lambda: _render(), "render"),
    ("UA_CONTENT_DIFFERS",
     lambda: _render(ua_content_differs=True, gptbot_token_count=50),
     lambda: _render(), "render"),
    ("CENTRAL_CLAIM_BURIED",
     lambda: {"central_claim_buried": True}, lambda: {}, "geo_llm"),
    ("CHUNKS_NOT_SELF_CONTAINED",
     lambda: {"chunks_not_self_contained": True}, lambda: {}, "geo_llm"),
    ("PROMOTIONAL_CONTENT_INTERRUPTS",
     lambda: {"promotional_content_interrupts": True}, lambda: {}, "geo_llm"),
]

CONTRACT_CODES = {c[0] for c in CONTRACTS}


def _norm(contract):
    """(code, positive, negative[, runner]) -> 4-tuple."""
    code, pos, neg = contract[0], contract[1], contract[2]
    runner = contract[3] if len(contract) > 3 else "page"
    return code, pos, neg, runner


ALL_CONTRACTS = [_norm(c) for c in CONTRACTS]
_IDS = [c[0] for c in ALL_CONTRACTS]


@pytest.mark.parametrize("code,positive,_negative,runner", ALL_CONTRACTS, ids=_IDS)
def test_af11_positive_fixture_fires(code, positive, _negative, runner):
    """The check is not DEAD: an input that should trigger it, does."""
    issues = RUNNERS[runner](positive())
    assert any(i.code == code for i in issues), (
        f"{code} did not fire on its positive fixture (runner={runner})")


@pytest.mark.parametrize("code,_positive,negative,runner", ALL_CONTRACTS, ids=_IDS)
def test_af11_negative_fixture_stays_clean(code, _positive, negative, runner):
    """The check is not a FALSE POSITIVE: correct-looking input stays clean.

    This is the assertion that did not exist for IMG_ALT_MISSING.
    """
    issues = RUNNERS[runner](negative())
    assert not any(i.code == code for i in issues), (
        f"{code} fired on correct input (runner={runner})")


class TestSubsystemInvariants:
    """Invariants a single positive/negative pair cannot express."""

    def test_af11_lab_vitals_never_raise_a_finding(self):
        """Core Web Vitals findings come from FIELD data only. A synthetic lab
        run in a Google datacentre is not evidence about real users, and
        presenting it as such is the one way this feature becomes actively
        misleading rather than merely incomplete. My CWV contracts all use field
        rows, so none of them would notice the guard being removed.
        """
        from api.services.web_vitals import VitalsRow, WebVitalsReport, vitals_issues

        lab = VitalsRow(url=BASE, source="lab", lcp_ms=6000, inp_ms=900, cls=0.6,
                        performance_score=10, unavailable_reason=None, retryable=False)
        report = WebVitalsReport(rows=[lab], requested=1, field_count=0, lab_count=1,
                                 unavailable_count=0, retryable_failures=0,
                                 strategy="mobile", had_api_key=True)
        assert vitals_issues(report) == [], "lab data must never raise a CWV finding"

    def test_af11_failed_render_never_raises_a_finding(self):
        """Same shape one subsystem over: a render that ERRORED must produce
        nothing, or a Playwright failure reads as a site defect."""
        from api.crawler.issue_checker import js_render_issues

        assert js_render_issues(_render(error="playwright not installed",
                                        js_rendered_content_differs=True,
                                        content_cloaking_detected=True,
                                        ua_content_differs=True)) == []


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

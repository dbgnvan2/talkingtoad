"""HTML-only checks must not run on a response that is not HTML.

Spec:  docs/functional-specification.md#418-non-html-responses-are-audited-as-assets-on-every-path-2026-09-08
Tests: this file

Reported from a real report: "The code reported six pages as blank, but they're
PDFs, and they are not blank at all."

Job 52a5aa00 (livingsystems.ca) carried six CONTENT_NOT_EXTRACTABLE_NO_TEXT
findings — "Page has no visible text" — on four policy PDFs, one URL that 301s
to a PDF, and a .kml file. The crawler never decodes a PDF body into words, so
word_count is NULL and assess_extractability() reads that as "no text content".
Alongside them came TITLE_MISSING, H1_MISSING, META_DESC_MISSING, LANG_MISSING,
MISSING_VIEWPORT_META, CANONICAL_SELF_MISSING, SOCIAL_PREVIEW_METADATA_MISSING,
ANALYTICS_TAG_MISSING, JSON_LD_MISSING and PAGE_SIZE_LARGE: 59 false findings of
63 on those six URLs.

The crawl engine had always gated its own branch on the content type. The
router's _fetch_and_check_page did not, so rescan / "Re-check all pages" /
single-page scan / page-details ran the whole HTML suite over a PDF, and one
press of the button rewrote all six (P16 — a capability, here a guard, present
at one front end only).

Two more findings at the same seam, both proved from the stored data:

* the rescan path never ran check_url_structure, and URL_UPPERCASE is not
  needs_full_crawl, so the re-check deleted four real URL_UPPERCASE findings and
  one INTERNAL_REDIRECT_301 and wrote them to the fixed-issues ledger as
  RESOLVED at 03:50 without evaluating them (P1/P6). The URLs still carry
  capitals;
* DOCUMENT_PROPS_MISSING lives only inside check_page, which the crawl never
  called for a PDF — 0 occurrences on crawl-only job 7b28539b, 4 only after the
  re-check (P16). AF5's test asserted it by calling check_page directly, one
  layer below the crawl that never called it.
"""
from __future__ import annotations

import io

import httpx
import pytest
import respx

from api.crawler.engine import CrawlSettings, run_crawl
from api.crawler.fetcher import FetchResult
from api.crawler.issue_checker import check_page
from api.crawler.parser import parse_page
from api.routers.crawl import _fetch_and_check_page
from api.services.sqlite_store import SQLiteJobStore

BASE = "https://e.test/"
PDF_URL = BASE + "wp-content/uploads/2026/05/Dispute-Resolution-Policy.pdf"
KML_URL = BASE + "locations.kml"

# Every code the six non-HTML URLs were charged in job 52a5aa00 that describes
# something only an HTML document can have. DOCUMENT_PROPS_MISSING is
# deliberately absent: it was the one legitimate finding of the 63.
HTML_ONLY_CODES = {
    "CONTENT_NOT_EXTRACTABLE_NO_TEXT",
    "TITLE_MISSING",
    "H1_MISSING",
    "META_DESC_MISSING",
    "LANG_MISSING",
    "MISSING_VIEWPORT_META",
    "CANONICAL_SELF_MISSING",
    "SOCIAL_PREVIEW_METADATA_MISSING",
    "ANALYTICS_TAG_MISSING",
    "JSON_LD_MISSING",
    "PAGE_SIZE_LARGE",
}

PDF_TEXT = "Dispute Resolution Policy for Student Complaints"


def _pdf_bytes(text: str = PDF_TEXT,
               title: str | None = "Microsoft Word - Dispute draft 3.docx",
               subject: str | None = None) -> bytes:
    """A real PDF carrying real, extractable text.

    Hand-built rather than pypdf-written because pypdf's writer cannot lay down
    a text stream, and a blank page would not reproduce the report: the point
    of the bug is that these documents are full of text.
    ``tests/test_non_html_asset_checks.py::test_the_fixture_is_not_actually_blank``
    proves the text is really there before anything else asserts on it.
    """
    stream = f"BT /F1 14 Tf 40 700 Td ({text}) Tj ET".encode()
    info = b""
    if title is not None:
        info += b"/Title (" + title.encode() + b") "
    if subject is not None:
        info += b"/Subject (" + subject.encode() + b") "
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< " + info + b"/Producer (TalkingToad test) >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objs) + 1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R /Info 6 0 R >>\n"
              f"startxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


def _parsed(url: str, content: bytes, content_type: str):
    return parse_page(
        FetchResult(url=url, final_url=url, status_code=200, headers={},
                    html=None, content=content, content_type=content_type),
        BASE)


def test_the_fixture_is_not_actually_blank():
    """The premise of every other test here: this PDF really does carry text."""
    pypdf = pytest.importorskip("pypdf")
    reader = pypdf.PdfReader(io.BytesIO(_pdf_bytes()))
    assert PDF_TEXT in reader.pages[0].extract_text()


# ── NH1 / NH2 — the reported bug, at the checker ───────────────────────────

def test_nh1_pdf_gets_no_html_only_codes():
    codes = {i.code for i in check_page(_parsed(PDF_URL, _pdf_bytes(), "application/pdf"))}
    leaked = codes & HTML_ONLY_CODES
    assert not leaked, (
        f"HTML-only checks ran on a PDF and charged {sorted(leaked)} — "
        f"a PDF has no title tag, h1, lang attribute, viewport, canonical, "
        f"OG tags, analytics tag or JSON-LD to be missing")


def test_nh2_a_pdf_is_never_reported_as_having_no_text():
    """The report, verbatim: six PDFs full of text, reported as blank."""
    codes = {i.code for i in check_page(_parsed(PDF_URL, _pdf_bytes(), "application/pdf"))}
    assert "CONTENT_NOT_EXTRACTABLE_NO_TEXT" not in codes, (
        "a PDF was reported as having no visible text. The crawler does not "
        "read PDF bodies at all — word_count is None — so this finding was "
        "never a measurement of the document")


def test_nh2b_a_kml_file_is_not_audited_as_a_page():
    """The sixth of the six: /locations.kml, same treatment."""
    page = _parsed(KML_URL, b"<kml><Placemark/></kml>",
                   "application/vnd.google-earth.kml+xml")
    assert not ({i.code for i in check_page(page)} & HTML_ONLY_CODES)


# ── NH3 — the PDF check that does apply still applies ──────────────────────

def test_nh3_document_props_missing_still_fires_for_a_pdf_without_a_subject():
    codes = {i.code for i in check_page(_parsed(PDF_URL, _pdf_bytes(), "application/pdf"))}
    assert "DOCUMENT_PROPS_MISSING" in codes, (
        "the gate removed the one check that does apply to a PDF")


def test_nh3b_a_well_described_pdf_is_not_flagged():
    """Adversarial: the surviving check must still discriminate."""
    good = _pdf_bytes(title="Dispute Resolution Policy",
                      subject="How a student raises a complaint")
    codes = {i.code for i in check_page(_parsed(PDF_URL, good, "application/pdf"))}
    assert "DOCUMENT_PROPS_MISSING" not in codes


def test_nh3c_document_props_fires_for_a_pdf_url_with_no_pdf_extension():
    """livingsystems' /ls-student-statement-of-rights-… 301s to a PDF and has no
    extension, so the old `url.endswith(".pdf")` test skipped it: 4 findings for
    5 PDFs. The check now keys on the parsed PDF metadata."""
    page = _parsed(BASE + "ls-student-statement-of-rights", _pdf_bytes(),
                   "application/pdf")
    assert "DOCUMENT_PROPS_MISSING" in {i.code for i in check_page(page)}


# ── NH4 / NH5 / NH10 — the gate must not touch HTML ────────────────────────

HTML = ("<!DOCTYPE html><html lang='en'><head><title>A Page With A Real Title "
        "Here</title></head><body><h1>Heading</h1><p>"
        + " ".join(["word"] * 120) + "</p></body></html>")


def _html_page(content_type: str | None):
    return parse_page(
        FetchResult(url=BASE + "p/", final_url=BASE + "p/", status_code=200,
                    headers={}, html=HTML, content=None,
                    content_type=content_type or ""),
        BASE)


def test_nh4_html_page_findings_unchanged():
    """An HTML response is checked identically whether or not the content type
    was recorded — the gate must be inert on every HTML path."""
    with_ct = {i.code for i in check_page(_html_page("text/html"))}
    without_ct = {i.code for i in check_page(_html_page(None))}
    assert with_ct == without_ct
    assert with_ct, "no checks ran on an HTML page at all"


def test_nh5_unknown_content_type_still_runs_html_checks():
    """A hand-built ParsedPage (no content type, no fetch) keeps the full suite,
    which is how most of this repo's tests call check_page."""
    page = _html_page(None)
    page.title = None
    assert "TITLE_MISSING" in {i.code for i in check_page(page)}


def test_nh10_empty_html_page_still_flagged_as_having_no_text():
    """Adversarial: the gate keys on the CONTENT TYPE, not on emptiness.
    An HTML page that genuinely has no text is a real finding and must survive.
    """
    empty = ("<!DOCTYPE html><html lang='en'><head><title>Gallery Page Title "
             "Goes Here</title></head><body>"
             "<img src='/a.jpg' alt='a'><img src='/b.jpg' alt='b'></body></html>")
    page = parse_page(
        FetchResult(url=BASE + "gallery/", final_url=BASE + "gallery/",
                    status_code=200, headers={}, html=empty, content=None,
                    content_type="text/html"),
        BASE)
    assert "CONTENT_NOT_EXTRACTABLE_NO_TEXT" in {i.code for i in check_page(page)}


def test_nh5b_a_typeless_binary_is_not_audited_as_a_page():
    """A server that sends a body with no Content-Type at all: unknown type AND
    no HTML parsed. Treating that as HTML would report a font file as a page
    with a missing title — the same bug through the back door."""
    page = _parsed(BASE + "f.woff2", b"wOF2\x00", "")
    assert not ({i.code for i in check_page(page)} & HTML_ONLY_CODES)


# ── NH6 / NH9 — the surface the operator actually presses ──────────────────

@pytest.fixture
async def store(tmp_path):
    s = SQLiteJobStore(db_path=str(tmp_path / "t.db"))
    await s.init()
    try:
        yield s
    finally:
        await s.close()


async def _rescan(store, url, body, content_type):
    with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
        rx.get(url).mock(return_value=httpx.Response(
            200, content=body, headers={"content-type": content_type}))
        rx.route().mock(return_value=httpx.Response(200, text="ok"))
        return await _fetch_and_check_page(
            url=url, job_id="j", store=store, base_url=BASE)


async def test_nh6_rescan_path_on_a_pdf_emits_no_html_only_codes(store):
    """P16: asserted at the ROUTER boundary. check_page being correct says
    nothing about the path "Re-check all pages" takes to reach it — that path
    is what rewrote six URLs in job 52a5aa00."""
    res = await _rescan(store, PDF_URL, _pdf_bytes(), "application/pdf")
    codes = {i.issue_code for i in res.issues}
    leaked = codes & HTML_ONLY_CODES
    assert not leaked, (
        f"the rescan/re-check path charged {sorted(leaked)} on a PDF")
    assert "DOCUMENT_PROPS_MISSING" in codes, (
        "the rescan path lost the one finding that does apply to a PDF")


async def test_nh9_rescan_runs_url_structure_checks(store):
    """The re-check deleted URL_UPPERCASE from four PDFs and recorded it as
    fixed without running it. It must be evaluated on this path."""
    res = await _rescan(store, PDF_URL, _pdf_bytes(), "application/pdf")
    assert "URL_UPPERCASE" in {i.issue_code for i in res.issues}, (
        "a rescan that does not run this check will resolve it silently")


async def test_nh9b_rescan_runs_url_structure_checks_on_html_too(store):
    res = await _rescan(store, BASE + "Some/Mixed_Case/", HTML.encode(), "text/html")
    codes = {i.issue_code for i in res.issues}
    assert {"URL_UPPERCASE", "URL_HAS_UNDERSCORES"} <= codes


# ── NH11 — asset SIZE limits, on every path (QA gate NB-2, 2026-09-08) ─────
#
# The first half of this fix gave the router path the URL-structure checks and
# left check_asset behind, so PDF_TOO_LARGE and IMG_OVERSIZED stayed
# crawl-only — the same path disagreement, one check over. The agreement test
# below could not see it because its fixture PDF is 400 bytes.

_OVERSIZE = 11 * 1024 * 1024  # over _PDF_SIZE_LIMIT (10 MB)


async def _rescan_with_length(store, url, body, content_type, content_length):
    """A HEAD-sized response: check_asset reads content-length, not the body,
    so an 11 MB PDF is declared rather than transferred."""
    with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
        rx.get(url).mock(return_value=httpx.Response(
            200, content=body,
            headers={"content-type": content_type,
                     "content-length": str(content_length)}))
        rx.route().mock(return_value=httpx.Response(200, text="ok"))
        return await _fetch_and_check_page(
            url=url, job_id="j", store=store, base_url=BASE)


async def test_nh11_rescan_reports_an_oversized_pdf(store):
    res = await _rescan_with_length(store, PDF_URL, _pdf_bytes(),
                                    "application/pdf", _OVERSIZE)
    assert "PDF_TOO_LARGE" in {i.issue_code for i in res.issues}, (
        "a re-check of an 11 MB PDF dropped the size finding the crawl "
        "reports — the same class as the URL_UPPERCASE loss")


async def test_nh11b_rescan_reports_an_oversized_image(store):
    res = await _rescan_with_length(store, BASE + "hero.jpg", b"\xff\xd8\xff",
                                    "image/jpeg", 900 * 1024)
    assert "IMG_OVERSIZED" in {i.issue_code for i in res.issues}


async def test_nh11c_the_jobs_own_image_limit_is_used(store):
    """Not the module default: a job configured to 1 MB must not have its
    900 KB image flagged by a path that assumed 200 KB."""
    with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
        rx.get(BASE + "hero.jpg").mock(return_value=httpx.Response(
            200, content=b"\xff\xd8\xff",
            headers={"content-type": "image/jpeg",
                     "content-length": str(900 * 1024)}))
        rx.route().mock(return_value=httpx.Response(200, text="ok"))
        res = await _fetch_and_check_page(
            url=BASE + "hero.jpg", job_id="j", store=store, base_url=BASE,
            img_size_limit_kb=1024)
    assert "IMG_OVERSIZED" not in {i.issue_code for i in res.issues}


async def test_nh11d_size_checks_are_inert_on_html(store):
    """Adversarial: check_asset now runs on every rescan, HTML included. An
    HTML page declaring 11 MB is PAGE_SIZE_LARGE's business, not PDF_TOO_LARGE's.
    """
    res = await _rescan_with_length(store, BASE + "big/", HTML.encode(),
                                    "text/html", _OVERSIZE)
    codes = {i.issue_code for i in res.issues}
    assert not (codes & {"PDF_TOO_LARGE", "IMG_OVERSIZED"})


# ── NH12 — the job's limit reaches the check, from each endpoint ───────────
#
# nh11c pins the PARAMETER: pass 1024, get 1024's behaviour. It says nothing
# about whether the three call sites pass the job's value at all — delete one
# of those lines and every nh11 test stays green. This intercepts the boundary
# function and reads the kwarg, per the repo's rule that a control which is not
# passed is decoration.

async def _job_with_image_limit(store, limit_kb: int):
    from api.models.job import CrawlJob, CrawlSettings
    from api.models.page import CrawledPage
    job = CrawlJob(target_url=BASE, status="complete",
                   settings=CrawlSettings(img_size_limit_kb=limit_kb))
    await store.create_job(job)
    await store.save_pages([CrawledPage(job_id=job.job_id, url=PDF_URL,
                                        status_code=200)])
    return job


@pytest.fixture
def captured_asset_limit(monkeypatch):
    """Record img_size_limit_kb as it arrives at check_asset, then restore."""
    from api.routers import crawl as crawl_router
    seen: list[int] = []
    real = crawl_router.check_asset

    def spy(result, *, img_size_limit_kb, **kw):
        seen.append(img_size_limit_kb)
        return real(result, img_size_limit_kb=img_size_limit_kb, **kw)

    monkeypatch.setattr(crawl_router, "check_asset", spy)
    return seen


async def test_nh12_rescan_url_passes_the_jobs_image_limit(store, captured_asset_limit):
    from api.routers.crawl import rescan_url
    job = await _job_with_image_limit(store, 512)
    with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
        rx.get(PDF_URL).mock(return_value=httpx.Response(
            200, content=_pdf_bytes(), headers={"content-type": "application/pdf"}))
        rx.route().mock(return_value=httpx.Response(200, text="ok"))
        await rescan_url(job.job_id, url=PDF_URL, store=store)
    assert captured_asset_limit == [512], (
        f"the endpoint did not hand the job's own limit to the size check: "
        f"{captured_asset_limit}")


async def test_nh12b_page_details_passes_the_jobs_image_limit(store, captured_asset_limit):
    from api.routers.crawl import get_page_details
    job = await _job_with_image_limit(store, 768)
    with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
        rx.get(PDF_URL).mock(return_value=httpx.Response(
            200, content=_pdf_bytes(), headers={"content-type": "application/pdf"}))
        rx.route().mock(return_value=httpx.Response(200, text="ok"))
        await get_page_details.__wrapped__(
            request=None, job_id=job.job_id, url=PDF_URL, code=None, store=store)
    assert captured_asset_limit == [768], captured_asset_limit


async def test_nh12c_single_page_scan_passes_the_jobs_image_limit(store, captured_asset_limit):
    from api.models.job import CrawlSettings
    from api.routers.crawl import _run_single_page_scan
    with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
        rx.get(PDF_URL).mock(return_value=httpx.Response(
            200, content=_pdf_bytes(), headers={"content-type": "application/pdf"}))
        rx.route().mock(return_value=httpx.Response(200, text="ok"))
        await _run_single_page_scan(
            url=PDF_URL, authenticated=False, store=store,
            reuse_settings=CrawlSettings(single_page=True, img_size_limit_kb=384))
    assert captured_asset_limit == [384], captured_asset_limit


# ── NH7 / NH8 — the crawl path ─────────────────────────────────────────────

INDEX = (f"<!DOCTYPE html><html lang='en'><head><title>Home Page Of The Test "
         f"Site</title></head><body><h1>Home</h1>"
         f"<a href='{PDF_URL}'>Policy</a><p>" + " ".join(["word"] * 120) +
         "</p></body></html>")


async def _crawl_with_pdf(pdf: bytes, content_length: int | None = None):
    pdf_headers = {"content-type": "application/pdf"}
    if content_length is not None:
        pdf_headers["content-length"] = str(content_length)
    with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
        rx.get(f"{BASE}robots.txt").mock(return_value=httpx.Response(
            200, text="User-agent: *\nDisallow:\n"))
        rx.get(f"{BASE}sitemap.xml").mock(return_value=httpx.Response(404))
        rx.get(BASE).mock(return_value=httpx.Response(
            200, text=INDEX, headers={"content-type": "text/html"}))
        rx.get(PDF_URL).mock(return_value=httpx.Response(
            200, content=pdf, headers=pdf_headers))
        rx.route().mock(return_value=httpx.Response(200, text="ok"))
        settings = CrawlSettings(crawl_delay_ms=0, max_pages=10)
        return await run_crawl("pdfjob", BASE, settings)


async def test_nh7_crawl_emits_document_props_missing_for_a_pdf():
    """The check has never fired on a real crawl: the engine's asset branch did
    not call check_page, so AF5's fix stopped one link short (P21)."""
    crawl = await _crawl_with_pdf(_pdf_bytes())
    codes = {i.code for i in crawl.issues if PDF_URL in (i.page_url or "")}
    assert "DOCUMENT_PROPS_MISSING" in codes, (
        f"a crawl of an untitled PDF did not report it; got {sorted(codes)}")


async def test_nh8_crawl_pdf_still_emits_no_html_codes():
    """Wiring the asset branch into check_page must not let the HTML suite in."""
    crawl = await _crawl_with_pdf(_pdf_bytes())
    codes = {i.code for i in crawl.issues if PDF_URL in (i.page_url or "")}
    leaked = codes & HTML_ONLY_CODES
    assert not leaked, f"the crawl charged {sorted(leaked)} on a PDF"


async def test_nh8b_crawl_still_reports_url_structure_for_a_pdf():
    """The crawl-path findings that were correct all along stay correct."""
    crawl = await _crawl_with_pdf(_pdf_bytes())
    codes = {i.code for i in crawl.issues if PDF_URL in (i.page_url or "")}
    assert "URL_UPPERCASE" in codes


async def test_nh8c_both_paths_agree_on_a_pdf(store):
    """The dual-path invariant this repo keeps having to restate: the same URL
    must not be audited differently depending on which button reached it."""
    crawl = await _crawl_with_pdf(_pdf_bytes())
    crawl_codes = {i.code for i in crawl.issues if PDF_URL in (i.page_url or "")}
    res = await _rescan(store, PDF_URL, _pdf_bytes(), "application/pdf")
    rescan_codes = {i.issue_code for i in res.issues}
    assert crawl_codes == rescan_codes, (
        f"crawl-only: {sorted(crawl_codes - rescan_codes)}; "
        f"rescan-only: {sorted(rescan_codes - crawl_codes)}")


async def test_nh8d_both_paths_agree_on_an_OVERSIZED_pdf(store):
    """The agreement test above ran on a 400-byte fixture, so it could not see
    PDF_TOO_LARGE going missing from the rescan path — which is exactly the gap
    the QA gate found in the first half of this fix. This one declares 11 MB on
    both paths, so the size code is inside the compared set."""
    crawl = await _crawl_with_pdf(_pdf_bytes(), content_length=_OVERSIZE)
    crawl_codes = {i.code for i in crawl.issues if PDF_URL in (i.page_url or "")}
    res = await _rescan_with_length(store, PDF_URL, _pdf_bytes(),
                                    "application/pdf", _OVERSIZE)
    rescan_codes = {i.issue_code for i in res.issues}
    assert "PDF_TOO_LARGE" in crawl_codes, "the fixture no longer trips the size limit"
    assert crawl_codes == rescan_codes, (
        f"crawl-only: {sorted(crawl_codes - rescan_codes)}; "
        f"rescan-only: {sorted(rescan_codes - crawl_codes)}")

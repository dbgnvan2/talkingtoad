"""AF5 — PDF metadata must survive the non-HTML path.

Spec:  docs/pending/2026-08-30_audit-fixes.md#AF5
Audit: docs/audit/2026-08-30_full-check-audit.md (F16)

parse_page returns a minimal record when `result.html` is falsy. A PDF carries
bytes in `.content`, not `.html`, so the pdf_metadata branch that used to sit
below that return was unreachable for exactly the content type it handles:
552 PDFs crawled, 0 metadata, and DOCUMENT_PROPS_MISSING never fired.
"""
from __future__ import annotations

import io

import pytest

from api.crawler.fetcher import FetchResult
from api.crawler.issue_checker import check_page
from api.crawler.parser import parse_page

BASE = "https://example.com/"


def _pdf_bytes(title: str | None = "A Policy Document", subject: str | None = "Policy") -> bytes:
    """Build a real PDF with pypdf so the test exercises the true parser."""
    pypdf = pytest.importorskip("pypdf")
    w = pypdf.PdfWriter()
    w.add_blank_page(width=200, height=200)
    meta = {}
    if title is not None:
        meta["/Title"] = title
    if subject is not None:
        meta["/Subject"] = subject
    if meta:
        w.add_metadata(meta)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def _pdf_page(content: bytes, url: str = "https://example.com/doc.pdf"):
    return parse_page(
        FetchResult(url=url, final_url=url, status_code=200, headers={},
                    html=None, content=content, content_type="application/pdf"),
        BASE)


def test_af5_pdf_metadata_survives_the_non_html_path():
    page = _pdf_page(_pdf_bytes())
    assert page.pdf_metadata is not None, "the PDF branch is below the early return again"
    assert page.pdf_metadata["title"] == "A Policy Document"


def test_af5_pdf_response_size_is_recorded():
    """response_size_bytes derived from `html`, so all 552 PDFs recorded 0."""
    content = _pdf_bytes()
    assert _pdf_page(content).response_size_bytes == len(content)


def test_af5_document_props_missing_fires_for_a_pdf_without_title():
    page = _pdf_page(_pdf_bytes(title=None, subject=None))
    assert any(i.code == "DOCUMENT_PROPS_MISSING" for i in check_page(page))


def test_af5_pdf_with_title_and_subject_is_not_flagged():
    """Adversarial: the check must not fire on a well-described PDF."""
    page = _pdf_page(_pdf_bytes(title="A Policy Document", subject="Student policy summary"))
    assert not any(i.code == "DOCUMENT_PROPS_MISSING" for i in check_page(page))


def test_af5_non_pdf_non_html_response_still_returns_a_minimal_record():
    """Adversarial: the early return itself must keep working."""
    page = parse_page(
        FetchResult(url="https://example.com/a.zip", final_url="https://example.com/a.zip",
                    status_code=200, headers={}, html=None, content=b"PK\x03\x04",
                    content_type="application/zip"),
        BASE)
    assert page.pdf_metadata is None
    assert page.title is None

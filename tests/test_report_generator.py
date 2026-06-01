import pytest
from api.models.job import CrawlJob
from api.models.issue import Issue
from api.services.report_generator import generate_pdf_report

@pytest.mark.asyncio
async def test_generate_pdf_report_unicode():
    job = CrawlJob(target_url="https://example.com/téßt")
    issues = [
        Issue(
            job_id=job.job_id,
            page_url="https://example.com/—dash—",
            category="metadata",
            severity="critical",
            issue_code="TITLE_MISSING",
            description="Page is missing a title tag with “quotes” and € symbols",
            recommendation="Add a <title> tag — ASAP!"
        )
    ]
    summary = {
        "health_score": 85,
        "pages_crawled": 10,
        "total_issues": 1,
        "by_category": {"metadata": 1}
    }
    
    # This should not raise UnicodeEncodeError
    pdf_bytes = await generate_pdf_report(job, issues, summary)
    assert pdf_bytes.startswith(b"%PDF")


class TestConfidenceInPDF:
    """M7.a — confidence_label renders in PDF without error."""

    @pytest.mark.asyncio
    async def test_confidence_label_renders(self):
        """AI-readiness issue with Established confidence produces valid PDF."""
        job = CrawlJob(target_url="https://example.com")
        issue = Issue(
            job_id=job.job_id,
            page_url="https://example.com/page1",
            category="ai_readiness",
            severity="warning",
            issue_code="LLMS_TXT_MISSING",
            description="Missing llms.txt file",
            recommendation="Add an llms.txt file",
            confidence_label="Established",
        )
        summary = {
            "health_score": 80,
            "pages_crawled": 1,
            "total_issues": 1,
            "by_severity": {"warning": 1},
            "by_category": {"ai_readiness": 1},
        }
        pdf_bytes = await generate_pdf_report(job, [issue], summary)
        assert pdf_bytes, "PDF bytes should not be empty"
        assert isinstance(pdf_bytes, (bytes, bytearray))
        assert len(pdf_bytes) > 1000

    @pytest.mark.asyncio
    async def test_confidence_none_no_crash(self):
        """Issue with confidence_label=None does not crash PDF generation."""
        job = CrawlJob(target_url="https://example.com")
        issue = Issue(
            job_id=job.job_id,
            page_url="https://example.com/page2",
            category="ai_readiness",
            severity="info",
            issue_code="LLMS_TXT_MISSING",
            description="Missing llms.txt",
            recommendation="Add llms.txt",
            confidence_label=None,
        )
        summary = {
            "health_score": 90,
            "pages_crawled": 1,
            "total_issues": 1,
            "by_severity": {"info": 1},
            "by_category": {"ai_readiness": 1},
        }
        pdf_bytes = await generate_pdf_report(job, [issue], summary)
        assert pdf_bytes
        assert len(pdf_bytes) > 1000

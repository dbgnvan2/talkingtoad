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

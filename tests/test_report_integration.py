import pytest
import io
from api.models.job import CrawlJob, CrawlSettings
from api.models.issue import Issue

@pytest.mark.asyncio
async def test_pdf_export_integration(api_client, auth_headers, test_store):
    """
    Integration Test: Verify the PDF export endpoint handles all 
    frontend parameters correctly using the test_store.
    """
    # 1. Create a dummy job and issues in the test_store
    settings = CrawlSettings(client_name="Test Client", prepared_by="Test User")
    job = CrawlJob(target_url="https://test.com", settings=settings)
    await test_store.create_job(job)
    
    issue = Issue(
        job_id=job.job_id,
        page_url="https://test.com/page1",
        category="metadata",
        severity="critical",
        issue_code="TITLE_MISSING",
        description="Test desc",
        recommendation="Test rec",
        human_description="Test human",
        what_it_is="What test",
        impact_desc="Impact test",
        how_to_fix="How test",
        impact=10,
        effort=1,
        priority_rank=98
    )
    await test_store.save_issues([issue])
    
    # 2. Test full report (default)
    response = await api_client.get(
        f"/api/crawl/{job.job_id}/export/pdf?include_help=true&include_pages=true",
        headers=auth_headers
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    
    # 3. Test summary only
    response = await api_client.get(
        f"/api/crawl/{job.job_id}/export/pdf?summary_only=true",
        headers=auth_headers
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"

    # 4. Test missing job (should return 404, not crash)
    response = await api_client.get(
        "/api/crawl/non-existent-id/export/pdf",
        headers=auth_headers
    )
    assert response.status_code == 404

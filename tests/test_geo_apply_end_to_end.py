"""
End-to-end test for GEO metadata application - LIVE INTEGRATION TEST.

Run with: pytest tests/test_geo_apply_end_to_end_fixed.py -v -s

Requires:
- Server running on localhost:8000
- Real crawl job with ID: 3e845e69-7ea3-44a5-8a0a-1a6e3c04cff7
- WordPress credentials in wp-credentials.json

This test:
1. Applies GEO metadata with TEST markers
2. Verifies changes persist through fetch
3. Cleans up by restoring original values
"""

import pytest
import httpx


@pytest.mark.asyncio
async def test_geo_apply_and_cleanup():
    """
    CRITICAL TEST: GEO changes must persist and can be cleaned up.
    
    Tests:
    1. Apply TEST values → verify saved
    2. Fetch → verify TEST values persist (not overwritten)
    3. Restore originals → verify cleanup works
    """
    job_id = "3e845e69-7ea3-44a5-8a0a-1a6e3c04cff7"
    image_url = "https://livingsystems.ca/wp-content/uploads/2024/09/Parents-and-child.png"
    base_url = "http://localhost:8000"

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        print(f"\n{'='*70}")
        print(f"LIVE INTEGRATION TEST: GEO Apply & Cleanup")
        print(f"{'='*70}")
        
        # Step 1: Get original values
        print(f"\n[STEP 1] Fetching original values...")
        response = await client.post(
            f"/api/crawl/{job_id}/images/fetch?image_url={image_url}"
        )
        assert response.status_code == 200
        original = response.json()["image"]
        original_alt = original["alt"]
        original_description = original["description"] or ""

        print(f"Original alt: {original_alt}")
        print(f"Original description: {original_description[:50] if original_description else '(empty)'}...")

        # Step 2: Apply GEO metadata with TEST markers
        print(f"\n[STEP 2] Applying TEST GEO metadata...")
        test_alt = "TEST_ALT_GEO: Parents and child in counselling session at Living Systems in Vancouver"
        test_description = "TEST_DESCRIPTION_GEO: This image shows a therapeutic family counselling session focused on Bowen Theory principles."

        response = await client.post(
            "/api/ai/image/apply-geo-metadata",
            json={
                "job_id": job_id,
                "image_url": image_url,
                "alt_text": test_alt,
                "description": test_description,
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        print(f"✓ GEO metadata applied")
        print(f"  WordPress updated: {result.get('wordpress_updated')}")
        print(f"  WordPress error: {result.get('wordpress_error')}")

        # Step 3: CRITICAL - Fetch and verify TEST values persist
        print(f"\n[STEP 3] Fetching image again to verify persistence...")
        response = await client.post(
            f"/api/crawl/{job_id}/images/fetch?image_url={image_url}"
        )
        assert response.status_code == 200
        fetched = response.json()["image"]

        print(f"Alt after fetch: {fetched['alt'][:80]}...")
        print(f"Description after fetch: {(fetched['description'] or '')[:80]}...")

        # CRITICAL ASSERTION
        assert "TEST_ALT_GEO" in fetched["alt"], (
            f"❌ GEO alt text was overwritten by fetch!\n"
            f"Expected: {test_alt}\n"
            f"Got: {fetched['alt']}"
        )
        print(f"✓ Alt text persisted through fetch!")

        if result.get("wordpress_updated"):
            assert "TEST_DESCRIPTION_GEO" in (fetched["description"] or ""), (
                f"❌ GEO description was overwritten by fetch!\n"
                f"Expected: {test_description}\n"
                f"Got: {fetched['description']}"
            )
            print(f"✓ Description persisted through fetch!")

        # Step 4: Restore original values
        print(f"\n[STEP 4] Cleaning up - restoring original values...")
        response = await client.post(
            "/api/ai/image/apply-geo-metadata",
            json={
                "job_id": job_id,
                "image_url": image_url,
                "alt_text": original_alt,
                "description": original_description,
            },
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        print(f"✓ Original values restored")

        # Step 5: Verify cleanup
        print(f"\n[STEP 5] Verifying cleanup...")
        response = await client.post(
            f"/api/crawl/{job_id}/images/fetch?image_url={image_url}"
        )
        cleaned = response.json()["image"]

        assert "TEST_ALT_GEO" not in cleaned["alt"], "❌ Failed to clean up TEST alt text"
        assert "TEST_DESCRIPTION_GEO" not in (cleaned["description"] or ""), "❌ Failed to clean up TEST description"
        
        print(f"✓ Cleanup successful - TEST values removed")
        print(f"\n{'='*70}")
        print(f"✅ ALL TESTS PASSED!")
        print(f"{'='*70}\n")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_geo_apply_and_cleanup())

"""
Calibration runner — execute Advisor on test pages and generate reports.

Run with:
    python3 -m pytest tests/test_advisor_calibration.py::test_run_all_calibration_pages -v -s

Then review each report and judge:
  1. Are findings traceable? (can you find the cited text?)
  2. Are findings accurate? (do they match what's really on the page?)
  3. Are findings prioritized? (critical issues first?)
  4. Is the decision sound? (should_generate_prompt makes sense?)

Track results in a spreadsheet:
  Page | Traceable? | Accurate? | Prioritized? | Decision OK? | Notes
"""

import asyncio
from pathlib import Path

import pytest

from api.models.advisor import AdvisorRequest
from api.services.advisor import evaluate_page

CALIBRATION_DIR = Path("tests/fixtures/calibration")


@pytest.mark.asyncio
async def test_run_all_calibration_pages():
    """Run Advisor on all calibration pages and print reports."""
    calibration_pages = sorted(CALIBRATION_DIR.glob("*.md"))

    if not calibration_pages:
        pytest.skip("No calibration pages found in tests/fixtures/calibration/")

    results = []

    for idx, page_file in enumerate(calibration_pages, 1):
        if page_file.name.startswith("orig_"):
            continue  # Skip originals, use them for comparison

        # Print separator
        print(f"\n{'='*80}")
        print(f"[{idx}] {page_file.name}")
        print(f"{'='*80}\n")

        content = page_file.read_text()

        # Check if there's a corresponding original for comparison
        original = None
        for prefix in ("7_rewrite", "8_rewrite", "9_rewrite"):
            if page_file.name.startswith(prefix):
                orig_name = f"orig_{page_file.name}"
                orig_path = CALIBRATION_DIR / orig_name
                if orig_path.exists():
                    original = orig_path.read_text()
                    break

        # Evaluate
        try:
            request = AdvisorRequest(
                content=content,
                original_content=original,
            )
            report, should_prompt = await evaluate_page(request)

            # Print report
            print(report)
            print(f"\n[Decision] Generate rewrite prompt: {should_prompt}")
            if original:
                print(f"[Context] Comparing rewrite to original")
            print(f"\n{'─'*80}\n")

            results.append({
                "file": page_file.name,
                "status": "✓ evaluated",
                "should_prompt": should_prompt,
            })
        except Exception as e:
            print(f"✗ ERROR: {e}\n")
            results.append({
                "file": page_file.name,
                "status": f"✗ error: {e}",
            })

    # Summary
    print(f"\n\n{'='*80}")
    print("CALIBRATION SUMMARY")
    print(f"{'='*80}\n")
    for r in results:
        status = r["status"]
        file = r["file"]
        decision = f"prompt={r.get('should_prompt')}" if "✓" in status else ""
        print(f"{status:20} {file:40} {decision}")

    print(f"\n\nNext step: Review each report and judge on 4 dimensions:")
    print(f"  1. Traceable?     — Can you find the cited text?")
    print(f"  2. Accurate?      — Do findings match the page?")
    print(f"  3. Prioritized?   — Are critical issues first?")
    print(f"  4. Decision OK?   — Does should_prompt make sense?")
    print(f"\nThreshold: 8/10 reports should feel useful.")
    print(f"If <6/10, iterate the critic prompt in advisor.py")

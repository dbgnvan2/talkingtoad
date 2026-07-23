"""Human-readable golden-site crawl report — proof the real crawler finds the
planted issues (no test-runner, no assertions to "fake out").

Run from the repo root:
    python3 tests/golden_site/report.py

It serves the golden site and runs the SAME crawl engine that
POST /api/crawl/start runs in production (nothing about detection is mocked;
the only concession is allowing the crawler to reach 127.0.0.1, which its SSRF
guard normally blocks). It then prints, per planted issue, whether the crawler
found it — plus every finding per page. Exit code is 0 only if all planted
issues were detected.
"""

from __future__ import annotations

import asyncio
import collections
import pathlib
import sys

# Make the repo importable when run as a plain script.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import api.crawler.fetcher as fetcher  # noqa: E402
from api.crawler.engine import run_crawl, CrawlSettings  # noqa: E402
from tests.golden_site.build_pages import main as build_pages  # noqa: E402
from tests.golden_site.server import GoldenSiteServer  # noqa: E402
from tests.golden_site.manifest import EXPECT, ENV_ARTIFACTS  # noqa: E402

GREEN, RED, DIM, BOLD, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"


async def _crawl():
    build_pages()
    orig = fetcher.is_ssrf_safe
    fetcher.is_ssrf_safe = lambda url: True  # allow the loopback fixture host
    try:
        with GoldenSiteServer() as srv:
            base = srv.base_url.rstrip("/")
            print(f"Serving the golden site at {srv.base_url}")
            print("Running the real crawl engine (same as POST /api/crawl/start)...\n")
            res = await run_crawl("golden-report", srv.base_url,
                                  CrawlSettings(crawl_delay_ms=0, max_pages=100))
    finally:
        fetcher.is_ssrf_safe = orig

    by_page = collections.defaultdict(set)
    for iss in res.issues:
        key = (iss.page_url or "").replace(base, "") or "/"
        by_page[key].add(iss.code)
    return res, dict(by_page)


def main():
    res, by_page = asyncio.run(_crawl())

    bar = "=" * 78
    print(bar)
    print(f"{BOLD} TalkingToad — Golden Site Crawl Report{RESET}")
    print(f"{DIM} (the crawl engine is the real one; only detection results below){RESET}")
    print(bar)

    # ── Planted-issue check ─────────────────────────────────────────────────
    print(f"\n{BOLD}PLANTED-ISSUE CHECK — did the crawler find each known defect?{RESET}")
    print("-" * 78)
    found = missing = 0
    for path in sorted(EXPECT):
        detected = by_page.get(path, set())
        for code in sorted(EXPECT[path]):
            ok = code in detected
            found += ok
            missing += not ok
            mark = f"{GREEN}found{RESET}" if ok else f"{RED}MISSING{RESET}"
            print(f"  {path:<28.28} {code:<30} {mark}")
    total = found + missing
    print("-" * 78)
    verdict = (f"{GREEN}{found}/{total} planted issues detected — detection is working.{RESET}"
               if missing == 0 else
               f"{RED}{found}/{total} detected — {missing} MISSING (a detector regressed!){RESET}")
    print(f"  {verdict}")

    # ── Totals ──────────────────────────────────────────────────────────────
    all_codes = {c for codes in by_page.values() for c in codes}
    real = all_codes - ENV_ARTIFACTS
    print(f"\n{BOLD}TOTALS{RESET}")
    print(f"  pages crawled ............ {res.pages_crawled}")
    print(f"  distinct issue codes ..... {len(real)}  {DIM}(+{len(all_codes & ENV_ARTIFACTS)} "
          f"local-hosting artifacts: {', '.join(sorted(all_codes & ENV_ARTIFACTS))}){RESET}")
    print(f"  total issue rows ......... {len(res.issues)}")

    # ── Full findings per page ──────────────────────────────────────────────
    print(f"\n{BOLD}FULL FINDINGS PER PAGE{RESET}  {DIM}(everything the crawler reported){RESET}")
    print("-" * 78)
    for path in sorted(by_page):
        codes = sorted(by_page[path] - ENV_ARTIFACTS)
        print(f"  {BOLD}{path}{RESET}")
        print(f"      {' · '.join(codes) if codes else DIM + '(no non-artifact issues)' + RESET}")

    print(f"\n{DIM}Re-run the automated gate with: pytest tests/test_golden_site.py -q{RESET}")
    return 0 if missing == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

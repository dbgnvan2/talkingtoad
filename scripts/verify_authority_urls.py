#!/usr/bin/env python3
"""Re-fetch every URL cited in authority.yaml and rewrite url_verification.yaml.

Purpose: keep the claim "this source exists" checked rather than asserted.
Spec:    docs/functional-specification.md (V1 — evidence basis)
Tests:   tests/test_authority.py::test_v1_every_citation_url_was_actually_fetched

Run it when a citation is added or changed, and periodically — sources move.
The test suite reads the recorded result and never touches the network.
"""
from __future__ import annotations

import asyncio
import datetime
import sys
from pathlib import Path

import httpx
import yaml

DATA = Path(__file__).resolve().parent.parent / "api/crawler/checkers/data"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")


async def main() -> int:
    record = yaml.safe_load((DATA / "authority.yaml").read_text(encoding="utf-8"))
    urls = sorted({v["url"] for v in record.values() if v.get("url")})
    results: dict[str, dict] = {}
    async with httpx.AsyncClient(timeout=25, follow_redirects=True,
                                 headers={"user-agent": UA}) as client:
        async def one(url: str) -> tuple[str, dict]:
            try:
                resp = await client.get(url)
                return url, {"status": resp.status_code, "final_url": str(resp.url)}
            except Exception as exc:                       # noqa: BLE001
                return url, {"status": None, "error": type(exc).__name__}
        for url, res in await asyncio.gather(*[one(u) for u in urls]):
            results[url] = res

    failed = {u: r for u, r in results.items() if r.get("status") != 200}
    (DATA / "url_verification.yaml").write_text(yaml.safe_dump({
        "checked_on": datetime.date.today().isoformat(),
        "method": "HTTP GET, redirects followed, desktop browser user agent",
        "note": ("Fetched for real; not asserted. A citation whose URL is not "
                 "recorded here as 200 must not ship. Re-run "
                 "scripts/verify_authority_urls.py to refresh."),
        "urls": results,
    }, sort_keys=True, default_flow_style=False, width=100), encoding="utf-8")

    print(f"{len(results) - len(failed)}/{len(results)} returned 200")
    for url, res in sorted(failed.items()):
        print(f"  FAILED {res.get('status') or res.get('error')}  {url}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

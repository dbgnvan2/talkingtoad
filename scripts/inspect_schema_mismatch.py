"""V2 — SCHEMA_VISIBLE_MISMATCH real-page inspection.

Purpose: Fetch specific live pages, run the SHIPPED parser + detector, and print
         for each fired mismatch the JSON-LD field value and whether it is a
         theme/plugin artifact or a true positive (value genuinely absent from
         visible copy). Read-only diagnostic — writes nothing.
Spec:    docs/pending/2026-07-06_deploy-gate-validation.md#V2

Note: R5.2 suppresses SCHEMA_VISIBLE_MISMATCH from the SCORE when JSON_LD_MISSING
co-fires, so we only care about pages that actually HAVE JSON-LD (has_json_ld).
"""

from __future__ import annotations

import asyncio
import sys

from api.crawler.fetcher import fetch_page, make_client
from api.crawler.parser import parse_page
from api.services.schema_typing import _normalize, _SCHEMA_FIELDS_TO_CHECK


def _extract_checked_values(schema_blocks: list[dict]) -> list[tuple[str, str]]:
    """Return (label, value) for each checked schema field present in the blocks."""
    out: list[tuple[str, str]] = []

    def walk(block: dict) -> None:
        btype = block.get("@type", "")
        types = (
            [t.lower() for t in btype if isinstance(t, str)]
            if isinstance(btype, list)
            else [btype.lower()] if isinstance(btype, str) else []
        )
        for tk in types:
            for field_name, label in _SCHEMA_FIELDS_TO_CHECK.get(tk, []):
                v = block.get(field_name)
                if isinstance(v, str) and v.strip():
                    out.append((label, v))
        graph = block.get("@graph")
        if isinstance(graph, list):
            for node in graph:
                if isinstance(node, dict):
                    walk(node)

    for b in schema_blocks:
        if isinstance(b, dict):
            walk(b)
    return out


async def inspect(urls: list[str]) -> None:
    async with make_client() as client:
        for url in urls:
            print("=" * 78)
            print(f"URL: {url}")
            fr = await fetch_page(url, client)
            if not fr or not getattr(fr, "html", None):
                print("  <fetch failed / no HTML>")
                continue
            parsed = parse_page(fr, "https://livingsystems.ca")
            has_jsonld = getattr(parsed, "has_json_ld", False)
            fields = getattr(parsed, "schema_visible_mismatch_fields", None) or []
            print(f"  has_json_ld: {has_jsonld}")
            print(f"  SCHEMA_VISIBLE_MISMATCH fields: {fields}")
            blocks = getattr(parsed, "schema_blocks", None) or []
            visible = _normalize(_get_visible(fr))
            checked = _extract_checked_values(blocks)
            if not checked:
                print("  (no checked schema fields present)")
            for label, value in checked:
                present = _normalize(value) in visible
                verdict = "IN visible text" if present else "NOT in visible text (fires)"
                print(f"    - {label}: {value!r}")
                print(f"        -> {verdict}")


def _get_visible(fr) -> str:
    """Reparse to grab visible text the same way the detector does."""
    from bs4 import BeautifulSoup

    return BeautifulSoup(fr.html, "html.parser").get_text()


if __name__ == "__main__":
    default_urls = [
        "https://livingsystems.ca/team_members/devana-weiss",
        "https://livingsystems.ca/s2e07-societal-emotional-process",
        "https://livingsystems.ca/about",
        "https://livingsystems.ca/counselling",
    ]
    urls = sys.argv[1:] or default_urls
    asyncio.run(inspect(urls))

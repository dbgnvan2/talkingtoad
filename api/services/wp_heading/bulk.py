"""
Bulk heading replacement across multiple pages.

Split from wp_heading_fixer.py (M9.4 refactor).
"""

import logging

from api.services.wp_client import WPClient
from api.services.wp_heading.sources import find_heading

logger = logging.getLogger(__name__)


async def bulk_replace_heading(
    wp: WPClient,
    store,
    job_id: str,
    heading_text: str,
    from_level: int,
    to_level: int | None = None,
) -> dict:
    """Find all pages with *heading_text* at *from_level* and change them to *to_level*.

    Two modes:
    - ``to_level is None``: preview-only. Returns matched pages without
      touching WP. Useful for the UI to show "applying this fix will affect
      N pages: ..." before the user confirms.
    - ``to_level is set``: iterate matches, calling change_heading_level for
      each. Skips pages where from_level == to_level (no-op). Records
      per-page success/failure.

    Returns:
        {
          "matched": int,           # total pages with matching heading
          "applied": int,           # successfully changed
          "skipped": int,           # already at to_level, or to_level is None
          "errors": int,            # change_heading_level returned success=False
          "results": [              # one entry per matched page
            {"page_url", "success", "changed", "error", ...}
          ],
        }
    """
    matched = await find_heading(store, job_id, heading_text, level=from_level)

    if to_level is None:
        # Preview mode — report matches without modifying WP.
        return {
            "matched": len(matched),
            "applied": 0,
            "skipped": len(matched),  # nothing to do is "skipped", not "errored"
            "errors": 0,
            "results": [
                {**m, "success": True, "changed": 0, "preview": True, "error": None}
                for m in matched
            ],
        }

    if from_level == to_level:
        # Adversarial guard — caller asked for a no-op.
        return {
            "matched": len(matched),
            "applied": 0,
            "skipped": len(matched),
            "errors": 0,
            "results": [
                {**m, "success": True, "changed": 0,
                 "error": "no-op: from_level == to_level"}
                for m in matched
            ],
        }

    # Deferred import: tests patch change_heading_level on the facade module
    # (api.services.wp_heading_fixer); a top-level import from edit.py would
    # bind a separate reference that the patch can't reach.  Importing from
    # the facade at call time picks up any active mock.
    from api.services.wp_heading_fixer import change_heading_level

    results: list[dict] = []
    applied = 0
    errors = 0
    for m in matched:
        try:
            r = await change_heading_level(
                wp=wp,
                page_url=m["page_url"],
                heading_text=heading_text,
                from_level=from_level,
                to_level=to_level,
            )
            if r.get("success"):
                applied += 1
            else:
                errors += 1
            results.append({**m, **r})
        except Exception as exc:
            logger.exception(
                "bulk_replace_heading_per_page_failed",
                extra={"page_url": m["page_url"], "error": str(exc)},
            )
            errors += 1
            results.append({
                **m,
                "success": False,
                "changed": 0,
                "error": str(exc),
            })

    return {
        "matched": len(matched),
        "applied": applied,
        "skipped": 0,
        "errors": errors,
        "results": results,
    }

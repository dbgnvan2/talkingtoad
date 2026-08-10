#!/usr/bin/env python3
"""Generate frontend/src/data/categories.generated.json from CATEGORY_DISPLAY.

CATEGORY_DISPLAY (api/crawler/checkers/registry.py) is the SINGLE SOURCE OF TRUTH
for the category display order + labels. This script projects it into a JSON file
the frontend imports (Results.jsx tabs, SummaryPanel.jsx grid) so the category
list is never hand-mirrored (CLN2). The PDF report imports CATEGORY_DISPLAY
directly.

Usage:
    python scripts/generate_categories_json.py            # write the JSON
    python scripts/generate_categories_json.py --check     # CI: exit 1 on drift
    python scripts/generate_categories_json.py --stdout     # print, don't write
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.crawler.checkers.registry import CATEGORY_DISPLAY  # noqa: E402

JSON_PATH = PROJECT_ROOT / "frontend" / "src" / "data" / "categories.generated.json"


def _render() -> str:
    data = [{"key": key, "label": label} for key, label in CATEGORY_DISPLAY]
    # 2-space indent + trailing newline to match Prettier/JSON conventions.
    return json.dumps(data, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate categories.generated.json from registry.CATEGORY_DISPLAY."
    )
    parser.add_argument("--check", action="store_true",
                        help="CI mode: exit 1 if the file on disk differs.")
    parser.add_argument("--stdout", action="store_true",
                        help="Print to stdout instead of writing.")
    args = parser.parse_args()

    generated = _render()

    if args.stdout:
        print(generated, end="")
        return 0

    if args.check:
        if not JSON_PATH.exists():
            print(f"ERROR: {JSON_PATH} missing — run "
                  "`python scripts/generate_categories_json.py`.", file=sys.stderr)
            return 1
        if JSON_PATH.read_text() != generated:
            print(f"ERROR: {JSON_PATH} is out of sync with registry.CATEGORY_DISPLAY. "
                  "Run `python scripts/generate_categories_json.py` and commit.",
                  file=sys.stderr)
            return 1
        return 0

    JSON_PATH.write_text(generated)
    print(f"Wrote {JSON_PATH.relative_to(PROJECT_ROOT)} "
          f"({len(CATEGORY_DISPLAY)} categories).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

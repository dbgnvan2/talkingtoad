#!/usr/bin/env python3
"""Generate ``api/services/issue_help_data.py`` from ``frontend/src/data/issueHelp.json``.

The JSON is the single authored source of every issue code's explanation
(docs/explanation-style-guide.md). The PDF report runs in a container that
copies only ``api/``, so it reads a generated Python copy — this script writes
it, and ``tests/test_issue_help_sync.py`` fails when the two differ, exactly as
``docs/issue-codes.md`` is guarded.

  python scripts/generate_issue_help_py.py           # write
  python scripts/generate_issue_help_py.py --check   # CI: fail if out of sync
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend" / "src" / "data" / "issueHelp.json"
DST = ROOT / "api" / "services" / "issue_help_data.py"

FIELDS = ("title", "mission_impact", "definition", "impact", "good_vs_bad",
          "how_it_can_mislead", "fix", "confidence")


def render() -> str:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    out = {}
    for code in sorted(data):
        e = data[code]
        out[code] = {k: e.get(k) for k in FIELDS if e.get(k) is not None}
    body = json.dumps(out, indent=4, ensure_ascii=False, sort_keys=True)
    return (
        '"""Issue help text for the PDF report — GENERATED, do not edit.\n\n'
        "Source: frontend/src/data/issueHelp.json (authored; see\n"
        "docs/explanation-style-guide.md). Regenerate with\n"
        "``python scripts/generate_issue_help_py.py``; tests/test_issue_help_sync.py\n"
        "fails when this file is out of date.\n"
        '"""\n\n'
        "from __future__ import annotations\n\n"
        "ISSUE_HELP: dict[str, dict] = " + body + "\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    text = render()
    if args.check:
        current = DST.read_text(encoding="utf-8") if DST.exists() else ""
        if current != text:
            print(f"OUT OF SYNC: {DST} — run python scripts/generate_issue_help_py.py", file=sys.stderr)
            return 1
        print(f"OK: {DST} is in sync with {SRC}")
        return 0
    DST.write_text(text, encoding="utf-8")
    print(f"Wrote {DST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

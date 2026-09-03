#!/usr/bin/env python3
"""Collapse the duplicate home-page rows left by pre-ND3 crawls.

Spec: docs/functional-specification.md §4.10 (LR, 2026-09-03)

ND3 (2026-09-03) made `normalise_url` map a bare origin to the root path, so
`https://site.ca` and `https://site.ca/` became one page. Jobs crawled BEFORE
that hold both as separate `crawled_pages` rows with different issue sets.

Measured on the development store when this was written: **71 jobs affected, 24
of them with a health score 1-2 points wrong** — `_compute_v15_health_score`
merges the two rows' issues under `RTRIM(page_url,'/')` but counts the page
TWICE in the denominator, so the home page is double-weighted at a merged
deduction. All 71 also show the home page twice in the By Page list.

New scans cannot produce this. Old ones stay wrong until something collapses
them, which is what this does: the bare row's issues, links and images are
re-pointed at the slashed row, and the bare `crawled_pages` row is deleted.

It does NOT rewrite stored `health_score` columns. The score is recomputed from
rows on read (`get_summary`), so collapsing the rows fixes it; writing a derived
value would create a second source of truth.

    python scripts/migrate_collapse_duplicate_origin_rows.py            # dry run
    python scripts/migrate_collapse_duplicate_origin_rows.py --apply    # write

Dry run is the default and writes nothing. `--apply` backs the database up first
and refuses to proceed if the backup cannot be written: this edits real crawl
history, and a migration that cannot be undone is not one to run unattended.
Idempotent — a second run finds nothing to do.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Tables whose rows point at a page by URL. Discovered from the schema rather
# than hard-coded blindly: a table added later that this misses would leave
# orphan rows pointing at a deleted page.
_URL_COLUMNS = {
    "issues": "page_url",
    "links": "source_url",
    "images": "page_url",
}


def _affected(con: sqlite3.Connection) -> list[tuple[str, str, str]]:
    """Return (job_id, bare_url, slashed_url) for every job holding both."""
    rows = con.execute(
        """
        SELECT p.job_id, p.url
        FROM crawled_pages p
        WHERE p.url NOT LIKE '%/'
          AND instr(substr(p.url, 9), '/') = 0
          AND EXISTS (SELECT 1 FROM crawled_pages q
                      WHERE q.job_id = p.job_id AND q.url = p.url || '/')
        """
    ).fetchall()
    return [(job, bare, bare + "/") for job, bare in rows]


def _counts(con: sqlite3.Connection, job: str, url: str) -> dict[str, int]:
    out = {}
    for table, col in _URL_COLUMNS.items():
        try:
            out[table] = con.execute(
                f"SELECT COUNT(*) FROM {table} WHERE job_id = ? AND {col} = ?",
                (job, url),
            ).fetchone()[0]
        except sqlite3.OperationalError:
            out[table] = 0          # table or column absent in this schema
    return out


def _health(con: sqlite3.Connection, job: str, *, collapse: bool) -> int | None:
    """Recompute the site health score, optionally with the duplicate removed."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from api.services.job_store_base import compute_impact_health

    per_page: dict[str, list[tuple[str, int, str]]] = {}
    for norm, code, impact, cat in con.execute(
        "SELECT RTRIM(page_url,'/'), issue_code, impact, category FROM issues WHERE job_id=?",
        (job,),
    ):
        per_page.setdefault(norm, []).append((code, impact or 0, cat or ""))
    urls = [u.rstrip("/") for (u,) in
            con.execute("SELECT url FROM crawled_pages WHERE job_id=?", (job,))]
    if collapse:
        seen: set[str] = set()
        urls = [u for u in urls if not (u in seen or seen.add(u))]
    if not urls:
        return None
    sev = {"critical": 0, "warning": 0, "info": 0}
    return compute_impact_health(urls, per_page, sev)[0]


def _backup(db: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = db.with_name(f"{db.name}.pre-origin-collapse.{stamp}.bak")
    shutil.copy2(db, dest)
    if not dest.exists() or dest.stat().st_size == 0:
        raise RuntimeError(f"backup at {dest} is missing or empty")
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="talkingtoad.db", help="path to the SQLite database")
    ap.add_argument("--apply", action="store_true",
                    help="write the changes (default is a dry run that writes nothing)")
    args = ap.parse_args(argv)

    db = Path(args.db)
    if not db.exists():
        print(f"no database at {db}", file=sys.stderr)
        return 2

    con = sqlite3.connect(db)
    con.row_factory = None
    affected = _affected(con)

    if not affected:
        print("Nothing to do — no job holds both spellings of its home page.")
        return 0

    print(f"{len(affected)} job(s) hold both spellings of the home page.\n")
    moved_rows = 0
    score_changes = 0
    for job, bare, slashed in affected:
        counts = _counts(con, job, bare)
        before = _health(con, job, collapse=False)
        after = _health(con, job, collapse=True)
        moved_rows += sum(counts.values())
        if before != after:
            score_changes += 1
        delta = "" if before == after else f"   health {before} -> {after}"
        print(f"  {job[:8]}  {bare}")
        print(f"      rows to re-point: " +
              ", ".join(f"{t}={n}" for t, n in counts.items()) + delta)

    print(f"\n{moved_rows} row(s) would be re-pointed; "
          f"{score_changes} job(s) would change health score.")

    if not args.apply:
        print("\nDry run — nothing was written. Re-run with --apply to make the change.")
        return 0

    backup = _backup(db)
    print(f"\nBacked up to {backup}")

    with con:
        for job, bare, slashed in affected:
            for table, col in _URL_COLUMNS.items():
                try:
                    con.execute(
                        f"UPDATE {table} SET {col} = ? WHERE job_id = ? AND {col} = ?",
                        (slashed, job, bare),
                    )
                except sqlite3.OperationalError:
                    continue
            con.execute("DELETE FROM crawled_pages WHERE job_id = ? AND url = ?",
                        (job, bare))
    print(f"Applied. {len(affected)} duplicate home-page row(s) collapsed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

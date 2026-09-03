#!/usr/bin/env python3
"""Collapse the duplicate home-page rows left by pre-ND3 crawls.

Spec: docs/functional-specification.md §4.10 (LR, 2026-09-03)

ND3 (2026-09-03) made `normalise_url` map a bare origin to the root path, so
`https://site.ca` and `https://site.ca/` became one page. Jobs crawled BEFORE
that hold both as separate `crawled_pages` rows with different issue sets.

Measured on the development store when this was written: **71 jobs affected, 24
of them with a health score wrong by up to 3 points** — `_compute_v15_health_score`
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
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
import re
from pathlib import Path

# A scheme+host with no path — the shape ND3 collapsed.
_BARE_URL_RE = re.compile(r'"(https?://[^"/]+)"')

# Tables whose rows point at a page by URL. `sqlite_store.py`'s job-expiry list
# — ("issues","crawled_pages","links","fixes","fixed_issues","images") — is the
# authoritative enumeration and this was written without consulting it, so
# `fixes` and `fixed_issues` were missed on the first pass (cold sweep).
#
# `fixes` carries UNIQUE(job_id, page_url, field): if both spellings hold a fix
# for the same field, a plain UPDATE raises IntegrityError and — because every
# table moves inside one transaction — aborts the whole migration mid-flight.
# Tables listed here as CONFLICT_SAFE drop the losing row instead.
_URL_COLUMNS = {
    "issues": "page_url",
    "links": "source_url",
    "links_target": ("links", "target_url"),
    "images": "page_url",
    "fixes": "page_url",
    "fixed_issues": "page_url",
}
_CONFLICT_SAFE = {"fixes"}          # has a UNIQUE index that a move can violate


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


def _stale_evidence_jobs(con: sqlite3.Connection) -> list[tuple[str, str, str]]:
    """(job, bare, slashed) for jobs whose ISSUE EVIDENCE still names a bare
    origin the job no longer has a page for.

    Phase 2 needs its own finder because phase 1 deletes the page rows that
    `_affected` keys on — after a collapse the evidence is stale and nothing
    points at it any more. This is what makes the two phases independently
    re-runnable on an already-migrated database.
    """
    out: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for job, extra in con.execute(
            "SELECT job_id, extra FROM issues WHERE extra LIKE '%http%'"):
        for m in _BARE_URL_RE.findall(extra or ""):
            key = (job, m)
            if key in seen:
                continue
            seen.add(key)
            if not con.execute(
                    "SELECT 1 FROM crawled_pages WHERE job_id = ? AND url = ?",
                    (job, m)).fetchone():
                if con.execute(
                        "SELECT 1 FROM crawled_pages WHERE job_id = ? AND url = ?",
                        (job, m + "/")).fetchone():
                    out.append((job, m, m + "/"))
    return out


def _duplicated_root_pages(con: sqlite3.Connection) -> list[tuple[str, str]]:
    """(job, url) for every origin-root page holding IDENTICAL issue rows.

    The dedupe was originally driven off the stale-evidence list, which missed
    the collapsed jobs whose evidence happened to be clean — 27 of the 71, and
    175 surplus rows. The condition to look for is the duplication itself, not a
    proxy for it.
    """
    return con.execute(
        """
        SELECT DISTINCT job_id, page_url FROM issues
        WHERE page_url LIKE '%://%'
          AND page_url LIKE '%/'
          AND length(page_url) - length(replace(page_url, '/', '')) = 3
          AND (job_id, page_url, issue_code, IFNULL(extra, '')) IN (
              SELECT job_id, page_url, issue_code, IFNULL(extra, '')
              FROM issues GROUP BY 1, 2, 3, 4 HAVING COUNT(*) > 1)
        """
    ).fetchall()


def _resolve(key: str, spec) -> tuple[str, str]:
    """(table, column) for a `_URL_COLUMNS` entry, which may be either form."""
    return spec if isinstance(spec, tuple) else (key, spec)


def _counts(con: sqlite3.Connection, job: str, url: str) -> dict[str, int]:
    out = {}
    for key, spec in _URL_COLUMNS.items():
        table, col = _resolve(key, spec)
        try:
            out[key] = con.execute(
                f"SELECT COUNT(*) FROM {table} WHERE job_id = ? AND {col} = ?",
                (job, url),
            ).fetchone()[0]
        except sqlite3.OperationalError:
            out[key] = 0            # table or column absent in this schema
    return out


# Codes whose whole meaning is "this page is the same as ANOTHER page". When the
# other page was only the second spelling of this one, the finding existed solely
# because of the duplication and is false once the pages are collapsed.
_CROSS_PAGE_DUPLICATE_CODES = frozenset({
    "NEAR_DUPLICATE_BODY", "TITLE_DUPLICATE", "META_DESC_DUPLICATE",
    "TITLE_META_DUPLICATE_PAIR",
})
_EVIDENCE_URL_KEYS = ("members", "near_identical_to", "duplicate_urls",
                      "occurrence_urls", "inaccessible_sources")


def _repoint_evidence(con: sqlite3.Connection, job: str, bare: str, slashed: str,
                      *, apply: bool) -> tuple[int, int]:
    """Rewrite URLs stored INSIDE `issues.extra`, and drop findings the collapse
    makes self-referential.

    Collapsing the page rows alone left the findings that existed *because* the
    page was duplicated — a home page reported as a near-duplicate of itself,
    citing a URL the job no longer contains (19 rows across 19 jobs, found by the
    cold sweep after the first version ran). Evidence is not just decoration
    here: for these codes it IS the finding.

    Returns (rows_rewritten, rows_deleted).
    """
    rewritten = deleted = 0
    rows = con.execute(
        "SELECT issue_id, issue_code, page_url, extra FROM issues "
        "WHERE job_id = ? AND extra IS NOT NULL AND instr(extra, ?) > 0",
        (job, bare),
    ).fetchall()
    for issue_id, code, page_url, extra in rows:
        try:
            payload = json.loads(extra)
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        changed = False
        for key in _EVIDENCE_URL_KEYS:
            v = payload.get(key)
            if not isinstance(v, list):
                continue
            seen: list[str] = []
            for item in v:
                item = slashed if item == bare else item
                if item not in seen:
                    seen.append(item)
            if seen != v:
                payload[key] = seen
                changed = True
        # A "duplicate of another page" finding whose other page was this page's
        # own second spelling is now a cluster of one. It is not a finding.
        if code in _CROSS_PAGE_DUPLICATE_CODES:
            # `near_identical_to` included: D3 stopped storing `members`, so a
            # row written after it has neither of the other two keys and would
            # slip past this guard entirely — leaving exactly the "page is a
            # near-duplicate of itself" row this rule exists to delete (P3/P13).
            partners = [u for k in ("members", "duplicate_urls", "near_identical_to")
                        for u in (payload.get(k) or []) if isinstance(u, str)]
            # Delete ONLY when the finding names no page other than this one.
            # The first version counted distinct partners and deleted anything
            # with fewer than two — which would have removed every legitimate
            # two-page duplicate, whose `duplicate_urls` holds exactly one entry.
            # Measured before the fix: 553 rows. After: only the self-references.
            own = (page_url or "").rstrip("/")
            others = {u.rstrip("/") for u in partners} - {own}
            if partners and not others:
                deleted += 1
                if apply:
                    con.execute("DELETE FROM issues WHERE issue_id = ?", (issue_id,))
                continue
        if changed:
            rewritten += 1
            if apply:
                con.execute("UPDATE issues SET extra = ? WHERE issue_id = ?",
                            (json.dumps(payload), issue_id))
    return rewritten, deleted


def _dedupe_identical(con: sqlite3.Connection, job: str, url: str,
                      *, apply: bool) -> int:
    """Drop issue rows that are byte-identical after the move.

    Re-pointing both spellings onto one URL put the same finding on the page
    twice — measured at ~450 surplus rows across the 71 collapsed jobs. Only
    IDENTICAL rows are dropped (same code AND same evidence): plenty of codes
    legitimately repeat on a page (one per image, one per link), and collapsing
    those would delete real findings.
    """
    ids = con.execute(
        """
        SELECT issue_id FROM issues
        WHERE job_id = ? AND page_url = ? AND issue_id NOT IN (
            SELECT MIN(issue_id) FROM issues
            WHERE job_id = ? AND page_url = ?
            GROUP BY issue_code, IFNULL(extra, '')
        )
        """,
        (job, url, job, url),
    ).fetchall()
    if apply and ids:
        con.executemany("DELETE FROM issues WHERE issue_id = ?", ids)
    return len(ids)


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
    # Phase 2 runs independently: after a collapse the page rows are gone but the
    # evidence inside `issues.extra` still names them, so it must be findable on
    # its own. (The first version of this script did phase 1 only, and the cold
    # sweep found 19 home pages still reported as near-duplicates of themselves.)
    stale = [t for t in _stale_evidence_jobs(con)
             if t[0] not in {j for j, _, _ in affected}]

    dupes = _duplicated_root_pages(con)

    # Decide "nothing to do" from the WORK, not from a proxy for it. The
    # stale-evidence finder over-reports (a bare URL can sit in a key this does
    # not rewrite), so keying the early exit on it made a finished database
    # report work it would not do.
    ev_rewritten = ev_deleted = 0
    for job, bare, slashed in (affected + stale):
        r, d = _repoint_evidence(con, job, bare, slashed, apply=False)
        ev_rewritten += r
        ev_deleted += d
    ev_deduped = sum(_dedupe_identical(con, j, u, apply=False) for j, u in dupes)

    if not affected and not (ev_rewritten or ev_deleted or ev_deduped):
        print("Nothing to do — no job holds both spellings of its home page, "
              "no stored evidence names a page that is gone, and no page holds "
              "the same finding twice.")
        return 0

    if affected:
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

    if ev_rewritten or ev_deleted:
        print(f"{len({j for j, _, _ in stale})} job(s) have stale evidence from an "
              f"earlier collapse.")
    print(f"Evidence: {ev_rewritten} row(s) re-pointed, {ev_deleted} self-referential "
          f"duplicate finding(s) removed, {ev_deduped} identical row(s) de-duplicated "
          f"across {len(dupes)} page(s).")

    if not args.apply:
        print("\nDry run — nothing was written. Re-run with --apply to make the change.")
        return 0

    backup = _backup(db)
    print(f"\nBacked up to {backup}")

    with con:
        for job, bare, slashed in affected:
            for key, spec in _URL_COLUMNS.items():
                table, col = _resolve(key, spec)
                try:
                    if table in _CONFLICT_SAFE:
                        # UNIQUE(job_id, page_url, field): if the slashed row
                        # already holds a fix for this field, drop the bare
                        # duplicate rather than abort the whole transaction.
                        con.execute(
                            f"DELETE FROM {table} WHERE job_id = ? AND {col} = ? "
                            f"AND field IN (SELECT field FROM {table} "
                            f"              WHERE job_id = ? AND {col} = ?)",
                            (job, bare, job, slashed))
                    con.execute(
                        f"UPDATE {table} SET {col} = ? WHERE job_id = ? AND {col} = ?",
                        (slashed, job, bare),
                    )
                except sqlite3.OperationalError:
                    continue
            con.execute("DELETE FROM crawled_pages WHERE job_id = ? AND url = ?",
                        (job, bare))
        for job, bare, slashed in (affected + stale):
            _repoint_evidence(con, job, bare, slashed, apply=True)
        for job, url in _duplicated_root_pages(con):
            _dedupe_identical(con, job, url, apply=True)
    print(f"Applied. {len(affected)} duplicate home-page row(s) collapsed; "
          f"evidence cleaned on {len({j for j, _, _ in affected + stale})} job(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

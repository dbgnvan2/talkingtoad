"""LR — collapsing the duplicate home-page rows left by pre-ND3 crawls.

Spec: docs/functional-specification.md §4.10 (LR, 2026-09-03)

ND3 made a bare origin normalise to the root path. Jobs crawled before it hold
`https://site.ca` and `https://site.ca/` as separate `crawled_pages` rows with
different issue sets — 71 jobs in the development store, 24 with a health score
1-2 points wrong, because the scorer merges the two rows' issues under
`RTRIM(page_url,'/')` and counts the page TWICE in the denominator.

Every test builds its own SQLite file under tmp_path. Nothing here touches the
real database (P28) — which matters more than usual for a migration whose whole
job is to delete rows.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from scripts.migrate_collapse_duplicate_origin_rows import main

BARE = "https://site.ca"
SLASHED = "https://site.ca/"


def _db(tmp_path: Path, *, both: bool = True) -> Path:
    """A minimal store with the columns the migration touches."""
    p = tmp_path / "t.db"
    con = sqlite3.connect(p)
    con.executescript(
        """
        CREATE TABLE crawled_pages (job_id TEXT, url TEXT);
        CREATE TABLE issues (job_id TEXT, page_url TEXT, issue_code TEXT,
                             impact INTEGER, category TEXT);
        CREATE TABLE links (job_id TEXT, source_url TEXT);
        CREATE TABLE images (job_id TEXT, page_url TEXT);
        """
    )
    pages = [("j", SLASHED), ("j", "https://site.ca/about")]
    if both:
        pages.insert(0, ("j", BARE))
    con.executemany("INSERT INTO crawled_pages VALUES (?,?)", pages)
    rows = [
        ("j", SLASHED, "TITLE_TOO_LONG", 2, "metadata"),
        ("j", "https://site.ca/about", "H1_MISSING", 4, "headings"),
    ]
    if both:
        rows += [("j", BARE, "META_DESC_TOO_LONG", 2, "metadata"),
                 ("j", BARE, "FAVICON_MISSING", 1, "metadata")]
    con.executemany("INSERT INTO issues VALUES (?,?,?,?,?)", rows)
    if both:
        con.executemany("INSERT INTO links VALUES (?,?)", [("j", BARE)])
        con.executemany("INSERT INTO images VALUES (?,?)", [("j", BARE)])
    con.commit()
    con.close()
    return p


def _snapshot(p: Path) -> dict:
    con = sqlite3.connect(p)
    out = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
           for t in ("crawled_pages", "issues", "links", "images")}
    out["pages"] = sorted(u for (u,) in con.execute("SELECT url FROM crawled_pages"))
    out["issue_urls"] = sorted(u for (u,) in con.execute("SELECT page_url FROM issues"))
    con.close()
    return out


class TestDryRunIsTheDefault:
    def test_it_writes_nothing_without_apply(self, tmp_path, capsys):
        p = _db(tmp_path)
        before = _snapshot(p)
        assert main(["--db", str(p)]) == 0
        assert _snapshot(p) == before, "a dry run modified the database"
        assert "Dry run" in capsys.readouterr().out

    def test_it_reports_what_it_would_do(self, tmp_path, capsys):
        p = _db(tmp_path)
        main(["--db", str(p)])
        out = capsys.readouterr().out
        assert "1 job(s)" in out
        assert BARE in out
        assert "health" in out, "the score consequence is not shown"


class TestApply:
    def test_the_bare_row_and_its_rows_are_collapsed(self, tmp_path):
        p = _db(tmp_path)
        assert main(["--db", str(p), "--apply"]) == 0
        after = _snapshot(p)
        assert BARE not in after["pages"], "the duplicate page row survived"
        assert SLASHED in after["pages"]
        assert BARE not in after["issue_urls"], "issues still point at the deleted row"
        # Nothing is lost — the rows moved, they were not deleted.
        assert after["issues"] == 4
        assert after["links"] == 1 and after["images"] == 1

    def test_it_backs_the_database_up_first(self, tmp_path):
        p = _db(tmp_path)
        main(["--db", str(p), "--apply"])
        backups = list(tmp_path.glob("t.db.pre-origin-collapse.*.bak"))
        assert len(backups) == 1, f"no backup written: {list(tmp_path.iterdir())}"
        assert backups[0].stat().st_size > 0
        # The backup is the PRE state, which is the only thing that makes it useful.
        assert BARE in _snapshot(backups[0])["pages"]

    def test_it_is_idempotent(self, tmp_path):
        p = _db(tmp_path)
        main(["--db", str(p), "--apply"])
        after_first = _snapshot(p)
        assert main(["--db", str(p), "--apply"]) == 0
        assert _snapshot(p) == after_first, "a second run changed something"

    def test_the_health_score_is_corrected(self, tmp_path):
        """The reason this migration exists. The scorer counts the home page
        twice in the denominator while merging both rows' issues, so the score
        is wrong until the duplicate is gone."""
        from api.services.job_store_base import compute_impact_health

        def score(path):
            con = sqlite3.connect(path)
            per_page: dict[str, list] = {}
            for norm, code, imp, cat in con.execute(
                    "SELECT RTRIM(page_url,'/'), issue_code, impact, category FROM issues"):
                per_page.setdefault(norm, []).append((code, imp or 0, cat or ""))
            urls = [u.rstrip("/") for (u,) in con.execute("SELECT url FROM crawled_pages")]
            con.close()
            return compute_impact_health(urls, per_page,
                                         {"critical": 0, "warning": 0, "info": 0})[0]

        p = _db(tmp_path)
        before = score(p)
        main(["--db", str(p), "--apply"])
        after = score(p)
        assert after != before, (
            "the score did not move — this fixture does not exercise the defect")


class TestItLeavesEverythingElseAlone:
    def test_a_job_with_only_one_spelling_is_untouched(self, tmp_path, capsys):
        p = _db(tmp_path, both=False)
        before = _snapshot(p)
        assert main(["--db", str(p), "--apply"]) == 0
        assert _snapshot(p) == before
        assert "Nothing to do" in capsys.readouterr().out
        assert not list(tmp_path.glob("*.bak")), "a no-op run still wrote a backup"

    def test_other_pages_issues_are_not_touched(self, tmp_path):
        p = _db(tmp_path)
        main(["--db", str(p), "--apply"])
        con = sqlite3.connect(p)
        n = con.execute("SELECT COUNT(*) FROM issues WHERE page_url=?",
                        ("https://site.ca/about",)).fetchone()[0]
        con.close()
        assert n == 1, "an unrelated page's issues were moved"

    def test_a_missing_database_is_an_error_not_a_crash(self, tmp_path):
        assert main(["--db", str(tmp_path / "nope.db")]) == 2

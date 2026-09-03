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

import json
import sqlite3
from pathlib import Path

import pytest

from scripts.migrate_collapse_duplicate_origin_rows import main

BARE = "https://site.ca"
SLASHED = "https://site.ca/"


# The schema below mirrors the REAL one, including `fixes`' UNIQUE index and the
# `extra` column. The first version invented a four-table schema with no `fixes`,
# no `fixed_issues`, no `extra` and no indexes — so the fixture and the
# migration's table list were written from the same mental model, agreed with
# each other and with nothing else, and structurally could not catch the two
# tables that were missing or the IntegrityError that adding them raises. That
# is the `_FakeWP` pattern from LEARNINGS, one file over (P26).
_REAL_SCHEMA = """
CREATE TABLE crawled_pages (page_id TEXT PRIMARY KEY, job_id TEXT NOT NULL,
                            url TEXT NOT NULL, status_code INTEGER NOT NULL DEFAULT 200,
                            title TEXT, meta_description TEXT);
CREATE TABLE issues (issue_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, page_id TEXT,
                     page_url TEXT, category TEXT NOT NULL DEFAULT '',
                     severity TEXT NOT NULL DEFAULT 'info',
                     issue_code TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
                     recommendation TEXT NOT NULL DEFAULT '',
                     impact INTEGER NOT NULL DEFAULT 0, extra TEXT);
CREATE TABLE links (link_id TEXT PRIMARY KEY, job_id TEXT NOT NULL,
                    source_url TEXT NOT NULL, target_url TEXT NOT NULL,
                    link_type TEXT NOT NULL DEFAULT 'internal');
CREATE TABLE images (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
                     url TEXT NOT NULL, page_url TEXT NOT NULL);
CREATE TABLE fixes (id TEXT PRIMARY KEY, job_id TEXT NOT NULL, issue_code TEXT NOT NULL,
                    page_url TEXT NOT NULL, field TEXT NOT NULL,
                    label TEXT NOT NULL DEFAULT '', proposed_value TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending');
CREATE UNIQUE INDEX idx_fixes_unique_field ON fixes(job_id, page_url, field);
CREATE TABLE fixed_issues (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
                           page_url TEXT NOT NULL, issue_code TEXT NOT NULL);
"""


def _db(tmp_path: Path, *, both: bool = True) -> Path:
    """A store whose schema mirrors the real one."""
    p = tmp_path / "t.db"
    con = sqlite3.connect(p)
    con.executescript(_REAL_SCHEMA)
    pages = [("p2", "j", SLASHED), ("p3", "j", "https://site.ca/about")]
    if both:
        pages.insert(0, ("p1", "j", BARE))
    con.executemany(
        "INSERT INTO crawled_pages (page_id,job_id,url) VALUES (?,?,?)", pages)

    def issue(iid, url, code, impact, extra=None):
        return (iid, "j", url, code, impact, json.dumps(extra) if extra else None)

    rows = [
        issue("i1", SLASHED, "TITLE_TOO_LONG", 2),
        issue("i2", "https://site.ca/about", "H1_MISSING", 4),
        # A LEGITIMATE two-page duplicate: /about names /contact, one entry.
        # Counting distinct partners and deleting anything under two would have
        # removed this — 553 such rows on the real database (cold sweep).
        issue("i3", "https://site.ca/about", "TITLE_DUPLICATE", 2,
              {"duplicate_urls": ["https://site.ca/contact"]}),
    ]
    if both:
        rows += [
            issue("i4", BARE, "META_DESC_TOO_LONG", 2),
            issue("i5", BARE, "FAVICON_MISSING", 1),
            # The self-duplicate: the home page under its two spellings.
            issue("i6", SLASHED, "NEAR_DUPLICATE_BODY", 4, {"members": [BARE, SLASHED]}),
            # The same finding recorded on both spellings — identical after the move.
            issue("i7", BARE, "FAVICON_MISSING", 1),
            # Two legitimately-repeating rows that must SURVIVE de-duplication.
            issue("i8", BARE, "IMG_ALT_MISSING", 1, {"image_url": "/a.png"}),
            issue("i9", SLASHED, "IMG_ALT_MISSING", 1, {"image_url": "/b.png"}),
        ]
    con.executemany(
        "INSERT INTO issues (issue_id,job_id,page_url,issue_code,impact,extra) "
        "VALUES (?,?,?,?,?,?)", rows)
    if both:
        con.execute("INSERT INTO links (link_id,job_id,source_url,target_url) "
                    "VALUES ('l1','j',?,?)", (BARE, "https://x.test/"))
        con.execute("INSERT INTO images (job_id,url,page_url) VALUES ('j','/a.png',?)", (BARE,))
        con.execute("INSERT INTO fixed_issues (job_id,page_url,issue_code) "
                    "VALUES ('j',?,'TITLE_TOO_LONG')", (BARE,))
        # Both spellings hold a fix for the SAME field: a plain UPDATE raises
        # IntegrityError on idx_fixes_unique_field and, inside one transaction,
        # aborts the entire migration.
        con.execute("INSERT INTO fixes (id,job_id,issue_code,page_url,field) "
                    "VALUES ('f1','j','TITLE_TOO_LONG',?, 'seo_title')", (BARE,))
        con.execute("INSERT INTO fixes (id,job_id,issue_code,page_url,field) "
                    "VALUES ('f2','j','TITLE_TOO_LONG',?, 'seo_title')", (SLASHED,))
    con.commit()
    con.close()
    return p


def _snapshot(p: Path) -> dict:
    con = sqlite3.connect(p)
    out = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
           for t in ("crawled_pages", "issues", "links", "images",
                     "fixes", "fixed_issues")}
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
        # 9 issues in, 7 out: the self-referential NEAR_DUPLICATE_BODY is gone
        # and one of the two identical FAVICON_MISSING rows is de-duplicated.
        # Everything else moved rather than vanished.
        assert after["issues"] == 7, after["issue_urls"]
        assert after["links"] == 1 and after["images"] == 1
        assert after["fixed_issues"] == 1
        # `fixes` has UNIQUE(job_id,page_url,field) and both spellings held a fix
        # for `seo_title`; the bare one is dropped rather than the whole
        # migration aborting on IntegrityError.
        assert after["fixes"] == 1

    def test_it_backs_the_database_up_first(self, tmp_path):
        p = _db(tmp_path)
        main(["--db", str(p), "--apply"])
        backups = list(tmp_path.glob("t.db.pre-origin-collapse.*.bak"))
        assert len(backups) == 1, f"no backup written: {list(tmp_path.iterdir())}"
        assert backups[0].stat().st_size > 0
        # The backup is the PRE state, which is the only thing that makes it useful.
        assert BARE in _snapshot(backups[0])["pages"]

    def test_it_is_idempotent(self, tmp_path, capsys):
        p = _db(tmp_path)
        main(["--db", str(p), "--apply"])
        after_first = _snapshot(p)
        capsys.readouterr()
        assert main(["--db", str(p), "--apply"]) == 0
        assert _snapshot(p) == after_first, "a second run changed something"
        # The row counts alone pass even when the first run did nothing, because
        # the second run is then equally a no-op (cold sweep, P27). The second
        # run must actually find nothing left to do.
        assert "Nothing to do" in capsys.readouterr().out, (
            "the second run still found work — the first did not finish")
        assert len(list(tmp_path.glob("*.bak"))) == 1, (
            "the no-op second run wrote another backup")

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
        # Direction, not just movement. `assert after != before` passed even with
        # the migration collapsing the WRONG way — keeping the bare row and
        # deleting the slashed one — which is a migration doing the opposite of
        # its purpose, green (cold sweep, P7/P27). Removing a double-counted
        # page can only raise the mean.
        assert after > before, (
            f"the score went {before} -> {after}; collapsing a duplicated page "
            f"must not lower it")


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
        assert n == 2, "an unrelated page's issues were moved or deleted"


class TestTheEvidenceIsCleanedToo:
    """Collapsing the page rows alone left the findings that existed BECAUSE the
    page was duplicated. The cold sweep found 19 home pages still reported as
    near-duplicates of themselves, citing a URL the job no longer contained —
    for these codes the evidence IS the finding, not decoration."""

    def _issues(self, p):
        con = sqlite3.connect(p)
        rows = con.execute(
            "SELECT issue_code, page_url, IFNULL(extra,'') FROM issues").fetchall()
        con.close()
        return rows

    def test_a_self_referential_duplicate_finding_is_removed(self, tmp_path):
        p = _db(tmp_path)
        main(["--db", str(p), "--apply"])
        codes = [c for c, _, _ in self._issues(p)]
        assert "NEAR_DUPLICATE_BODY" not in codes, (
            "the home page is still reported as a near-duplicate of itself")

    def test_a_legitimate_two_page_duplicate_survives(self, tmp_path):
        """The adversarial partner, and the one that matters most. The first
        version of this rule counted DISTINCT partners and deleted anything with
        fewer than two — which is every real two-page duplicate, whose
        `duplicate_urls` holds exactly one entry. Measured against the real
        database that rule would have deleted 553 rows; the correct rule (does
        the finding name any page other than this one?) deletes 73."""
        p = _db(tmp_path)
        main(["--db", str(p), "--apply"])
        rows = [(c, u) for c, u, _ in self._issues(p)]
        assert ("TITLE_DUPLICATE", "https://site.ca/about") in rows, (
            "a real duplicate between two different pages was deleted")

    def test_evidence_urls_are_repointed(self, tmp_path):
        p = _db(tmp_path)
        con = sqlite3.connect(p)
        con.execute("INSERT INTO issues (issue_id,job_id,page_url,issue_code,impact,extra) "
                    "VALUES ('i10','j',?,'TITLE_DUPLICATE',2,?)",
                    ("https://site.ca/about",
                     json.dumps({"duplicate_urls": [BARE, "https://site.ca/contact"]})))
        con.commit(); con.close()
        main(["--db", str(p), "--apply"])
        con = sqlite3.connect(p)
        extra = con.execute("SELECT extra FROM issues WHERE issue_id='i10'").fetchone()[0]
        con.close()
        urls = json.loads(extra)["duplicate_urls"]
        assert BARE not in urls, f"evidence still names the deleted page: {urls}"
        assert SLASHED in urls and "https://site.ca/contact" in urls, urls

    def test_identical_rows_are_de_duplicated(self, tmp_path):
        p = _db(tmp_path)
        main(["--db", str(p), "--apply"])
        codes = [c for c, u, _ in self._issues(p) if u == SLASHED]
        assert codes.count("FAVICON_MISSING") == 1, (
            f"the same finding is on the page twice: {codes}")

    def test_legitimately_repeating_rows_are_not_collapsed(self, tmp_path):
        """Adversarial: only IDENTICAL rows are dropped. Plenty of codes repeat
        on a page — one per image, one per link — and collapsing those by code
        alone would delete real findings."""
        p = _db(tmp_path)
        main(["--db", str(p), "--apply"])
        codes = [c for c, u, _ in self._issues(p) if u == SLASHED]
        assert codes.count("IMG_ALT_MISSING") == 2, (
            f"two different images collapsed into one finding: {codes}")

    def test_a_missing_database_is_an_error_not_a_crash(self, tmp_path):
        assert main(["--db", str(tmp_path / "nope.db")]) == 2

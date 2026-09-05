"""§1 — re-keying the misfiled ledger rows onto the crawled-page key.

Spec: docs/pending/2026-09-05_deferral-sweep.md §1

Every test builds its own database under `tmp_path` through the REAL store, so
the schema is the shipped one by construction — including `gsc_top_queries`,
which arrives via the `ALTER TABLE` migration loop and not the base DDL. A
hand-copied schema would have been written from the same mental model as the
migration, agreed with it, and structurally could not catch a column either of
them forgot (the lesson `test_migrate_duplicate_origin_rows.py` records, and the
reason `recorded_at` is asserted below).

Nothing here touches `talkingtoad.db` (P28).
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest

from scripts.migrate_rekey_performance_ledger import (
    _crawled_key_map,
    apply_moves,
    main,
    plan,
)

SITE = "https://site.ca"


def _fresh(tmp_path: Path) -> Path:
    """A database whose schema is built by the store itself, not transcribed."""
    from api.services.job_store import SQLiteJobStore

    p = tmp_path / "t.db"

    async def build():
        async with SQLiteJobStore(db_path=str(p)):
            pass

    asyncio.run(build())
    return p


def _pages(db: sqlite3.Connection, *urls: str) -> None:
    """One row per url per job. `crawled_pages` is UNIQUE(job_id, url), so a
    spelling repeats only across jobs — which is precisely how the development
    store came to hold 26 rows for one spelling of the home page and 3 for
    another."""
    db.executemany(
        "INSERT INTO crawled_pages (page_id, job_id, url, status_code, crawled_at) "
        "VALUES (?, ?, ?, 200, '2026-08-01T00:00:00Z')",
        [(f"p{i}", f"j{i}", u) for i, u in enumerate(urls)],
    )


def _ledger(db: sqlite3.Connection, url: str, period="2026-08", *,
            clicks=0, imps=0, ctr=0.0, pos=0.0, recorded="2026-08-01T00:00:00Z",
            queries=None) -> None:
    db.execute(
        "INSERT INTO performance_ledger (url, period, gsc_clicks_mo, "
        "gsc_impressions_mo, gsc_ctr_mo, gsc_avg_position_mo, recorded_at, "
        "gsc_top_queries) VALUES (?,?,?,?,?,?,?,?)",
        (url, period, clicks, imps, ctr, pos, recorded, queries),
    )


def _row(db: sqlite3.Connection, url: str, period="2026-08"):
    db.row_factory = sqlite3.Row
    return db.execute(
        "SELECT * FROM performance_ledger WHERE url = ? AND period = ?",
        (url, period),
    ).fetchone()


def _run(path: Path) -> None:
    db = sqlite3.connect(path)
    moves, _ = plan(db)
    apply_moves(db, moves)
    db.commit()
    db.close()


# ── 3.1–3.3: what it moves, what it merges, what it leaves ──────────────────


class TestWhatItTouches:
    def test_recoverable_rows_are_re_keyed_not_deleted(self, tmp_path):
        """3.1 — the whole point: the row becomes readable, and still exists."""
        p = _fresh(tmp_path)
        db = sqlite3.connect(p)
        _pages(db, f"{SITE}/about")
        _ledger(db, f"{SITE}/about/", clicks=12, imps=400)
        db.commit()
        db.close()

        _run(p)

        db = sqlite3.connect(p)
        assert db.execute("SELECT COUNT(*) FROM performance_ledger").fetchone()[0] == 1, (
            "a row was lost — this migration may re-key or leave alone, never delete"
        )
        moved = _row(db, f"{SITE}/about")
        assert moved is not None, "the row is still unreadable by the consumers"
        assert moved["gsc_clicks_mo"] == 12

    def test_rows_matching_no_crawled_page_are_left_alone(self, tmp_path):
        """3.3 — nothing establishes which page they belong to, so inventing a
        key would be the fabrication this repo keeps refusing."""
        p = _fresh(tmp_path)
        db = sqlite3.connect(p)
        _pages(db, f"{SITE}/about")
        _ledger(db, "https://elsewhere.test/gone/", clicks=9)
        db.commit()
        db.close()

        _run(p)

        db = sqlite3.connect(p)
        assert _row(db, "https://elsewhere.test/gone/") is not None, (
            "an unmatched row was moved or dropped"
        )
        assert db.execute("SELECT COUNT(*) FROM performance_ledger").fetchone()[0] == 1

    def test_a_collision_merges_by_the_same_rule_as_the_fold(self, tmp_path):
        """3.2 — the case that can lose data.

        The numbers are chosen so summing, averaging the rates, and taking
        EITHER row wholesale all give different answers; with round numbers the
        assertion cannot tell a merge from an overwrite.

            slice A: 100 clicks / 1000 imps, ctr 0.1,    position 5
            slice B:  50 clicks / 4000 imps, ctr 0.0125, position 20

            summed:            150 / 5000 -> ctr 0.03, position 17.0
            mean of the rates:                   0.05625,          12.5
            either wholesale:               0.1 or 0.0125,     5 or 20
        """
        p = _fresh(tmp_path)
        db = sqlite3.connect(p)
        _pages(db, f"{SITE}/a")
        _ledger(db, f"{SITE}/a", clicks=100, imps=1000, ctr=0.1, pos=5.0)
        _ledger(db, f"{SITE}/a/", clicks=50, imps=4000, ctr=0.0125, pos=20.0)
        db.commit()
        db.close()

        _run(p)

        db = sqlite3.connect(p)
        r = _row(db, f"{SITE}/a")
        assert r["gsc_clicks_mo"] == 150, f"clicks were discarded, not summed: {r['gsc_clicks_mo']}"
        assert r["gsc_impressions_mo"] == 5000
        assert r["gsc_ctr_mo"] == pytest.approx(0.03), (
            "the CTR is not the summed parts — an averaged or inherited rate"
        )
        assert r["gsc_avg_position_mo"] == pytest.approx(17.0), (
            "the position is not impression-weighted"
        )
        assert db.execute("SELECT COUNT(*) FROM performance_ledger").fetchone()[0] == 1

    def test_a_merge_keeps_the_columns_it_does_not_compute(self, tmp_path):
        """`recorded_at` is written by the store on every ledger write and read
        by page_priority for freshness. It is not summed, weighted or derived —
        which is exactly why a merge that only handles the arithmetic columns
        silently blanks it. Found by writing this test, not by reading the code.
        """
        p = _fresh(tmp_path)
        db = sqlite3.connect(p)
        _pages(db, f"{SITE}/a")
        _ledger(db, f"{SITE}/a/", clicks=5, imps=100, recorded="2026-08-30T12:00:00Z",
                queries='[{"query": "grief support", "impressions": 90}]')
        db.commit()
        db.close()

        _run(p)

        db = sqlite3.connect(p)
        r = _row(db, f"{SITE}/a")
        assert r["recorded_at"] == "2026-08-30T12:00:00Z", (
            "the row lost its freshness stamp in the move — page_priority reads it"
        )
        assert r["gsc_top_queries"] and "grief support" in r["gsc_top_queries"], (
            "P8.4's per-page queries did not survive the re-key"
        )

    def test_a_merge_folds_the_queries_instead_of_taking_one_slice(self, tmp_path):
        """The defect that made this script call `fold_performance_rows` instead
        of paraphrasing it.

        The hand-rolled merge summed clicks correctly and took `gsc_top_queries`
        from whichever row had a value first — so the query striking distance
        names in its rewrite brief came from one slice of the page's traffic.
        The inputs are chosen so summing and taking-one-slice give a different
        ORDER, not merely a different number: A leads with Q2, B leads with Q1,
        and Q1 wins on the sum (150+400 vs 300+50).
        """
        p = _fresh(tmp_path)
        db = sqlite3.connect(p)
        _pages(db, f"{SITE}/a")
        _ledger(db, f"{SITE}/a", clicks=1, imps=500, recorded="2026-08-02T00:00:00Z",
                queries='[{"query": "q2", "impressions": 300}, '
                        '{"query": "q1", "impressions": 150}]')
        _ledger(db, f"{SITE}/a/", clicks=1, imps=400, recorded="2026-08-01T00:00:00Z",
                queries='[{"query": "q1", "impressions": 400}, '
                        '{"query": "q2", "impressions": 50}]')
        db.commit()
        db.close()

        _run(p)

        db = sqlite3.connect(p)
        queries = json.loads(_row(db, f"{SITE}/a")["gsc_top_queries"])
        assert [q["query"] for q in queries] == ["q1", "q2"], (
            f"the queries came from one slice instead of being summed: {queries}"
        )
        assert queries[0]["impressions"] == 550

    def test_the_earliest_first_seen_date_survives(self, tmp_path):
        """`created_at` is a first-seen date. Taking it from whichever row the
        fold happens to base itself on can move a page's history forward in
        time, which is the field quietly saying something false."""
        p = _fresh(tmp_path)
        db = sqlite3.connect(p)
        _pages(db, f"{SITE}/a")
        db.execute("INSERT INTO performance_ledger (url, period, created_at, recorded_at) "
                   "VALUES (?, '2026-08', '2024-01-01', '2026-08-09T00:00:00Z')",
                   (f"{SITE}/a",))
        db.execute("INSERT INTO performance_ledger (url, period, created_at, recorded_at) "
                   "VALUES (?, '2026-08', '2025-06-01', '2026-08-01T00:00:00Z')",
                   (f"{SITE}/a/",))
        db.commit()
        db.close()

        _run(p)

        db = sqlite3.connect(p)
        assert _row(db, f"{SITE}/a")["created_at"] == "2024-01-01"


# ── 3.4–3.5: run it twice, and run it by accident ───────────────────────────


class TestRunningItAgain:
    def test_the_migration_is_idempotent(self, tmp_path):
        """3.4 — this is the kind of migration that gets run twice: once in
        dry-run, once for real, and later by someone unsure whether it ran."""
        p = _fresh(tmp_path)
        db = sqlite3.connect(p)
        _pages(db, f"{SITE}/a")
        _ledger(db, f"{SITE}/a", clicks=100, imps=1000)
        _ledger(db, f"{SITE}/a/", clicks=50, imps=4000)
        db.commit()
        db.close()

        _run(p)
        _run(p)

        db = sqlite3.connect(p)
        r = _row(db, f"{SITE}/a")
        assert r["gsc_clicks_mo"] == 150, (
            f"the second pass double-counted: {r['gsc_clicks_mo']}"
        )
        moves, _ = plan(sqlite3.connect(p))
        assert moves == [], f"a third run would still move rows: {moves}"

    def test_dry_run_writes_nothing(self, tmp_path, capsys, monkeypatch):
        """3.5 — the default must be safe. Asserted on the bytes, because a
        migration that wrote and then reported honestly would still have written.
        """
        p = _fresh(tmp_path)
        db = sqlite3.connect(p)
        _pages(db, f"{SITE}/a")
        _ledger(db, f"{SITE}/a/", clicks=5, imps=100)
        db.commit()
        db.close()

        before = p.read_bytes()
        monkeypatch.setattr("sys.argv", ["m", "--db", str(p)])
        assert main() == 0
        assert p.read_bytes() == before, "the dry run modified the database"
        assert "DRY RUN" in capsys.readouterr().out
        assert not list(tmp_path.glob("*.bak")), "the dry run took a backup it did not need"


# ── The ambiguity the first dry run exposed ─────────────────────────────────


class TestTheTargetIsChosen:
    """One logical page, several crawled spellings.

    The first version of `_crawled_key_map` wrote `out[key] = url` in cursor
    order, so the target was whichever row the query happened to yield last. On
    the development store that sent the livingsystems.ca home page's GSC data to
    `https://www.livingsystems.ca` (3 page rows) instead of
    `https://livingsystems.ca` (26). It was caught by reading the dry run's
    sample, not by review — so it is pinned here.

    Each test asserts the SAME answer under both insertion orders. One ordering
    alone cannot tell a rule from an accident: a last-wins map passes whichever
    ordering happens to suit it.
    """

    @pytest.mark.parametrize("reverse", [False, True], ids=["as-inserted", "reversed"])
    def test_the_majority_spelling_wins(self, tmp_path, reverse):
        p = _fresh(tmp_path)
        db = sqlite3.connect(p)
        urls = [f"https://www.site.ca"] * 3 + [SITE] * 26
        _pages(db, *(reversed(urls) if reverse else urls))
        db.commit()

        assert _crawled_key_map(db)["//site.ca/"] == SITE, (
            "the target is the spelling the fewest crawled pages use — a choice "
            "made by iteration order rather than by a rule"
        )

    @pytest.mark.parametrize("reverse", [False, True], ids=["as-inserted", "reversed"])
    def test_a_tie_resolves_the_same_way_every_run(self, tmp_path, reverse):
        """Equal counts is the case where "most used" says nothing. Shortest,
        then lexicographic — stable across runs and machines, not merely
        deterministic-looking."""
        p = _fresh(tmp_path)
        db = sqlite3.connect(p)
        urls = [SITE, "https://www.site.ca"]
        _pages(db, *(reversed(urls) if reverse else urls))
        db.commit()

        assert _crawled_key_map(db)["//site.ca/"] == SITE

    def test_the_ledger_row_follows_the_chosen_target(self, tmp_path):
        """The map is internal; this is the behaviour that matters — the data
        lands where the pages actually are."""
        p = _fresh(tmp_path)
        db = sqlite3.connect(p)
        _pages(db, "https://www.site.ca", *([SITE] * 5))
        _ledger(db, "http://site.ca/", clicks=41, imps=900)
        db.commit()
        db.close()

        _run(p)

        db = sqlite3.connect(p)
        assert _row(db, SITE)["gsc_clicks_mo"] == 41
        assert _row(db, "https://www.site.ca") is None, (
            "the data went to the minority spelling"
        )

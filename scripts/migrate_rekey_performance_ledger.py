#!/usr/bin/env python3
"""Re-key performance-ledger rows onto the crawled-page key they belong to.

Spec: docs/pending/2026-09-05_deferral-sweep.md §1

Before P6.3 (2026-09-04), `/api/gsc/ingest` stored a GSC row under its RAW url
when the join to a crawled page failed. `match_key` folds www / scheme /
trailing slash, so the join failing did not mean the page was absent — it meant
the URL was spelled differently. The consumers (striking distance,
page-priority, the Authority Matrix) all look rows up by the crawled page's
EXACT url, so those rows are unreadable.

Measured on the development store when this was written:

    distinct ledger urls:                        344
      stored under the crawled-page key already:  37
      would match a crawled page via match_key:  242   <- read by nothing
      genuinely match no crawled page:            65

This was deferred on 2026-09-04 as "invisible rather than wrong". The first half
was true. The second was not: it is performance data for pages that exist, and
the app behaves as if it never arrived.

What this does NOT do:

  * It does not delete. A row is re-keyed or left alone.
  * It does not touch the 65 rows matching no crawled page. Nothing establishes
    which page they belong to, and inventing a key is the fabrication this
    codebase keeps refusing.
  * It does not rewrite anything derived. Scores are computed from rows on read.

Collisions MERGE. Re-keying can land on an occupied `(url, period)`, and taking
either row wholesale would discard the other's clicks — two rows for one page in
one period are two slices of it, so counts add, rates are recomputed and the
average position is impression-weighted. That is P6.3's arithmetic, reused
rather than re-invented.

    python scripts/migrate_rekey_performance_ledger.py            # dry run
    python scripts/migrate_rekey_performance_ledger.py --apply    # write

Dry run is the default and writes nothing. `--apply` backs the database up first
and refuses to proceed if the backup cannot be written. Idempotent — a second
run finds nothing to do, which matters because a migration like this gets run
once in dry-run, once for real, and again by someone unsure whether it ran.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.models.performance import PerformanceRecord  # noqa: E402
from api.services.perf_join import fold_performance_rows, match_key  # noqa: E402

# Every ledger column the record models, taken from the model so this cannot
# become a fourth hand-kept list of the same fields.
_COLS = tuple(PerformanceRecord.model_fields)
_VALUE_COLS = tuple(c for c in _COLS if c not in ("url", "period"))


def _crawled_key_map(db: sqlite3.Connection) -> dict[str, str]:
    """match_key(crawled url) -> the crawled page's exact url.

    The same logical page can exist under several spellings across jobs — the
    development store has three keys like that, one with
    `https://livingsystems.ca` (26 page rows), `https://livingsystems.ca/` and
    `https://www.livingsystems.ca` (3). A naive `out[key] = url` takes whichever
    the cursor yields last, which is a choice made by iteration order rather
    than by a rule; the first dry run of this script picked the 3-row spelling
    over the 26-row one, and the sample output is what exposed it.

    The target is the spelling the MOST crawled pages actually use, because the
    consumers look rows up by the url on the page row in front of them — so that
    maximises the rows that become readable. Ties break on shortest-then-
    lexicographic, so the result is stable across runs and machines rather than
    merely deterministic-looking.
    """
    counts: dict[str, dict[str, int]] = {}
    for url, n in db.execute(
        "SELECT url, COUNT(*) FROM crawled_pages GROUP BY url"
    ):
        try:
            key = match_key(url)
        except Exception:  # noqa: BLE001 — an unparseable stored url is skipped, not fatal
            continue
        counts.setdefault(key, {})[url] = n
    return {
        key: sorted(spellings, key=lambda u: (-spellings[u], len(u), u))[0]
        for key, spellings in counts.items()
    }


def _read(db: sqlite3.Connection, url: str, period: str) -> PerformanceRecord | None:
    row = db.execute(
        f"SELECT {', '.join(_COLS)} FROM performance_ledger WHERE url = ? AND period = ?",
        (url, period),
    ).fetchone()
    if row is None:
        return None
    data = dict(zip(_COLS, row))
    data["gsc_top_queries"] = json.loads(data["gsc_top_queries"] or "null")
    return PerformanceRecord(**data)


def _merge(target: str, recs: list[PerformanceRecord]) -> PerformanceRecord:
    """One record for one (url, period), by the SHIPPED fold.

    The first draft of this script re-implemented P6.3's arithmetic here. It
    summed the counts and weighted the position correctly and still got
    `gsc_top_queries` wrong — taking one slice's list where `fold_performance_rows`
    sums each query's impressions across slices. Two implementations of one rule
    is P13, and the copy had already drifted before it shipped. So this calls
    the real one.

    The fold reasons about counts, rates and queries. It takes every remaining
    scalar from its FIRST record, which in the ingest path is arbitrary because
    those rows are written together in one pass. Here they were written at
    different times, so the order is chosen rather than inherited: freshest
    `recorded_at` first, so `index_state` and `source_generated_at` come from the
    most recent slice. The two date fields the fold does not reason about are
    then settled explicitly — `created_at` is a first-seen date, so the EARLIEST
    is the true one, and `last_technical_improvement_at` is a most-recent date.
    """
    ordered = sorted(recs, key=lambda r: (r.recorded_at is None, r.recorded_at or ""),
                     reverse=False)
    ordered = sorted(ordered, key=lambda r: r.recorded_at or "", reverse=True)
    merged, _folded = fold_performance_rows(
        [(target, r.url, r) for r in ordered]
    )
    out = merged[0].model_copy(deep=True)
    out.url = target
    firsts = [r.created_at for r in recs if r.created_at]
    lasts = [r.last_technical_improvement_at for r in recs
             if r.last_technical_improvement_at]
    out.created_at = min(firsts) if firsts else None
    out.last_technical_improvement_at = max(lasts) if lasts else None
    if out.recorded_at is None:
        stamps = [r.recorded_at for r in recs if r.recorded_at]
        out.recorded_at = max(stamps) if stamps else None
    return out


def plan(db: sqlite3.Connection) -> tuple[list[tuple[str, str, str]], dict[str, int]]:
    """Return (moves, counts). A move is (old_url, new_url, period)."""
    db.row_factory = sqlite3.Row
    crawled = _crawled_key_map(db)
    exact = set(crawled.values())

    moves: list[tuple[str, str, str]] = []
    counts = {"already_keyed": 0, "recoverable": 0, "unmatched": 0}
    for row in db.execute("SELECT url, period FROM performance_ledger"):
        url, period = row["url"], row["period"]
        if url in exact:
            counts["already_keyed"] += 1
            continue
        try:
            key = match_key(url)
        except Exception:  # noqa: BLE001
            counts["unmatched"] += 1
            continue
        target = crawled.get(key)
        if target is None or target == url:
            counts["unmatched"] += 1
            continue
        counts["recoverable"] += 1
        moves.append((url, target, period))
    return moves, counts


def apply_moves(db: sqlite3.Connection, moves: list[tuple[str, str, str]]) -> int:
    by_target: dict[tuple[str, str], list[str]] = defaultdict(list)
    for old, new, period in moves:
        by_target[(new, period)].append(old)

    written = 0
    for (target, period), olds in by_target.items():
        recs = [r for r in (_read(db, u, period) for u in [target, *olds]) if r is not None]
        if not recs:
            continue
        merged = _merge(target, recs)
        values = merged.model_dump()
        values["gsc_top_queries"] = (
            json.dumps(values["gsc_top_queries"]) if values["gsc_top_queries"] else None
        )
        db.execute(
            "INSERT INTO performance_ledger (url, period) VALUES (?, ?) "
            "ON CONFLICT(url, period) DO NOTHING",
            (target, period),
        )
        db.execute(
            f"UPDATE performance_ledger SET {', '.join(f'{c} = ?' for c in _VALUE_COLS)} "
            f"WHERE url = ? AND period = ?",
            (*(values[c] for c in _VALUE_COLS), target, period),
        )
        for u in olds:
            db.execute(
                "DELETE FROM performance_ledger WHERE url = ? AND period = ?", (u, period))
        written += 1
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="talkingtoad.db")
    ap.add_argument("--apply", action="store_true",
                    help="write the changes (default is a dry run that writes nothing)")
    args = ap.parse_args()

    path = Path(args.db)
    if not path.exists():
        print(f"no database at {path}")
        return 1

    db = sqlite3.connect(path)
    moves, counts = plan(db)

    print(f"database: {path}")
    print(f"  ledger rows already on the crawled-page key: {counts['already_keyed']}")
    print(f"  recoverable (misfiled, readable by nothing): {counts['recoverable']}")
    print(f"  matching no crawled page — LEFT ALONE:       {counts['unmatched']}")
    targets = {(n, p) for _o, n, p in moves}
    print(f"  rows to move: {len(moves)} onto {len(targets)} (url, period) keys")

    collisions = [
        (n, p) for (n, p) in targets
        if db.execute("SELECT 1 FROM performance_ledger WHERE url = ? AND period = ?",
                      (n, p)).fetchone()
    ]
    print(f"  of those, keys that ALREADY hold a row (will merge): {len(collisions)}")

    if moves:
        print("\n  sample:")
        for old, new, period in moves[:5]:
            print(f"    {period}  {old}\n           -> {new}")

    if not args.apply:
        print("\nDRY RUN — nothing written. Re-run with --apply to write.")
        return 0

    backup = path.with_suffix(f".pre-rekey-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.bak")
    try:
        shutil.copy2(path, backup)
    except OSError as exc:
        print(f"refusing to apply: could not write backup {backup}: {exc}")
        return 1
    print(f"\nbackup: {backup}")

    written = apply_moves(db, moves)
    db.commit()
    print(f"applied: {written} (url, period) keys written, {len(moves)} rows re-keyed")

    after, _ = plan(db)
    print(f"re-run finds {len(after)} rows to move (idempotent if 0)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

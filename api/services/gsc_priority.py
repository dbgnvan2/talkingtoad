"""GSC priority-pages upload — parse & validate the sibling GSC app's
`priority_pages.json` into a normalized seed.

The seed feeds two things (one uploaded file, both flows):
  (ii) crawl prioritisation — `pages[]` in file order = priority order.
  (i)  the Performance Ledger — per-page GSC metrics for Page Priority ranking.

Purpose: turn the GSC file into a domain-guarded, normalized seed; hold out
         off-domain/blank rows honestly (announce "used N of M"), never crash.
Spec:    docs/pending/2026-08-14_gsc-performance-handoff-plan.md  (§3 contract, U1)
Tests:   tests/test_priority_upload.py

Contract (the real file, reconciled 2026-08-14):
  {generated_for, site(bare host), count, pages:[
     {url(abs), path, clicks(int), impressions(int), avg_position(float),
      top_queries:[str], inquiries(int)}]}
CTR is not supplied — derived here as clicks/impressions.
"""

from __future__ import annotations

from api.crawler.normaliser import is_same_domain


class PriorityUploadError(ValueError):
    """The uploaded file is unusable (wrong shape, or no rows for this domain)."""


def _int(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _float(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _int_or_none(v):
    """Nullable coercion — absent/None/unparseable stays None. Used for GSC numeric
    fields where a *missing* value must not be written as a definitive 0 (which
    would (a) mistake unknown for measured-zero on ranking, and (b) wipe a prior
    ledger row's real value on write — P2/P5)."""
    if v is None:
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _float_or_none(v):
    """Nullable float coercion (see _int_or_none)."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_priority_upload(raw, target_url: str) -> dict:
    """Parse a GSC `priority_pages.json` object against the scan's ``target_url``.

    Returns a normalized seed dict; raises ``PriorityUploadError`` if the file is
    the wrong shape or has no page that belongs to this scan's domain (a strong
    signal it's the wrong site's file). Off-domain / blank-url rows are held out
    and counted, not fatal (P2 — surface, don't silently drop)."""
    if not isinstance(raw, dict):
        raise PriorityUploadError("The priority file must be a JSON object.")
    # `generated_for` is the GSC app's signature. Reject a file another tool
    # stamped with a different value; an ABSENT marker is tolerated (the per-URL
    # domain guard below is the primary protection — a softening of §3 for
    # robustness against future producers that omit the header).
    gf = raw.get("generated_for")
    if gf is not None and gf != "talkingtoad":
        raise PriorityUploadError(
            f"This priority file was produced for '{gf}', not TalkingToad.")
    pages_in = raw.get("pages")
    if not isinstance(pages_in, list) or not pages_in:
        raise PriorityUploadError("The priority file has no 'pages' list.")

    seed_pages: list[dict] = []
    held_out_offdomain = 0
    held_out_blank = 0
    for row in pages_in:
        if not isinstance(row, dict):
            held_out_blank += 1
            continue
        url = (row.get("url") or "").strip()
        if not url:
            held_out_blank += 1
            continue
        try:
            same = is_same_domain(url, target_url)
        except Exception:
            same = False
        if not same:
            held_out_offdomain += 1
            continue
        # GSC numeric fields are NULLABLE: a *missing* field stays None so the
        # ledger write carries forward any prior real value instead of clobbering
        # it with a spurious 0 (P5 — match the bundle ingest's read-merge). A
        # present 0 is a real measured zero. F9 always emits these, so None is the
        # partial/hand-edited-file edge.
        clicks = _int_or_none(row.get("clicks"))
        impressions = _int_or_none(row.get("impressions"))
        if clicks is None:
            ctr = None                                   # unknown clicks → unknown ctr
        elif impressions:
            ctr = clicks / impressions                   # derived (§3)
        else:
            ctr = 0.0                                     # measured 0 impressions → 0 ctr
        seed_pages.append({
            "url": url,
            "clicks": clicks,
            "impressions": impressions,
            "ctr": ctr,
            "position": _float_or_none(row.get("avg_position")),    # avg_position → position
            "conversions": _int_or_none(row.get("inquiries")),      # inquiries → conversions
            "top_queries": [q for q in (row.get("top_queries") or []) if isinstance(q, str)],
        })

    if not seed_pages:
        raise PriorityUploadError(
            "No priority pages matched this scan's domain — is this the right "
            "site's priority file?")

    return {
        "generated_for": raw.get("generated_for"),
        "site": raw.get("site"),
        "count_claimed": raw.get("count"),
        "pages": seed_pages,                 # file order == priority order (ii)
        "used": len(seed_pages),
        "total": len(pages_in),
        "held_out_offdomain": held_out_offdomain,
        "held_out_blank": held_out_blank,
    }


def seed_urls(parsed: dict) -> list[str]:
    """The ordered priority URL list (ii) — highest priority first."""
    return [p["url"] for p in parsed.get("pages", [])]


def _seed_omits_gsc_field(parsed: dict) -> bool:
    """True if any seed page left a GSC numeric field absent (None) — the only
    case that needs a read-merge (F9 full files never do, so the common path is a
    cheap no-op)."""
    return any(
        p.get("clicks") is None or p.get("impressions") is None or p.get("position") is None
        for p in parsed.get("pages", [])
    )


async def build_existing_merge_map(store, crawled_pages, parsed: dict, period: str) -> dict:
    """Prior same-period ledger rows keyed by the crawled-page url, for the F3
    read-merge. Returns ``{}`` (NO store reads) unless the upload omitted a GSC
    field. Reads are restricted to crawled pages that are actually in the seed
    (F3 efficiency), and scoped to ``period`` (a carry-forward only makes sense
    within the same month). Extracted so the gate/period/keying is unit-testable."""
    if not _seed_omits_gsc_field(parsed):
        return {}
    from api.services.perf_join import match_key

    seed_keys: set[str] = set()
    for p in parsed.get("pages", []):
        try:
            seed_keys.add(match_key(p["url"]))
        except ValueError:
            continue
    out: dict = {}
    for pg in crawled_pages:
        try:
            if match_key(pg.url) not in seed_keys:
                continue
        except ValueError:
            continue
        prior = [r for r in await store.get_performance_records(url=pg.url)
                 if r.period == period]
        if prior:
            out[pg.url] = prior[-1]
    return out


def build_ledger_records(parsed: dict, crawled_pages, *, period: str, recorded_at: str,
                         existing_by_key: dict | None = None):
    """Join the seed's per-page metrics onto crawled pages → PerformanceRecords (i).

    Uses the same www/scheme/slash-tolerant join as ``/api/performance/ingest``
    (`match_key`/`build_crawled_key_map`). A seed page that wasn't crawled has no
    page to attach to and is skipped (it simply never enters the ledger). ``period``
    and ``recorded_at`` come from the upload time (D-N4 — freshness from upload).
    ``inquiries`` are GA4 key events per page, so they map to ``ga4_conversions_mo``.

    ``existing_by_key`` (optional): prior PerformanceRecords keyed by storage_key
    for the SAME period. When the upload OMITS a GSC field (parsed as None), the
    prior real value is carried forward instead of being overwritten with 0 — the
    same read-merge the bundle ingest does, so a partial file can't wipe traffic
    (P5). Absent → 0 only when there is no prior row.
    """
    # Local imports keep this module import-light and avoid any cycle.
    from api.models.performance import PerformanceRecord
    from api.services.perf_join import build_crawled_key_map, match_key

    existing_by_key = existing_by_key or {}
    key_map = build_crawled_key_map(crawled_pages)
    records: list = []
    for p in parsed.get("pages", []):
        try:
            k = match_key(p["url"])
        except ValueError:
            continue
        storage_key = key_map.get(k)
        if storage_key is None:
            continue  # seed URL wasn't crawled — nothing to attach metrics to
        prior = existing_by_key.get(storage_key)
        # Resolve clicks/impressions/position per-field (present → use it; absent →
        # carry prior, else 0), THEN derive ctr from the RESOLVED clicks/impressions
        # so a mixed-null row (e.g. clicks present, impressions carried) can never
        # store a ctr inconsistent with its own clicks/impressions (F1).
        clicks = p["clicks"] if p["clicks"] is not None else (prior.gsc_clicks_mo if prior else 0)
        impressions = (p["impressions"] if p["impressions"] is not None
                       else (prior.gsc_impressions_mo if prior else 0))
        position = (p["position"] if p["position"] is not None
                    else (prior.gsc_avg_position_mo if prior else 0.0))
        records.append(PerformanceRecord(
            url=storage_key,
            period=period,
            gsc_clicks_mo=clicks,
            gsc_impressions_mo=impressions,
            gsc_ctr_mo=(clicks / impressions) if impressions else 0.0,
            gsc_avg_position_mo=position,
            ga4_conversions_mo=p["conversions"],   # GSC "inquiries" = GA4 key events
            recorded_at=recorded_at,
            source_generated_at=recorded_at,
        ))
    return records

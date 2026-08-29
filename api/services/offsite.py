"""D1 — off-site authority, joined to the crawl.

Purpose: turn Search Console's Links report into findings only a tool holding
         BOTH the link data and the crawl can produce.
Spec:    docs/pending/2026-08-29_D1-off-site-authority.md
Tests:   tests/test_offsite.py

**Why there is no backlink-index integration here.** Renting Semrush/Ahrefs/Moz
is a recurring cost with a per-customer key, and a per-customer key is the parked
multi-tenant work (`docs/TODO-MULTITENANT.md`). Declining that was the right call.
But "we can't buy the third-party estimate" was never the same as "off-site is out
of reach": Search Console reports referring domains, top linking sites and top
linked pages for free, inside the OAuth scope the producer app already holds. So
this consumes a Performance Bundle section rather than calling a vendor.

**The join is worth more than the number.** An Authority Score is a number you can
read anywhere. These three are not:

    Earned authority, poor health  A page with real incoming links and fixable
                                   defects is the highest-leverage work on the site.
    Links to a broken target       An external site pointing at a URL that 404s is
                                   link equity being thrown away, and a redirect
                                   recovers it. Neither an analytics export nor a
                                   backlink tool can find this alone — it needs the
                                   crawl's broken-link set.
    Orphaned authority             A linked page the crawl found disconnected is
                                   authority the site is not circulating internally.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Display caps. The uncapped total always travels alongside (rule 6).
_SITE_LIST_CAP = int(os.getenv("TT_OFFSITE_SITE_CAP", "20"))

# A page needs at least this many incoming links before "earned authority" means
# anything — one stray link from a scraper is not authority.
_MIN_INCOMING = int(os.getenv("TT_OFFSITE_MIN_INCOMING", "2"))

# Below this health score, a linked page is worth surfacing as leverage.
_LEVERAGE_HEALTH = int(os.getenv("TT_OFFSITE_LEVERAGE_HEALTH", "80"))


@dataclass
class OffsiteReport:
    referring_domains: int | None = None
    total_external_links: int | None = None
    top_linking_sites: list[dict] = field(default_factory=list)
    top_linking_sites_total: int = 0
    # The three joins.
    earned_authority_poor_health: list[dict] = field(default_factory=list)
    links_to_broken_targets: list[dict] = field(default_factory=list)
    orphaned_authority: list[dict] = field(default_factory=list)
    pages_matched: int = 0
    pages_in_report: int = 0

    @property
    def has_data(self) -> bool:
        return bool(self.top_linking_sites or self.referring_domains
                    or self.total_external_links or self.pages_in_report)


def build_offsite(
    links: dict | None,
    ranked_pages: list[dict],
    *,
    broken_target_urls: set[str] | None = None,
    orphan_urls: set[str] | None = None,
) -> OffsiteReport | None:
    """Join the Links report to the crawl. ``None`` when no links were supplied.

    ``None`` means "not supplied" — the caller must omit the section and record
    the omission rather than rendering zeros, which would read as "nobody links
    to you" (P2).
    """
    if not links:
        return None

    from api.services.page_priority import ledger_key

    sites = list(links.get("top_linking_sites") or [])
    report = OffsiteReport(
        referring_domains=links.get("referring_domains"),
        total_external_links=links.get("total_external_links"),
        top_linking_sites=sites[:_SITE_LIST_CAP],
        top_linking_sites_total=len(sites),
    )

    linked_pages = list(links.get("top_linked_pages") or [])
    report.pages_in_report = len(linked_pages)
    if not linked_pages:
        return report

    # Same join key as the ledger. An exact match silently lost 96% of the
    # Performance Ledger before E3's fix; repeating that here would be the same
    # bug in a new place (P5).
    health_by_key = {ledger_key(p["url"]): p for p in ranked_pages if p.get("url")}
    broken_keys = {ledger_key(u) for u in (broken_target_urls or set())}
    orphan_keys = {ledger_key(u) for u in (orphan_urls or set())}

    for entry in linked_pages:
        url = entry.get("url")
        if not url:
            continue
        key = ledger_key(url)
        incoming = int(entry.get("incoming_links") or 0)

        # Join 1 — an external site links to a URL that is broken. This one is
        # worth the whole feature: the link exists, the equity is being discarded,
        # and a one-hop redirect recovers it.
        if key in broken_keys:
            report.links_to_broken_targets.append({
                "url": url, "incoming_links": incoming,
                "linking_sites": int(entry.get("linking_sites") or 0),
            })
            continue

        page = health_by_key.get(key)
        if page is None:
            continue
        report.pages_matched += 1

        # Join 2 — earned authority pointing at a page with fixable defects.
        health = page.get("health_score")
        if (incoming >= _MIN_INCOMING and health is not None
                and health < _LEVERAGE_HEALTH):
            report.earned_authority_poor_health.append({
                "url": url, "incoming_links": incoming,
                "linking_sites": int(entry.get("linking_sites") or 0),
                "health_score": health,
            })

        # Join 3 — a linked page the crawl found disconnected internally.
        if key in orphan_keys and incoming >= _MIN_INCOMING:
            report.orphaned_authority.append({
                "url": url, "incoming_links": incoming,
                "health_score": health,
            })

    report.earned_authority_poor_health.sort(key=lambda r: -r["incoming_links"])
    report.links_to_broken_targets.sort(key=lambda r: -r["incoming_links"])
    report.orphaned_authority.sort(key=lambda r: -r["incoming_links"])
    return report


def to_dict(report: OffsiteReport | None) -> dict | None:
    if report is None:
        return None
    return {
        "referring_domains": report.referring_domains,
        "total_external_links": report.total_external_links,
        "top_linking_sites": report.top_linking_sites,
        "top_linking_sites_total": report.top_linking_sites_total,
        "earned_authority_poor_health": report.earned_authority_poor_health,
        "links_to_broken_targets": report.links_to_broken_targets,
        "orphaned_authority": report.orphaned_authority,
        "pages_matched": report.pages_matched,
        "pages_in_report": report.pages_in_report,
    }

"""V4 — GSC Authority-Matrix correlation report.

Purpose: Correlate each page's structural HealthScore against its real Google
         Search Console click volume, placing every page in a 2x2 quadrant
         (health high/low x clicks high/low). The disagreement quadrants
         (high-health/low-clicks and low-health/high-clicks) are the empirical
         calibration signal per R3 spec §6.
Spec:    docs/pending/2026-07-06_deploy-gate-validation.md#V4

The correlation/quadrant logic is PURE and unit-tested with a synthetic fixture
(tests/test_gsc_authority_matrix.py). The LIVE run needs a Google OAuth session
(creds live in-memory in api/routers/gsc._creds_cache, populated only after the
owner connects Search Console) so it CANNOT run headless — see run steps below.

Run steps (owner, after connecting GSC via the Connections panel / GET
/api/gsc/connect → Google consent → /api/gsc/callback):

    # with the API server running and GSC connected in that SAME process,
    # so _creds_cache holds the credentials:
    python -m scripts.gsc_authority_matrix --site "https://livingsystems.ca/" \
        --days 30 --max-pages 120

If creds are absent the script writes NOTHING live and exits 2 (blocked-on-
connection) — it never fabricates GSC numbers.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Correlation / quadrant logic (PURE — unit-tested)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PageMetric:
    """One page's structural health and real GSC click volume."""

    url: str
    health: int
    clicks: int


# Quadrant names (health x clicks).
Q_STRONG = "healthy_and_found"        # high health, high clicks — as expected
Q_HIDDEN_GEM = "healthy_but_unfound"  # high health, low clicks — health overstates?
Q_UNDERRATED = "unhealthy_but_found"  # low health, high clicks — health understates?
Q_WEAK = "unhealthy_and_unfound"      # low health, low clicks — as expected

# The two DISAGREEMENT quadrants — where structural health and real search
# performance diverge (the empirical calibration signal, R3 §6).
DISAGREEMENT_QUADRANTS = frozenset({Q_HIDDEN_GEM, Q_UNDERRATED})


def _median_threshold(values: list[int]) -> float:
    """Median split point. A page strictly ABOVE the median is 'high'."""
    if not values:
        return 0.0
    return float(statistics.median(values))


def classify_quadrant(
    metric: PageMetric, health_split: float, clicks_split: float
) -> str:
    """Assign a page to one of the four quadrants using > split thresholds."""
    high_health = metric.health > health_split
    high_clicks = metric.clicks > clicks_split
    if high_health and high_clicks:
        return Q_STRONG
    if high_health and not high_clicks:
        return Q_HIDDEN_GEM
    if not high_health and high_clicks:
        return Q_UNDERRATED
    return Q_WEAK


def build_authority_matrix(
    metrics: list[PageMetric],
) -> dict[str, list[PageMetric]]:
    """Split pages into the four quadrants by the MEDIAN of health and clicks.

    Median split makes the matrix scale-free (works for any site size / traffic
    level). Returns ``{quadrant_name: [PageMetric, ...]}`` for all four keys.
    Pure/deterministic.
    """
    health_split = _median_threshold([m.health for m in metrics])
    clicks_split = _median_threshold([m.clicks for m in metrics])
    out: dict[str, list[PageMetric]] = {
        Q_STRONG: [], Q_HIDDEN_GEM: [], Q_UNDERRATED: [], Q_WEAK: []
    }
    for m in metrics:
        out[classify_quadrant(m, health_split, clicks_split)].append(m)
    return out


def health_clicks_correlation(metrics: list[PageMetric]) -> float | None:
    """Pearson correlation between health and clicks (None if undefined).

    A POSITIVE correlation means healthier pages get more clicks — the
    calibration is directionally validated. Near-zero / negative correlation is
    a flag that structural health is not tracking real search performance.
    """
    if len(metrics) < 2:
        return None
    health = [float(m.health) for m in metrics]
    clicks = [float(m.clicks) for m in metrics]
    if len(set(health)) < 2 or len(set(clicks)) < 2:
        return None  # a constant series has no defined correlation
    return statistics.correlation(health, clicks)


# ---------------------------------------------------------------------------
# Report rendering (driven purely by real data)
# ---------------------------------------------------------------------------


def render_matrix_report(
    *, site: str, days: int, metrics: list[PageMetric], synthetic: bool
) -> str:
    matrix = build_authority_matrix(metrics)
    corr = health_clicks_correlation(metrics)
    health_split = _median_threshold([m.health for m in metrics])
    clicks_split = _median_threshold([m.clicks for m in metrics])

    lines: list[str] = []
    lines.append("---")
    lines.append("status: validation report (V4 — GSC Authority-Matrix)")
    lines.append("date: 2026-07-06")
    lines.append(f"site: {site}")
    lines.append(f"window_days: {days}")
    lines.append(f"data_source: {'SYNTHETIC FIXTURE (no live GSC)' if synthetic else 'LIVE Google Search Console'}")
    lines.append("---")
    lines.append("")
    lines.append("# V4 — GSC Authority-Matrix (HealthScore x GSC clicks)")
    lines.append("")
    if synthetic:
        lines.append(
            "> **NOTE:** This report was rendered from a SYNTHETIC fixture to "
            "demonstrate the quadrant/correlation logic. No live GSC data was "
            "available in this session (creds absent). Re-run per the header "
            "steps once the owner connects Search Console for real numbers."
        )
        lines.append("")
    lines.append("## Split thresholds (median)")
    lines.append("")
    lines.append(f"- Health median: {health_split}")
    lines.append(f"- Clicks median: {clicks_split}")
    lines.append(f"- Health↔clicks Pearson correlation: {'n/a' if corr is None else round(corr, 3)}")
    lines.append("")
    lines.append("## Quadrant counts")
    lines.append("")
    lines.append("| Quadrant | Meaning | Pages |")
    lines.append("|---|---|---|")
    lines.append(f"| {Q_STRONG} | high health · high clicks (as expected) | {len(matrix[Q_STRONG])} |")
    lines.append(f"| {Q_HIDDEN_GEM} | high health · LOW clicks (**disagree**) | {len(matrix[Q_HIDDEN_GEM])} |")
    lines.append(f"| {Q_UNDERRATED} | LOW health · high clicks (**disagree**) | {len(matrix[Q_UNDERRATED])} |")
    lines.append(f"| {Q_WEAK} | low health · low clicks (as expected) | {len(matrix[Q_WEAK])} |")
    lines.append("")
    lines.append("## Disagreement pages (calibration signal — R3 §6, AC V4.2)")
    lines.append("")
    lines.append("Pages where structural health and real search performance strongly disagree.")
    lines.append("")
    lines.append("| Page | Health | Clicks | Quadrant |")
    lines.append("|---|---|---|---|")
    disagree = [
        m for q in DISAGREEMENT_QUADRANTS for m in matrix[q]
    ]
    disagree.sort(key=lambda m: abs(m.health - health_split), reverse=True)
    for m in disagree:
        q = classify_quadrant(m, health_split, clicks_split)
        lines.append(f"| {m.url} | {m.health} | {m.clicks} | {q} |")
    if not disagree:
        lines.append("| (none) | | | |")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Live driver (blocked-on-connection in headless sessions)
# ---------------------------------------------------------------------------


async def _live_metrics(site: str, days: int, max_pages: int) -> list[PageMetric]:
    """Fetch real GSC clicks + crawl-derived HealthScores. Raises if no creds."""
    from google.oauth2.credentials import Credentials

    from api.routers.gsc import _load_creds
    from api.services.gsc_client import fetch_page_performance

    creds_json = _load_creds()
    if not creds_json:
        raise RuntimeError(
            "no GSC credentials in _creds_cache — connect Search Console first "
            "(GET /api/gsc/connect in the running server, then re-run here)."
        )
    import json

    creds = Credentials.from_authorized_user_info(json.loads(creds_json))
    perf = await fetch_page_performance(creds, site, days=days)
    clicks_by_url = {row["url"].rstrip("/"): int(row["clicks"]) for row in perf}

    # HealthScores from a real crawl via the shipped path.
    from scripts.before_after_healthscore import _crawl_per_page_rows
    from api.services.job_store_base import compute_page_health

    per_page, _ = await _crawl_per_page_rows(site, max_pages)
    metrics: list[PageMetric] = []
    for url, rows in per_page.items():
        metrics.append(
            PageMetric(
                url=url,
                health=compute_page_health(rows),
                clicks=clicks_by_url.get(url.rstrip("/"), 0),
            )
        )
    return metrics


def _synthetic_metrics() -> list[PageMetric]:
    """A small, deterministic fixture spanning all four quadrants (demo only)."""
    return [
        PageMetric("https://x/strong-1", health=90, clicks=500),
        PageMetric("https://x/strong-2", health=85, clicks=300),
        PageMetric("https://x/hidden-gem", health=88, clicks=5),      # healthy, unfound
        PageMetric("https://x/underrated", health=40, clicks=420),    # unhealthy, found
        PageMetric("https://x/weak-1", health=35, clicks=2),
        PageMetric("https://x/weak-2", health=50, clicks=10),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="V4 GSC Authority-Matrix report")
    parser.add_argument("--site", default="https://livingsystems.ca/")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--max-pages", type=int, default=120)
    parser.add_argument(
        "--out",
        default=str(_REPO_ROOT / "docs" / "review" / "2026-07-06_gsc-authority-matrix.md"),
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="render from the synthetic fixture (no live GSC) — demo the logic",
    )
    args = parser.parse_args()

    if args.synthetic:
        report = render_matrix_report(
            site=args.site, days=args.days, metrics=_synthetic_metrics(), synthetic=True
        )
        Path(args.out).write_text(report)
        print(f"[V4] wrote SYNTHETIC {args.out}")
        return 0

    try:
        metrics = asyncio.run(_live_metrics(args.site, args.days, args.max_pages))
    except Exception as exc:
        # Honest blocked-on-connection: never fabricate GSC data.
        print(f"[V4] LIVE RUN BLOCKED — no artifact written: {exc}")
        print("[V4] connect GSC (GET /api/gsc/connect) then re-run, or use --synthetic.")
        return 2

    report = render_matrix_report(
        site=args.site, days=args.days, metrics=metrics, synthetic=False
    )
    Path(args.out).write_text(report)
    print(f"[V4] wrote LIVE {args.out} — {len(metrics)} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

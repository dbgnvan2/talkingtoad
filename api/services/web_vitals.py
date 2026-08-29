"""D2 — Core Web Vitals: field data from CrUX, lab data from PSI.

Purpose: answer "is this slow for real people?" for the pages that actually earn
         traffic, without slowing the crawl or pretending a synthetic run is a
         user measurement.
Spec:    docs/pending/2026-08-29_D2-core-web-vitals.md
Tests:   tests/test_web_vitals.py, tests/test_web_vitals_report.py

**Why this is TalkingToad's to call, and GSC/GA4 are not.** The Performance
Bundle contract states "TalkingToad does not do OAuth to Google — the producer
owns acquisition". That rule is about *account-scoped* data: reading someone's
Search Console property requires them to authorise access to their account. CrUX
and PSI are **API-key gated and callable for any public URL** without touching an
account. Different class, so this does not cross the line. Recorded here so the
next reader does not have to re-derive it.

**Field and lab are different measurements and are never conflated.**

    CrUX (field)  28-day aggregate of real Chrome users. Only exists for URLs
                  with enough traffic to anonymise. Answers "is this slow for
                  people?" — and is the ONLY source allowed to raise a finding.
    PSI (lab)     one synthetic Lighthouse run. Exists for any URL. Answers
                  "why might this be slow?" — diagnostic context only.

Google is discontinuing CrUX field data *inside* the PSI response, so field data
is fetched from the CrUX API directly. Every row records which source it came
from, and every surface prints it. A lab number presented as user experience is
the P2 shape: a plausible figure standing in for a measurement nobody took.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from api.config import load_config

logger = logging.getLogger(__name__)

_CFG_KEYS = (
    "poor_thresholds", "good_thresholds", "crux_endpoint", "psi_endpoint",
    "default_top_n", "max_top_n", "strategy", "request_timeout_s",
    "max_retries", "retry_backoff_s", "min_interval_s",
)


def _cfg() -> dict:
    return load_config("web_vitals", required_keys=_CFG_KEYS)


def api_key() -> str | None:
    """The Google API key, from env only. Never logged, never persisted."""
    return (os.getenv("TT_PSI_API_KEY") or "").strip() or None


def scrub(text: str) -> str:
    """Remove the API key from any string before it is logged or returned.

    Google's APIs take the key as a query parameter, so an httpx transport error
    — whose message includes the request URL — carries the key with it. Without
    this, a timeout would write the key into the application log and into the
    502 body the endpoint returns. `standards/security.md`: keys live in env and
    go nowhere else.
    """
    key = api_key()
    text = str(text)
    if key:
        text = text.replace(key, "***")
    return re.sub(r"([?&]key=)[^&\s]+", r"\1***", text)


class WebVitalsError(RuntimeError):
    """A typed failure. Carries whether a retry could succeed (P1)."""

    def __init__(self, message: str, *, retryable: bool):
        super().__init__(message)
        self.retryable = retryable


@dataclass
class VitalsRow:
    """One page's vitals. `source` is load-bearing — see the module docstring."""
    url: str
    source: str                      # "field" | "lab" | "unavailable"
    lcp_ms: float | None = None
    inp_ms: float | None = None
    cls: float | None = None
    # Only set for lab rows; Lighthouse's own performance score, 0-100.
    performance_score: int | None = None
    # Why there is no data. Distinguishes "no CrUX record" (a quiet page) from
    # "quota exhausted" (retryable) — those must never look the same (P1/P2).
    unavailable_reason: str | None = None
    retryable: bool = False


@dataclass
class WebVitalsReport:
    rows: list[VitalsRow] = field(default_factory=list)
    requested: int = 0
    field_count: int = 0
    lab_count: int = 0
    unavailable_count: int = 0
    retryable_failures: int = 0
    strategy: str = "mobile"
    had_api_key: bool = False

    @property
    def measured(self) -> list[VitalsRow]:
        return [r for r in self.rows if r.source in ("field", "lab")]


# ---------------------------------------------------------------------------
# Parsing — tolerant, because the fixtures are constructed, not recorded
# ---------------------------------------------------------------------------
#
# P19/P20 honesty note: no live CrUX or PSI response could be recorded while
# writing this (no API key, and the shared keyless PSI pool returned 429). The
# checked-in fixtures are therefore built from the documented response contract,
# NOT captured from the live API — which is precisely the situation those
# patterns warn about. Two mitigations:
#   1. The parsers below read defensively and return None rather than raising on
#      a shape they do not recognise, so a contract drift degrades to
#      "not measured" instead of a crash or a wrong number.
#   2. tests/test_web_vitals.py carries a live contract test that runs only when
#      TT_PSI_API_KEY is set. The moment a key exists, real verification runs.
# Re-record the fixtures at that point and delete this note.


def _crux_percentile(metrics: dict, name: str) -> float | None:
    metric = metrics.get(name)
    if not isinstance(metric, dict):
        return None
    p75 = metric.get("percentiles", {}).get("p75")
    try:
        return float(p75)
    except (TypeError, ValueError):
        return None


def parse_crux(payload: dict, url: str) -> VitalsRow | None:
    """A CrUX record → a field row, or None when the URL has no record."""
    record = (payload or {}).get("record")
    if not isinstance(record, dict):
        return None
    metrics = record.get("metrics")
    if not isinstance(metrics, dict) or not metrics:
        return None
    lcp = _crux_percentile(metrics, "largest_contentful_paint")
    inp = _crux_percentile(metrics, "interaction_to_next_paint")
    cls = _crux_percentile(metrics, "cumulative_layout_shift")
    if lcp is None and inp is None and cls is None:
        return None
    return VitalsRow(url=url, source="field", lcp_ms=lcp, inp_ms=inp, cls=cls)


def parse_psi(payload: dict, url: str) -> VitalsRow | None:
    """A PSI response → a lab row, or None when no audits are present."""
    lighthouse = (payload or {}).get("lighthouseResult")
    if not isinstance(lighthouse, dict):
        return None
    audits = lighthouse.get("audits")
    if not isinstance(audits, dict):
        return None

    def _numeric(audit_id: str) -> float | None:
        audit = audits.get(audit_id)
        if not isinstance(audit, dict):
            return None
        try:
            return float(audit.get("numericValue"))
        except (TypeError, ValueError):
            return None

    lcp = _numeric("largest-contentful-paint")
    cls = _numeric("cumulative-layout-shift")
    # Lighthouse has no INP audit — INP is a field-only metric. Total Blocking
    # Time is its lab proxy, and it is deliberately NOT mapped onto `inp_ms`:
    # they are different measurements and conflating them is the whole failure
    # this module exists to avoid.
    score = None
    try:
        raw = lighthouse.get("categories", {}).get("performance", {}).get("score")
        score = round(float(raw) * 100) if raw is not None else None
    except (TypeError, ValueError, AttributeError):
        score = None

    if lcp is None and cls is None and score is None:
        return None
    return VitalsRow(url=url, source="lab", lcp_ms=lcp, cls=cls,
                     performance_score=score)


# ---------------------------------------------------------------------------
# Fetching — hardened as a class (P5): timeout, bounded retry, backoff
# ---------------------------------------------------------------------------


async def _get_json(
    client: httpx.AsyncClient, url: str, *, params: dict | None = None,
    json_body: dict | None = None, method: str = "GET",
) -> dict:
    cfg = _cfg()
    attempts = int(cfg["max_retries"])
    backoff = float(cfg["retry_backoff_s"])
    last: Exception | None = None

    for attempt in range(attempts):
        try:
            if method == "POST":
                resp = await client.post(url, params=params, json=json_body)
            else:
                resp = await client.get(url, params=params)
        except httpx.HTTPError as exc:
            last = WebVitalsError(scrub(f"transport error: {exc}"), retryable=True)
        else:
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 404:
                # CrUX says "no record for this URL" with a 404. That is a real
                # answer, not a failure — a quiet page, not a broken request.
                raise WebVitalsError("no record", retryable=False)
            if resp.status_code in (429, 500, 502, 503, 504):
                # P1: quota exhaustion and upstream blips are RETRYABLE. Writing
                # them as "no data" would make page 9 of 10 look fine because
                # the quota ran out at page 8.
                last = WebVitalsError(
                    f"HTTP {resp.status_code}", retryable=True)
            else:
                raise WebVitalsError(f"HTTP {resp.status_code}", retryable=False)

        if attempt < attempts - 1:
            await asyncio.sleep(backoff * (2 ** attempt))

    raise last or WebVitalsError("unknown failure", retryable=True)


async def fetch_field_vitals(client: httpx.AsyncClient, url: str) -> VitalsRow | None:
    """CrUX field data for one URL, or None when it has no record."""
    key = api_key()
    if not key:
        raise WebVitalsError("no API key configured", retryable=False)
    cfg = _cfg()
    try:
        payload = await _get_json(
            client, cfg["crux_endpoint"], params={"key": key},
            json_body={"url": url, "formFactor": "PHONE"}, method="POST",
        )
    except WebVitalsError as exc:
        if not exc.retryable and "no record" in str(exc):
            return None
        raise
    return parse_crux(payload, url)


async def fetch_lab_vitals(client: httpx.AsyncClient, url: str) -> VitalsRow | None:
    """PSI lab data for one URL. Works without a key at a much lower quota."""
    cfg = _cfg()
    params: dict[str, Any] = {"url": url, "strategy": cfg["strategy"]}
    key = api_key()
    if key:
        params["key"] = key
    payload = await _get_json(client, cfg["psi_endpoint"], params=params)
    return parse_psi(payload, url)


async def collect_web_vitals(
    store, job_id: str, *, top_n: int | None = None,
) -> WebVitalsReport:
    """Field-first vitals for the top N pages of the §6.9 priority queue.

    Never called from the crawl engine — see
    tests/test_architecture_constraints.py. The binding API constraint is 100
    queries per 100 seconds, so a whole-site sweep would add minutes to every run
    for data that only matters where traffic already is.
    """
    from api.services.page_priority import build_page_priority

    cfg = _cfg()
    limit = min(int(top_n or cfg["default_top_n"]), int(cfg["max_top_n"]))
    ranked = await build_page_priority(store, job_id)
    urls = [r["url"] for r in ranked[:limit]]

    report = WebVitalsReport(requested=len(urls), strategy=cfg["strategy"],
                             had_api_key=bool(api_key()))
    if not urls:
        return report

    min_interval = float(cfg["min_interval_s"])
    timeout = float(cfg["request_timeout_s"])
    last_call = 0.0

    async with httpx.AsyncClient(timeout=timeout) as client:
        for url in urls:
            # Client-side pacing to stay inside the published quota.
            elapsed = time.monotonic() - last_call
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            last_call = time.monotonic()

            row = await _collect_one(client, url)
            report.rows.append(row)

    report.field_count = sum(1 for r in report.rows if r.source == "field")
    report.lab_count = sum(1 for r in report.rows if r.source == "lab")
    report.unavailable_count = sum(1 for r in report.rows if r.source == "unavailable")
    report.retryable_failures = sum(1 for r in report.rows if r.retryable)
    if report.retryable_failures:
        logger.warning(
            "web_vitals_retryable_failures",
            extra={"job_id": job_id, "failed": report.retryable_failures,
                   "requested": report.requested},
        )
    return report


async def _collect_one(client: httpx.AsyncClient, url: str) -> VitalsRow:
    """CrUX first; PSI lab as the fallback; an honest unavailable row otherwise."""
    if api_key():
        try:
            row = await fetch_field_vitals(client, url)
            if row is not None:
                return row
        except WebVitalsError as exc:
            if exc.retryable:
                return VitalsRow(url=url, source="unavailable",
                                 unavailable_reason=f"field data unavailable ({exc})",
                                 retryable=True)
            logger.info("crux_unavailable", extra={"reason": scrub(exc)})

    try:
        row = await fetch_lab_vitals(client, url)
    except WebVitalsError as exc:
        return VitalsRow(url=url, source="unavailable",
                         unavailable_reason=scrub(f"lab data unavailable ({exc})"),
                         retryable=exc.retryable)
    if row is None:
        return VitalsRow(url=url, source="unavailable",
                         unavailable_reason="no field or lab data for this URL")
    return row


# ---------------------------------------------------------------------------
# Findings — field data only
# ---------------------------------------------------------------------------


def vitals_issues(report: WebVitalsReport) -> list:
    """Issues for pages whose FIELD data is in the poor band.

    Lab data never raises a finding. A synthetic run in a Google datacentre is
    not evidence about the site's real users, and presenting it as such is the
    single way this feature could become actively misleading rather than merely
    incomplete.
    """
    from api.crawler.issue_checker import make_issue

    poor = _cfg()["poor_thresholds"]
    issues = []
    for row in report.rows:
        if row.source != "field":
            continue
        # Each code is emitted with a LITERAL name, not through a variable —
        # tests/test_class1_invariants.py greps for `make_issue("CODE"` to prove
        # no catalogue entry is dead, and a variable defeats that guard (P21).
        if row.lcp_ms is not None and row.lcp_ms > float(poor["lcp_ms"]):
            issues.append(make_issue("CWV_LCP_POOR", row.url, extra=_extra(
                f"{row.lcp_ms / 1000:.1f}s", f"{poor['lcp_ms'] / 1000:.1f}s")))
        if row.inp_ms is not None and row.inp_ms > float(poor["inp_ms"]):
            issues.append(make_issue("CWV_INP_POOR", row.url, extra=_extra(
                f"{row.inp_ms:.0f}ms", f"{poor['inp_ms']:.0f}ms")))
        if row.cls is not None and row.cls > float(poor["cls"]):
            issues.append(make_issue("CWV_CLS_POOR", row.url, extra=_extra(
                f"{row.cls:.2f}", f"{poor['cls']:.2f}")))
    return issues


CWV_CODES: tuple[str, ...] = ("CWV_LCP_POOR", "CWV_INP_POOR", "CWV_CLS_POOR")


def _extra(measured: str, threshold: str) -> dict:
    return {
        "measured": measured,
        "poor_threshold": threshold,
        "source": "field",
        "diagnosis": (
            f"Real Chrome users see {measured} at the 75th percentile; Google's "
            f"'poor' boundary is {threshold}. This is a 28-day rolling average, "
            f"so a fix made today will not show here for several weeks."
        ),
    }

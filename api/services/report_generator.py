import logging
import io
from datetime import datetime
from fpdf import FPDF
from api.models.job import CrawlJob
from api.models.issue import Issue
from api.services.issue_help_data import ISSUE_HELP

logger = logging.getLogger(__name__)

# Standard Professional Colors
COLOR_CRITICAL = (220, 38, 38)
COLOR_WARNING = (217, 119, 6)
COLOR_INFO = (37, 99, 235)
COLOR_GRAY_800 = (31, 41, 55)
COLOR_GRAY_600 = (75, 85, 99)
COLOR_GRAY_500 = (107, 114, 128)
COLOR_GRAY_100 = (243, 244, 246)
COLOR_TOAD_GREEN = (22, 163, 74)
COLOR_BLUE_BG = (239, 246, 255) # Light blue help box
COLOR_BLUE_TEXT = (30, 58, 138) # Dark blue help labels
COLOR_AMBER = (204, 153, 0)  # RGB amber

# Constants for 8.5 x 11 (Letter) in mm
# Width: 215.9mm
# Left/Right Margin: 25.4mm
# Effective Width: 165.1mm
W = 165.1 

class TalkingToadReport(FPDF):
    def __init__(self):
        # 8.5 x 11 inches (Letter size)
        super().__init__(orientation="P", unit="mm", format="Letter")
        self.set_margins(25.4, 25.4, 25.4) 
        self.set_auto_page_break(auto=True, margin=25.4)

    _TRANSLITERATE = {
        "\u2014": "-", "\u2013": "-", "\u2026": "...", "\u2192": "->", "\u2715": "x",
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2265": ">=",
        "\u2264": "<=", "\u00d7": "x", "\u2022": "-", "\u2713": "yes", "\u2717": "no",
        "\u2705": "Good:", "\u274c": "Bad:",
    }

    def clean_text(self, text):
        """Latin-1 safe text. Phase 2 (2026-09-02): the authored explanations
        use em dashes, ellipses and arrows freely (500+ of them); a bare
        ``encode('latin-1', 'replace')`` printed every one as ``?``, so the
        client's caveat read "the server sends ? before any JavaScript".
        Transliterate the common typography first, then replace the rest."""
        if not text: return ""
        s = str(text)
        for ch, rep in self._TRANSLITERATE.items():
            s = s.replace(ch, rep)
        return s.encode('latin-1', 'replace').decode('latin-1')

    # The PDF is Latin-1 (CLAUDE.md, Reporting), so any non-Latin-1 character
    # reaching fpdf raises UnicodeEncodeError and takes the whole export to a
    # 500. Cleaning was left to each call site and 36 of them skipped it —
    # including `_render_priority_pages_section`, whose no-GSC-data blurb
    # contains an em dash and therefore broke the PDF for every site without
    # Search Console, which is the default for a nonprofit. Cleaning here
    # instead of at 36 call sites means a new call cannot reintroduce it.
    # Guarded by tests/test_pdf_latin1_safety.py.
    def cell(self, *args, **kwargs):
        return super().cell(*self._clean_args(args), **self._clean_kwargs(kwargs))

    def multi_cell(self, *args, **kwargs):
        return super().multi_cell(*self._clean_args(args), **self._clean_kwargs(kwargs))

    def _clean_args(self, args):
        return tuple(self.clean_text(a) if isinstance(a, str) else a for a in args)

    def _clean_kwargs(self, kwargs):
        return {k: (self.clean_text(v) if k in ("text", "txt") and isinstance(v, str) else v)
                for k, v in kwargs.items()}

    def header(self):
        if self.page_no() > 1:
            self.set_font('helvetica', 'I', 8)
            self.set_text_color(*COLOR_GRAY_500)
            date_str = datetime.now().strftime("%Y-%m-%d")
            self.set_x(25.4)
            self.cell(W, 10, self.clean_text(f'TalkingToad SEO Audit - {date_str}'), align='R', new_x="LMARGIN", new_y="NEXT")

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(*COLOR_GRAY_500)
        self.set_x(25.4)
        self.cell(W, 10, self.clean_text(f'Page {self.page_no()}/{{nb}}'), align='C')

    def chapter_title(self, title, size=18):
        self.set_x(25.4)
        self.ln(5)
        self.set_font('helvetica', 'B', size)
        self.set_text_color(*COLOR_GRAY_800)
        self.multi_cell(W, 10, self.clean_text(title))
        self.ln(2)

    def draw_help_section(self, what, impact, how, good_vs_bad=None, mislead=None, mission=None):
        """The explainer under an issue type. Phase 2 (2026-09-02): GOOD vs BAD
        and HOW THIS CAN MISLEAD sit between IMPACT and HOW TO FIX so the
        client's printed copy teaches the same way the screen does."""
        gb = ""
        if isinstance(good_vs_bad, dict) and (good_vs_bad.get("good") or good_vs_bad.get("bad")):
            gb = f"Good: {good_vs_bad.get('good', '')}  Bad: {good_vs_bad.get('bad', '')}"
        blocks = [("WHY IT MATTERS TO YOU", mission), ("WHAT IT IS", what), ("IMPACT", impact),
                  ("GOOD vs BAD", gb), ("HOW THIS CAN MISLEAD", mislead), ("HOW TO FIX", how)]
        for label, content in blocks:
            if not content:
                continue
            if self.get_y() > 240:
                self.add_page()
            # Label: bold black
            self.set_x(25.4)
            self.set_font('helvetica', 'B', 9)
            self.set_text_color(*COLOR_GRAY_800)
            self.cell(W, 5, self.clean_text(label), new_x="LMARGIN", new_y="NEXT")
            # Content: regular 10pt black
            self.set_x(25.4)
            self.set_font('helvetica', '', 10)
            self.set_text_color(*COLOR_GRAY_800)
            self.multi_cell(W, 5, self.clean_text(content))
            self.ln(1)

        self.ln(1)


# ---------------------------------------------------------------------------
# E3 — Search Performance and Priority Pages
# Spec: docs/pending/2026-08-29_E3-performance-data-in-report.md
# Tests: tests/test_performance_report.py
# ---------------------------------------------------------------------------


def _fmt_pct(value: float | None) -> str:
    """Format a 0-1 ratio as a percentage. Ledger CTRs are stored as ratios.

    ``None`` means the value was never measured and renders as such — printing
    "0.00%" for an unknown is the P2 shape that turns missing data into a finding.
    """
    if value is None:
        return "not measured"
    return f"{value * 100:.2f}%"


def _fmt_pos(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}"


def _short_url(url: str, limit: int = 62) -> str:
    """Trim the scheme and, if still long, the middle — keeping both ends, which
    is where the identifying information lives."""
    trimmed = url.replace("https://", "").replace("http://", "").rstrip("/")
    if len(trimmed) <= limit:
        return trimmed
    keep = (limit - 3) // 2
    return f"{trimmed[:keep]}...{trimmed[-keep:]}"


def _reorder_by_priority(top_pages: list[dict], priority_pages: list[dict]) -> list[dict]:
    """Re-order `top_pages` to follow the §6.9 work-queue order (E3.3).

    Pages absent from the priority queue keep their original relative order and
    follow the ranked ones — dropping them would silently shrink the section.
    """
    rank_by_url = {
        (p.get("url") or "").rstrip("/"): p.get("priority_rank", 10**6)
        for p in priority_pages
    }
    original = {id(p): i for i, p in enumerate(top_pages)}
    return sorted(
        top_pages,
        key=lambda p: (
            rank_by_url.get((p.get("url") or "").rstrip("/"), 10**6),
            original[id(p)],
        ),
    )


def _render_performance_section(pdf, performance: dict | None) -> None:
    """Site-level GSC/GA4 rollup joined to per-page health.

    The join is the point: a crawler alone cannot say which defect costs traffic,
    and an analytics export alone cannot say what is wrong with the page.
    """
    if not performance:
        return

    pdf.add_page()
    pdf.chapter_title("Search Performance")

    periods = performance.get("periods") or []
    period_text = ", ".join(periods) if periods else "unknown period"
    pdf.set_font('helvetica', '', 10)
    pdf.set_text_color(*COLOR_GRAY_600)
    pdf.set_x(25.4)
    pdf.multi_cell(W, 5, pdf.clean_text(
        f"First-party data from {performance.get('source', 'Search Console + GA4')}, "
        f"covering {period_text}, for the {performance.get('pages_with_data', 0)} crawled "
        f"pages that have records."
    ))

    # E3.5 (P6): never present stale numbers as current.
    if performance.get("is_stale"):
        pdf.ln(2)
        pdf.set_x(25.4)
        pdf.set_font('helvetica', 'B', 10)
        pdf.set_text_color(*COLOR_WARNING)
        pdf.multi_cell(W, 5, pdf.clean_text(
            f"Performance data is {performance.get('data_age_days')} days old. "
            f"Treat the figures below as a historical baseline, not current traffic."
        ))
    pdf.ln(4)

    stats = [
        ("Impressions", f"{performance.get('total_impressions', 0):,}"),
        ("Clicks", f"{performance.get('total_clicks', 0):,}"),
        ("Average CTR", _fmt_pct(performance.get('site_ctr', 0.0))),
    ]
    for label, total_key, count_key in (
        ("GA4 sessions", "total_sessions", "sessions_pages_with_data"),
        ("Conversions", "total_conversions", "conversions_pages_with_data"),
        ("AI-assistant sessions", "total_ai_referral_sessions", "ai_referral_pages_with_data"),
    ):
        n = performance.get(count_key, 0)
        # "0 across 0 pages" is not a measurement — say so instead of printing 0.
        stats.append((label, f"{performance.get(total_key, 0):,} (across {n} page"
                             f"{'s' if n != 1 else ''} with data)" if n else "not measured"))
    for label, value in stats:
        pdf.set_x(25.4)
        pdf.set_font('helvetica', 'B', 11)
        pdf.set_text_color(*COLOR_GRAY_500)
        pdf.cell(70, 8, pdf.clean_text(label + ":"))
        pdf.set_font('helvetica', 'B', 12)
        pdf.set_text_color(*COLOR_GRAY_800)
        pdf.cell(W - 70, 8, value, new_x="LMARGIN", new_y="NEXT")

    # ── Top pages by impressions, with health alongside ──
    top = performance.get("top_by_impressions") or []
    if top:
        pdf.ln(5)
        pdf.set_x(25.4)
        pdf.set_font('helvetica', 'B', 12)
        pdf.set_text_color(*COLOR_GRAY_800)
        with_data = performance.get("pages_with_data", len(top))
        heading = (f"Top {len(top)} Pages by Impressions (of {with_data} with data)"
                   if with_data > len(top) else "Pages by Impressions")
        pdf.cell(W, 8, pdf.clean_text(heading), new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(25.4)
        pdf.set_font('helvetica', '', 8)
        pdf.set_text_color(*COLOR_GRAY_500)
        pdf.cell(W, 5, "Page / Impressions / Clicks / CTR / Avg position / Health",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
        for row in top:
            if pdf.get_y() > 245:
                pdf.add_page()
            pdf.set_x(25.4)
            pdf.set_font('helvetica', '', 9)
            pdf.set_text_color(*COLOR_GRAY_800)
            pdf.multi_cell(W, 5, pdf.clean_text(_short_url(row["url"])))
            pdf.set_x(30)
            pdf.set_font('helvetica', '', 9)
            pdf.set_text_color(*COLOR_GRAY_600)
            health = row.get("health_score")
            pdf.cell(W - 5, 5, pdf.clean_text(
                f"{row['impressions']:,} impr | {row['clicks']:,} clicks | "
                f"{_fmt_pct(row['ctr'])} CTR | pos {_fmt_pos(row['position'])} | "
                f"health {health if health is not None else 'n/a'}"
            ), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)

    # ── High impressions, low CTR — the snippet-rewrite worklist ──
    low_ctr = performance.get("low_ctr_high_impression") or []
    if low_ctr:
        if pdf.get_y() > 200:
            pdf.add_page()
        pdf.ln(4)
        pdf.set_x(25.4)
        pdf.set_font('helvetica', 'B', 12)
        pdf.set_text_color(*COLOR_GRAY_800)
        pdf.cell(W, 8, "Seen But Not Clicked", new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(25.4)
        pdf.set_font('helvetica', '', 9)
        pdf.set_text_color(*COLOR_GRAY_600)
        pdf.multi_cell(W, 5, pdf.clean_text(
            "These pages earn more impressions than most of the site but are clicked "
            "less often than the site average. The ranking is already there; the title "
            "and description are what is losing the click."
        ))
        pdf.ln(2)
        for row in low_ctr:
            if pdf.get_y() > 245:
                pdf.add_page()
            pdf.set_x(25.4)
            pdf.set_font('helvetica', '', 9)
            pdf.set_text_color(*COLOR_GRAY_800)
            pdf.multi_cell(W, 5, pdf.clean_text(_short_url(row["url"])))
            pdf.set_x(30)
            pdf.set_text_color(*COLOR_WARNING)
            pdf.cell(W - 5, 5, pdf.clean_text(
                f"{row['impressions']:,} impressions, {_fmt_pct(row['ctr'])} CTR, "
                f"average position {_fmt_pos(row['position'])}"
            ), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)


def _render_web_vitals_section(pdf, vitals: dict | None) -> None:
    """Core Web Vitals for the top priority pages (D2).

    Every row states whether it is FIELD data (real Chrome users) or LAB data
    (one synthetic run). Presenting a lab number as user experience is the single
    way this section could become actively misleading.
    """
    if not vitals or not vitals.get("rows"):
        return

    pdf.add_page()
    pdf.chapter_title("Core Web Vitals")
    pdf.set_font('helvetica', '', 10)
    pdf.set_text_color(*COLOR_GRAY_600)
    pdf.set_x(25.4)
    pdf.multi_cell(W, 5, pdf.clean_text(
        f"Measured for the top {vitals.get('requested', 0)} pages of the priority "
        f"queue, on a {vitals.get('strategy', 'mobile')} profile. "
        f"FIELD figures are the 75th percentile across real Chrome users over the "
        f"last 28 days. LAB figures are a single synthetic test run — useful for "
        f"diagnosis, but not a measurement of what your visitors experience. "
        f"Only field data raises a finding."
    ))
    pdf.ln(3)

    counts = (f"{vitals.get('field_count', 0)} field, "
              f"{vitals.get('lab_count', 0)} lab, "
              f"{vitals.get('unavailable_count', 0)} not measured")
    pdf.set_x(25.4)
    pdf.set_font('helvetica', 'B', 10)
    pdf.set_text_color(*COLOR_GRAY_800)
    pdf.cell(W, 6, pdf.clean_text(counts), new_x="LMARGIN", new_y="NEXT")

    if vitals.get("retryable_failures"):
        pdf.set_x(25.4)
        pdf.set_font('helvetica', 'B', 9)
        pdf.set_text_color(*COLOR_WARNING)
        pdf.multi_cell(W, 5, pdf.clean_text(
            f"{vitals['retryable_failures']} page(s) could not be measured because "
            f"the API was rate-limited or unavailable. That is a temporary failure, "
            f"not a result — re-run to complete them."
        ))
    pdf.ln(3)

    for row in vitals["rows"]:
        if pdf.get_y() > 240:
            pdf.add_page()
        pdf.set_x(25.4)
        pdf.set_font('helvetica', '', 9)
        pdf.set_text_color(*COLOR_GRAY_800)
        pdf.multi_cell(W, 5, pdf.clean_text(_short_url(row.get("url", ""))))

        pdf.set_x(30)
        pdf.set_font('helvetica', '', 9)
        source = row.get("source")
        if source == "unavailable":
            pdf.set_text_color(*COLOR_GRAY_500)
            pdf.multi_cell(W - 5, 4.5, pdf.clean_text(
                f"Not measured — {row.get('unavailable_reason') or 'no data available'}. "
                f"A page with no field data is not a fast page; it is one too few "
                f"people visited for Chrome to report anonymously."
            ))
        else:
            pdf.set_text_color(*COLOR_GRAY_600)
            bits = [f"{'FIELD (real users)' if source == 'field' else 'LAB (synthetic run)'}"]
            if row.get("lcp_ms") is not None:
                bits.append(f"LCP {row['lcp_ms'] / 1000:.1f}s")
            if row.get("inp_ms") is not None:
                bits.append(f"INP {row['inp_ms']:.0f}ms")
            if row.get("cls") is not None:
                bits.append(f"CLS {row['cls']:.2f}")
            if row.get("performance_score") is not None:
                bits.append(f"Lighthouse {row['performance_score']}/100")
            pdf.multi_cell(W - 5, 4.5, pdf.clean_text(" | ".join(bits)))
        pdf.ln(1)


def _render_offsite_section(pdf, offsite: dict | None) -> None:
    """Off-site authority from Search Console's Links report, joined to the crawl (D1).

    The joins are the reason this exists. A referring-domain count is available
    anywhere; "an external site links to a page of yours that 404s" needs both the
    link data and the crawl, and no other tool in the stack holds both.
    """
    if not offsite:
        return

    pdf.add_page()
    pdf.chapter_title("Off-Site Authority")
    pdf.set_font('helvetica', '', 10)
    pdf.set_text_color(*COLOR_GRAY_600)
    pdf.set_x(25.4)
    pdf.multi_cell(W, 5, pdf.clean_text(
        "From Search Console's own Links report - first-party data, not a "
        "third-party estimate. Third-party authority scores and full backlink "
        "graphs are not included; see Scope, Method and Caveats."
    ))
    pdf.ln(3)

    for label, key in (("Referring domains", "referring_domains"),
                       ("Total external links", "total_external_links")):
        value = offsite.get(key)
        if value is None:
            continue
        pdf.set_x(25.4)
        pdf.set_font('helvetica', 'B', 11)
        pdf.set_text_color(*COLOR_GRAY_500)
        pdf.cell(70, 8, pdf.clean_text(label + ":"))
        pdf.set_font('helvetica', 'B', 12)
        pdf.set_text_color(*COLOR_GRAY_800)
        pdf.cell(W - 70, 8, f"{value:,}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    def _join_block(title, rows, blurb, colour=COLOR_WARNING):
        if not rows:
            return
        if pdf.get_y() > 225:
            pdf.add_page()
        pdf.set_x(25.4)
        pdf.set_font('helvetica', 'B', 12)
        pdf.set_text_color(*COLOR_GRAY_800)
        pdf.cell(W, 7, pdf.clean_text(title), new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(25.4)
        pdf.set_font('helvetica', '', 9)
        pdf.set_text_color(*COLOR_GRAY_600)
        pdf.multi_cell(W, 4.5, pdf.clean_text(blurb))
        pdf.ln(1)
        for row in rows:
            if pdf.get_y() > 248:
                pdf.add_page()
            pdf.set_x(30)
            pdf.set_font('helvetica', '', 9)
            pdf.set_text_color(*COLOR_GRAY_800)
            pdf.multi_cell(W - 5, 4.5, pdf.clean_text(_short_url(row["url"])))
            pdf.set_x(34)
            pdf.set_font('helvetica', '', 8)
            pdf.set_text_color(*colour)
            bits = [f"{row.get('incoming_links', 0)} incoming links"]
            if row.get("linking_sites"):
                bits.append(f"from {row['linking_sites']} sites")
            if row.get("health_score") is not None:
                bits.append(f"health {row['health_score']}")
            pdf.multi_cell(W - 5, 4, pdf.clean_text(" | ".join(bits)))
        pdf.ln(3)

    _join_block(
        "External links pointing at broken pages",
        offsite.get("links_to_broken_targets") or [],
        "Other sites are linking to these URLs and the URLs do not resolve. The "
        "link exists and its value is being discarded; a one-hop redirect to the "
        "right page recovers it. This is the highest-return fix on this page.",
        COLOR_CRITICAL,
    )
    _join_block(
        "Earned authority on pages with fixable problems",
        offsite.get("earned_authority_poor_health") or [],
        "These pages have real incoming links AND a low health score. The hard "
        "part - getting other sites to link to you - is already done.",
    )
    _join_block(
        "Linked pages your own site does not link to",
        offsite.get("orphaned_authority") or [],
        "Other sites link to these pages, but the crawl found no internal link "
        "path to them. That authority is not circulating through your site.",
    )

    sites = offsite.get("top_linking_sites") or []
    if sites:
        if pdf.get_y() > 230:
            pdf.add_page()
        pdf.set_x(25.4)
        pdf.set_font('helvetica', 'B', 12)
        pdf.set_text_color(*COLOR_GRAY_800)
        total = offsite.get("top_linking_sites_total", len(sites))
        heading = ("Top linking sites" if total <= len(sites)
                   else f"Top linking sites (showing {len(sites)} of {total})")
        pdf.cell(W, 7, pdf.clean_text(heading), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font('helvetica', '', 9)
        pdf.set_text_color(*COLOR_GRAY_600)
        for site in sites:
            if pdf.get_y() > 250:
                pdf.add_page()
            pdf.set_x(30)
            pdf.multi_cell(W - 5, 4.5, pdf.clean_text(
                f"{site.get('domain', '')} - {site.get('linking_pages', 0)} linking pages"))


def _render_priority_pages_section(
    pdf, priority_pages: list[dict] | None, performance: dict | None, limit: int = 15
) -> None:
    """The §6.9 Authority-Matrix work queue, as a client-readable table."""
    if not priority_pages:
        return

    pdf.add_page()
    pdf.chapter_title("Priority Pages")
    pdf.set_font('helvetica', '', 10)
    pdf.set_text_color(*COLOR_GRAY_600)
    pdf.set_x(25.4)
    if performance:
        blurb = ("Ranked by the Authority Matrix: pages that earn traffic and have "
                 "problems come first, then traffic decay and staleness, then worst "
                 "health. Within a group, pages with more clicks and conversions lead.")
    else:
        blurb = ("Ranked by page health. No Search Console or GA4 data was supplied for "
                 "this site, so traffic and conversions could not be weighed — see "
                 "Scope, Method and Caveats.")
    pdf.multi_cell(W, 5, blurb)
    pdf.ln(4)

    for row in priority_pages[:limit]:
        if pdf.get_y() > 240:
            pdf.add_page()
        gsc = row.get("gsc") or {}
        flag = row.get("review_flag") or {}
        reasons = flag.get("reasons") if isinstance(flag, dict) else getattr(flag, "reasons", None)

        pdf.set_x(25.4)
        pdf.set_font('helvetica', 'B', 9)
        pdf.set_text_color(*COLOR_GRAY_800)
        pdf.multi_cell(W, 5, pdf.clean_text(
            f"{row.get('priority_rank', '?')}. {_short_url(row.get('url', ''))}"
        ))

        pdf.set_x(30)
        pdf.set_font('helvetica', '', 9)
        pdf.set_text_color(*COLOR_GRAY_600)
        bits = [
            f"{row.get('bucket', 'Unranked')}",
            f"health {row.get('health_score', 'n/a')}",
            f"citability {row.get('citability_grade', 'n/a')}",
        ]
        if gsc:
            bits.append(f"{gsc.get('impressions') or 0:,} impr")
            bits.append(f"{gsc.get('clicks') or 0:,} clicks")
            conv = gsc.get("conversions")
            bits.append(f"{conv if conv is not None else 'n/a'} conv")
        pdf.multi_cell(W - 5, 5, pdf.clean_text(" | ".join(bits)))

        if reasons:
            pdf.set_x(30)
            pdf.set_font('helvetica', 'I', 8)
            pdf.set_text_color(*COLOR_WARNING)
            pdf.multi_cell(W - 5, 4, pdf.clean_text("; ".join(reasons)))

        pdf.set_draw_color(229, 231, 235)
        pdf.set_x(25.4)
        pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + W, pdf.get_y())
        pdf.ln(3)


def _checklist_sort_key(prevalence: list | None):
    """Order the action checklist by (tier weight, pages affected, priority).

    Without prevalence this collapses to the previous `-priority_rank` ordering
    exactly, so a scan with no prevalence data reads as it always did.
    Spec: docs/pending/2026-08-29_E4-site-prevalence-escalation.md#E4.3
    """
    by_code = {p.code: p for p in (prevalence or [])}

    def key(issue):
        p = by_code.get(issue.issue_code)
        weight = p.tier_weight if p else 0
        affected = p.pages_affected if p else 0
        return (-weight, -affected, -(issue.priority_rank or 0))

    return key


def _render_systemic_defects_section(pdf, prevalence: list | None) -> None:
    """Defects present on a large share of the indexable estate.

    A defect on 56 of 272 pages is a template or editorial-process problem, and
    saying so changes what the reader does about it. Omitted entirely when
    nothing qualifies — and the Caveats section records that (E7.4).
    """
    if not prevalence:
        return
    systemic = [p for p in prevalence if p.tier == "systemic"]
    if not systemic:
        return

    pdf.add_page()
    pdf.chapter_title("Systemic Defects")
    pdf.set_font('helvetica', '', 10)
    pdf.set_text_color(*COLOR_GRAY_600)
    pdf.set_x(25.4)
    pdf.multi_cell(W, 5, pdf.clean_text(
        "Each of these comes from one cause rather than one page — either because it "
        "appears across a large share of the site, or because the fix is inherently a "
        "template or settings change however few pages show it. One fix resolves them "
        "all, so they come before working through individual pages. The footprint of "
        "each is stated beneath it."
    ))
    pdf.ln(4)

    for p in systemic:
        if pdf.get_y() > 235:
            pdf.add_page()
        pdf.set_x(25.4)
        pdf.set_font('helvetica', 'B', 11)
        pdf.set_text_color(*COLOR_GRAY_800)
        pdf.multi_cell(W, 6, pdf.clean_text(p.human_description))

        pdf.set_x(30)
        pdf.set_font('helvetica', 'B', 10)
        pdf.set_text_color(*COLOR_WARNING)
        pdf.cell(W - 5, 5, pdf.clean_text(
            f"{p.pages_affected} of {p.indexable_pages} indexable pages "
            f"({p.share * 100:.0f}%)"
        ), new_x="LMARGIN", new_y="NEXT")

        spec = ISSUE_HELP.get(p.code) or {}
        fix = spec.get("fix") or ""
        if fix:
            pdf.set_x(30)
            pdf.set_font('helvetica', '', 9)
            pdf.set_text_color(*COLOR_GRAY_600)
            pdf.multi_cell(W - 5, 4.5, pdf.clean_text(fix))

        pdf.ln(2)
        pdf.set_draw_color(229, 231, 235)
        pdf.set_x(25.4)
        pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + W, pdf.get_y())
        pdf.ln(3)


def _render_issue_evidence(pdf, issue) -> None:
    """Render the offending elements for one issue, from its `extra` payload.

    Spec:  docs/pending/2026-08-29_EV-issue-evidence.md
    Tests: tests/test_issue_evidence.py::TestReportRendering
    """
    from api.services.issue_evidence import evidence_lines

    extra = getattr(issue, "extra", None)
    code = getattr(issue, "issue_code", None) or getattr(issue, "code", "")
    try:
        lines, _total = evidence_lines(code, extra)
    except Exception:  # noqa: BLE001 — evidence must never break a report
        logger.warning("issue_evidence_failed", extra={"code": code}, exc_info=True)
        return
    if not lines:
        return

    if pdf.get_y() > 235:
        pdf.add_page()
    pdf.set_x(25.4)
    pdf.set_font('helvetica', 'B', 9)
    pdf.set_text_color(*COLOR_GRAY_600)
    pdf.cell(W, 6, "What to look for:", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font('helvetica', '', 8)
    pdf.set_text_color(*COLOR_GRAY_800)
    for line in lines:
        if pdf.get_y() > 250:
            pdf.add_page()
        pdf.set_x(30 if line.startswith("  ") else 28)
        pdf.multi_cell(W - 5, 4, pdf.clean_text(line.strip()))
    pdf.ln(1)


def _render_roadmap_section(pdf, issues, prevalence, priority_pages) -> None:
    """Owner / phase / effort / done-when per finding (E7.1)."""
    if not issues:
        return
    from api.services.remediation import build_roadmap, phase_blurb, phase_titles

    try:
        items, weighted, phase_totals = build_roadmap(
            issues, prevalence=prevalence, priority_pages=priority_pages
        )
    except Exception:  # noqa: BLE001 — a config problem must not kill the report
        logger.warning("roadmap_unavailable", exc_info=True)
        return
    if not items:
        return

    pdf.add_page()
    pdf.chapter_title("Remediation Roadmap")
    pdf.set_font('helvetica', '', 10)
    pdf.set_text_color(*COLOR_GRAY_600)
    pdf.set_x(25.4)
    if weighted:
        intro = ("Work grouped into three phases. An item is in Phase 1 because the defect is "
                 "systemic - one template or setting is responsible - and in Phase 2 because it "
                 'sits on a page that already earns traffic. Each "done when" is written so a '
                 "re-crawl can confirm it.")
    else:
        intro = ("Work ordered by impact. No prevalence or traffic data was available for this "
                 "scan, so the phases below reflect impact alone rather than how widespread a "
                 "defect is or what a page earns - see Scope, Method and Caveats.")
    pdf.multi_cell(W, 5, pdf.clean_text(intro))
    pdf.ln(3)

    for phase_name, phase_title in phase_titles():
        in_phase = [i for i in items if i.phase == phase_name]
        if not in_phase:
            continue
        if pdf.get_y() > 225:
            pdf.add_page()
        pdf.set_x(25.4)
        pdf.set_font('helvetica', 'B', 13)
        pdf.set_text_color(*COLOR_GRAY_800)
        pdf.multi_cell(W, 7, pdf.clean_text(phase_title))
        pdf.set_x(25.4)
        pdf.set_font('helvetica', 'I', 9)
        pdf.set_text_color(*COLOR_GRAY_500)
        blurb = phase_blurb(phase_name)
        # Rule 6: a cap must say what it dropped.
        total = phase_totals.get(phase_name, len(in_phase))
        if total > len(in_phase):
            blurb += (f" Showing the top {len(in_phase)} of {total} items in this "
                      f"phase; the full list is in the Excel Roadmap sheet.")
        pdf.multi_cell(W, 4.5, pdf.clean_text(blurb))
        pdf.ln(2)

        for item in in_phase:
            if pdf.get_y() > 235:
                pdf.add_page()
            pdf.set_x(25.4)
            pdf.set_font('helvetica', 'B', 10)
            pdf.set_text_color(*COLOR_GRAY_800)
            pdf.multi_cell(W, 5.5, pdf.clean_text(f"[ ] {item.title}"))

            pdf.set_x(30)
            pdf.set_font('helvetica', '', 9)
            pdf.set_text_color(*COLOR_GRAY_600)
            meta = (f"Owner: {item.owner}  |  Impact: {item.impact}/10  |  "
                    f"Effort: {item.effort_label}")
            if item.pages_affected:
                meta += f"  |  {item.pages_affected} page{'s' if item.pages_affected != 1 else ''}"
            pdf.multi_cell(W - 5, 4.5, pdf.clean_text(meta))

            pdf.set_x(30)
            pdf.set_font('helvetica', 'I', 9)
            pdf.set_text_color(*COLOR_BLUE_TEXT)
            pdf.multi_cell(W - 5, 4.5, pdf.clean_text(f"Done when: {item.done_when}"))
            pdf.ln(2)
        pdf.ln(2)


def _render_blueprints_section(pdf, blueprints, *, include: bool) -> None:
    """Approved page blueprints (D4.4).

    Two gates, both required: the caller opted in, AND the draft was approved by
    a person. An unapproved draft can never reach a client artifact.
    """
    if not include or not blueprints:
        return
    from api.services.blueprints import approved_only

    approved = approved_only(blueprints)
    if not approved:
        return

    pdf.add_page()
    pdf.chapter_title("Proposed Page Copy")
    pdf.set_font('helvetica', '', 10)
    pdf.set_text_color(*COLOR_GRAY_600)
    pdf.set_x(25.4)
    pdf.multi_cell(W, 5, pdf.clean_text(
        "These are DRAFTS, generated from each page's existing content and "
        "reviewed by a person before inclusion. They still need checking for "
        "factual accuracy, professional standards, accessibility, privacy, "
        "crisis-language requirements and brand voice before anything is "
        "published."
    ))
    pdf.ln(4)

    for draft in approved:
        if pdf.get_y() > 220:
            pdf.add_page()
        pdf.set_x(25.4)
        pdf.set_font('helvetica', 'B', 10)
        pdf.set_text_color(*COLOR_GRAY_800)
        pdf.multi_cell(W, 5.5, pdf.clean_text(_short_url(draft.get("url", ""))))

        for label, key in (("Title", "proposed_title"),
                           ("Meta description", "proposed_meta_description"),
                           ("H1", "proposed_h1"),
                           ("Opening paragraph", "proposed_lead")):
            value = (draft.get(key) or "").strip()
            if not value:
                continue
            if pdf.get_y() > 245:
                pdf.add_page()
            pdf.set_x(30)
            pdf.set_font('helvetica', 'B', 9)
            pdf.set_text_color(*COLOR_GRAY_500)
            pdf.cell(W - 5, 5, pdf.clean_text(label + ":"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_x(30)
            pdf.set_font('helvetica', '', 9)
            pdf.set_text_color(*COLOR_GRAY_800)
            pdf.multi_cell(W - 5, 4.5, pdf.clean_text(value))

        approver = draft.get("approved_by")
        if approver:
            pdf.set_x(30)
            pdf.set_font('helvetica', 'I', 8)
            pdf.set_text_color(*COLOR_GRAY_500)
            pdf.multi_cell(W - 5, 4, pdf.clean_text(
                f"Reviewed and approved by {approver}"))
        pdf.ln(3)


def _render_wp_audit_section(pdf, audit: dict | None) -> None:
    """WordPress plugin/theme/Site-Health configuration (D3).

    Rendered only when the audit was actually run; otherwise omitted and named in
    Caveats, so a missing section never reads as a clean WordPress install.
    """
    if not audit or not audit.get("plugins_total"):
        return

    pdf.add_page()
    pdf.chapter_title("WordPress Configuration")
    pdf.set_font('helvetica', '', 10)
    pdf.set_text_color(*COLOR_GRAY_600)
    pdf.set_x(25.4)
    pdf.multi_cell(W, 5, pdf.clean_text(
        f"{audit['plugins_total']} plugins installed - "
        f"{audit.get('plugins_active', 0)} active, "
        f"{audit.get('plugins_inactive', 0)} inactive. This section reads the "
        f"site's configuration only; nothing was changed."
    ))
    pdf.ln(4)

    def _block(title, rows, colour=COLOR_GRAY_800):
        if not rows:
            return
        if pdf.get_y() > 235:
            pdf.add_page()
        pdf.set_x(25.4)
        pdf.set_font('helvetica', 'B', 11)
        pdf.set_text_color(*COLOR_GRAY_800)
        pdf.cell(W, 7, pdf.clean_text(title), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font('helvetica', '', 9)
        pdf.set_text_color(*colour)
        for row in rows:
            if pdf.get_y() > 248:
                pdf.add_page()
            pdf.set_x(30)
            pdf.multi_cell(W - 5, 4.5, pdf.clean_text(row))
        pdf.ln(3)

    _block("Updates pending", [
        f"{p['name']} {p['version']} -> {p['new_version']}"
        for p in audit.get("pending_updates") or []
    ], COLOR_WARNING)

    _block("Installed but inactive", [
        f"{p['name']} ({p['slug']})" for p in audit.get("inactive_plugins") or []
    ] + [f"Theme: {t}" for t in audit.get("inactive_themes") or []])

    overlaps = audit.get("overlaps") or []
    if overlaps:
        if pdf.get_y() > 220:
            pdf.add_page()
        pdf.set_x(25.4)
        pdf.set_font('helvetica', 'B', 11)
        pdf.set_text_color(*COLOR_GRAY_800)
        pdf.cell(W, 7, "Two plugins doing the same job", new_x="LMARGIN", new_y="NEXT")
        for overlap in overlaps:
            if pdf.get_y() > 240:
                pdf.add_page()
            pdf.set_x(30)
            pdf.set_font('helvetica', 'B', 9)
            pdf.set_text_color(*COLOR_WARNING)
            pdf.multi_cell(W - 5, 4.5, pdf.clean_text(
                f"{overlap['label']}: {', '.join(overlap['plugins'])}"))
            pdf.set_x(30)
            pdf.set_font('helvetica', '', 9)
            pdf.set_text_color(*COLOR_GRAY_600)
            pdf.multi_cell(W - 5, 4.5, pdf.clean_text(overlap["why_one_owner"]))
            pdf.ln(1)
        pdf.ln(2)

    # `status` distinguishes a WordPress "critical" from a "recommended", and
    # this is the only surface that shows Site Health at all — dropping it made
    # the two render identically.
    _block("WordPress Site Health says", [
        (f"[{str(h.get('status')).upper()}] " if h.get("status") else "")
        + f"{h['label']}  ({h['source']})"
        for h in audit.get("site_health") or []
    ], COLOR_GRAY_600)

    # The boundary, stated. Without it the reader may assume a clean section
    # means the backup plugin is working — which this cannot know.
    _block("Not inspected", audit.get("not_inspected") or [], COLOR_GRAY_500)


def _info_notices_figure(summary: dict):
    """The scored info count, with the excluded count when the level left any out."""
    stored = summary.get("by_severity", {}).get("info", 0)
    excluded = summary.get("info_excluded") or 0
    if not excluded:
        return stored
    return f"{summary.get('info_scored', stored - excluded)} (+{excluded} excluded)"


def _total_issues_figure(summary: dict):
    """Findings recorded, and how many of them the score charged.

    P5.2/P16: `SummaryPanel` has shown "found - N scored" beneath this number
    since the info_detail change; the PDF printed the bare stored count two rows
    under Health Score and said nothing. Same fact, same report, one front end.
    """
    stored = summary.get("total_issues", 0)
    excluded = summary.get("info_excluded") or 0
    if not excluded:
        return stored
    return f"{stored} ({stored - excluded} scored)"


def _render_caveats_section(pdf, job, summary, *, performance, image_summary,
                            filter_note=None,
                            prevalence, performance_failed: bool = False,
                            offsite: dict | None = None) -> None:
    """What was covered, what every cap dropped, and what was NOT checked (E7.2).

    Always rendered. An omitted section elsewhere in this report is named here
    by name, so a gap in the data can never read as a clean bill of health (E7.4).
    """
    pdf.add_page()
    pdf.chapter_title("Scope, Method and Caveats")

    def _para(text, *, bold=False, color=COLOR_GRAY_600, size=10, gap=2):
        pdf.set_x(25.4)
        pdf.set_font('helvetica', 'B' if bold else '', size)
        pdf.set_text_color(*color)
        pdf.multi_cell(W, 5, pdf.clean_text(text))
        pdf.ln(gap)

    # ── What was covered ──
    _para("What this audit covered", bold=True, color=COLOR_GRAY_800, size=12)
    covered = [
        f"Pages crawled: {summary.get('pages_crawled', 0)}",
        f"Findings recorded: {summary.get('total_issues', 0)}",
        f"Crawl date: {datetime.now().strftime('%B %d, %Y')}",
    ]
    if getattr(job, "scoring_model_version", None):
        covered.append(f"Scoring model: {job.scoring_model_version}")
    robots = summary.get("robots_txt")
    if robots is not None:
        covered.append(f"robots.txt: {'found' if robots else 'not found'}")
    sitemap = summary.get("sitemap")
    if sitemap is not None:
        covered.append(f"XML sitemap: {'found' if sitemap else 'not found'}")
    for line in covered:
        _para(f"- {line}", gap=0)
    pdf.ln(3)

    # ── Limits that actually bit ──
    limits: list[str] = []
    seen_imgs = getattr(job, "images_seen_total", None)
    got_imgs = getattr(job, "images_collected", None)
    if seen_imgs and got_imgs is not None and seen_imgs > got_imgs:
        limits.append(f"Images: analysed {got_imgs} of {seen_imgs} distinct images found.")
    # O2: a suppressed orphan check produces zero rows in the crawlability
    # section. Without this line the report reads as "no orphaned pages" for a
    # scan that never looked — the same false all-clear the panel fixes (P31).
    from api.services.coverage_notes import (analysis_coverage_note,
                                              orphan_coverage_note,
                                              sitemap_coverage_note)
    _orphan_note = orphan_coverage_note(job)
    if _orphan_note:
        limits.append(_orphan_note)
    # AF10: a URL the site declares but we never fetched must not be silently
    # absent from the audit.
    _sitemap_note = sitemap_coverage_note(job)
    if _sitemap_note:
        limits.append(_sitemap_note)
    _analysis_note = analysis_coverage_note(job)   # C2
    if _analysis_note:
        limits.append(_analysis_note)
    # F1 — this report shows the on-screen (filtered) list. Say so, in the
    # section a reader already scans for what the audit did not cover. The
    # reader of a forwarded PDF is usually not the operator who set the
    # filter, and 123 of 170 codes are `info`.
    if filter_note:
        limits.append(filter_note)
    if limits:
        _para("Limits reached during this crawl", bold=True, color=COLOR_GRAY_800, size=12)
        for line in limits:
            _para(f"- {line}", gap=0)
        pdf.ln(3)

    # ── Sections omitted, by name (E7.4) ──
    omissions: list[str] = []
    if not performance:
        if performance_failed:
            # Our failure, not their data. Saying "no data was supplied" here would
            # be a false statement about the client's own inputs (P1/P2).
            omissions.append(
                "Search Performance and Priority Pages were omitted: the performance "
                "data could not be read while building this report. This is a tooling "
                "failure on our side, not a finding about your data - re-export to "
                "retry."
            )
        else:
            omissions.append(
                "Search Performance and Priority Pages were omitted: no Search Console "
                "or GA4 data was supplied for this site, so pages could not be ranked "
                "by what they earn. This is missing data, not a finding of no traffic."
            )
    if not image_summary or not image_summary.get("total_images"):
        omissions.append(
            "Image Health was omitted: no images were collected during this crawl. "
            "This is not a statement that the site's images are fine."
        )
    if not prevalence:
        omissions.append(
            "Systemic Defects and Site Hygiene were omitted: prevalence could not be "
            "computed for this crawl."
        )
    if omissions:
        _para("Sections omitted from this report", bold=True, color=COLOR_GRAY_800, size=12)
        for line in omissions:
            _para(f"- {line}", gap=1)
        pdf.ln(2)

    # ── What was NOT checked ──
    # E7 promised Core Web Vitals were unchecked. Once D2 can run, that line has
    # to reflect whether it actually did — shipping the capability without
    # updating this would make the report lie in the other direction.
    _vitals = getattr(job, "web_vitals", None)
    if _vitals and _vitals.get("rows"):
        _CWV_CAVEAT = (
            "Core Web Vitals were measured, but only for the top "
            f"{_vitals.get('requested', 0)} pages of the priority queue, and only "
            "where enough real-user data exists. The rest of the site is unmeasured."
        )
    else:
        _CWV_CAVEAT = (
            "Core Web Vitals and real-user performance. Page weight and image size "
            "are measured; loading behaviour in a real browser is not."
        )
    _wp = getattr(job, "wp_audit", None)
    if _wp and _wp.get("plugins_total"):
        _CMS_CAVEAT = (
            "CMS configuration was read (see WordPress Configuration), but only "
            "what the plugin, theme and Site Health APIs expose. Plugin-internal "
            "state - whether a backup has ever run, how a security plugin is "
            "configured - has no generic API and was not inspected."
        )
    else:
        _CMS_CAVEAT = (
            "CMS and plugin configuration. TalkingToad reads only what the site "
            "serves publicly; it never signs in to WordPress during a scan."
        )
    if offsite:
        _OFFSITE_CAVEAT = (
            "Third-party authority scores, full backlink graphs and directory-listing "
            "consistency. Search Console's own link data IS included (see Off-Site "
            "Authority); the rest needs a commercial index TalkingToad does not license."
        )
    else:
        _OFFSITE_CAVEAT = (
            "Off-site authority - backlinks, referring domains and directory listings. "
            "Search Console link data was not supplied for this site, and third-party "
            "authority scores need a commercial index TalkingToad does not license."
        )
    _para("What this audit did not check", bold=True, color=COLOR_GRAY_800, size=12)
    for line in [
        _OFFSITE_CAVEAT,
        _CWV_CAVEAT,
        "Server logs, hosting configuration and CDN behaviour.",
        _CMS_CAVEAT,
        "WCAG conformance. Several accessibility signals are checked, but this is not "
        "an accessibility audit and must not be presented as one.",
        "Anything behind a login, and any page excluded by robots.txt.",
    ]:
        _para(f"- {line}", gap=1)
    pdf.ln(2)

    # ── Data sources ──
    if performance:
        _para("Data sources", bold=True, color=COLOR_GRAY_800, size=12)
        periods = ", ".join(performance.get("periods") or []) or "unknown period"
        _para(f"- Traffic figures: {performance.get('source', 'Search Console + GA4')}, "
              f"covering {periods}. These are first-party measurements, not estimates.", gap=1)
        if performance.get("is_stale"):
            _para(f"- That data is {performance.get('data_age_days')} days old and describes "
                  f"a past period, not current traffic.", gap=1)
        pdf.ln(2)

    # ── What the scores mean ──
    _para("What the scores mean", bold=True, color=COLOR_GRAY_800, size=12)
    for line in [
        "Health Score: per-page quality, averaged across the site.",
        "Agent Health Score: how readable the site is to AI assistants and answer engines.",
        "Site Hygiene: breadth - how much of the indexable estate is touched by "
        "widespread defects. A site can score well on Health and poorly on Hygiene.",
        "Citability grade: how quotable a page is likely to be to an answer engine.",
        "All of these are prioritisation aids. None of them forecasts rankings, traffic, "
        "enquiries or revenue.",
    ]:
        _para(f"- {line}", gap=1)


async def generate_pdf_report(
    job: CrawlJob,
    issues: list[Issue],
    summary: dict,
    include_help: bool = True,
    include_pages: bool = True,
    top_pages: list[dict] = None,
    image_summary: dict = None,
    top_images: list = None,
    executive_summary: str | None = None,
    performance: dict | None = None,
    priority_pages: list[dict] | None = None,
    prevalence: list | None = None,
    performance_failed: bool = False,
    filter_note: str | None = None,
    all_issues: list[Issue] | None = None,
    include_blueprints: bool = False,
    offsite: dict | None = None,
) -> bytes:
    # `issues` is what gets LISTED (filtered for this domain, if rules exist).
    # `_all_issues` is what the report REASONS FROM — llms.txt presence and the
    # off-site joins are facts about the site, not rows in a list. Defaults to
    # `issues`, so an unfiltered caller is unaffected.
    _all_issues = issues if all_issues is None else all_issues
    pdf = TalkingToadReport()
    pdf.alias_nb_pages()
    
    # ── Page 1: Title ──────────────────────────────────────────────────────
    pdf.add_page()
    pdf.set_y(80)
    pdf.set_font('helvetica', 'B', 48)
    pdf.set_text_color(*COLOR_TOAD_GREEN)
    pdf.set_x(25.4)
    pdf.cell(W, 25, "TalkingToad", align='C', new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_font('helvetica', 'B', 24)
    pdf.set_text_color(*COLOR_GRAY_800)
    pdf.set_x(25.4)
    pdf.cell(W, 15, "SEO Audit Report", align='C', new_x="LMARGIN", new_y="NEXT")
    
    pdf.ln(30)
    pdf.set_font('helvetica', '', 14)
    pdf.set_text_color(*COLOR_GRAY_500)
    pdf.set_x(25.4)
    
    # Use custom names if provided, fallback to URL
    prepared_for = job.settings.client_name if job.settings and job.settings.client_name else job.target_url
    pdf.multi_cell(W, 10, f"Prepared for: {pdf.clean_text(prepared_for)}", align='C')
    
    if job.settings and job.settings.prepared_by:
        pdf.set_x(25.4)
        pdf.cell(W, 10, f"Prepared by: {pdf.clean_text(job.settings.prepared_by)}", align='C', new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(25.4)
    pdf.cell(W, 10, f"Generated on: {datetime.now().strftime('%B %d, %Y')}", align='C', new_x="LMARGIN", new_y="NEXT")
    
    # ── Executive Summary (optional, AI-generated) ─────────────────────────
    if executive_summary:
        pdf.add_page()
        pdf.chapter_title("Executive Summary")
        pdf.set_font('helvetica', '', 11)
        pdf.set_text_color(*COLOR_GRAY_800)
        pdf.set_x(25.4)
        pdf.multi_cell(W, 6, pdf.clean_text(executive_summary))
        pdf.ln(5)

    # ── Page 2: Dashboard Summary ─────────────────────────────────────────
    pdf.add_page()
    pdf.chapter_title("Dashboard Summary")
    
    stats = [
        ("Health Score", summary.get("health_score", 0), COLOR_TOAD_GREEN),
        ("Agent Health Score", summary.get("agent_health_score", 0), COLOR_TOAD_GREEN),
        ("Pages Crawled", summary.get("pages_crawled", 0), COLOR_GRAY_800),
        ("Total Issues Found", _total_issues_figure(summary), COLOR_GRAY_800),
        ("Critical Issues", summary.get("by_severity", {}).get("critical", 0), COLOR_CRITICAL),
        ("Warnings", summary.get("by_severity", {}).get("warning", 0), COLOR_WARNING),
        # Info detail (2026-09-01): the figure beside "Health Score" is the one
        # the score counted; what the scan left out is stated in the same cell.
        ("Info Notices", _info_notices_figure(summary), COLOR_INFO),
    ]
    
    # E4 — Site Hygiene sits beside Health, with its meaning stated. Health is
    # per-page quality averaged; Hygiene is how much of the estate one defect
    # touches. Two numbers with stated meanings beat one asked to carry both.
    if prevalence:
        from api.services.prevalence import site_hygiene_score
        hygiene = site_hygiene_score(prevalence)
        systemic_n = sum(1 for p in prevalence if p.tier == "systemic")
        stats.insert(2, ("Site Hygiene", hygiene,
                         COLOR_TOAD_GREEN if hygiene >= 80 else
                         COLOR_WARNING if hygiene >= 60 else COLOR_CRITICAL))

    for label, val, color in stats:
        pdf.set_x(25.4)
        pdf.set_font('helvetica', 'B', 12)
        pdf.set_text_color(*COLOR_GRAY_500)
        pdf.cell(60, 10, pdf.clean_text(label + ":"))
        pdf.set_font('helvetica', 'B', 14)
        pdf.set_text_color(*color)
        pdf.cell(W - 60, 10, str(val), new_x="LMARGIN", new_y="NEXT")

    if prevalence:
        pdf.ln(3)
        pdf.set_x(25.4)
        pdf.set_font('helvetica', '', 9)
        pdf.set_text_color(*COLOR_GRAY_600)
        note = (
            "Health Score is per-page quality, averaged across the site. Site Hygiene is "
            "breadth: the percentage of indexable pages carrying NO systemic defect. A "
            "site can score well on one and poorly on the other - individually decent "
            "pages, all sharing the same template problem, is exactly that shape."
        )
        if systemic_n:
            note += (f" {systemic_n} systemic defect{'s' if systemic_n != 1 else ''} "
                     f"affect 30% or more of indexable pages - see Systemic Defects.")
        pdf.multi_cell(W, 4.5, pdf.clean_text(note))

    pdf.ln(10)
    pdf.set_x(25.4)
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(*COLOR_GRAY_800)
    pdf.cell(W, 10, "Issues by Category", new_x="LMARGIN", new_y="NEXT")
    
    # CLN2: category rows come from the single source of truth
    # registry.CATEGORY_DISPLAY (ordered key→label), so this list can never drift
    # from the crawler's categories or the frontend grid.
    from api.crawler.checkers.registry import CATEGORY_DISPLAY
    cat_list = [(label, key) for key, label in CATEGORY_DISPLAY]
    
    # P5.2: the SCORED count, so this table agrees with the health score two
    # pages back, with the findings list that follows, and with the workbook.
    # `by_category` (stored) is the fallback for an audit produced before the
    # scored map existed. The excluded figure travels with the count — a bare 0
    # is what a clean category looks like (P31).
    scored_map = summary.get("by_category_scored") or summary.get("by_category", {})
    excluded_map = summary.get("by_category_excluded") or {}

    for label, key in cat_list:
        count = scored_map.get(key, 0)
        excluded = excluded_map.get(key, 0)
        pdf.set_x(25.4)
        pdf.set_font('helvetica', '', 11)
        pdf.set_text_color(*COLOR_GRAY_600)
        pdf.cell(60, 8, pdf.clean_text(label + ":"))
        pdf.set_font('helvetica', 'B', 11)
        pdf.set_text_color(*COLOR_GRAY_800)
        pdf.cell(W - 60, 8, pdf.clean_text(
            f"{count} ({excluded} not scored)" if excluded else str(count)),
            new_x="LMARGIN", new_y="NEXT")

    # ── Search Performance + Priority Pages (E3.2) ────────────────────────
    # Rendered only when the Performance Ledger holds data for this domain. When
    # it does not, both sections are OMITTED and the omission is recorded in the
    # Scope & Caveats section — a missing section must never read as a pass (E7.4).
    _render_performance_section(pdf, performance)
    _render_web_vitals_section(pdf, getattr(job, "web_vitals", None))
    _render_offsite_section(pdf, offsite)
    _render_priority_pages_section(pdf, priority_pages, performance)

    # ── Page 3: Top 10 Pages ──────────────────────────────────────────────
    if top_pages:
        pdf.add_page()
        pdf.chapter_title("Top 10 Pages to Fix First")
        pdf.set_font('helvetica', '', 10)
        pdf.set_text_color(*COLOR_GRAY_600)
        pdf.set_x(25.4)
        # E3.3: the subtitle must name the ordering actually applied. With ledger
        # data the list is re-ordered by the §6.9 work queue (traffic + conversions
        # + health); without it, ordering and wording are exactly as before.
        if priority_pages:
            top_pages = _reorder_by_priority(top_pages, priority_pages)
            subtitle = ("Ranked by traffic, conversions and page health — the pages where "
                        "fixing an issue is worth the most. Issue counts are shown for context.")
        else:
            subtitle = "These pages have the highest concentration of issues and should be prioritized."
        pdf.multi_cell(W, 5, pdf.clean_text(subtitle))
        pdf.ln(5)

        for p in top_pages:
            if pdf.get_y() > 230:
                pdf.add_page()
            url = p.get("url", "")
            counts = p.get("issue_counts", {})
            crit = counts.get("critical", 0)
            warn = counts.get("warning", 0)
            info = counts.get("info", 0)

            pdf.set_x(25.4)
            pdf.set_font('helvetica', '', 9)
            pdf.set_text_color(*COLOR_GRAY_800)
            pdf.multi_cell(W, 5, pdf.clean_text(url))

            # Issue counts on one line with color coding
            pdf.set_x(30)
            pdf.set_font('helvetica', 'B', 9)
            if crit:
                pdf.set_text_color(*COLOR_CRITICAL)
                pdf.cell(0, 5, f"{crit} Critical  ", new_x="END")
            if warn:
                pdf.set_text_color(*COLOR_WARNING)
                pdf.cell(0, 5, f"{warn} Warning{'s' if warn != 1 else ''}  ", new_x="END")
            if info:
                pdf.set_text_color(*COLOR_INFO)
                pdf.cell(0, 5, f"{info} Info", new_x="END")
            # What the scan's info_detail dropped from THIS row. Same phrasing as
            # the Dashboard's Info Notices figure.
            if counts.get("info_excluded"):
                pdf.set_text_color(*COLOR_GRAY_500)
                pdf.cell(0, 5, f"  (+{counts['info_excluded']} excluded)", new_x="END")
            if not crit and not warn and not info:
                pdf.set_text_color(*COLOR_TOAD_GREEN)
                pdf.cell(0, 5, "No issues", new_x="END")
            pdf.ln(4)

            pdf.set_draw_color(229, 231, 235)
            pdf.set_x(25.4)
            pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + W, pdf.get_y())
            pdf.ln(3)

    # ── Systemic Defects (E4) ─────────────────────────────────────
    _render_systemic_defects_section(pdf, prevalence)

    # ── Remediation Roadmap (E7.1) ───────────────────────────────
    # Replaces the old flat "What to Do Next" checklist: same findings, but with
    # an owner, a phase and a countable exit condition, because a list of issue
    # names leaves "who does this, when, and how do we know it's done" unanswered.
    _render_roadmap_section(pdf, issues, prevalence, priority_pages)

    # ── Action Checklist ─────────────────────────────────────────
    if issues:
        pdf.add_page()
        pdf.chapter_title("What to Do Next")
        pdf.set_font('helvetica', '', 10)
        pdf.set_text_color(*COLOR_GRAY_600)
        pdf.set_x(25.4)
        # E4: ordering names itself. With prevalence available the list leads
        # with defects that touch the most pages, because a 56-page template
        # defect is one edit and a 3-page one is three.
        if prevalence:
            checklist_blurb = ("Highest-priority actions, ordered by how much of the site each "
                               "defect touches and then by impact. Work through them in order.")
        else:
            checklist_blurb = ("These are the highest-priority actions to improve your site's SEO. "
                               "Work through them in order.")
        pdf.multi_cell(W, 5, pdf.clean_text(checklist_blurb))
        pdf.ln(5)

        # Deduplicate by issue_code, take highest-priority first
        from collections import OrderedDict
        seen_codes: OrderedDict[str, Issue] = OrderedDict()
        sorted_issues = sorted(issues, key=_checklist_sort_key(prevalence))
        for iss in sorted_issues:
            if iss.issue_code not in seen_codes and len(seen_codes) < 15:
                seen_codes[iss.issue_code] = iss

        for idx, (code, iss) in enumerate(seen_codes.items(), 1):
            if pdf.get_y() > 240:
                pdf.add_page()

            sev_color = (
                COLOR_CRITICAL if iss.severity == "critical"
                else COLOR_WARNING if iss.severity == "warning"
                else COLOR_INFO
            )

            # Checkbox + description
            pdf.set_x(25.4)
            pdf.set_font('helvetica', '', 11)
            pdf.set_text_color(*COLOR_GRAY_800)
            pdf.cell(8, 7, "[ ]")

            pdf.set_font('helvetica', 'B', 10)
            pdf.set_text_color(*sev_color)
            label = iss.human_description or iss.issue_code
            pdf.cell(0, 7, pdf.clean_text(label), new_x="LMARGIN", new_y="NEXT")

            # Count + recommendation
            count = sum(1 for i in issues if i.issue_code == code)
            pdf.set_x(33.4)
            pdf.set_font('helvetica', '', 9)
            pdf.set_text_color(*COLOR_GRAY_500)
            rec = iss.recommendation or iss.description or ""
            if len(rec) > 120:
                rec = rec[:117] + "..."
            pdf.multi_cell(W - 8, 5, pdf.clean_text(f"{count} page{'s' if count != 1 else ''} affected. {rec}"))
            pdf.ln(2)

    # ── AI Readiness (llms.txt) ───────────────────────────────────
    pdf.add_page()
    pdf.chapter_title("AI Readiness: llms.txt Status")
    pdf.set_font('helvetica', '', 10)
    pdf.set_text_color(*COLOR_GRAY_600)
    pdf.set_x(25.4)
    pdf.multi_cell(W, 5, "An llms.txt file is a machine-readable index that helps AI agents (like Gemini and ChatGPT) navigate your most important content.")
    pdf.ln(5)

    # 1. Existing file status
    pdf.set_x(25.4)
    pdf.set_font('helvetica', 'B', 11)
    pdf.set_text_color(*COLOR_GRAY_800)
    pdf.cell(W, 8, "Status of live /llms.txt file:", new_x="LMARGIN", new_y="NEXT")
    
    # F1 — derived from the UNFILTERED set. Hiding a row is
    # presentational; deciding a FACT about the site from the absence
    # of a row is not. LLMS_TXT_MISSING is `info`, so the headline
    # 'hide all info' rule made this assert the opposite of the truth.
    existing_issue = next((i for i in _all_issues if i.issue_code == "LLMS_TXT_MISSING"), None)
    pdf.set_x(25.4)
    if existing_issue:
        pdf.set_font('helvetica', 'B', 10)
        pdf.set_text_color(*COLOR_CRITICAL)
        pdf.cell(W, 8, "MISSING - No /llms.txt file was detected during the crawl.", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font('helvetica', 'B', 10)
        pdf.set_text_color(*COLOR_TOAD_GREEN)
        pdf.cell(W, 8, "FOUND - A file exists at your root domain.", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)

    # 2. Proposed content
    pdf.set_x(25.4)
    pdf.set_font('helvetica', 'B', 11)
    pdf.set_text_color(*COLOR_GRAY_800)
    pdf.cell(W, 8, "Proposed /llms.txt content (Machine-readable):", new_x="LMARGIN", new_y="NEXT")
    
    proposed_content = job.llms_txt_custom or "No proposed content has been saved yet. Use the TalkingToad dashboard to generate and save your optimized llms.txt file."
    
    pdf.set_x(25.4)
    pdf.set_fill_color(*COLOR_GRAY_100)
    pdf.set_font('courier', '', 8)
    pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(W, 4, pdf.clean_text(proposed_content), fill=True, border=1)
    
    pdf.ln(10)

    # ── Image Health Summary ──────────────────────────────────────────────
    if image_summary and image_summary.get("total_images", 0) > 0:
        pdf.add_page()
        pdf.chapter_title("Image Health Summary")
        pdf.set_font('helvetica', '', 10)
        pdf.set_text_color(*COLOR_GRAY_600)
        pdf.set_x(25.4)
        pdf.multi_cell(W, 5, "Analysis of images found during the crawl, including accessibility, performance, and optimization metrics.")

        # E1.4 (rule 6, P9): when the per-job image cap turned images away, say so
        # here rather than letting the health score read as full coverage.
        seen_total = getattr(job, "images_seen_total", None)
        collected = getattr(job, "images_collected", None)
        if seen_total and collected is not None and seen_total > collected:
            pdf.ln(2)
            pdf.set_x(25.4)
            pdf.set_font('helvetica', 'B', 10)
            pdf.set_text_color(*COLOR_WARNING)
            pdf.multi_cell(W, 5, pdf.clean_text(
                f"Coverage: analysed {collected} of {seen_total} distinct images found. "
                f"The scores below describe the analysed sample, not the whole site."
            ))
            pdf.set_text_color(*COLOR_GRAY_600)
        pdf.ln(5)

        # Image stats
        img_stats = [
            ("Image Health Score", f"{image_summary.get('image_health_score', 0)}%",
             COLOR_TOAD_GREEN if image_summary.get('image_health_score', 0) >= 80 else
             COLOR_WARNING if image_summary.get('image_health_score', 0) >= 60 else COLOR_CRITICAL),
            ("Total Images", str(image_summary.get('total_images', 0)), COLOR_GRAY_800),
            ("Total Size", f"{image_summary.get('total_size_kb', 0)} KB", COLOR_GRAY_800),
            ("Avg Load Time", f"{image_summary.get('avg_load_time_ms', 0)}ms",
             COLOR_WARNING if image_summary.get('avg_load_time_ms', 0) > 500 else COLOR_GRAY_800),
        ]

        for label, val, color in img_stats:
            pdf.set_x(25.4)
            pdf.set_font('helvetica', 'B', 12)
            pdf.set_text_color(*COLOR_GRAY_500)
            pdf.cell(60, 10, pdf.clean_text(label + ":"))
            pdf.set_font('helvetica', 'B', 14)
            pdf.set_text_color(*color)
            pdf.cell(W - 60, 10, val, new_x="LMARGIN", new_y="NEXT")

        # Format breakdown
        by_format = image_summary.get("by_format", {})
        if by_format:
            pdf.ln(5)
            pdf.set_x(25.4)
            pdf.set_font('helvetica', 'B', 12)
            pdf.set_text_color(*COLOR_GRAY_800)
            pdf.cell(W, 8, "Images by Format:", new_x="LMARGIN", new_y="NEXT")

            for fmt, count in sorted(by_format.items(), key=lambda x: -x[1]):
                pdf.set_x(25.4)
                pdf.set_font('helvetica', '', 11)
                pdf.set_text_color(*COLOR_GRAY_600)
                pdf.cell(60, 8, pdf.clean_text(fmt.upper() + ":"))
                pdf.set_font('helvetica', 'B', 11)
                pdf.set_text_color(*COLOR_GRAY_800)
                pdf.cell(W - 60, 8, str(count), new_x="LMARGIN", new_y="NEXT")

        # Top issue counts
        by_issue = image_summary.get("by_issue", {})
        if by_issue:
            pdf.ln(5)
            pdf.set_x(25.4)
            pdf.set_font('helvetica', 'B', 12)
            pdf.set_text_color(*COLOR_GRAY_800)
            pdf.cell(W, 8, "Top Image Issues:", new_x="LMARGIN", new_y="NEXT")

            for code, count in sorted(by_issue.items(), key=lambda x: -x[1])[:8]:
                pdf.set_x(25.4)
                pdf.set_font('helvetica', '', 11)
                pdf.set_text_color(*COLOR_GRAY_600)
                display_code = code.replace('IMG_', '').replace('_', ' ').title()
                pdf.cell(80, 8, pdf.clean_text(display_code + ":"))
                pdf.set_font('helvetica', 'B', 11)
                pdf.set_text_color(*COLOR_GRAY_800)
                pdf.cell(W - 80, 8, f"{count} image{'s' if count != 1 else ''}", new_x="LMARGIN", new_y="NEXT")

        # Top problematic images
        if top_images and len(top_images) > 0:
            pdf.ln(5)
            pdf.set_x(25.4)
            pdf.set_font('helvetica', 'B', 12)
            pdf.set_text_color(*COLOR_GRAY_800)
            pdf.cell(W, 8, "Images Needing Attention:", new_x="LMARGIN", new_y="NEXT")

            for img in top_images[:10]:
                if pdf.get_y() > 230:
                    pdf.add_page()

                score = img.overall_score if hasattr(img, 'overall_score') else img.get('overall_score', 0)
                filename = img.filename if hasattr(img, 'filename') else img.get('filename', 'Unknown')
                issues_list = img.issues if hasattr(img, 'issues') else img.get('issues', [])

                score_color = COLOR_TOAD_GREEN if score >= 80 else COLOR_WARNING if score >= 60 else COLOR_CRITICAL

                pdf.set_x(25.4)
                pdf.set_font('helvetica', 'B', 10)
                pdf.set_text_color(*score_color)
                pdf.cell(15, 6, str(round(score)))
                pdf.set_text_color(*COLOR_GRAY_800)
                pdf.cell(W - 15, 6, pdf.clean_text(filename[:60]), new_x="LMARGIN", new_y="NEXT")

                if issues_list:
                    pdf.set_x(40)
                    pdf.set_font('helvetica', '', 9)
                    pdf.set_text_color(*COLOR_GRAY_500)
                    issue_text = ", ".join([c.replace('IMG_', '') for c in issues_list[:4]])
                    if len(issues_list) > 4:
                        issue_text += f" +{len(issues_list) - 4} more"
                    pdf.cell(W - 15, 5, pdf.clean_text(issue_text), new_x="LMARGIN", new_y="NEXT")

    # ── Detailed Issues by Category ──────────────────────────────────────
    from collections import defaultdict
    groups = defaultdict(lambda: defaultdict(list))
    for i in issues:
        groups[i.category][i.issue_code].append(i)
        
    for cat_slug in sorted(groups.keys()):
        pdf.add_page()
        pdf.chapter_title(cat_slug.replace('_', ' ').title() + " Details", size=22)

        # Tier-explainer intro for AI Readiness category
        if cat_slug == "ai_readiness":
            pdf.set_font('helvetica', 'I', 9)
            pdf.set_text_color(*COLOR_GRAY_600)
            intro_text = (
                "The confidence tier indicates the strength of evidence behind each finding: "
                "Established (strong evidence), Reasonable proxy (moderate evidence), "
                "Heuristic (limited evidence)."
            )
            pdf.set_x(25.4)
            pdf.multi_cell(W, 5, pdf.clean_text(intro_text))
            pdf.ln(3)
            pdf.set_font('helvetica', '', 9)
            pdf.set_text_color(*COLOR_GRAY_600)

        # Sort issue types by severity (critical first), then by count
        sev_order = {"critical": 0, "warning": 1, "info": 2}
        sorted_codes = sorted(
            groups[cat_slug].keys(),
            key=lambda c: (sev_order.get(groups[cat_slug][c][0].severity, 3), -len(groups[cat_slug][c]))
        )

        for code in sorted_codes:
            # Prevent orphaned titles: need room for title + description + start of help
            if pdf.get_y() > 200:
                pdf.add_page()

            examples = groups[cat_slug][code]
            first = examples[0]
            urls = sorted(list(set([str(i.page_url) for i in examples if i.page_url])))
            count = len(urls)

            # Severity color for the badge
            sev_color = (
                COLOR_CRITICAL if first.severity == "critical"
                else COLOR_WARNING if first.severity == "warning"
                else COLOR_INFO
            )

            # Issue title with count: "Dead Link - CRITICAL (23 pages)"
            pdf.set_x(25.4)
            pdf.set_font('helvetica', 'B', 12)
            pdf.set_text_color(*COLOR_GRAY_800)
            title = first.human_description or code
            pdf.cell(0, 8, pdf.clean_text(title), new_x="END")

            pdf.set_font('helvetica', 'B', 10)
            pdf.set_text_color(*sev_color)
            sev_label = f"  {first.severity.upper()}"
            pdf.cell(0, 8, sev_label, new_x="END")

            pdf.set_text_color(*COLOR_GRAY_500)
            pdf.set_font('helvetica', '', 10)
            pdf.cell(0, 8, f"  ({count} page{'s' if count != 1 else ''})", new_x="LMARGIN", new_y="NEXT")

            # Description line (always shown — one line summary)
            desc = first.description
            if desc:
                pdf.set_x(25.4)
                pdf.set_font('helvetica', '', 9)
                pdf.set_text_color(*COLOR_GRAY_600)
                pdf.multi_cell(W, 5, pdf.clean_text(desc))
                pdf.ln(1)

            # Confidence evidence line (AI Readiness issues)
            if first.confidence_label:
                confidence_colors = {
                    "Established": COLOR_TOAD_GREEN,
                    "Reasonable proxy": COLOR_AMBER,
                    "Heuristic": COLOR_GRAY_500,
                }
                color = confidence_colors.get(first.confidence_label, COLOR_GRAY_600)
                pdf.set_x(25.4)
                pdf.set_text_color(*color)
                pdf.set_font('helvetica', 'I', 8)
                pdf.multi_cell(W, 4, pdf.clean_text(f"Evidence: {first.confidence_label}"))
                pdf.set_font('helvetica', '', 9)
                pdf.set_text_color(*COLOR_GRAY_600)

            # Help text (optional)
            if include_help:
                help_entry = ISSUE_HELP.get(code, {})
                what = help_entry.get("definition") or help_entry.get("what") or first.what_it_is or first.description or ""
                impact_text = help_entry.get("impact") or first.impact_desc or f"Impact score: {first.impact}/10."
                how = help_entry.get("fix") or first.how_to_fix or first.recommendation or ""
                good_vs_bad = help_entry.get("good_vs_bad")
                mislead = help_entry.get("how_it_can_mislead")
                mission = help_entry.get("mission_impact")
                if what or how:
                    pdf.draw_help_section(what, impact_text, how, good_vs_bad=good_vs_bad,
                                          mislead=mislead, mission=mission)

            # Evidence — WHICH element on the page is wrong (2026-08-29).
            # Previously the report showed only the affected page URLs, so a
            # finding like "6 unsafe external links" named the page and left the
            # operator to re-audit it by hand. Most codes already carried the
            # detail in `extra`; nothing rendered it (P25).
            # `first` is this group's representative issue. Passing `iss` here
            # (a leaked variable from the checklist loop above) was in scope,
            # raised nothing, and rendered the wrong issue's evidence.
            _render_issue_evidence(pdf, first)

            # Affected URLs (always shown — this is the core value of the report)
            if include_pages and urls:
                pdf.set_x(25.4)
                pdf.set_font('helvetica', 'B', 9)
                pdf.set_text_color(*COLOR_GRAY_600)
                pdf.cell(W, 6, f"Affected URLs:", new_x="LMARGIN", new_y="NEXT")

                pdf.set_font('helvetica', '', 8)
                pdf.set_text_color(*COLOR_GRAY_800)
                for url in urls[:20]:
                    if pdf.get_y() > 250:
                        pdf.add_page()
                    pdf.set_x(30)
                    pdf.multi_cell(W - 5, 4, pdf.clean_text(url))

                if len(urls) > 20:
                    pdf.set_x(30)
                    pdf.set_font('helvetica', 'I', 8)
                    pdf.set_text_color(*COLOR_GRAY_500)
                    pdf.cell(W - 5, 5, f"... and {len(urls)-20} more. See spreadsheet for full list.", new_x="LMARGIN", new_y="NEXT")

            pdf.ln(3)
            pdf.set_draw_color(229, 231, 235)
            pdf.set_x(25.4)
            pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + W, pdf.get_y())
            pdf.ln(4)

    # ── Page Blueprints (D4) ─────────────────────────────────────
    # APPROVED drafts only, and only when the caller opted in. The default is
    # off: AI-drafted copy in a client PDF changes what the document is, and the
    # external audit that inspired this required human review of its own drafts
    # before publication.
    _render_blueprints_section(pdf, getattr(job, "blueprints", None),
                               include=include_blueprints)

    # ── WordPress Configuration (D3) ─────────────────────────────
    _render_wp_audit_section(pdf, getattr(job, "wp_audit", None))

    # ── Scope, Method and Caveats (E7.2) ─────────────────────────
    # ALWAYS rendered, including on a clean site. A reader who cannot see what
    # was NOT checked will assume the audit was complete.
    _render_caveats_section(
        pdf, job, summary,
        filter_note=filter_note,
        performance=performance,
        image_summary=image_summary,
        prevalence=prevalence,
        performance_failed=performance_failed,
        offsite=offsite,
    )

    pdf.set_x(25.4)
    pdf.ln(10)
    pdf.set_font('helvetica', 'I', 8)
    pdf.set_text_color(156, 163, 175)
    pdf.multi_cell(W, 4, "Disclaimer: TalkingToad is an automated tool. Please verify critical findings manually.")

    return pdf.output()

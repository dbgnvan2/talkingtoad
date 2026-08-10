"""Analytics & Measurement checker tests (MI1–MI6).

Exercises the per-page checker (``checkers/analytics.py``) via the full
``check_page`` path and the site-level MI3 via ``check_cross_page``.

Spec: docs/pending/2026-08-06_measurement-integrity-checks.md
"""

from api.crawler.fetcher import FetchResult
from api.crawler.parser import parse_page
from api.crawler.issue_checker import check_page, check_cross_page

BASE = "https://example.org/"

GA4_SRC = '<script async src="https://www.googletagmanager.com/gtag/js?id=G-ABC123XYZ"></script>'
GA4_CFG = ("<script>function gtag(){dataLayer.push(arguments);}"
           "gtag('config','G-ABC123XYZ');</script>")
GA4 = GA4_SRC + GA4_CFG
GA4_CFG_B = "<script>function gtag(){};gtag('config','G-ABC123XYZ');</script>"
GTM = (
    "<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':new Date().getTime(),"
    "event:'gtm.js'});var j=d.createElement(s);"
    "j.src='https://www.googletagmanager.com/gtm.js?id=GTM-XYZ123';"
    "})(window,document,'script','dataLayer','GTM-XYZ123');</script>"
)
CONSENT = "<script>gtag('consent','default',{analytics_storage:'denied'});</script>"


def _page(body_or_head, url=BASE + "p", head=True):
    inner = f"<head>{body_or_head}</head><body><p>hi</p></body>" if head \
        else f"<head><title>t</title></head><body>{body_or_head}</body>"
    res = FetchResult(url=url, final_url=url, status_code=200, headers={},
                      html=f"<html>{inner}</html>", content_type="text/html")
    return parse_page(res, BASE)


def _codes(page):
    return {i.code for i in check_page(page)}


# ── MI1 ────────────────────────────────────────────────────────────────────
def test_mi1_tag_missing_fires_and_clears():
    assert "ANALYTICS_TAG_MISSING" in _codes(_page("<title>t</title>"))
    assert "ANALYTICS_TAG_MISSING" not in _codes(_page(GA4))
    assert "ANALYTICS_TAG_MISSING" not in _codes(_page(GTM))


def test_mi1_dead_ua_only_still_missing():
    """Adversarial: a page whose ONLY tag is legacy Universal Analytics is still
    'unmeasured' for current GA4 reporting → MI1 fires."""
    ua = ("<script src='https://www.google-analytics.com/analytics.js'></script>"
          "<script>ga('create','UA-12345-1','auto');</script>")
    assert "ANALYTICS_TAG_MISSING" in _codes(_page(ua))


# ── MI2 ────────────────────────────────────────────────────────────────────
def test_mi2_duplicate_ga4_plus_gtm():
    assert "ANALYTICS_TAG_DUPLICATE" in _codes(_page(GA4 + GTM))


def test_mi2_two_ga4_config_calls():
    assert "ANALYTICS_TAG_DUPLICATE" in _codes(_page(GA4_CFG + GA4_CFG_B))


def test_mi2_standard_single_install_not_duplicate():
    """Adversarial: the normal install (one gtag.js loader + one config call for
    one id, no GTM) must NOT be flagged as duplicate."""
    assert "ANALYTICS_TAG_DUPLICATE" not in _codes(_page(GA4))
    # GTM-only (GTM loads GA4 internally) is also not a duplicate.
    assert "ANALYTICS_TAG_DUPLICATE" not in _codes(_page(GTM))


# Google Ads gtag('config','AW-…') / gtag/js loader shares GA4's call shape but
# is NOT GA4 — the require_id gate must exclude it. Common on Google Ad Grants
# nonprofit sites running GA4-via-GTM alongside Ads remarketing.
ADS = ('<script async src="https://www.googletagmanager.com/gtag/js?id=AW-99988877"></script>'
       "<script>gtag('config','AW-99988877');</script>")


def test_mi2_ga4_via_gtm_plus_google_ads_not_duplicate():
    """Regression (review finding #1): GA4-via-GTM + Google Ads via gtag must NOT
    be flagged as a duplicate GA4 tag (Ads carries no G- id → not type ga4)."""
    codes = _codes(_page(GTM + ADS))
    assert "ANALYTICS_TAG_DUPLICATE" not in codes
    assert "ANALYTICS_TAG_MISSING" not in codes  # GTM present → measured


def test_mi1_google_ads_only_is_still_untagged():
    """Regression (review finding #1): a page whose only gtag is Google Ads has
    no analytics measurement → MI1 fires."""
    assert "ANALYTICS_TAG_MISSING" in _codes(_page(ADS))


# ── GT: the unified Google tag (GT-…) must count as a present tag ────────────
# The exact form observed on livingsystems.ca (a real false-positive site).
GOOGLE_TAG = ('<script async src="https://www.googletagmanager.com/gtag/js?id=GT-T9K65DT"></script>'
              "<script>function gtag(){dataLayer.push(arguments);}gtag('config','GT-T9K65DT');</script>")


def test_gt3_1_google_tag_gt_id_is_not_missing():
    """GT3.1 (adversarial): a genuinely-measured site whose tag is a Google tag
    (GT-…) must NOT be reported as ANALYTICS_TAG_MISSING."""
    codes = _codes(_page(GOOGLE_TAG))
    assert "ANALYTICS_TAG_MISSING" not in codes
    assert "ANALYTICS_TAG_DUPLICATE" not in codes  # a single GT- install is not a duplicate


def test_gt3_3_google_ads_only_still_missing():
    """GT3.3: the fix didn't flip everything to 'present' — an AW--only (Google
    Ads) page still has no measurement tag → MI1 fires."""
    assert "ANALYTICS_TAG_MISSING" in _codes(_page(ADS))


def test_gt3_4_google_tag_plus_gtm_is_duplicate():
    """GT3.4: a direct Google tag (GT-) co-existing with a GTM container is a
    double-tag, exactly like GA4 (G-) + GTM."""
    assert "ANALYTICS_TAG_DUPLICATE" in _codes(_page(GOOGLE_TAG + GTM))


# ── MI3 (cross-page) ─────────────────────────────────────────────────────────
def _p(html, url):
    res = FetchResult(url=url, final_url=url, status_code=200, headers={},
                      html=f"<html><head>{html}</head><body><p>hi</p></body></html>",
                      content_type="text/html")
    return parse_page(res, BASE)


def test_mi3_inconsistent_ids_cross_page():
    GA4_B = ('<script async src="https://www.googletagmanager.com/gtag/js?id=G-BBB222CCC"></script>'
             "<script>gtag('config','G-BBB222CCC');</script>")
    pages = [_p(GA4, BASE + "a"), _p(GA4, BASE + "b"), _p(GA4_B, BASE + "c")]
    codes = {i.code for i in check_cross_page(pages)}
    assert "ANALYTICS_ID_INCONSISTENT" in codes


def test_mi3_tag_on_some_pages_only():
    pages = [_p(GA4, BASE + "a"), _p("<title>t</title>", BASE + "b")]
    codes = {i.code for i in check_cross_page(pages)}
    assert "ANALYTICS_ID_INCONSISTENT" in codes


def test_mi3_uniform_ids_no_flag():
    """Adversarial: identical tag on every page must NOT flag inconsistency."""
    pages = [_p(GA4, BASE + "a"), _p(GA4, BASE + "b"), _p(GA4, BASE + "c")]
    codes = {i.code for i in check_cross_page(pages)}
    assert "ANALYTICS_ID_INCONSISTENT" not in codes


# ── MI4 ────────────────────────────────────────────────────────────────────
def test_mi4_consent_and_suppression():
    # Tag present, no consent → fires
    assert "CONSENT_MODE_MISSING" in _codes(_page(GA4))
    # Tag present + consent default → cleared
    assert "CONSENT_MODE_MISSING" not in _codes(_page(GA4 + CONSENT))
    # No tag → MI4 suppressed entirely (only MI1 fires)
    codes = _codes(_page("<title>t</title>"))
    assert "CONSENT_MODE_MISSING" not in codes
    assert "ANALYTICS_TAG_MISSING" in codes


# ── MI5 ────────────────────────────────────────────────────────────────────
def test_mi5_self_ref_utm_internal_only():
    # Internal link with UTM → fires
    codes = _codes(_page('<a href="/about?utm_source=newsletter">About</a>', head=False))
    assert "SELF_REFERENCING_UTM" in codes
    # External link with UTM → must NOT fire (adversarial)
    codes = _codes(_page('<a href="https://other.com/x?utm_source=n">x</a>', head=False))
    assert "SELF_REFERENCING_UTM" not in codes
    # Clean internal link → no fire
    codes = _codes(_page('<a href="/about">About</a>', head=False))
    assert "SELF_REFERENCING_UTM" not in codes


def test_mi5_click_id_params():
    codes = _codes(_page('<a href="/landing?gclid=abc123">Landing</a>', head=False))
    assert "SELF_REFERENCING_UTM" in codes


def test_mi5_blank_and_uppercase_params():
    """Regression (review finding #3): blank-valued and upper-cased campaign
    params still reset attribution and must be caught."""
    assert "SELF_REFERENCING_UTM" in _codes(_page('<a href="/a?utm_source=">A</a>', head=False))
    assert "SELF_REFERENCING_UTM" in _codes(_page('<a href="/b?UTM_Source=news">B</a>', head=False))
    assert "SELF_REFERENCING_UTM" in _codes(_page('<a href="/c?GCLID=xyz">C</a>', head=False))


# ── MI6 ────────────────────────────────────────────────────────────────────
def test_mi6_untrackable_outbound():
    # External image-only link, no label → fires
    codes = _codes(_page('<a href="https://partner.org/"><img src="/l.png"></a>', head=False))
    assert "OUTBOUND_LINK_UNTRACKABLE" in codes
    # Same link WITH aria-label → must NOT fire (adversarial)
    codes = _codes(_page('<a href="https://partner.org/" aria-label="Partner"><img src="/l.png"></a>',
                         head=False))
    assert "OUTBOUND_LINK_UNTRACKABLE" not in codes

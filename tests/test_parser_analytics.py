"""Parser-level tests for Analytics & Measurement signal extraction.

Covers the three parser additions behind the ``analytics`` category checks:
``analytics_tags``, ``has_consent_mode`` and ``untrackable_outbound_hrefs``.

Spec: docs/pending/2026-08-06_measurement-integrity-checks.md (MI1–MI6)
"""

from api.crawler.fetcher import FetchResult
from api.crawler.parser import parse_page

BASE = "https://example.org/"

GA4 = (
    '<script async src="https://www.googletagmanager.com/gtag/js?id=G-ABC123XYZ"></script>'
    "<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}"
    "gtag('js',new Date());gtag('config','G-ABC123XYZ');</script>"
)
GTM = (
    "<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':new Date().getTime(),"
    "event:'gtm.js'});var f=d.getElementsByTagName(s)[0],j=d.createElement(s);j.async=true;"
    "j.src='https://www.googletagmanager.com/gtm.js?id=GTM-XYZ123';f.parentNode.insertBefore(j,f);"
    "})(window,document,'script','dataLayer','GTM-XYZ123');</script>"
)
CONSENT = "<script>gtag('consent','default',{ad_storage:'denied',analytics_storage:'denied'});</script>"


def _page(html, url=BASE + "p"):
    res = FetchResult(url=url, final_url=url, status_code=200, headers={},
                      html=f"<html><head>{html}</head><body><p>hi</p></body></html>",
                      content_type="text/html")
    return parse_page(res, BASE)


def test_extract_tags_and_consent():
    # GA4 only → one ga4 detection, no consent signal
    p = _page(GA4)
    types = {t["type"] for t in (p.analytics_tags or [])}
    assert "ga4" in types
    ids = {t["id"] for t in p.analytics_tags}
    assert "G-ABC123XYZ" in ids
    assert p.has_consent_mode is False

    # GTM only → gtm detection with the container id
    p = _page(GTM)
    types = {t["type"] for t in (p.analytics_tags or [])}
    assert "gtm" in types
    assert any(t["id"] == "GTM-XYZ123" for t in p.analytics_tags)

    # GA4 + consent default → consent detected
    p = _page(GA4 + CONSENT)
    assert p.has_consent_mode is True

    # No scripts at all → tags None, consent None (not False)
    p = _page("<title>t</title>")
    assert p.analytics_tags is None
    assert p.has_consent_mode is None


def test_consent_mode_requires_real_gtag_consent_call():
    """Regression (review finding #4): an unrelated script variable containing
    'consent_mode' must NOT be read as Consent Mode being configured."""
    noise = "<script>var cookie_consent_mode = getBannerChoice();</script>"
    p = _page(GA4 + noise)
    assert p.has_consent_mode is False


def test_google_ads_gtag_is_not_ga4():
    """Regression (review finding #1): a Google Ads gtag('config','AW-…') must
    not be typed as a GA4 tag."""
    ads = ('<script async src="https://www.googletagmanager.com/gtag/js?id=AW-99988877"></script>'
           "<script>gtag('config','AW-99988877');</script>")
    p = _page(ads)
    assert p.analytics_tags is None  # no G- id → no ga4 detection, nothing else present


def test_cta_elements_extracted_with_markers():
    """MI7.4.6: parser records button-like CTAs with text + marker attributes;
    a track- class, a data-track attr, and an inline gtag onclick all surface."""
    html = ("<html><head><title>t</title></head><body>"
            '<a class="elementor-button track-donate" href="/donate">Donate now</a>'
            '<button data-track-event="book">Book a session</button>'
            "<button onclick=\"gtag('event','x')\">Contact us</button>"
            '<a class="btn" href="/x">Read more</a>'
            "<span>not a button</span>"
            "</body></html>")
    res = FetchResult(url=BASE + "p", final_url=BASE + "p", status_code=200, headers={},
                      html=html, content_type="text/html")
    p = parse_page(res, BASE)
    ctas = p.cta_elements
    assert ctas, "CTA elements must be extracted"
    by_text = {c["text"]: c for c in ctas}
    assert {"Donate now", "Book a session", "Contact us", "Read more"} <= set(by_text)
    assert "not a button" not in by_text
    assert "track-donate" in by_text["Donate now"]["class"]
    assert "data-track-event" in by_text["Book a session"]["data_attrs"]
    assert "gtag(" in by_text["Contact us"]["onclick"]


def test_cta_ancestor_marker_captured_in_context():
    """MI7: a track_ class on the widget WRAPPER (not the <a>) is captured in the
    CTA's ancestor `context` so the checker can detect wrapper-based tracking."""
    html = ("<html><head><title>t</title></head><body>"
            '<div class="elementor-widget elementor-widget-button track_beginCounselling">'
            '<span><a class="elementor-button" href="/x">Begin Counselling Intake</a></span>'
            "</div></body></html>")
    res = FetchResult(url=BASE + "p", final_url=BASE + "p", status_code=200, headers={},
                      html=html, content_type="text/html")
    p = parse_page(res, BASE)
    cta = p.cta_elements[0]
    assert "track" not in cta["class"].lower()                    # marker is NOT on the <a>
    assert "track_begincounselling" in cta["context_classes"]     # it IS on an ancestor


def test_gt3_2_google_tag_typed_and_id_extracted():
    """GT3.2: a Google tag (GT-…) is typed 'google_tag' with its GT- id — not
    ga4, not a dropped None (the livingsystems.ca form)."""
    html = ('<script async src="https://www.googletagmanager.com/gtag/js?id=GT-T9K65DT"></script>'
            "<script>function gtag(){dataLayer.push(arguments);}gtag('config','GT-T9K65DT');</script>")
    p = _page(html)
    assert p.analytics_tags, "the GT- Google tag must be detected"
    types = {t["type"] for t in p.analytics_tags}
    assert "google_tag" in types
    assert "ga4" not in types
    gt = next(t for t in p.analytics_tags if t["type"] == "google_tag")
    assert gt["id"] == "GT-T9K65DT"


def test_bare_measurement_id_in_prose_is_not_a_tag():
    """Adversarial: a G-XXXX string in visible text (no gtag call/loader) must
    NOT be detected as an analytics tag."""
    p = _page("<title>t</title>")
    body = "<p>Our GA4 id is G-FAKE123ID but there is no tag installed.</p>"
    res = FetchResult(url=BASE, final_url=BASE, status_code=200, headers={},
                      html=f"<html><body>{body}</body></html>", content_type="text/html")
    p = parse_page(res, BASE)
    assert p.analytics_tags is None


def test_untrackable_outbound_href_detection():
    # External image-only link, no label → detected
    html = '<a href="https://partner.org/"><img src="/logo.png"></a>'
    p = _page(html)
    assert p.untrackable_outbound_hrefs == ["https://partner.org/"]

    # Same link WITH aria-label → not detected (adversarial)
    p = _page('<a href="https://partner.org/" aria-label="Partner"><img src="/logo.png"></a>')
    assert p.untrackable_outbound_hrefs is None

    # External image link WITH alt text → not detected
    p = _page('<a href="https://partner.org/"><img src="/logo.png" alt="Partner logo"></a>')
    assert p.untrackable_outbound_hrefs is None

    # INTERNAL image-only link → not detected (external only)
    p = _page('<a href="/about"><img src="/logo.png"></a>')
    assert p.untrackable_outbound_hrefs is None

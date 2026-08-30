"""AF8 — <image:loc> must not be mistaken for a page URL.

Spec:  docs/pending/2026-08-30_audit-fixes.md#AF8
Audit: docs/audit/2026-08-30_full-check-audit.md (F20)

BeautifulSoup's `find_all("loc")` matches on LOCAL name, so it also returns the
`<image:loc>` entries the sitemap-image extension nests inside each `<url>`.
Yoast emits those for every featured image. Measured on livingsystems.ca: the
parser returned 236 "pages" for a 139-page site — 97 image files — which were
then seeded into the crawl queue and fetched as pages.
"""
from __future__ import annotations

from api.crawler.sitemap import _parse_sitemap_content

YOAST_URLSET = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
  <url>
    <loc>https://example.com/a-real-page/</loc>
    <lastmod>2026-08-29T22:34:41+00:00</lastmod>
    <image:image><image:loc>https://example.com/wp-content/uploads/one.jpg</image:loc></image:image>
    <image:image><image:loc>https://example.com/wp-content/uploads/two.jpg</image:loc></image:image>
  </url>
  <url>
    <loc>https://example.com/second-page/</loc>
    <image:image><image:loc>https://example.com/wp-content/uploads/three.png</image:loc></image:image>
  </url>
</urlset>"""

INDEX = b"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/post-sitemap.xml</loc></sitemap>
  <sitemap><loc>https://example.com/page-sitemap.xml</loc></sitemap>
</sitemapindex>"""


def _parse(content):
    return _parse_sitemap_content(content, "https://example.com/sitemap.xml", client=None)


def test_af8_image_loc_entries_are_not_page_urls():
    urls = _parse(YOAST_URLSET)
    assert urls == ["https://example.com/a-real-page/", "https://example.com/second-page/"]


def test_af8_no_image_file_survives_the_parse():
    """The concrete symptom: image files entering the crawl queue as pages."""
    assert not [u for u in _parse(YOAST_URLSET) if u.endswith((".jpg", ".png"))]


def test_af8_page_count_is_not_inflated():
    """236 reported for a 139-page site — a 70% overstatement to the user."""
    assert len(_parse(YOAST_URLSET)) == 2


def test_af8_sitemap_index_children_still_parse():
    """Adversarial: the index path must keep working."""
    assert _parse(INDEX) == [
        "https://example.com/post-sitemap.xml",
        "https://example.com/page-sitemap.xml",
    ]


def test_af8_plain_sitemap_without_the_image_namespace_is_unchanged():
    plain = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/x/</loc></url>
  <url><loc>https://example.com/y/</loc></url>
</urlset>"""
    assert _parse(plain) == ["https://example.com/x/", "https://example.com/y/"]

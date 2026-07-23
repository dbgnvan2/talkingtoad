"""Generate the golden-fixture HTML pages into ./pages/.

Each page is crafted to trip a specific cluster of issue codes. Run:
    python tests/golden_site/build_pages.py
Kept in the repo as the source-of-truth for what each fixture page intends to
trigger; the emitted .html files are what the local server serves.
"""

from pathlib import Path

OUT = Path(__file__).parent / "pages"
OUT.mkdir(exist_ok=True)

# A short (~55-word) shared paragraph. Kept deliberately UNDER the 150-word
# near-duplicate gate so pages that reuse it are not (correctly) clustered as
# near-duplicates of each other — only the dedicated neardup-*.html pair below
# is long enough and shared enough to form the intended NEAR_DUPLICATE_BODY cluster.
PARA = (
    "Living Systems Counselling supports individuals and families across the "
    "region with evidence-based therapy. In 2025 our team completed 4,200 "
    "sessions and 87% of clients reported measurable improvement within twelve "
    "weeks. According to a study we conducted with the local health authority, "
    "early intervention reduced crisis referrals by roughly one third. "
)
BODY_300 = PARA  # short body — see note above (name kept for readability)

NAV = '<nav><a href="/">Home</a> <a href="/about.html">About</a></nav>'


def page(body, *, title="A Clear Descriptive Page Title For Testing",
         head_extra="", lang=' lang="en"', desc="A good meta description that is long enough to comfortably pass the minimum length validation checks here.",
         viewport=True, main=True, nav=True):
    meta_desc = f'<meta name="description" content="{desc}">' if desc is not None else ""
    vp = '<meta name="viewport" content="width=device-width, initial-scale=1">' if viewport else ""
    title_tag = f"<title>{title}</title>" if title is not None else ""
    inner = f"<main>{body}</main>" if main else body
    navtag = NAV if nav else ""
    return f"""<!DOCTYPE html>
<html{lang}>
<head>{title_tag}{meta_desc}{vp}{head_extra}</head>
<body>{navtag}{inner}</body>
</html>"""


FILES: dict[str, str] = {}

# ── Homepage — hub linking to every issue page (so they're discovered) ──────
_links = [
    "title-missing.html", "title-short.html", "title-long.html",
    "meta-missing.html", "meta-short.html", "meta-long.html", "lang-missing.html",
    "social-missing.html", "headings-none.html", "headings-multi.html",
    "headings-skip.html", "headings-empty.html", "links-bad.html", "redirects.html",
    "thin.html", "noindex-meta.html", "noindex-header.html", "no-viewport.html",
    "semantic-bad.html", "article-noauthor.html", "article-bare-author.html",
    "howto-incomplete.html", "product-norating.html", "jsonld-invalid.html",
    "faq-noschema.html", "dup-a.html", "dup-b.html", "neardup-a.html",
    "neardup-b.html", "entity-a.html", "entity-b.html", "URL_Uppercase.html",
    "has_underscores.html", "control-clean.html", "about.html",
]
_link_html = " ".join(f'<a href="/{h}">{h}</a>' for h in _links)
FILES["index.html"] = page(
    f"<h1>Golden Fixture Site Home</h1><p>{PARA}</p><p>Links:</p>{_link_html}",
    title="Golden Fixture Test Site — Home Page For Crawler Verification",
)

# ── Metadata ────────────────────────────────────────────────────────────────
FILES["title-missing.html"] = page(f"<h1>Heading</h1><p>{PARA}</p>", title=None)
FILES["title-short.html"] = page(f"<h1>Heading</h1><p>{PARA}</p>", title="Hi")
FILES["title-long.html"] = page(
    f"<h1>Heading</h1><p>{PARA}</p>",
    title="This Is An Extremely Long Page Title That Comfortably Exceeds The Sixty Character Limit For Titles")
FILES["meta-missing.html"] = page(f"<h1>Heading</h1><p>{PARA}</p>", desc=None)
FILES["meta-short.html"] = page(f"<h1>Heading</h1><p>{PARA}</p>", desc="Too short.")
FILES["meta-long.html"] = page(
    f"<h1>Heading</h1><p>{PARA}</p>",
    desc="This meta description is deliberately far too long. " * 6)
FILES["lang-missing.html"] = page(f"<h1>Heading</h1><p>{PARA}</p>", lang="")
FILES["social-missing.html"] = page(
    f"<h1>No Social Tags</h1><p>{PARA}</p>",
    title="Page Without Any Open Graph Or Twitter Card Social Metadata Tags")

# ── Headings ────────────────────────────────────────────────────────────────
FILES["headings-none.html"] = page(f"<p>No H1 anywhere.</p><p>{PARA}</p>")
FILES["headings-multi.html"] = page(f"<h1>First</h1><h1>Second</h1><p>{PARA}</p>")
FILES["headings-skip.html"] = page(f"<h1>Top</h1><h3>Skipped H2</h3><p>{PARA}</p>")
FILES["headings-empty.html"] = page(f"<h1>Top</h1><h2></h2><p>{PARA}</p>")

# ── Links / redirects / broken ──────────────────────────────────────────────
FILES["links-bad.html"] = page(
    f"<h1>Bad Links</h1><p>{PARA}</p>"
    '<a href="#">placeholder</a> '
    '<a href="/missing-404.html">dead internal link</a> '
    '<a href="/read-more">click here</a> '
    '<a href="/somewhere"></a>')  # (no external link — keep the crawl hermetic)
FILES["redirects.html"] = page(
    f"<h1>Redirects</h1><p>{PARA}</p>"
    '<a href="/redirect-301">r301</a> <a href="/redirect-302">r302</a> '
    '<a href="/chain-a">chain</a> <a href="/loop-a">loop</a> '
    '<a href="/gone">410</a> <a href="/unavailable">503</a> '
    '<a href="/secret-area">login redirect</a>')
FILES["target.html"] = page(f"<h1>Redirect Target</h1><p>{PARA}</p>",
                            title="Redirect Target Page With A Perfectly Good Title Here")
FILES["read-more"] = page(f"<h1>Read More</h1><p>{PARA}</p>",
                          title="Read More Landing Page With A Descriptive Title Here")

# ── Crawlability ────────────────────────────────────────────────────────────
FILES["thin.html"] = page("<h1>Thin</h1><p>Only a few words here.</p>",
                          title="A Very Thin Page With Almost No Content At All Here")
FILES["noindex-meta.html"] = page(
    f"<h1>Noindex Meta</h1><p>{PARA}</p>",
    head_extra='<meta name="robots" content="noindex">',
    title="Page That Is Noindexed Via A Robots Meta Tag In The Head")
FILES["noindex-header.html"] = page(
    f"<h1>Noindex Header</h1><p>{PARA}</p>",
    title="Page That Is Noindexed Via The X Robots Tag Response Header")
FILES["no-viewport.html"] = page(f"<h1>No Viewport</h1><p>{PARA}</p>", viewport=False,
                                 title="Page Missing The Responsive Viewport Meta Tag Entirely")
FILES["orphan.html"] = page(
    f"<h1>Orphan</h1><p>{PARA}</p>",
    title="Orphan Page Not Linked From Anywhere But Present In The Sitemap")

# ── Semantic HTML ───────────────────────────────────────────────────────────
FILES["semantic-bad.html"] = (
    "<!DOCTYPE html><html lang=\"en\"><head>"
    "<title>Page With Non Semantic Markup And Missing Landmarks Here</title>"
    "<meta name=\"description\" content=\"A good meta description long enough to pass the length checks comfortably.\">"
    "<meta name=\"viewport\" content=\"width=device-width\"></head><body>"
    f"<h1>Non-semantic</h1><p>{PARA}</p>"
    "<div onclick=\"go()\">Fake button</div>"
    "<button></button>"
    "</body></html>")

# ── AI-readiness / GEO ──────────────────────────────────────────────────────
_article_head = '<meta property="og:title" content="x"><meta property="og:description" content="y"><meta property="og:image" content="/i.jpg"><meta name="twitter:card" content="summary">'
FILES["article-noauthor.html"] = page(
    f'<h1>Blog Post Without An Author</h1>'
    f'<script type="application/ld+json">{{"@context":"https://schema.org","@type":"BlogPosting","headline":"Post"}}</script>'
    f"<p>{BODY_300}</p>",
    head_extra=_article_head,
    title="Blog Post That Is Missing Its Author Byline And Published Dates")
FILES["article-bare-author.html"] = page(
    f'<h1>Blog Post With A Bare Author</h1>'
    f'<address>By Jane Doe</address>'
    f'<script type="application/ld+json">{{"@context":"https://schema.org","@type":"BlogPosting","headline":"Post","datePublished":"2025-01-01","dateModified":"2025-02-01","author":{{"@type":"Person","name":"Jane Doe"}}}}</script>'
    f"<p>{BODY_300}</p>",
    head_extra=_article_head,
    title="Blog Post Whose Author Schema Has A Name But No Credentials At All")
FILES["howto-incomplete.html"] = page(
    f'<h1>How To Do The Thing</h1>'
    f'<script type="application/ld+json">{{"@context":"https://schema.org","@type":"HowTo","name":"How to do the thing"}}</script>'
    f"<p>{BODY_300}</p>",
    title="A How To Guide Whose HowTo Schema Declares No Steps At All Here")
FILES["product-norating.html"] = page(
    f'<h1>The Product</h1>'
    f'<script type="application/ld+json">{{"@context":"https://schema.org","@type":"Product","name":"Widget","offers":{{"@type":"Offer","price":"9.99"}}}}</script>'
    f"<p>{BODY_300}</p>",
    title="A Product Page Whose Schema Has No Review Or Aggregate Rating Here")
FILES["jsonld-invalid.html"] = page(
    f'<h1>Invalid JSON-LD</h1>'
    f'<script type="application/ld+json">{{"@context":"https://schema.org","name":"No type here"}}</script>'
    f"<p>{PARA}</p>",
    title="A Page Whose JSON LD Structured Data Block Is Missing Its Type")
FILES["faq-noschema.html"] = page(
    f'<h1>Frequently Asked Questions</h1>'
    f'<h2>What is this?</h2><p>{PARA}</p><h2>How does it work?</h2><p>{PARA}</p>'
    f'<h2>Why should I care?</h2><p>{PARA}</p>',
    title="A Frequently Asked Questions Page With No FAQPage Schema Markup")

# ── Cross-page: duplicates ──────────────────────────────────────────────────
_dup = page(f"<h1>Duplicate</h1><p>{PARA}</p>",
            title="Exactly The Same Duplicated Title On Two Different Pages Here",
            desc="Exactly the same duplicated meta description text shared across two distinct pages of the site.")
FILES["dup-a.html"] = _dup
FILES["dup-b.html"] = _dup

# ── Cross-page: near-duplicate body (needs 150+ words, mostly identical) ─────
_neardup_body = (
    "Our grief counselling service supports you through loss with weekly sessions "
    "led by a registered clinical counsellor in a safe confidential space where you "
    "can process difficult emotions and rebuild a sense of meaning after bereavement "
    "at a pace that feels right for you and your family over many months of care and "
    "gentle guidance from an experienced and compassionate professional therapist team. "
) * 3  # ~165 words — clears the 150-word near-duplicate gate
FILES["neardup-a.html"] = page(f"<h1>Grief Counselling Vancouver</h1><p>{_neardup_body} vancouver</p>",
                              title="Grief Counselling Services In Vancouver For Local Families Here")
FILES["neardup-b.html"] = page(f"<h1>Grief Counselling Burnaby</h1><p>{_neardup_body} burnaby</p>",
                              title="Grief Counselling Services In Burnaby For Local Families Here")

# ── Cross-page: entity inconsistency + missing sameAs ───────────────────────
FILES["entity-a.html"] = page(
    f'<h1>About Living Systems</h1>'
    f'<script type="application/ld+json">{{"@context":"https://schema.org","@type":"Organization","name":"Living Systems Counselling Society","sameAs":["https://en.wikipedia.org/wiki/Example"]}}</script>'
    f"<p>{PARA}</p>",
    title="About Page One Naming The Organisation One Particular Way Here")
FILES["entity-b.html"] = page(
    f'<h1>About Wellness Collective</h1>'
    f'<script type="application/ld+json">{{"@context":"https://schema.org","@type":"Organization","name":"Wellness Collective Inc"}}</script>'
    f"<p>{PARA}</p>",
    title="About Page Two Naming The Organisation A Completely Different Way")

# ── URL structure ───────────────────────────────────────────────────────────
FILES["URL_Uppercase.html"] = page(f"<h1>Uppercase URL</h1><p>{PARA}</p>",
                                   title="A Page Served At A URL Containing Uppercase Letters Here")
FILES["has_underscores.html"] = page(f"<h1>Underscore URL</h1><p>{PARA}</p>",
                                     title="A Page Served At A URL That Contains Underscore Characters")

# ── About (linked, generally clean-ish) ─────────────────────────────────────
FILES["about.html"] = page(
    f"<h1>About Us</h1><p>{BODY_300}</p><p>Contact: hello@example.org or call 604-555-0100.</p>",
    head_extra=_article_head + '<link rel="canonical" href="/about.html">',
    title="About Our Counselling Society And The Services We Provide Locally")

# ── Control — a deliberately well-formed page (false-positive tripwire) ──────
FILES["control-clean.html"] = page(
    f"<h1>Well Formed Control Page</h1>"
    f"<h2>What we offer</h2><p>{BODY_300}</p>"
    f"<h2>How it works</h2><p>{BODY_300}</p>"
    f'<p>Contact hello@example.org.</p>',
    head_extra=_article_head + '<link rel="canonical" href="/control-clean.html">',
    title="A Deliberately Well Formed Control Page That Should Stay Clean Here")


def main():
    for name, html in FILES.items():
        (OUT / name).write_text(html, encoding="utf-8")
    print(f"wrote {len(FILES)} pages to {OUT}")


if __name__ == "__main__":
    main()

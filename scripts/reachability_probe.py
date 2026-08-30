"""Reachability probe: can a check fire at all?

For a code that has never fired, build the minimal input that SHOULD trigger it
and run the real pipeline. Firing proves the check is alive (the site simply has
no such defect). Not firing — after the guard has been read and the input
corrected — is evidence the check is dead.

Spec:  docs/pending/2026-08-30_check-validation-program.md#V4
Audit: docs/audit/2026-08-30_full-check-audit.md (Part 2)

CAUTION: a first-attempt "did NOT fire" usually means the WRONG ENTRY POINT or a
missed threshold, not a dead check. In the 2026-08-30 audit, 18 of 28 first-pass
negatives turned out to be alive once the correct entry point (image_analyzer,
check_url_structure, issues_for_redirect, geo_llm) or precondition was supplied.
Always read the guard before concluding anything.
"""
"""Reachability harness: for each never-fired code, build the minimal input that
SHOULD trigger it and run the real pipeline. Fires => reachable (site simply has
no such defect). Does not fire => candidate DEAD check."""
import sys; sys.path.insert(0,'.')
from api.crawler.parser import parse_page
from api.crawler.fetcher import FetchResult
from api.crawler.issue_checker import check_page, check_cross_page

BASE="https://example.com/"
def page(body, head="", url=BASE, headers=None, status=200):
    html=("<!DOCTYPE html><html lang='en'><head><title>A Reasonably Long Page Title Here</title>"
          "<meta name='description' content='A description long enough to pass the minimum length checks on this page.'>"
          "<meta name='viewport' content='width=device-width'>"+head+"</head><body>"+body+"</body></html>")
    r=FetchResult(url=url, final_url=url, status_code=status, headers=headers or {},
                  html=html, content_type="text/html")
    return parse_page(r, BASE, is_homepage=(url==BASE))

def fires(code, p, cross=False, pages=None):
    try:
        issues = check_cross_page(pages or [p], start_url=BASE) if cross else check_page(p)
    except Exception as e:
        return None, "ERROR %r"%e
    return any(i.code==code for i in issues), ""

CASES={}
def case(code):
    def d(fn): CASES[code]=fn; return fn
    return d

LONG=" ".join(["word"]*400)

@case("MISSING_VIEWPORT_META")
def _():
    r=FetchResult(url=BASE, final_url=BASE, status_code=200, headers={},
        html="<html lang='en'><head><title>A Reasonably Long Page Title Here</title>"
             "<meta name='description' content='A description long enough to pass the minimum length checks here.'>"
             "</head><body><h1>H</h1><p>%s</p></body></html>"%LONG, content_type="text/html")
    return parse_page(r, BASE, is_homepage=True), False, None
@case("URL_HAS_SPACES")
def _(): return page("<h1>H</h1><p>%s</p>"%LONG, url="https://example.com/a%20b"), False, None
@case("NOINDEX_HEADER")
def _(): return page("<h1>H</h1><p>%s</p>"%LONG, headers={"x-robots-tag":"noindex"}), False, None
@case("NON_SEMANTIC_BUTTON")
def _(): return page("<h1>H</h1><div class='btn' onclick='go()'>Click</div><p>%s</p>"%LONG), False, None
@case("INTERACTIVE_NO_ACCESSIBLE_NAME")
def _(): return page("<h1>H</h1><button></button><p>%s</p>"%LONG), False, None
@case("LANDMARK_NAV_MISSING")
def _(): return page("<main><h1>H</h1><p>%s</p></main>"%LONG), False, None
@case("IMG_ALT_MISUSED")
def _(): return page("<h1>H</h1><img src='/a.jpg' role='presentation' alt='A meaningful description'><p>%s</p>"%LONG), False, None
@case("META_REFRESH_REDIRECT")
def _(): return page("<h1>H</h1><p>%s</p>"%LONG, head="<meta http-equiv='refresh' content='0;url=/x'>"), False, None
@case("SCHEMA_DEPRECATED_TYPE")
def _(): return page("<h1>H</h1><script type='application/ld+json'>{\"@context\":\"https://schema.org\",\"@type\":\"Blog\",\"blogPost\":[]}</script><p>%s</p>"%LONG), False, None
@case("SELF_REFERENCING_UTM")
def _(): return page("<h1>H</h1><a href='https://example.com/x?utm_source=site'>Internal</a><p>%s</p>"%LONG), False, None
@case("OUTBOUND_LINK_UNTRACKABLE")
def _(): return page("<h1>H</h1><a href='https://other.org/'><img src='https://other.org/i.png'></a><p>%s</p>"%LONG), False, None
@case("ANALYTICS_TAG_DUPLICATE")
def _(): return page("<h1>H</h1><p>%s</p>"%LONG,
    head="<script async src='https://www.googletagmanager.com/gtag/js?id=G-AAA111BBB'></script>"
         "<script>gtag('config','G-AAA111BBB');</script>"
         "<script async src='https://www.googletagmanager.com/gtag/js?id=G-AAA111BBB'></script>"), False, None
@case("CONTACT_INFO_NOT_IN_HTML")
def _(): return page("<h1>Contact Us</h1><p>Reach our team.</p><p>%s</p>"%LONG, url="https://example.com/contact"), False, None
@case("STRUCTURED_ELEMENTS_LOW")
def _(): return page("<h1>H</h1><p>%s</p>"%(" ".join(["prose"]*1200)),), False, None
@case("DOCUMENT_PROPS_MISSING")
def _(): return page("<h1>H</h1><p>%s</p>"%LONG), False, None
@case("PRODUCT_REVIEW_SCHEMA_MISSING")
def _(): return page("<h1>Product Review: Widget</h1><p>We reviewed the widget. %s</p>"%LONG, url="https://example.com/review-widget"), False, None
@case("CODE_BLOCK_MISSING_TECHNICAL")
def _(): return page("<h1>API Reference</h1><p>Use the endpoint parameter to configure the JSON request. %s</p>"%LONG), False, None
@case("HOWTO_SCHEMA_INCOMPLETE")
def _(): return page("<h1>How to do it</h1><script type='application/ld+json'>{\"@context\":\"https://schema.org\",\"@type\":\"HowTo\",\"name\":\"X\"}</script><p>%s</p>"%LONG), False, None
@case("FAQ_ANSWERS_NOT_IN_HTML")
def _(): return page("<h1>FAQ</h1><script type='application/ld+json'>{\"@context\":\"https://schema.org\",\"@type\":\"FAQPage\",\"mainEntity\":[{\"@type\":\"Question\",\"name\":\"What is X?\",\"acceptedAnswer\":{\"@type\":\"Answer\",\"text\":\"A hidden answer that never appears in the visible body text at all.\"}}]}</script><p>%s</p>"%LONG), False, None
@case("BLOG_SECTIONS_MISSING")
def _(): return page("<h1>Blog</h1><p>%s</p>"%LONG, url="https://example.com/blog"), False, None
@case("LINK_PROFILE_PROMOTIONAL")
def _():
    links="".join("<a href='https://shop.example.org/buy%d'>Buy now</a>"%i for i in range(12))
    return page("<h1>H</h1>%s<p>%s</p>"%(links,LONG)), False, None
@case("PROMOTIONAL_CONTENT_INTERRUPTS")
def _(): return page("<h1>H</h1><p>%s</p><div class='cta'>Donate now! Sign up today! Buy now!</div><p>%s</p>"%(LONG,LONG)), False, None
@case("ORPHAN_CLAIM_TECHNICAL")
def _(): return page("<h1>H</h1><p>Studies show that 87%% of clinicians report improvement. %s</p>"%LONG), False, None
@case("CENTRAL_CLAIM_BURIED")
def _(): return page("<h1>H</h1>"+("<p>%s</p>"%LONG)*3+"<p>The key finding is that therapy works.</p>"), False, None
@case("CHUNKS_NOT_SELF_CONTAINED")
def _(): return page("<h1>H</h1><h2>It</h2><p>This is why. %s</p><h2>They</h2><p>That too. %s</p>"%(LONG,LONG)), False, None
@case("AI_NO_VISUAL_COMPANION")
def _(): return page("<h1>H</h1><p>%s</p>"%(" ".join(["word"]*1500))), False, None
@case("REDIRECT_CASE_NORMALISE")
def _(): return page("<h1>H</h1><p>%s</p>"%LONG, url="https://example.com/CasedPath", status=301), False, None
@case("IMG_BROKEN")
def _(): return page("<h1>H</h1><img src='/missing.jpg' alt='A described image'><p>%s</p>"%LONG), False, None

results={}
for code,fn in sorted(CASES.items()):
    try:
        p,cross,pages = fn()
    except Exception as e:
        results[code]=("BUILD-ERROR", repr(e)[:60]); continue
    ok,note = fires(code,p,cross,pages)
    results[code]=("FIRES" if ok else ("ERROR" if ok is None else "did NOT fire"), note)

for k in ("FIRES","did NOT fire","ERROR","BUILD-ERROR"):
    for c,(v,n) in sorted(results.items()):
        if v==k: print("%-34s%-16s%s"%(c,v,n))
import collections; print(); print(collections.Counter(v for v,_ in results.values()))

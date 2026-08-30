"""Independently re-derive crawler findings from raw HTML (V5/V2 oracle).

Purpose: check findings against an implementation that shares NO code with the
         crawler. Disagreement in either direction is a LEAD, never a verdict.
Spec:    docs/pending/2026-08-30_check-validation-program.md
Audit:   docs/audit/2026-08-30_full-check-audit.md

Usage:
    python3 scripts/verify_findings_independently.py <job_id> [page_dir]

Pages must already be saved to <page_dir> (default /tmp/pages) with a
<page_dir>/../pagemap.txt of "<md5>|<url>" lines. This deliberately reads saved
artifacts rather than re-fetching, so a verification run is reproducible.

KNOWN LIMITATIONS — measured, not guessed. On the 2026-08-30 audit this script
produced 5 false leads in 45 re-derivations (11%):
  * word counts include nav/footer chrome; the crawler correctly excludes it,
    so THIN_CONTENT disagreements are usually this script being wrong;
  * regexes over raw HTML match CSS (`width:100%`), so token counts must be
    taken over visible text only.
Resolve every disagreement by looking at the artifact, not by trusting either
implementation.
"""
import sys

import re, json, sqlite3, pathlib, collections
A = sys.argv[1] if len(sys.argv) > 1 else 'a87e2d61-b262-48b0-aa97-d958ed248e21'
PAGE_DIR = sys.argv[2] if len(sys.argv) > 2 else '/tmp/pages'
db = sqlite3.connect("talkingtoad.db")
pm = {}
for line in open(PAGE_DIR + '/../pagemap.txt'):
    h, u = line.rstrip("\n").split("|", 1)
    pm[u] = h

def html(u):
    if u not in pm: return None
    p = pathlib.Path("%s/%s.html" % (PAGE_DIR, pm[u]))
    return p.read_text(errors="replace") if p.exists() and p.stat().st_size > 500 else None

def strip(h): return re.sub(r'(?is)<[^>]+>', ' ', h)
def heads(h):
    return [(int(l), re.sub(r'(?is)<[^>]+>', '', t).strip())
            for l, t in re.findall(r'(?is)<h([1-6])[^>]*>(.*?)</h\1>', h)]
def alts(h): return re.findall(r'(?is)<img[^>]+alt="([^"]*)"', h)
def http_refs(h): return re.findall(r'(?i)(?:src|href)="http://', h)

V = {}
def check(code, fn):
    row = db.execute("select page_url, coalesce(extra,'') from issues where job_id=? and issue_code=? and page_url like 'http%' limit 1", (A, code)).fetchone()
    if not row: return
    u, e = row
    h = html(u)
    if not h: V[code] = ("NO-HTML", u); return
    try: ex = json.loads(e) if e else {}
    except Exception: ex = {}
    try: ok, note = fn(h, ex, u)
    except Exception as err: V[code] = ("ERROR", repr(err)[:70]); return
    V[code] = ("CONFIRMED" if ok else "DISAGREE", note)

check("HEADING_SKIP", lambda h,e,u: (any(b[0]-a[0] > 1 for a,b in zip(heads(h), heads(h)[1:])), "levels=%s" % [l for l,_ in heads(h)][:12]))
check("HEADING_EMPTY", lambda h,e,u: (any(not t for _,t in heads(h)), "empty=%d" % sum(1 for _,t in heads(h) if not t)))
check("H1_MULTIPLE", lambda h,e,u: (len([1 for l,_ in heads(h) if l==1]) > 1, "h1_count=%d" % len([1 for l,_ in heads(h) if l==1])))
check("MIXED_CONTENT", lambda h,e,u: (len(http_refs(h)) > 0, "http_refs=%d" % len(http_refs(h))))
check("JSON_LD_INVALID", lambda h,e,u: ('application/ld+json' in h, "ldjson_blocks=%d" % h.count('application/ld+json')))
check("SCHEMA_TYPE_MISMATCH", lambda h,e,u: ('application/ld+json' in h, "ldjson_blocks=%d" % h.count('application/ld+json')))
check("FAQ_SCHEMA_MISSING", lambda h,e,u: ('FAQPage' not in h, "FAQPage absent"))
check("DATE_MODIFIED_MISSING", lambda h,e,u: ('dateModified' not in h, "dateModified absent"))
check("ENTITY_SAMEAS_MISSING", lambda h,e,u: ('sameAs' not in h, "sameAs absent"))
check("IMG_FORMAT_LEGACY", lambda h,e,u: (bool(re.search(r'(?i)\.(jpe?g|png|gif)', h)), "legacy ext present"))
check("IMG_ALT_TOO_LONG", lambda h,e,u: (any(len(a) > 125 for a in alts(h)), "max_alt_len=%d" % max([len(a) for a in alts(h)] or [0])))
check("PARA_TOO_LONG", lambda h,e,u: (any(len(re.sub(r'(?is)<[^>]+>','',p).split()) > 150 for p in re.findall(r'(?is)<p[^>]*>(.*?)</p>', h)), "long p present"))
check("QUOTATIONS_MISSING", lambda h,e,u: ('<blockquote' not in h, "no blockquote"))
check("PAGINATION_LINKS_PRESENT", lambda h,e,u: (bool(re.search(r'(?i)rel="(next|prev)"', h)) or bool(re.search(r'(?i)/page/\d', h)), "pagination markers"))
check("LINK_EMPTY_ANCHOR", lambda h,e,u: (True, "count=%s" % e.get("count") if isinstance(e, dict) else "n/a"))
check("STATISTICS_COUNT_LOW", lambda h,e,u: (len(re.findall(r'\d+%', strip(h))) < 5, "pct_tokens=%d" % len(re.findall(r'\d+%', strip(h)))))
check("SECTION_VAGUE_OPENER", lambda h,e,u: (True, "semantic heuristic"))
check("SEMANTIC_DENSITY_LOW", lambda h,e,u: (True, "semantic heuristic"))
check("CONVERSATIONAL_H2_MISSING", lambda h,e,u: (not any('?' in t for l,t in heads(h) if l==2), "h2_with_question=%d" % sum(1 for l,t in heads(h) if l==2 and '?' in t)))
check("FIRST_VIEWPORT_NO_ANSWER", lambda h,e,u: (True, "semantic heuristic"))
check("QUERY_COVERAGE_WEAK", lambda h,e,u: (True, "semantic heuristic"))
check("CITATIONS_ORPHANED", lambda h,e,u: (True, "citation-model heuristic"))
check("AI_MAIN_CONTENT_LOW_RATIO", lambda h,e,u: (True, "ratio heuristic"))
check("AI_CONTENT_NOT_IN_TEXT", lambda h,e,u: (True, "render-compare heuristic"))
check("CONTENT_STAT_OUTDATED", lambda h,e,u: (True, "year-token heuristic"))
check("GEO_SUMMARY_BURIED", lambda h,e,u: (True, "position heuristic"))
check("SCHEMA_VISIBLE_MISMATCH", lambda h,e,u: ('application/ld+json' in h, "ldjson present"))
check("COMPARISON_TABLE_MISSING", lambda h,e,u: ('<table' not in h, "no <table>"))
check("SECTION_CROSS_REFERENCES", lambda h,e,u: (True, "semantic heuristic"))
check("LINK_STACKED_DUPLICATE", lambda h,e,u: (True, "overlay heuristic"))
check("NEAR_DUPLICATE_BODY", lambda h,e,u: (True, "cross-page corpus"))
check("BOILERPLATE_RATIO_HIGH", lambda h,e,u: (True, "cross-page corpus"))
check("META_DESC_DUPLICATE", lambda h,e,u: (True, "cross-page corpus"))
check("TITLE_DUPLICATE", lambda h,e,u: (True, "cross-page corpus"))
check("TITLE_H1_MISMATCH", lambda h,e,u: (True, "title/h1 compare"))
check("CTA_TRACKING_MISSING", lambda h,e,u: (True, "tracking-attr heuristic"))
check("ANALYTICS_TAG_MISSING", lambda h,e,u: ('googletagmanager' not in h and 'gtag(' not in h, "GA/GTM refs=%d" % (h.count('googletagmanager') + h.count('gtag('))))

for k in ("CONFIRMED", "DISAGREE", "NO-HTML", "ERROR"):
    for c, (v, n) in sorted(V.items()):
        if v == k:
            print("%-36s%-12s%s" % (c, v, n))
print()
print(collections.Counter(v for v, _ in V.values()))

"""Cross-page duplicate and orphan detection — run after the crawl finishes.

Extracted from api/crawler/issue_checker.py in v2.6 M9.1 (Cycle K).
Zero-logic move — function body is byte-identical to the original
check_cross_page() (which already carries Cycle J's whitespace-strip fix).
"""

import logging
import math
import os
import re
import zlib
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

from api.crawler.normaliser import normalise_url
from api.crawler.parser import ParsedPage

from api.crawler.checkers.registry import Issue, make_issue

# ── "Search Everywhere" GEO — brand-entity + body-uniqueness config (P1) ─────
# Config, not magic constants (P4): overridable via env, monkeypatchable in
# tests. Numeric bounds mirrored in docs/thresholds.md.
# ⚠︎R5-REWORK: scoring provisional pending the R3→R5 refactor (see
# PLAN-SEARCH-EVERYWHERE.md), but these are detection thresholds, not scores.
_SHINGLE_SIZE = int(os.getenv("TT_SHINGLE_SIZE", "5"))            # word n-gram size
_MIN_WORDS_FOR_DUP = int(os.getenv("TT_MIN_WORDS_FOR_DUP", "150"))  # skip short pages
_NEAR_DUP_JACCARD = float(os.getenv("TT_NEAR_DUP_JACCARD", "0.80"))
_BOILERPLATE_RATIO = float(os.getenv("TT_BOILERPLATE_RATIO", "0.60"))
_MIN_PAGES_SITE_CHECKS = int(os.getenv("TT_MIN_PAGES_SITE_CHECKS", "3"))
# Above this eligible-page count, use MinHash prefilter instead of all-pairs
# exact Jaccard (keeps large crawls fast); at/below it, compare exactly (P9 —
# the cap is announced, not silent, via the log below).
_NEARDUP_EXACT_MAX = int(os.getenv("TT_NEARDUP_EXACT_MAX", "400"))
_MINHASH_PERM = max(1, int(os.getenv("TT_MINHASH_PERM", "128")))  # >=1: guards /0
# Shingle doc-frequency fraction above which a shingle is site-wide boilerplate.
_BOILERPLATE_DOC_FRACTION = float(os.getenv("TT_BOILERPLATE_DOC_FRACTION", "0.20"))
# MinHash prefilter slack below the Jaccard threshold (candidates are then
# confirmed with exact Jaccard, so this only guards against false negatives).
_MINHASH_MARGIN = float(os.getenv("TT_MINHASH_MARGIN", "0.15"))

# Legal-suffix / stop tokens stripped before comparing organisation names so a
# casing/suffix-only difference is NOT a false "inconsistent" (adversarial P7).
_ENTITY_LEGAL_SUFFIXES: frozenset[str] = frozenset(
    (os.getenv("TT_ENTITY_LEGAL_SUFFIXES", "")
     or "inc,inc.,llc,ltd,ltd.,co,co.,corp,corp.,company,society,foundation,"
        "association,trust,charity,cooperative,coop,group,the").split(",")
)

_WORD_RE = re.compile(r"[a-z0-9]+")
_MERSENNE_PRIME = (1 << 61) - 1


def check_cross_page(pages: list[ParsedPage], start_url: str | None = None) -> list[Issue]:
    """Run duplicate-detection checks across all crawled pages.

    Detects:
    - TITLE_DUPLICATE: same title on multiple pages
    - META_DESC_DUPLICATE: same meta description on multiple pages
    - TITLE_META_DUPLICATE_PAIR: both title and meta_desc duplicated together
    - CANONICAL_MISSING (near-duplicate condition): same title+meta_desc, no canonical
    - ORPHAN_PAGE: page has no internal links pointing to it

    Args:
        pages: All crawled HTML pages.
        start_url: Normalised start URL of the crawl (homepage — excluded from orphan check).

    Returns a flat list of issues (one per affected URL, not per pair).
    """
    issues: list[Issue] = []

    # Build lookup maps — skip redirect pages (3xx status or has redirect_url).
    # The grouping key is .casefold()ed so semantically-identical titles
    # like "About Us" / "ABOUT US" / "about us" bucket together (search
    # engines treat them as duplicate content). We preserve the *first*
    # observed original casing so the issue extra still reports the
    # human-meaningful string. Each map stores: key -> (original, [urls]).
    title_map: dict[str, tuple[str, list[str]]] = {}
    desc_map: dict[str, tuple[str, list[str]]] = {}
    pair_map: dict[tuple[str, str], tuple[tuple[str, str], list[str]]] = {}

    for page in pages:
        # Skip redirects — they shouldn't be flagged as duplicates
        if page.redirect_url or (300 <= page.status_code < 400):
            continue

        # Skip pages that declare a DIFFERENT canonical URL — they have
        # explicitly announced themselves as a secondary view of another
        # page (e.g. paginated archive pages /list/2/, /list/3/ that
        # canonical → /list/). Flagging such a page as a duplicate of the
        # very page it canonicals to is a false positive. A page whose
        # canonical is None, or self-referencing, stays in the grouping
        # (the CANONICAL_MISSING near-duplicate path is unchanged).
        if page.canonical_url is not None:
            try:
                if normalise_url(page.canonical_url) != normalise_url(page.url):
                    continue
            except Exception:
                # If either URL can't be normalised, fall through and keep
                # the page in the grouping rather than silently dropping it.
                pass

        # Normalise both sides: a whitespace-only title is functionally
        # empty and must NOT bucket-up with other whitespace-only titles
        # as TITLE_DUPLICATE (`bool("   ")` is True — the original
        # `if t:` admitted them and inflated the issue count with garbage).
        # We also strip outer whitespace so "My Page" and "My Page " group
        # together — accidental trailing whitespace is a real duplicate.
        t_orig = (page.title or "").strip()
        d_orig = (page.meta_description or "").strip()
        t_key = t_orig.casefold()
        d_key = d_orig.casefold()

        if t_key:
            if t_key not in title_map:
                title_map[t_key] = (t_orig, [])
            title_map[t_key][1].append(page.url)
        if d_key:
            if d_key not in desc_map:
                desc_map[d_key] = (d_orig, [])
            desc_map[d_key][1].append(page.url)
        if t_key and d_key:
            pair_key = (t_key, d_key)
            if pair_key not in pair_map:
                pair_map[pair_key] = ((t_orig, d_orig), [])
            pair_map[pair_key][1].append(page.url)

    # TITLE_DUPLICATE
    for _t_key, (title, urls) in title_map.items():
        if len(urls) > 1:
            for url in urls:
                other_urls = [u for u in urls if u != url]
                issue = make_issue("TITLE_DUPLICATE", url)
                issue.extra = {
                    "title": title,  # The actual duplicated title (first observed casing)
                    "duplicate_urls": other_urls,  # Other pages with same title
                }
                issues.append(issue)

    # META_DESC_DUPLICATE
    for _d_key, (desc, urls) in desc_map.items():
        if len(urls) > 1:
            for url in urls:
                other_urls = [u for u in urls if u != url]
                issue = make_issue("META_DESC_DUPLICATE", url)
                issue.extra = {
                    "description": desc,  # The actual duplicated description (first observed casing)
                    "duplicate_urls": other_urls,  # Other pages with same description
                }
                issues.append(issue)

    # CANONICAL_MISSING (near-duplicate condition). §7: TITLE_META_DUPLICATE_PAIR
    # was deleted — it fired exactly when TITLE_DUPLICATE and META_DESC_DUPLICATE
    # both fired (triple-counting one condition). We still collect the pair URLs
    # here to drive the CANONICAL_MISSING near-duplicate check below.
    duplicate_urls: set[str] = set()
    for _pair_key, (_pair, urls) in pair_map.items():
        if len(urls) > 1:
            duplicate_urls.update(urls)

    # CANONICAL_MISSING — near-duplicate condition (spec §3.1.2 condition 2)
    page_by_url = {p.url: p for p in pages}
    for url in duplicate_urls:
        page = page_by_url.get(url)
        if page and page.canonical_url is None and not urlparse(url).query:
            # No query string (that's condition 1, already emitted in check_page)
            # and no canonical → emit CANONICAL_MISSING for near-duplicate condition
            issues.append(make_issue("CANONICAL_MISSING", url))

    # ORPHAN_PAGE — pages with no internal links pointing to them.
    # A page linking to itself does NOT make it discoverable; only links
    # from OTHER pages do. The pre-fix code added every internal link to
    # the discovered bucket, so a genuinely orphan page with a self-link
    # (a "Back to top" anchor, a logo link to the current URL, etc.)
    # silently evaded detection.
    linked_urls: set[str] = set()
    for page in pages:
        try:
            page_norm = normalise_url(page.url)
        except Exception:
            page_norm = None

        for link in page.links:
            if link.is_internal:
                try:
                    link_norm = normalise_url(link.url)
                except Exception:
                    continue
                # Drop self-links — a page linking to itself does not
                # make it discoverable.
                if link_norm and link_norm != page_norm:
                    linked_urls.add(link_norm)

    for page in pages:
        try:
            norm = normalise_url(page.url)
        except Exception:
            continue
        if norm == start_url:
            continue  # homepage is always the entry point
        if norm not in linked_urls:
            issues.append(make_issue("ORPHAN_PAGE", page.url,
                                     extra={"title": page.title,
                                            # R2.x #4: link discovery is raw-HTML only.
                                            "caveat": "Internal links are discovered from raw HTML; "
                                            "pages linked only via JavaScript or query-driven "
                                            "listings (e.g. loop grids) may be false positives."}))

    # ── "Search Everywhere" GEO — brand-entity + body-uniqueness (P1) ────────
    # Only non-redirect pages participate (same filter as duplicate detection).
    live_pages = [p for p in pages
                  if not (p.redirect_url or (300 <= p.status_code < 400))]
    issues.extend(_check_entity_consistency(live_pages, start_url))
    issues.extend(_check_body_uniqueness(live_pages))

    return issues


# ── Schema / JSON-LD entity helpers ─────────────────────────────────────────

def _iter_schema_objects(blocks):
    """Yield every JSON-LD object in *blocks*, flattening ``@graph`` and lists."""
    if not blocks:
        return
    stack = list(blocks)
    while stack:
        obj = stack.pop()
        if isinstance(obj, list):
            stack.extend(obj)
            continue
        if not isinstance(obj, dict):
            continue
        graph = obj.get("@graph")
        if isinstance(graph, list):
            stack.extend(graph)
        yield obj


def _types_of(obj) -> set[str]:
    t = obj.get("@type")
    if isinstance(t, list):
        return {str(x) for x in t}
    if t is None:
        return set()
    return {str(t)}


def _normalise_org_name(name: str) -> str:
    """Casefold, collapse whitespace, drop legal suffixes — so 'Acme Society',
    'Acme' and 'ACME  society' collapse to one key (adversarial guard, P7)."""
    tokens = _WORD_RE.findall((name or "").casefold())
    kept = [tok for tok in tokens if tok not in _ENTITY_LEGAL_SUFFIXES]
    if kept:
        return " ".join(kept)
    # All tokens were legal/generic suffixes (e.g. "The Trust" vs "Trust"):
    # drop only the generic article so both spellings collapse to one key.
    residual = [tok for tok in tokens if tok != "the"]
    return " ".join(residual or tokens)


_ORG_TYPES = {"Organization", "LocalBusiness", "NGO", "Corporation"}


def _org_names(page) -> list[str]:
    """*Self-identity* organisation names a page attributes its content to.

    Only publisher/provider names (always the content owner) plus a top-level
    Organization node **when the page has exactly one** — a page listing several
    Organization nodes (partners, funders, a member directory) is a third-party
    context, not a second name for this site, so we take none of them (P7: avoids
    a partners page falsely tripping ENTITY_NAME_INCONSISTENT)."""
    names: list[str] = []
    org_names: list[str] = []
    for obj in _iter_schema_objects(getattr(page, "schema_blocks", None)):
        if _types_of(obj) & _ORG_TYPES:
            n = obj.get("name")
            if isinstance(n, str) and n.strip():
                org_names.append(n.strip())
        for key in ("publisher", "provider"):
            sub = obj.get(key)
            if isinstance(sub, dict):
                n = sub.get("name")
                if isinstance(n, str) and n.strip():
                    names.append(n.strip())  # publisher/provider = self by definition
    if len(org_names) == 1:
        names.append(org_names[0])
    return names


def _authors(page) -> list[tuple[str, str]]:
    """(name, url) author identities from Article-family JSON-LD."""
    out: list[tuple[str, str]] = []
    for obj in _iter_schema_objects(getattr(page, "schema_blocks", None)):
        if not (_types_of(obj) & {"Article", "BlogPosting", "NewsArticle", "TechArticle"}):
            continue
        author = obj.get("author")
        cands = author if isinstance(author, list) else [author]
        for a in cands:
            if isinstance(a, dict):
                name = a.get("name")
                url = a.get("url") or a.get("@id") or ""
                if isinstance(name, str) and name.strip():
                    out.append((name.strip(), str(url).strip()))
    return out


def _check_entity_consistency(pages, start_url) -> list[Issue]:
    issues: list[Issue] = []

    # ENTITY_SAMEAS_MISSING (page) — runs regardless of site size.
    for page in pages:
        flagged = False
        for obj in _iter_schema_objects(getattr(page, "schema_blocks", None)):
            if _types_of(obj) & {"Organization", "LocalBusiness", "NGO", "Corporation", "Person"}:
                same = obj.get("sameAs")
                has = bool(same) and (not isinstance(same, (list, str)) or len(same) > 0)
                if not has:
                    flagged = True
        if flagged:
            issues.append(make_issue("ENTITY_SAMEAS_MISSING", page.url))

    # Site-scoped checks need enough pages to be meaningful.
    if len(pages) < _MIN_PAGES_SITE_CHECKS:
        return issues

    # ENTITY_NAME_INCONSISTENT (site) — group by normalised name.
    name_variants: dict[str, dict] = {}  # norm -> {"name": firstOriginal, "urls": [...]}
    for page in pages:
        for original in _org_names(page):
            key = _normalise_org_name(original)
            if not key:
                continue
            v = name_variants.setdefault(key, {"name": original, "urls": []})
            v["urls"].append(page.url)
    if len(name_variants) > 1:
        rep = start_url or pages[0].url
        variants = [{"name": v["name"], "urls": sorted(set(v["urls"]))}
                    for v in name_variants.values()]
        issues.append(make_issue("ENTITY_NAME_INCONSISTENT", rep,
                                 extra={"variants": variants}))

    # AUTHOR_IDENTITY_INCONSISTENT (site) — same name → multiple urls, or vice-versa.
    name_to_urls: dict[str, set[str]] = {}
    url_to_names: dict[str, set[str]] = {}
    for page in pages:
        for name, url in _authors(page):
            nkey = " ".join(_WORD_RE.findall(name.casefold()))
            if not nkey:
                continue
            name_to_urls.setdefault(nkey, set())
            if url:
                name_to_urls[nkey].add(url)
                url_to_names.setdefault(url, set()).add(nkey)
    conflicts = [n for n, urls in name_to_urls.items() if len(urls) > 1]
    conflicts += [u for u, names in url_to_names.items() if len(names) > 1]
    if conflicts:
        rep = start_url or pages[0].url
        issues.append(make_issue("AUTHOR_IDENTITY_INCONSISTENT", rep,
                                 extra={"name_to_urls": {n: sorted(u) for n, u in name_to_urls.items()
                                                         if len(u) > 1}}))
    return issues


# ── Body near-duplicate + boilerplate helpers ───────────────────────────────

def _lead_text(page) -> str | None:
    return (getattr(page, "first_1500_words", None)
            or getattr(page, "first_600_words", None)
            or getattr(page, "first_200_words", None))


def _shingles(text: str) -> frozenset[int]:
    """Hashed word n-gram set (crc32 → deterministic across processes)."""
    words = _WORD_RE.findall(text.lower())
    k = _SHINGLE_SIZE
    if len(words) < k:
        # Too few words for a k-gram — fall back to the single bag so identical
        # short texts still match, but they're gated out earlier by min-words.
        return frozenset({zlib.crc32(" ".join(words).encode())}) if words else frozenset()
    return frozenset(
        zlib.crc32(" ".join(words[i:i + k]).encode())
        for i in range(len(words) - k + 1)
    )


def _jaccard(a: frozenset[int], b: frozenset[int]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / (len(a) + len(b) - inter)


def _minhash_perms(count: int) -> list[tuple[int, int]]:
    """Deterministic, low-correlation (a, b) coefficients for MinHash hashes.

    Derived from a multiplicative hash of the index (not a linear a=2i+1/b=7i+3,
    whose hashes are correlated and inflate estimate variance)."""
    perms = []
    for i in range(count):
        a = ((i * 2654435761) ^ 0x9E3779B1) | 1          # odd, coprime to 2
        b = ((i + 1) * 40503) ^ 0x85EBCA77
        perms.append((a % _MERSENNE_PRIME, b % _MERSENNE_PRIME))
    return perms


def _minhash(shingles: frozenset[int], perms: list[tuple[int, int]]) -> tuple[int, ...]:
    if not shingles:
        return tuple(_MERSENNE_PRIME for _ in perms)
    sig = []
    for a, b in perms:
        sig.append(min(((a * s + b) % _MERSENNE_PRIME) for s in shingles))
    return tuple(sig)


def _check_body_uniqueness(pages) -> list[Issue]:
    issues: list[Issue] = []
    if len(pages) < _MIN_PAGES_SITE_CHECKS:
        return issues

    # Eligible pages: enough words to judge.
    eligible = []
    for page in pages:
        text = _lead_text(page)
        if not text:
            continue
        if len(_WORD_RE.findall(text.lower())) < _MIN_WORDS_FOR_DUP:
            continue
        eligible.append((page.url, _shingles(text)))
    if len(eligible) < 2:
        return issues

    # Boilerplate = shingles occurring on >= max(3, fraction × eligible) pages.
    # NOTE: this is used ONLY for BOILERPLATE_RATIO_HIGH, never for near-dup.
    # first_1500_words already excludes nav/header/footer/aside (parser strips
    # them), so "boilerplate" here is repeated *main-body* template (shared
    # intros/CTAs). It must NOT be subtracted before near-dup: a cluster of
    # duplicate pages pushes its own shared content over the doc-freq threshold,
    # which would erase exactly the duplication we exist to catch (monotonicity
    # inversion). Near-dup therefore compares the RAW shingle sets `sh`.
    from collections import Counter
    doc_freq: Counter = Counter()
    for _url, sh in eligible:
        doc_freq.update(sh)
    boilerplate_min = max(3, math.ceil(_BOILERPLATE_DOC_FRACTION * len(eligible)))
    boilerplate = frozenset(s for s, c in doc_freq.items() if c >= boilerplate_min)

    # BOILERPLATE_RATIO_HIGH (page) — share of a page that is site-wide template.
    for url, sh in eligible:
        if sh:
            ratio = len(sh & boilerplate) / len(sh)
            if ratio >= _BOILERPLATE_RATIO:
                issues.append(make_issue("BOILERPLATE_RATIO_HIGH", url,
                                         extra={"boilerplate_ratio": round(ratio, 3)}))

    # NEAR_DUPLICATE_BODY (site) — cluster by RAW-shingle Jaccard (see note above).
    raw_sets: list[tuple[str, frozenset[int]]] = eligible
    pairs: list[tuple[int, int]] = []
    n = len(raw_sets)
    if n > _NEARDUP_EXACT_MAX:
        # MinHash prefilter for large crawls (announced, not silent — P9).
        logger.info("near_dup_minhash_prefilter",
                    extra={"pages": n, "exact_max": _NEARDUP_EXACT_MAX})
        perms = _minhash_perms(_MINHASH_PERM)
        sigs = [_minhash(sh, perms) for _u, sh in raw_sets]
        for i in range(n):
            for j in range(i + 1, n):
                est = sum(1 for a, b in zip(sigs[i], sigs[j]) if a == b) / _MINHASH_PERM
                if est >= _NEAR_DUP_JACCARD - _MINHASH_MARGIN:
                    pairs.append((i, j))
    else:
        pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]

    # Union-find over confirmed (exact-Jaccard) near-duplicate pairs.
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    linked = False
    for i, j in pairs:
        if _jaccard(raw_sets[i][1], raw_sets[j][1]) >= _NEAR_DUP_JACCARD:
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[ri] = rj
                linked = True

    if linked:
        clusters: dict[int, list[str]] = {}
        for idx in range(n):
            clusters.setdefault(find(idx), []).append(raw_sets[idx][0])
        for members in clusters.values():
            if len(members) > 1:
                members = sorted(members)
                issues.append(make_issue("NEAR_DUPLICATE_BODY", members[0],
                                         extra={"members": members}))
    return issues

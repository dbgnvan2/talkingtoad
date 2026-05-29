---
status: pending
proposed: 2026-05-28
author: claude (Cycle J)
source: external QA agent vulnerability report
---

# Issue Checker — Adversarial Hardening (3 latent crashes / 1 false-positive)

## Why

An external QA agent ran an adversarial audit against `api/crawler/issue_checker.py` and identified three brittle assumptions. Two crash the entire crawl job for the affected domain when the parser sees a malformed input; one silently inflates the SEO issue count with garbage. All three are confirmed against the current code (`api/crawler/issue_checker.py` at HEAD `5909cf2`).

The pattern is the same in every case: **trust in the shape of input that the parser may not actually guarantee.** This spec adds defensive normalisation at each site and locks the behaviour in with adversarial tests.

## Vulnerabilities (confirmed)

### V1 — Null reference crash on banner H1 detection

- **Site:** `api/crawler/issue_checker.py:1505`
- **Code:** `_BANNER_CLASSES.search(first_h1_outline.get("classes", ""))`
- **Trigger:** When an outline entry has `"classes": None` (key present, value None — common when BeautifulSoup/WordPress emits a malformed tag), `dict.get("classes", "")` returns `None`, not the default `""`. `re.search(None)` raises `TypeError: expected string or bytes-like object`.
- **Blast radius:** The entire `check_page` call raises, which crashes the crawl job for that domain — every page after the offending one is never analysed.

### V2 — KeyError on malformed anchor dictionaries

- **Sites:** `api/crawler/issue_checker.py:1687`, `1693`, `1694` (3 separate `a["href"]` reads)
- **Code:**
  ```python
  anchors = [a for a in anchors if a["href"] not in exempt_anchor_urls]   # 1687
  ...
  "empty_anchor_hrefs": [a["href"] for a in anchors[:10]]                  # 1693
  href_list = [a["href"] for a in anchors[:5]]                             # 1694
  ```
- **Trigger:** An `<a>` tag with only `name` or `id` (no `href`) — or any parser variant that omits the `"href"` key — produces a dict like `{"aria_label": "donate", "has_children": True}`. The blind `a["href"]` raises `KeyError: 'href'`.
- **Blast radius:** Same as V1 — `check_page` raises, crawl job dies.
- **Note on the str/dict coercion:** the existing `isinstance(anchors[0], str)` check only looks at the *first* element. A mixed list (legacy strings interleaved with new dicts, or vice versa) will skip coercion and crash later. The fix should normalise every element, not just sniff the first.

### V3 — Whitespace-only titles flagged as TITLE_DUPLICATE

- **Site:** `api/crawler/issue_checker.py:2280, 2282, 2284`
- **Code:**
  ```python
  if t: title_map.setdefault(t, []).append(page.url)
  if d: desc_map.setdefault(d, []).append(page.url)
  if t and d: pair_map.setdefault((t, d), []).append(page.url)
  ```
- **Trigger:** Two pages with `title = "   "` (or `" "`, or `"\n"`). `bool("   ")` is `True`, so both get bucketed under the same `"   "` key and flagged as TITLE_DUPLICATE. Same for META_DESC_DUPLICATE and TITLE_META_DUPLICATE_PAIR.
- **Blast radius:** No crash, but artificially inflates the issue count and contaminates the prioritised action checklist with phantom duplicates. Reduces user trust in the report.

## Proposed fixes

### F1 — Coalesce `None` to `""` before regex search (V1)

`api/crawler/issue_checker.py:1505`:

```python
# BEFORE
has_banner_class = bool(
    first_h1_outline
    and _BANNER_CLASSES.search(first_h1_outline.get("classes", ""))
)

# AFTER
has_banner_class = bool(
    first_h1_outline
    and _BANNER_CLASSES.search(first_h1_outline.get("classes") or "")
)
```

The `or ""` form handles both "key missing" and "key present with value `None`" in one expression. No behaviour change for valid string classes; no behaviour change for missing key (still `""` → no match).

### F2 — Normalise anchors in a single pass; drop malformed entries (V2)

`api/crawler/issue_checker.py:1681-1694` — replace the three blind reads with normalisation up-front:

```python
# BEFORE
anchors = page.empty_anchor_hrefs or []
# Support both old format (list[str]) and new format (list[dict])
if anchors and isinstance(anchors[0], str):
    anchors = [{"href": h, "aria_label": None, "has_children": False} for h in anchors]
# Filter out URLs the user has explicitly exempted (e.g. social media icon links)
if exempt_anchor_urls:
    anchors = [a for a in anchors if a["href"] not in exempt_anchor_urls]
if anchors:
    issue = make_issue("LINK_EMPTY_ANCHOR", url,
                       extra={"empty_anchor_count": len(anchors),
                              "empty_anchors": anchors[:10],
                              # Keep legacy field for backwards compat
                              "empty_anchor_hrefs": [a["href"] for a in anchors[:10]]})
    href_list = [a["href"] for a in anchors[:5]]

# AFTER
raw_anchors = page.empty_anchor_hrefs or []
# Normalise every element: legacy strings → dicts, dicts without a usable
# href are dropped silently (malformed parser output should not crash the crawl).
normalised: list[dict] = []
for a in raw_anchors:
    if isinstance(a, str):
        if a:
            normalised.append({"href": a, "aria_label": None, "has_children": False})
    elif isinstance(a, dict):
        href = a.get("href")
        if isinstance(href, str) and href:
            normalised.append(a)
    # else: malformed entry — drop
anchors = normalised
if exempt_anchor_urls:
    anchors = [a for a in anchors if a["href"] not in exempt_anchor_urls]
if anchors:
    issue = make_issue("LINK_EMPTY_ANCHOR", url,
                       extra={"empty_anchor_count": len(anchors),
                              "empty_anchors": anchors[:10],
                              # Keep legacy field for backwards compat
                              "empty_anchor_hrefs": [a["href"] for a in anchors[:10]]})
    href_list = [a["href"] for a in anchors[:5]]
```

Note: `empty_anchor_count` and `len(anchors)` may now diverge — `empty_anchor_count` is the raw parser count, while `len(normalised)` is the count of *reportable* anchors. The issue is only emitted when `anchors` (post-normalisation) is non-empty, so the existing "no issue if everything is malformed" behaviour is preserved. The `extra["empty_anchor_count"]` field already reports `len(anchors)` (the filtered count), so the API contract is unchanged.

### F3 — Treat whitespace-only titles/descriptions as empty (V3)

`api/crawler/issue_checker.py:2272-2285`:

```python
# BEFORE
for page in pages:
    if page.redirect_url or (300 <= page.status_code < 400):
        continue
    t = page.title
    d = page.meta_description
    if t:
        title_map.setdefault(t, []).append(page.url)
    if d:
        desc_map.setdefault(d, []).append(page.url)
    if t and d:
        pair_map.setdefault((t, d), []).append(page.url)

# AFTER
for page in pages:
    if page.redirect_url or (300 <= page.status_code < 400):
        continue
    # Normalise: a whitespace-only title is functionally empty.
    # We also strip outer whitespace so "My Page" and "My Page " group
    # together — accidental trailing whitespace is still a real duplicate.
    t = (page.title or "").strip()
    d = (page.meta_description or "").strip()
    if t:
        title_map.setdefault(t, []).append(page.url)
    if d:
        desc_map.setdefault(d, []).append(page.url)
    if t and d:
        pair_map.setdefault((t, d), []).append(page.url)
```

**Decision point — for user review:** the `.strip()` normalisation produces a small *intentional* behaviour change beyond the QA report. Previously `"My Page"` and `"My Page "` (trailing space) were treated as distinct titles and not flagged as duplicates. After the fix they group together and are flagged. This is the correct behaviour for duplicate detection — invisible trailing whitespace is a real bug worth surfacing — but it is a behaviour change, not a pure bug fix.

If the user wants a pure-minimal fix that *only* solves the whitespace-only case without the broader normalisation, the alternative is:

```python
if t and t.strip():
    title_map.setdefault(t, []).append(page.url)
# … same shape for d and (t, d)
```

(This keeps the raw `t` as the key, so trailing-whitespace variants stay distinct.) The spec's recommended fix is the `.strip()` variant; the alternative is offered for the user to pick at approval time.

## Tests (adversarial, must be written first)

Add a new class `TestAdversarialBoundaries` at the end of `tests/test_issue_checker.py`. The first three tests are the QA report's verbatim cases; the remaining four lock in edge cases the same fixes need to handle so we don't regress.

```python
# ---------------------------------------------------------------------------
# Adversarial Boundaries (QA Audit — Cycle J)
# ---------------------------------------------------------------------------

class TestAdversarialBoundaries:
    # ── V1: Banner H1 ──────────────────────────────────────────────────────
    def test_null_css_classes_in_heading_outline_does_not_crash(self):
        """Outline entry has classes=None (key present, value None).
        .get('classes', '') returns None, not '', so re.search(None) crashes."""
        page = _page(
            title="Mismatch Title",
            h1_tags=["Banner Title", "Content Title"],
            headings_outline=[
                {"level": 1, "text": "Banner Title", "classes": None},
                {"level": 1, "text": "Content Title", "classes": ""},
            ],
        )
        issues = check_page(page, suppress_banner_h1=True)
        assert isinstance(issues, list)  # no TypeError

    def test_missing_classes_key_in_heading_outline_does_not_crash(self):
        """Outline entry omits the 'classes' key entirely. Sanity check
        that the default branch of `.get()` still works after the fix."""
        page = _page(
            title="Mismatch Title",
            h1_tags=["Banner Title", "Content Title"],
            headings_outline=[
                {"level": 1, "text": "Banner Title"},  # no classes key
                {"level": 1, "text": "Content Title"},
            ],
        )
        issues = check_page(page, suppress_banner_h1=True)
        assert isinstance(issues, list)

    # ── V2: Empty anchor dictionaries ──────────────────────────────────────
    def test_malformed_anchor_dict_does_not_crash(self):
        """Anchor dict missing the 'href' key. Must be dropped, not crash."""
        page = _page(
            empty_anchor_count=1,
            empty_anchor_hrefs=[{"aria_label": "donate", "has_children": True}],
        )
        issues = check_page(page)
        assert isinstance(issues, list)
        # Malformed entry was dropped → no LINK_EMPTY_ANCHOR issue emitted.
        assert "LINK_EMPTY_ANCHOR" not in _codes(issues)

    def test_mixed_string_and_dict_anchors_normalised(self):
        """Mixed legacy strings and new dicts in the same list.
        Pre-fix code only sniffed the first element; the fix must normalise every entry."""
        page = _page(
            empty_anchor_count=2,
            empty_anchor_hrefs=[
                "https://example.com/legacy-string-href",
                {"href": "https://example.com/dict-href", "aria_label": None, "has_children": False},
            ],
        )
        issues = check_page(page)
        codes = _codes(issues)
        assert "LINK_EMPTY_ANCHOR" in codes
        issue = next(i for i in issues if i.code == "LINK_EMPTY_ANCHOR")
        assert issue.extra["empty_anchor_count"] == 2

    def test_anchor_dict_with_empty_href_dropped(self):
        """A dict whose 'href' is the empty string is malformed for our
        purposes — drop it rather than emitting a bogus issue."""
        page = _page(
            empty_anchor_count=1,
            empty_anchor_hrefs=[{"href": "", "aria_label": None, "has_children": False}],
        )
        issues = check_page(page)
        assert "LINK_EMPTY_ANCHOR" not in _codes(issues)

    # ── V3: Whitespace-only titles ─────────────────────────────────────────
    def test_whitespace_only_titles_not_flagged_as_duplicates(self):
        """'   ' is truthy in Python, so the original code grouped all
        whitespace-only titles under one key and flagged TITLE_DUPLICATE."""
        pages = [
            _page(url="https://example.com/1", title="   "),
            _page(url="https://example.com/2", title="   "),
        ]
        issues = check_cross_page(pages)
        assert "TITLE_DUPLICATE" not in _codes(issues)

    def test_whitespace_only_meta_descriptions_not_flagged_as_duplicates(self):
        """Same vulnerability, meta-description side."""
        pages = [
            _page(url="https://example.com/1", meta_description="   "),
            _page(url="https://example.com/2", meta_description="   "),
        ]
        issues = check_cross_page(pages)
        assert "META_DESC_DUPLICATE" not in _codes(issues)
```

If the user approves the `.strip()` (broader-normalisation) variant of F3, add one more test confirming the new behaviour:

```python
    def test_titles_differing_only_in_trailing_whitespace_flagged_as_duplicates(self):
        """Intentional behaviour change in F3: trailing/leading whitespace
        differences should now group as duplicates."""
        pages = [
            _page(url="https://example.com/1", title="My Page"),
            _page(url="https://example.com/2", title="My Page "),  # trailing space
        ]
        issues = check_cross_page(pages)
        assert "TITLE_DUPLICATE" in _codes(issues)
```

If the user chooses the minimal `t.strip()` variant instead, omit that test and leave the behaviour unchanged.

## Out of scope

- Same-shaped audits of other checkers (heading skip, image alt, etc.) — only the three sites the QA report flagged are in scope here.
- Parser fixes upstream in `api/crawler/parser.py` — the right defense lives at the consumer (checker) because the parser cannot guarantee well-formedness for adversarial HTML.
- Frontend changes — `extra.empty_anchor_count` and `extra.empty_anchors` schemas are unchanged.

## Acceptance criteria

1. All seven (or eight, with the F3 broader-normalisation variant) adversarial tests in `TestAdversarialBoundaries` are added to `tests/test_issue_checker.py` **before** the fixes land — they fail on `main`, pass after the fix.
2. The existing 1,250-test suite still passes — no regressions in `TestLinkEmptyAnchor`, `TestTitleDuplicate`, `TestMetaDescDuplicate`, `TestTitleMetaDuplicatePair`, or any banner-H1 test.
3. The architecture parity tests (`tests/test_architecture_constraints.py`, `tests/test_issue_codes_doc_in_sync.py`) still pass — no catalogue churn.
4. No documentation update required for `docs/issue-codes.md` (issue codes are unchanged). `docs/functional-specification.md` is read-only and unchanged by this work.

## Decisions for user approval

1. **Approve / reject the spec as a whole.**
2. **F3 variant:** broader-normalisation (`.strip()` — recommended, flags trailing-whitespace title duplicates) or minimal (`t and t.strip()` — only fixes the whitespace-only case)?
3. **Test class placement:** new `TestAdversarialBoundaries` class at end of file (matches QA report) — or merge each test into the existing per-feature class (`TestLinkEmptyAnchor`, `TestTitleDuplicate`, etc.)? Default: new class, easier to track audit provenance.

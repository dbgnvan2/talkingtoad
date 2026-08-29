# Micro-spec E1: Extract lazy-loaded images (`data-src`) — the parser currently sees none

Date: 2026-08-29
Status: **proposal — awaiting approval**
Area: `api/crawler/parser.py`, `api/crawler/issue_checker.py`
Codes affected: `IMG_ALT_MISSING`, `IMG_BROKEN`, `IMG_OVERSIZED`, `IMG_FORMAT_LEGACY`,
`IMG_NO_SRCSET`, `IMG_OVERSCALED`, `IMG_POOR_COMPRESSION`, `IMG_SLOW_LOAD`,
`IMG_ALT_GENERIC`, `IMG_ALT_TOO_LONG`, `IMG_ALT_TOO_SHORT`, `IMG_ALT_DUP_FILENAME`,
`IMG_DUPLICATE_CONTENT` — plus the whole Image Health score.

## Problem (verified against the live site, 2026-08-29)

`_extract_image_data` (`parser.py:1202`), `_extract_image_urls` (`parser.py:1080`) and
`_find_img_missing_alt_srcs` all iterate `soup.find_all("img", src=True)` and then
`continue` when `src` starts with `data:`.

Lazy-loading plugins (Smush, Elementor, WP Rocket, Lazy Load by WP Rocket, a3 Lazy Load,
and WordPress core's own `loading="lazy"` variants used with a placeholder) emit:

```html
<img src="data:image/svg+xml;base64,…" data-src="https://…/real-image.jpg" alt="…">
```

The real URL is in `data-src`. TalkingToad discards it and records **nothing**.

Measured on livingsystems.ca (a Smush site) on 2026-08-29:

| Page | `<img>` tags | counted by TalkingToad | carry `data-src` |
|---|---|---|---|
| `/emotional-pain-and-suffering/` | 9 | **0** | 9 |
| `/` (homepage) | 11 | **0** | 11 |

Job `05cd2496` crawled **272 pages** and stored **13 images** — those 13 come from the
custom post types Smush excludes from lazy-loading. The report then printed
**"Image Health Score: 97%"** over that 5% sample. This is P9 (a filter silently discards
most of the input) compounded by P2 (a reassuring score where the honest answer is
"not measured").

### The alt-text finding is being suppressed outright (P2 + P13)

`_count_img_missing_alt` (`parser.py:1097`) iterates **all** `<img>` with no `src` filter,
so the *count* is correct. But `_find_img_missing_alt_srcs` requires `src=True` and
non-`data:`, so on a lazy-loaded page it returns `[]`. `issue_checker.py:482` then reads:

```python
if page.img_missing_alt_count > 0:
    srcs = page.img_missing_alt_srcs or []
    …
    if srcs:                     # <-- empty list silences a real finding
        issue = make_issue("IMG_ALT_MISSING", url, …)
```

Measured on the live site: homepage has **10 of 11 images with missing or empty alt**;
`/emotional-pain-and-suffering/` has **8 of 9**. TalkingToad reported `IMG_ALT_MISSING`
on **1 page out of 272**. The count knew; the empty URL list threw the finding away.

## Change

### E1.1 — One shared source-URL resolver

Add to `parser.py`:

```python
# Attribute priority for the real image URL. `src` wins unless it is a data:
# placeholder, in which case the lazy-load attributes are tried in order.
_LAZY_SRC_ATTRS: tuple[str, ...] = (
    "data-src", "data-lazy-src", "data-original", "data-lazy", "data-echo",
)
_LAZY_SRCSET_ATTRS: tuple[str, ...] = ("data-srcset", "data-lazy-srcset")

def _resolve_img_src(tag, page_url: str = "") -> str | None:
    """Return the absolute real URL for an <img>, seeing through lazy-load
    placeholders. Returns None when no http(s) URL can be resolved."""
```

Resolution order: `src` (when non-empty and not `data:`) → each of `_LAZY_SRC_ATTRS` →
first candidate of `srcset` → first candidate of `_LAZY_SRCSET_ATTRS`. Result is
`urljoin`'d against `page_url` and rejected unless the scheme is `http`/`https`.

### E1.2 — Use it in all three extractors

`_extract_image_data`, `_extract_image_urls` and `_find_img_missing_alt_srcs` iterate
`soup.find_all("img")` (**no `src=True` filter**) and call `_resolve_img_src`. A tag whose
URL cannot be resolved is skipped for URL-keyed work but still counts toward
`img_missing_alt_count` (unchanged behaviour).

`img_data["has_srcset"]` becomes true for `srcset` **or** `data-srcset`.
`img_data["is_lazy_loaded"]` becomes true for `loading="lazy"` **or** a resolved
lazy-attribute URL, so `IMG_SLOW_LOAD` / LCP reasoning stays honest.

### E1.3 — Never let an empty URL list silence a non-zero count (P2)

`issue_checker.py:482` changes from `if srcs:` to:

```python
if srcs:
    …existing rich message…
elif page.img_missing_alt_count > 0:
    # URLs could not be resolved (unusual after E1.1) — still report the count
    # rather than dropping the finding. extra carries unresolved=True.
```

The `ignored_image_patterns` filter still applies to resolved URLs. When filtering empties
a previously non-empty list, that is a genuine suppression and stays silent; when the list
was **never** populated, the finding is reported.

### E1.4 — Announce the image cap (P9, rule 6)

`engine.py:675` caps `image_data_queue` at `_IMAGE_URL_CAP_PER_JOB = 150`. Post-E1 this cap
will actually bite on real sites. The engine records `images_seen_total` and
`images_collected` on `CrawlResult`; `get_image_summary` returns both; the PDF and the
Results image panel print **"Analysed 150 of 1,284 images found"** whenever they differ.
The cap value moves to `TT_IMAGE_URL_CAP_PER_JOB` (env, default 150) per rule 8.

## Acceptance criteria → tests

| ID | Criterion | Test |
|---|---|---|
| E1.1a | `_resolve_img_src` returns `data-src` when `src` is a `data:` placeholder | `tests/test_parser_lazy_images.py::test_e1_1a_data_src_resolved_over_data_uri` |
| E1.1b | A real `src` always wins over `data-src` | `…::test_e1_1b_real_src_wins` |
| E1.1c | `srcset` / `data-srcset` first candidate used when no single-URL attribute exists | `…::test_e1_1c_srcset_fallback` |
| E1.1d | Returns `None` for `mailto:`/relative-with-no-page_url/unresolvable, never raises | `…::test_e1_1d_unresolvable_returns_none` |
| E1.2a | **Real-artifact fixture** (P19/P9): saved HTML of `livingsystems.ca/emotional-pain-and-suffering/` yields 9 image records, not 0 | `…::test_e1_2a_real_smush_page_yields_nine_images` |
| E1.2b | `has_srcset` true for `data-srcset` | `…::test_e1_2b_data_srcset_counts_as_srcset` |
| E1.3a | Page with `img_missing_alt_count=10` and unresolvable srcs still emits `IMG_ALT_MISSING` | `tests/test_issue_checker.py::test_e1_3a_alt_missing_not_silenced_by_empty_srcs` |
| E1.3b | Real-artifact homepage fixture emits `IMG_ALT_MISSING` with count 10 | `tests/test_parser_lazy_images.py::test_e1_3b_real_homepage_alt_missing_fires` |
| E1.3c | **Adversarial (P7):** a page where every image is genuinely decorative (`alt=""` + `role="presentation"`) must NOT fire | `…::test_e1_3c_decorative_images_do_not_fire` |
| E1.4a | `get_image_summary` returns `images_seen_total` ≥ `images_collected` | `tests/test_image_analyzer.py::test_e1_4a_summary_reports_seen_and_collected` |
| E1.4b | **Real-scale (P9):** 400-image fixture → cap bites, summary reports `150 of 400` | `…::test_e1_4b_cap_announced_at_real_scale` |
| E1.4c | Image Health Score is suppressed (rendered "not measured") when `images_collected == 0` | `tests/test_report_generator.py::test_e1_4c_no_health_score_without_images` |

Fix→test map (P10): **E1.2a is the highest-impact, most-likely-to-regress test and is
written first.** It is a real saved artifact, not a synthetic fixture — a synthetic fixture
built with the ideal `<img src="...">` shape is exactly what let this bug live.

## Fixture

`tests/fixtures/lazy_images/livingsystems_emotional_pain.html` and
`…/livingsystems_home.html` — real saved responses, trimmed to `<body>`, checked in.
Recorded 2026-08-29. No live HTTP in tests.

## Adjacent issues found, not fixed (rule 10)

- `_detect_decorative` and `_extract_surrounding_text` were only ever exercised on
  non-lazy images; their behaviour on lazy markup is unverified. Flagged, not changed.
- `image_processor.py` / `wp_image_fixer.py` consume `ImageInfo.url`. Post-E1 they will
  receive many more URLs; the WP media-matching path is untested at that volume.
- `IMG_BROKEN` will start firing on lazy images whose `data-src` 404s. Expected, but it
  means the first post-E1 crawl of any site will look worse. Intended.

## Out of scope

Rendering JavaScript to see images injected client-side (that is `js_renderer.py`'s job and
a separate decision). E1 only reads attributes already present in the raw HTML.

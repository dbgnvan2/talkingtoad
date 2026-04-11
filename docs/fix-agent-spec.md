# TalkingToad — Bug Fix Specification for Code Agent

> **Scope:** Fix all bugs identified in the expert review. Vercel-specific issues
> (serverless timeout on long crawls, `wp-credentials.json` on Vercel's read-only
> filesystem) are **excluded** — the app runs locally for now.
>
> **Required outcome:** All existing tests pass. New tests are added as specified.
> No regressions.

---

## Project Context

- **Stack:** Python 3.11 + FastAPI backend; React 18 + Vite + Tailwind CSS frontend
- **Test runner:** `pytest` with `asyncio_mode = auto` (see `pytest.ini`)
- **Root directory:** `TalkingToad/`

---

## Fix 1 — NOINDEX_HEADER never fires (critical bug)

**Files:** `api/crawler/parser.py`, `api/crawler/issue_checker.py`,
`tests/test_issue_checker.py`

### The bug

`_check_crawlability` in `issue_checker.py` tries to detect whether a noindex
directive came from an HTTP response header (→ `NOINDEX_HEADER`) or from an HTML
meta tag (→ `NOINDEX_META`):

```python
# issue_checker.py lines 832–848 (current broken code)
def _check_crawlability(page: ParsedPage, issues: list[Issue]) -> None:
    url = page.url
    if not page.is_indexable:
        directive = (page.robots_directive or "").lower()
        # THIS CHECK IS ALWAYS FALSE — directive is the header VALUE ("noindex, noarchive"),
        # not the header NAME ("x-robots-tag"), so "x-robots-tag" can never appear in it
        if "x-robots-tag" in directive or _looks_like_header_directive(page):
            issues.append(make_issue("NOINDEX_HEADER", url))
        else:
            issues.append(make_issue("NOINDEX_META", url))

def _looks_like_header_directive(page: ParsedPage) -> bool:
    if page.robots_directive is None:
        return False
    return False  # ALWAYS returns False — stub function
```

The parser's `_parse_robots_signals` function populates `robots_directive` with the
raw value (e.g. `"noindex, noarchive"`), but there is no field to record **where**
that directive came from (header vs meta tag).

### The fix

**Step 1 — Add `robots_source` field to `ParsedPage`**

In `api/crawler/parser.py`, add a new field after `robots_directive`:

```python
# In the ParsedPage dataclass, add after:
#   robots_directive: str | None      # raw value from meta or X-Robots-Tag header
robots_source: str | None = None  # "header" | "meta" | None (None = indexable)
```

> `robots_source` defaults to `None` so the existing dataclass usages in tests
> that construct `ParsedPage` directly continue to work without changes.

**Step 2 — Set `robots_source` in `_parse_robots_signals`**

In `api/crawler/parser.py`, update `_parse_robots_signals` to return a 3-tuple
and record the source:

```python
def _parse_robots_signals(
    soup: BeautifulSoup, headers: dict[str, str]
) -> tuple[bool, str | None, str | None]:
    """Return (is_indexable, robots_directive, robots_source)."""
    directive: str | None = None
    source: str | None = None

    # Check X-Robots-Tag header first
    x_robots = headers.get("x-robots-tag", "")
    if x_robots:
        directive = x_robots
        source = "header"
        if "noindex" in x_robots.lower():
            return False, directive, source

    # Check meta robots tag
    meta_robots = soup.find("meta", attrs={"name": lambda n: n and n.lower() == "robots"})
    if meta_robots:
        content = meta_robots.get("content", "").strip()
        if content:
            directive = content
            source = "meta"
            if "noindex" in content.lower():
                return False, directive, source

    return True, directive, source
```

**Step 3 — Update `parse_page` to unpack the 3-tuple and set `robots_source`**

In `api/crawler/parser.py`, find where `_parse_robots_signals` is called
(line ~136) and change it to:

```python
# Before:
is_indexable, robots_directive = _parse_robots_signals(soup, result.headers)

# After:
is_indexable, robots_directive, robots_source = _parse_robots_signals(soup, result.headers)
```

Then, in the `ParsedPage(...)` constructor call inside `parse_page`, add:

```python
robots_source=robots_source,
```

**Step 4 — Fix `_check_crawlability` to use `robots_source`**

In `api/crawler/issue_checker.py`, replace the entire `_check_crawlability`
function and the stub `_looks_like_header_directive` with:

```python
def _check_crawlability(page: ParsedPage, issues: list[Issue]) -> None:
    url = page.url
    if not page.is_indexable:
        if getattr(page, "robots_source", None) == "header":
            issues.append(make_issue("NOINDEX_HEADER", url))
        else:
            issues.append(make_issue("NOINDEX_META", url))
```

Delete `_looks_like_header_directive` entirely — it is no longer used.

### New test required

In `tests/test_issue_checker.py`, add a test class (or add to the existing
`TestNoindexMeta` class area):

```python
class TestNoindexHeader:
    def test_noindex_via_header_emits_noindex_header(self):
        """X-Robots-Tag: noindex should emit NOINDEX_HEADER, not NOINDEX_META."""
        page = _page(is_indexable=False, robots_source="header")
        codes = _codes(check_page(page))
        assert "NOINDEX_HEADER" in codes
        assert "NOINDEX_META" not in codes

    def test_noindex_via_meta_emits_noindex_meta(self):
        """Meta robots noindex should emit NOINDEX_META, not NOINDEX_HEADER."""
        page = _page(is_indexable=False, robots_source="meta")
        codes = _codes(check_page(page))
        assert "NOINDEX_META" in codes
        assert "NOINDEX_HEADER" not in codes

    def test_noindex_source_none_emits_noindex_meta(self):
        """robots_source=None (default) should fall through to NOINDEX_META."""
        page = _page(is_indexable=False, robots_source=None)
        codes = _codes(check_page(page))
        assert "NOINDEX_META" in codes
        assert "NOINDEX_HEADER" not in codes
```

> The `_page()` helper in the test file must be extended to accept `robots_source`
> and pass it through to `ParsedPage`. Check the existing `_page()` signature
> and add `robots_source: str | None = None` as a keyword argument.

---

## Fix 2 — `_count_words` shallow copy corrupts BeautifulSoup tree (critical bug)

**File:** `api/crawler/parser.py`

### The bug

`_count_words` (line ~366) does:

```python
import copy
body_copy = copy.copy(body)         # ← SHALLOW copy
for tag in body_copy.find_all(_EXCLUDED_TAGS):
    tag.decompose()                 # ← modifies ORIGINAL soup's tree
```

`copy.copy` on a BeautifulSoup tag creates a shallow copy. The child elements in
`body_copy` are the **same objects** as in the original `soup`. Calling
`tag.decompose()` on them removes them from the original tree, corrupting every
subsequent parser call that reads `soup` after `_count_words` runs (e.g. link
extraction, heading extraction).

### The fix

Change `copy.copy` to `copy.deepcopy`:

```python
def _count_words(soup: BeautifulSoup) -> int:
    """Count visible body words, excluding navigation/chrome elements (spec §E5)."""
    body = soup.find("body")
    if not body:
        return 0
    import copy
    body_copy = copy.deepcopy(body)   # ← deep copy, does NOT mutate original
    for tag in body_copy.find_all(_EXCLUDED_TAGS):
        tag.decompose()
    text = body_copy.get_text(separator=" ")
    return len(text.split())
```

### Tests

This fix does not require new test cases of its own, but the existing test suite
exercises link extraction, heading extraction, and word count on the same page —
if the shallow copy was corrupting the tree, those tests would have been failing
intermittently. Verify all existing `test_issue_checker.py` and
`test_crawl_engine.py` tests still pass after the change.

---

## Fix 3 — `URL_HAS_SPACES` false positive on `+` in query strings (warning bug)

**File:** `api/crawler/issue_checker.py`

### The bug

`check_url_structure` (line ~1029):

```python
if "%20" in url or "+" in urlparse(url).query:
    issues.append(make_issue("URL_HAS_SPACES", url))
```

The `+` character is **valid** in URL query strings — it is the standard
form-encoding for a space in a query parameter value (e.g. `?q=mental+health`).
Flagging it as a URL structure issue produces false positives for any site whose
search or filter URLs use form-encoded query strings.

The actual problem is **literal spaces encoded as `%20` in the URL path** — that
indicates spaces were used in a page slug or file name.

### The fix

Remove the `"+" in urlparse(url).query` check. Keep the `"%20"` check but scope
it to the **path** only (not the query string, where `%20` can also be legitimate
but less common):

```python
def check_url_structure(url: str) -> list[Issue]:
    """Return URL structure issues for *url* (spec §E2)."""
    issues: list[Issue] = []
    parsed = urlparse(url)
    path = parsed.path

    if len(url) > 200:
        issues.append(make_issue("URL_TOO_LONG", url))
    if any(c.isupper() for c in path):
        issues.append(make_issue("URL_UPPERCASE", url))
    if "%20" in path:                       # spaces in path slug only, not query string
        issues.append(make_issue("URL_HAS_SPACES", url))
    if "_" in path:
        issues.append(make_issue("URL_HAS_UNDERSCORES", url))

    return issues
```

### New tests required

Add to `tests/test_issue_checker.py` in the `TestUrlStructure` class (or equivalent):

```python
def test_plus_in_query_string_no_false_positive(self):
    """+ in query string is valid form-encoding — must not fire URL_HAS_SPACES."""
    codes = _codes(check_url_structure("https://example.org/search?q=mental+health"))
    assert "URL_HAS_SPACES" not in codes

def test_percent20_in_path_emits_url_has_spaces(self):
    """Literal %20 in URL path indicates a space in the slug — must fire."""
    codes = _codes(check_url_structure("https://example.org/my%20page/"))
    assert "URL_HAS_SPACES" in codes

def test_percent20_in_query_string_no_false_positive(self):
    """Encoded space in query value only — should not fire URL_HAS_SPACES."""
    codes = _codes(check_url_structure("https://example.org/search?q=mental%20health"))
    assert "URL_HAS_SPACES" not in codes
```

---

## Fix 4 — `CANONICAL_SELF_MISSING` fires on same pages as `CANONICAL_MISSING` (double-fire)

**File:** `api/crawler/issue_checker.py`

### The bug

In `check_page` (lines ~677–682):

```python
# ── Canonical tag ──────────────────────────────────────────────────────────
_check_canonical(page, issues)      # emits CANONICAL_MISSING for query-string pages with no canonical

# ── Canonical self (best-practice recommendation for all indexable pages) ──
if page.canonical_url is None:
    issues.append(make_issue("CANONICAL_SELF_MISSING", url))  # fires on EVERY page with no canonical
```

A page with a query string and no canonical tag gets **both** `CANONICAL_MISSING`
(from `_check_canonical`) **and** `CANONICAL_SELF_MISSING`. These represent the
same underlying problem and should not both fire on the same page.

`CANONICAL_MISSING` is the actionable issue (warning severity). `CANONICAL_SELF_MISSING`
is a best-practice info signal that only adds noise when `CANONICAL_MISSING` has
already fired.

### The fix

Check whether `CANONICAL_MISSING` was emitted **before** emitting
`CANONICAL_SELF_MISSING`, and suppress the latter if so:

```python
# ── Canonical tag ──────────────────────────────────────────────────────────
_check_canonical(page, issues)

# ── Canonical self (best-practice — suppress if CANONICAL_MISSING already fired) ──
canonical_missing_fired = any(i.code == "CANONICAL_MISSING" for i in issues)
if page.canonical_url is None and not canonical_missing_fired:
    issues.append(make_issue("CANONICAL_SELF_MISSING", url))
```

### New tests required

Add to the canonical tests section:

```python
def test_canonical_self_missing_suppressed_when_canonical_missing_fires(self):
    """Query-string page with no canonical: CANONICAL_MISSING fires, CANONICAL_SELF_MISSING must not."""
    page = _page(url="https://example.com/page?ref=123", canonical_url=None)
    codes = _codes(check_page(page))
    assert "CANONICAL_MISSING" in codes
    assert "CANONICAL_SELF_MISSING" not in codes

def test_canonical_self_missing_fires_for_plain_page_with_no_canonical(self):
    """Plain indexable page (no query string) with no canonical: CANONICAL_SELF_MISSING fires."""
    page = _page(url="https://example.com/about", canonical_url=None)
    codes = _codes(check_page(page))
    assert "CANONICAL_SELF_MISSING" in codes
    assert "CANONICAL_MISSING" not in codes
```

---

## Fix 5 — `apply_fix` silently overwrites WordPress content with an empty string

**File:** `api/services/wp_fixer.py`

### The bug

In `apply_fix` (line ~295):

```python
proposed = fix.get("proposed_value", "")
```

If `proposed_value` is an empty string and `field` is a text field (anything
other than `indexable`), the function proceeds to call:

```python
r = await wp.patch(endpoint, json={"meta": {meta_key: ""}})
```

This **clears the meta field in WordPress** — erasing the existing SEO title,
meta description, or OG tag. A user who approves a fix without entering a value
(or whose value was never auto-proposed and left blank) will silently destroy live
content.

The UI already disables the Approve button for empty text fields, but the backend
has no protection against this condition being bypassed (e.g. direct API calls,
race conditions).

### The fix

Add an early-return guard for empty `proposed_value` on non-indexable fields,
immediately after `proposed` is set:

```python
async def apply_fix(
    wp: WPClient,
    fix: dict,
    seo_plugin: str | None,
) -> tuple[bool, str | None]:
    """Apply a single approved fix via the WP REST API.

    Returns (success, error_message).
    """
    field = fix.get("field", "")
    spec = _FIELD_SPECS.get(field)
    if not spec:
        return False, f"No fix spec for field '{field}'"

    if not seo_plugin:
        return False, "No supported SEO plugin detected (Yoast or Rank Math required)"

    meta_key = spec.yoast_key if seo_plugin == "yoast" else spec.rank_math_key
    if not meta_key:
        return False, f"No meta key for field '{field}' with plugin '{seo_plugin}'"

    wp_post_id = fix.get("wp_post_id")
    wp_post_type = fix.get("wp_post_type", "page")
    if not wp_post_id:
        return False, "Missing wp_post_id — regenerate fixes"

    proposed = fix.get("proposed_value", "")

    # Guard: refuse to clear live content with an empty value
    if field != "indexable" and not proposed.strip():
        return False, (
            "Proposed value is empty — enter a replacement before approving this fix."
        )

    endpoint = f"{'pages' if wp_post_type == 'page' else 'posts'}/{wp_post_id}"

    # Special handling for the indexable field
    if field == "indexable":
        meta_value = _indexable_meta_value(seo_plugin)
    else:
        meta_value = proposed

    try:
        r = await wp.patch(endpoint, json={"meta": {meta_key: meta_value}})
        if r.status_code == 200:
            return True, None
        body = r.json()
        return False, body.get("message", f"HTTP {r.status_code}: {r.text[:120]}")
    except Exception as exc:
        return False, str(exc)
```

---

## Fix 6 — Dead duplicate entries in `issueHelp.js`

**File:** `frontend/src/data/issueHelp.js`

### The bug

The file contains three entries with **stale keys that no longer exist in the
catalogue**. Each has a correct-key duplicate immediately present elsewhere in
the same file. The stale entries are dead code — the UI looks up entries by the
catalogue code, so these old keys are never rendered:

| Stale key (dead) | Correct key (already present) |
|---|---|
| `PAGE_TOO_LARGE` | `PAGE_SIZE_LARGE` |
| `NO_VIEWPORT_META` | `MISSING_VIEWPORT_META` |
| `NO_SCHEMA` | `SCHEMA_MISSING` |

There is also one entry for `EXCESSIVE_EXTERNAL_DEPS` which has **no
corresponding catalogue code** — it is a Phase 2 concept that was never
implemented. This is dead code too.

### The fix

**Delete** the following four complete entries from `issueHelp.js`:

1. The `PAGE_TOO_LARGE: { ... }` entry (currently around line 1032)
2. The `EXCESSIVE_EXTERNAL_DEPS: { ... }` entry (currently around line 1051)
3. The `NO_VIEWPORT_META: { ... }` entry (currently around line 1072)
4. The `NO_SCHEMA: { ... }` entry (currently around line 1144)

Do not modify any other entries. The correct-key versions (`PAGE_SIZE_LARGE`,
`MISSING_VIEWPORT_META`, `SCHEMA_MISSING`) are already present and should be
left untouched.

After deletion, verify the file still exports correctly by checking for
syntax errors (no trailing commas on the last entry before `}`).

---

## Fix 7 — Add confirmation dialogs before destructive actions in FixManager

**File:** `frontend/src/components/FixManager.jsx`

### The bug

Two actions in `FixManager.jsx` are destructive and irreversible from the user's
perspective, but have no confirmation step:

1. **"Clear & Regenerate"** (`handleClear`) — deletes all fix proposals and the
   user's review progress (approvals, edits, skips) without warning.
2. **"Apply N Approved Fixes"** (`handleApply`) — writes changes to live
   WordPress content. This is the most consequential action in the app.

### The fix

Use `window.confirm()` at the top of each handler. If the user cancels, return
immediately without making any API call.

```jsx
async function handleClear() {
  const ok = window.confirm(
    'Delete all fix proposals? Your review progress (approvals, edits, skips) will be lost.'
  )
  if (!ok) return

  await apiFetch(`/api/fixes/${jobId}`, { method: 'DELETE' })
  setFixes([])
  setGenerated(false)
  setApplyResult(null)
  setError(null)
  setSeoPlugin(null)
}

async function handleApply() {
  const ok = window.confirm(
    `Apply ${approvedCount} approved fix${approvedCount !== 1 ? 'es' : ''} to WordPress? ` +
    `This will update live content on your site and cannot be automatically undone.`
  )
  if (!ok) return

  setApplying(true)
  setApplyResult(null)
  setError(null)
  try {
    const res = await apiFetch(`/api/fixes/apply/${jobId}`, { method: 'POST' })
    const data = await res.json()
    if (!res.ok) {
      setError(data.error?.message || 'Apply failed.')
      return
    }
    setApplyResult(data)
    const refreshed = await apiFetch(`/api/fixes/${jobId}`)
    if (refreshed.ok) setFixes(await refreshed.json())
  } catch (e) {
    setError('Could not connect to the API.')
  } finally {
    setApplying(false)
  }
}
```

Note: the `approvedCount` variable is already computed in the component and is
in scope when `handleApply` is defined.

---

## Fix 8 — Silent error handling on FixManager initial load

**File:** `frontend/src/components/FixManager.jsx`

### The bug

The `useEffect` that loads existing fixes on mount (line ~203):

```jsx
useEffect(() => {
  apiFetch(`/api/fixes/${jobId}`)
    .then(r => r.ok ? r.json() : [])
    .then(data => {
      if (data.length > 0) {
        setFixes(data)
        setGenerated(true)
      }
    })
    .catch(() => {})    // ← swallows ALL errors silently
}, [jobId])
```

If the API is down or the request fails, the user sees an empty Fix Manager with
no explanation. The `catch` block discards the error completely.

### The fix

Surface the error to the user via the existing `error` state:

```jsx
useEffect(() => {
  apiFetch(`/api/fixes/${jobId}`)
    .then(r => {
      if (!r.ok) throw new Error(`Server returned ${r.status}`)
      return r.json()
    })
    .then(data => {
      if (data.length > 0) {
        setFixes(data)
        setGenerated(true)
      }
    })
    .catch(err => {
      setError(`Could not load existing fixes: ${err.message}`)
    })
}, [jobId])
```

---

## Fix 9 — No timeout on `apiFetch`

**File:** `frontend/src/components/FixManager.jsx`

### The bug

`apiFetch` has no timeout. If the WordPress server is slow or unresponsive, the
"Connecting to WordPress…" or "Applying…" spinner runs indefinitely with no user
feedback.

### The fix

Add an `AbortController` with a 30-second timeout:

```jsx
async function apiFetch(path, opts = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 30_000)
  try {
    const res = await fetch(`${API}${path}`, {
      headers: { 'Content-Type': 'application/json', ...authHeader(), ...opts.headers },
      signal: controller.signal,
      ...opts,
    })
    return res
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new Error('Request timed out after 30 seconds. Check your WordPress connection.')
    }
    throw err
  } finally {
    clearTimeout(timer)
  }
}
```

> Note: `signal` must be in the `fetch` call options before the spread of `opts`
> so that `opts` passed by callers cannot accidentally override it. The current
> implementation spreads `opts` last — add `signal` before the spread.

---

## Fix 10 — Silent CSV export errors

**File:** Find the export/CSV component (likely `frontend/src/pages/Results.jsx`
or a dedicated export hook/component — search for `Blob`, `URL.createObjectURL`,
or `text/csv` to locate it)

### The bug

CSV export errors are currently only logged to the browser console (`console.error`)
with no visible feedback to the user. A nonprofit staff member whose export silently
fails will not know to retry or report the issue.

### The fix

Wherever the CSV export fails, show an error to the user. The exact implementation
depends on the component structure, but the pattern should be:

```jsx
// Instead of:
} catch (err) {
  console.error('Export failed', err)
}

// Use:
} catch (err) {
  console.error('Export failed', err)
  // Show visible error — use alert() if no error state is available,
  // or set a local error state and display an error banner
  alert(`Export failed: ${err.message}. Please try again.`)
}
```

If the export is already within a component that has a state setter for errors,
prefer `setError(...)` over `alert()` for consistency with the rest of the UI.

---

## Fix 11 — `IMG_OVERSIZED` has no test coverage

**File:** `tests/test_issue_checker.py`

### The gap

`check_asset()` in `issue_checker.py` handles both PDF and image size checks,
but the existing test suite only tests PDF size. `IMG_OVERSIZED` has no test.

### New tests required

Add a test class for `check_asset` image checks:

```python
class TestImgOversized:
    def _asset_result(self, content_type: str, size_bytes: int) -> FetchResult:
        """Helper to create a FetchResult for an asset."""
        return FetchResult(
            url="https://example.com/photo.jpg",
            final_url="https://example.com/photo.jpg",
            status_code=200,
            html="",
            content_type=content_type,
            headers={"content-length": str(size_bytes)},
            redirect_chain=[],
            timed_out=False,
        )

    def test_image_over_default_threshold_emits_issue(self):
        result = self._asset_result("image/jpeg", 210 * 1024)
        codes = [i.code for i in check_asset(result)]
        assert "IMG_OVERSIZED" in codes

    def test_image_exactly_at_threshold_no_issue(self):
        result = self._asset_result("image/jpeg", 200 * 1024)
        codes = [i.code for i in check_asset(result)]
        assert "IMG_OVERSIZED" not in codes

    def test_image_under_threshold_no_issue(self):
        result = self._asset_result("image/png", 50 * 1024)
        codes = [i.code for i in check_asset(result)]
        assert "IMG_OVERSIZED" not in codes

    def test_custom_threshold_respected(self):
        result = self._asset_result("image/webp", 100 * 1024)
        # Under default 200KB — no issue
        assert "IMG_OVERSIZED" not in [i.code for i in check_asset(result)]
        # Over custom 50KB threshold — issue fires
        assert "IMG_OVERSIZED" in [i.code for i in check_asset(result, img_size_limit_kb=50)]

    def test_pdf_not_flagged_as_img_oversized(self):
        result = self._asset_result("application/pdf", 300 * 1024)
        codes = [i.code for i in check_asset(result)]
        assert "IMG_OVERSIZED" not in codes

    def test_missing_content_length_no_issue(self):
        """No content-length header → size is 0 → no issue emitted."""
        result = FetchResult(
            url="https://example.com/photo.jpg",
            final_url="https://example.com/photo.jpg",
            status_code=200,
            html="",
            content_type="image/jpeg",
            headers={},
            redirect_chain=[],
            timed_out=False,
        )
        codes = [i.code for i in check_asset(result)]
        assert "IMG_OVERSIZED" not in codes
```

> Adjust `FetchResult` constructor arguments to match the actual dataclass fields
> in `api/crawler/fetcher.py`.

---

## Fix 12 — Update `docs/overview.md` (stale threshold)

**File:** `docs/overview.md`

### The issue

Line ~113 reads:
```
- Page HTML exceeds 150 KB
```

The actual threshold in `issue_checker.py` is now **300 KB** (updated by the
developer). The documentation is stale.

### The fix

Update line 113:
```
- Page HTML exceeds 300 KB (configurable via `page_size_limit_kb` parameter)
```

---

## Implementation Order

Implement in this order to keep tests passing at each step:

1. **Fix 3** (URL_HAS_SPACES) — pure string logic, easiest, no new fields
2. **Fix 4** (CANONICAL double-fire) — pure logic change
3. **Fix 1** (NOINDEX_HEADER) — requires new dataclass field + parser change
4. **Fix 2** (_count_words deep copy) — one-line change, verify no test regressions
5. **Fix 5** (wp_fixer empty proposed_value) — backend only, no tests to write
6. **Fix 6** (issueHelp.js dead entries) — frontend data cleanup
7. **Fixes 7–9** (FixManager.jsx UX) — frontend logic
8. **Fix 10** (CSV export error) — frontend UX
9. **Fixes 11–12** (tests + docs) — can be done alongside related fixes

---

## Verification Checklist

After all fixes:

```bash
# From project root with venv active
pytest tests/ -v
```

All tests must pass with no warnings about missing fields or unexpected codes.

Specifically verify:
- `TestNoindexHeader` — all 3 new tests pass
- `TestNoindexMeta` — still passes (regression check)
- `TestUrlStructure` — plus/query false positive tests pass
- `TestCanonical*` — no CANONICAL_SELF_MISSING on query-string pages
- `TestImgOversized` — all new tests pass
- `TestPageSizeLarge` — existing tests still pass (threshold already at 300KB)

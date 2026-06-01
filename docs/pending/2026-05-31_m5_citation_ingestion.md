---
status: pending
proposed: 2026-05-31
author: Architect (M5 cycle, TalkingToad session)
type: feature
source: PLAN-V3.0.md Milestone 5 (Citation ingestion from sibling phrase tool)
---

# M5 — Citation Ingestion (`POST /api/jobs/{job_id}/ai-citations`) + `AI_CITED_PAGE` / `AI_HIGH_VALUE_UNCITED`

> Catalogue: `api/crawler/checkers/registry.py`. **Note:** the existing
> `api/services/citation_model.py` is about *in-page* citations (different concept) —
> do NOT reuse it. M5 is about per-URL AI-citation **counts** ingested from the sibling tool.

## Goal
Let the sibling phrase tool POST per-URL AI-citation data into a crawl job; store it on
each page; surface two issue codes. (PLAN-V3.0 §M5.)

## Data model (new CrawledPage fields)
`api/models/page.py` `CrawledPage` (Pydantic, `extra="allow"`) — add explicit fields:
- `ai_citation_count_30d: int | None = None`  (NULL ≠ 0 — None means "no data ingested")
- `ai_citation_engines: list[str] | None = None`
- `ai_citation_last_updated: str | None = None`  (ISO timestamp)

## Endpoint
`POST /api/jobs/{job_id}/ai-citations` — **new router** `api/routers/citations.py`,
registered in `api/main.py`. **Bearer auth required** (`dependencies=[Depends(require_auth)]`,
the pattern used by ai.py/geo.py).
- Path `job_id` validated with the UUID regex pattern (as the fix routers do).
- Pydantic request models:
  - `EngineCitation { engine: str, count_30d: int, last_seen: str | None = None }`
  - `CitationEntry { url: str, engines: list[EngineCitation] }`
  - `CitationIngestionRequest { citations: list[CitationEntry] }`
- For each entry: normalise the URL via `normalise_url` (note British spelling)
  and match against the job's pages (`await store.get_pages(job_id)`, compare normalised URLs).
  On match, mutate the matched `CrawledPage` (set `ai_citation_count_30d=sum(counts)`,
  `ai_citation_engines=[e.engine...]`, `ai_citation_last_updated=<now iso>`) and persist via
  `await store.save_pages([...])`. **There is no `update_page`** — the store API is async:
  `await store.get_pages(job_id)` then `await store.save_pages(pages)`.
- Response: `{ "matched_count": int, "unmatched_count": int, "unmatched_urls": list[str] }`.
- **404** if `job_id` unknown; **422** on malformed body; **401** without auth.
- **SSRF note:** citation URLs are matched as strings, **never fetched**. Document that if a
  future version fetches them it MUST go through `is_ssrf_safe()` first.
- **Rate limit:** the app HAS slowapi wired (`from api.services.rate_limiter import limiter`).
  Apply `@limiter.limit(...)` with a sensible per-IP limit (mirror `AI_ANALYSIS_LIMIT` usage
  in crawl.py). A `429` test is optional.

## Issue codes (all 3 registries in `checkers/registry.py`)
- `AI_CITED_PAGE` — **info, positive signal, impact 0** — emitted when
  `ai_citation_count_30d` is not None and `> 0`. Confidence: **"Established when data present"**
  → use `"Established"` (the confidence enum). `_ISSUE_SCORING: (0, 0)`.
- `AI_HIGH_VALUE_UNCITED` — **warning, impact 4, "Reasonable proxy"** — emitted when the page
  is structurally healthy (heuristic: `score >= 80` AND `word_count > 300`) AND
  `ai_citation_count_30d == 0` AND data was ingested recently (`ai_citation_last_updated`
  within 60 days of the runtime `today` — pass `today` explicitly for determinism, per M4).
  `_ISSUE_SCORING: (4, 2)`.
- Emission lives where per-page issues are assembled. Both emit only when citation data is
  present (`ai_citation_count_30d is not None`) — **NULL ≠ 0**, so pages with no ingested
  data emit neither.

## Parity (mandatory)
- `issueHelp.js`: two entries with confidence + full V4 fields (template:
  `SCHEMA_VISIBLE_MISMATCH`). Regenerate `docs/issue-codes.md`.

## Contract tests (CLAUDE.md NON-NEGOTIABLE — endpoint is frontend/sibling-facing)
`tests/test_citation_ingestion.py`:
- `POST .../ai-citations` 200 → response has `matched_count`, `unmatched_count`, `unmatched_urls`.
- 10 URLs, 7 match → `matched_count == 7`, `unmatched_count == 3`.
- **URL normalization matches the crawler** (trailing slash, percent-encoding) →
  `test_ingest_citations_url_normalisation_matches_crawler`.
- Malformed body → 422; missing auth → 401; unknown job_id → 404.
- After ingest, `GET /api/crawl/{id}/pages?url=...` includes `ai_citation_count_30d`,
  `ai_citation_engines` (may be null) → `test_pages_endpoint_has_citation_fields`.
- `AI_HIGH_VALUE_UNCITED` only when ingestion within 60 days (fixed `today`); NULL ≠ 0
  (a never-ingested page emits neither code).
- **Adversarial:** ingest for a URL not in the job → counted in `unmatched_urls`, no crash;
  `count_30d == 0` on a healthy page with recent ingest → `AI_HIGH_VALUE_UNCITED` fires;
  same page but ingest 90 days old → does NOT fire.

## Files
| File | Change |
|---|---|
| `api/models/page.py` | 3 new CrawledPage fields |
| `api/routers/citations.py` | **NEW** router + endpoint + Pydantic models |
| `api/main.py` | register the router |
| `api/crawler/checkers/registry.py` | 2 codes × 3 registries |
| issue-assembly site (`issue_checker.py` or wherever per-page issues finalize with score) | emit both codes |
| `frontend/src/data/issueHelp.js` | 2 entries + V4 fields |
| `docs/issue-codes.md` | regenerate |
| `docs/api.md` | document the new endpoint |

## Security check
- **SSRF:** No — citation URLs matched as strings, never fetched.
- **Auth:** **Yes** — `require_auth` on the new router.
- **WordPress:** No.  **XSS:** No.

## Documentation impact
`docs/api.md` (+endpoint), `docs/issue-codes.md` regenerated. `docs/thresholds.md`
(READ-ONLY) untouched (60-day / score-80 / 300-word constants live in code).
`PLAN-V3.0-UNIFIED.md` note when merged.

## Acceptance criteria
1. Endpoint stores citation data keyed by crawler-normalized URL; response carries
   matched/unmatched counts + unmatched_urls.
2. `AI_CITED_PAGE` on cited pages; `AI_HIGH_VALUE_UNCITED` only when healthy + count 0 +
   recent ingest; **NULL ≠ 0** (never-ingested pages emit neither).
3. Contract tests (200 schema, 401, 404, 422, normalization, pages-field) pass BEFORE any
   frontend work; adversarial guards pass.
4. 2 codes in all 3 registries; issueHelp (V4) + issue-codes.md parity passes.
5. `thresholds.md` untouched. Full suite green, 0 regressions.

## Note for architect/dev — verify before coding
Store API is async with NO `update_page`: use `await store.get_pages(job_id)`, mutate the
matched CrawledPage, `await store.save_pages(pages)`. Confirm the per-page issue-assembly site has access to `page.score` and
`word_count` at emit time (score may be computed late — if so, emit these two codes in the
same place scores are finalized, not in `check_page` which runs pre-score).

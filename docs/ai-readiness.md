---
title: AI-Readiness Confidence Labels
status: draft
last_updated: 2026-06-01
---

# AI-Readiness Confidence Labels

## Overview

The AI-readiness system assigns confidence labels to individual checks based on the reliability of the detection method. These labels are documented per-issue in `_AI_READINESS_CONFIDENCE` (see `api/crawler/checkers/registry.py`).

Each issue code in the `ai_readiness` category carries one of three confidence labels. The label is attached to the `Issue` object via `make_issue()` and surfaced in PDF/Excel reports as confidence pills (M7).

## Label Definitions

### Established

- **Meaning**: The check uses a directly measured, deterministic signal.
- **Examples**: `AI_PREVIEW_SUPPRESSED` (detects meta tags that suppress previews), `AI_PREVIEW_BLOCKED_AT_BOT` (bot-specific preview blocking), `SCHEMA_VISIBLE_MISMATCH` (compares structured data to rendered text), `AI_BOT_SEARCH_BLOCKED` (vendor-confirmed via robots.txt protocol).
- **Reliability**: High. No inference or heuristic involved.

### Reasonable Proxy

- **Meaning**: The check uses a strong proxy signal that correlates highly with the intended property.
- **Examples**: `AI_CONTENT_NOT_IN_TEXT` (checks if AI-generated content blocks are present in rendered text vs. hidden), `JSON_LD_MISSING` (structured data absence), `DATE_PUBLISHED_MISSING` (missing publication date metadata), `CONTENT_THIN` (Google has published thin-content guidance).
- **Reliability**: Moderate-high. Proxy is well-established but not a direct measurement.

### Heuristic

- **Meaning**: The check uses a heuristic or pattern match with known false-positive/negative rates.
- **Examples**: `AI_MAIN_CONTENT_LOW_RATIO` (ratio of main content to boilerplate), `AI_NO_VISUAL_COMPANION` (checks for images near AI content), `SEMANTIC_DENSITY_LOW` (word-count heuristic), `CENTRAL_CLAIM_BURIED` (DOM position heuristic).
- **Reliability**: Moderate. Results should be manually verified.

## Required Disclosures

1. **Heuristics are not measured signals**: Heuristic-based checks (`Heuristic` label) are pattern matches, not direct measurements. They may produce false positives or negatives.
2. **No aggregated AI score**: TalkingToad does not compute a single "AI-readiness score." Each check is reported independently with its confidence label.
3. **Vendor-unconfirmed where applicable**: Checks that infer AI content presence (e.g., `AI_CONTENT_NOT_IN_TEXT`) are not confirmed by the AI vendor (OpenAI, Google). They are based on observable page characteristics.

## Citation Ingestion Contract

The `POST /api/jobs/{job_id}/ai-citations` endpoint accepts citation data for AI-readiness analysis. Contract:

- **Input**: Array of citation objects with `url` and `engines` (array of `{engine, count_30d, last_seen?}`).
- **Processing**: Each citation is matched against crawled pages by URL. Matched pages get citation data stored; unmatched URLs are returned for user review.
- **Output**: `{matched_count, unmatched_count, unmatched_urls}`. Triggers re-scoring of `AI_CITED_PAGE` (page is cited by AI engines) and `AI_HIGH_VALUE_UNCITED` (high-value page lacks citations).
- **Idempotency**: Duplicate citations (same URL + engine) are silently overwritten.
- **SSRF**: Citation URLs are matched as strings only — they are never fetched.
- **Auth**: Bearer token required. Rate limited to 10/minute per IP.

## Related

- Issue catalogue: [`issue-codes.md`](issue-codes.md)
- AI routing: [`ai-routing.md`](ai-routing.md)
- API reference: [`api.md`](api.md)

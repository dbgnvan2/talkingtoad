# PARKED — SERP-Discovery (separate repo)

> **Status: parked idea, separate project.** Not part of TalkingToad's codebase or roadmap.
> Captured here (2026-06-01) so the division of labour and the hand-off contract aren't lost.
> When built, this lives in its own repo (`serp-discovery`), NOT in TalkingToad.

## The three-tool stack (division of labour)

| Tool | Question | Repo | Status |
|---|---|---|---|
| **SERP-Discovery** | "What should I build?" — search intent, volume, keyword difficulty, content gaps | `serp-discovery` (separate) | **parked (this doc)** |
| **TalkingToad** | "Is it built correctly?" — structure, extractability, GEO authority signals | this repo | active (v3.0) |
| **GSC (the bridge)** | "How does the world actually see what I built?" — measured performance | TalkingToad M6 | spec'd, blocked on Google OAuth creds |

**Key principle:** TalkingToad is an **Authority Engineering engine**, NOT a keyword-research
tool. Do not add keyword/intent/volume features to TalkingToad — that belongs in
SERP-Discovery. Keeping them separate keeps each architecture clean.

## What SERP-Discovery is for
- Keyword/phrase discovery: what people search, volume, difficulty.
- Content-gap analysis: topics/intents not yet covered.
- Output: a prioritised "what to build" list (target entities + phrases per planned page).

## The hand-off contract (how the three connect)
1. **SERP-Discovery → author:** "Build a page targeting *Bowen Theory Vancouver* (these
   long-tail questions, these entities)."
2. **Author creates the content.**
3. **TalkingToad audits it:** is it structured for AI retrieval? (GEO moat: M3.1–M3.4,
   GA1–GA4). Feed SERP-Discovery's target entities into `GeoConfig.topic_entities` so the
   FAQ generator (GA3) and entity schema (GA4) align with the intent that motivated the page.
4. **GSC (M6) validates:** is it actually ranking / featured / cited?
   - High impressions + low clicks on a question query → GEO moat failing → re-audit in
     TalkingToad (Answerability / ExtractabilityScore).
   - **Hidden Gem** (structurally healthy, near-zero clicks) → TalkingToad's M6 emits a signal
     back to SERP-Discovery to re-check intent / refresh the topic.

## Potential integration points (when SERP-Discovery exists)
- **Shared `GeoConfig.topic_entities`:** SERP-Discovery writes the target entities;
  TalkingToad consumes them (already the GA3/GA4 input).
- **Citation loop:** SERP-Discovery could be (or feed) the "sibling phrase tool" that posts
  to TalkingToad's M5 endpoint `POST /api/jobs/{job_id}/ai-citations` — already built.
- **M6 "Hidden Gem" signal:** TalkingToad's refresh-trigger (`refresh_trigger.py`) emits
  "structurally healthy but not ranking → re-check intent," consumed by SERP-Discovery.

## Why parked
TalkingToad v3.0 is mid-flight and is deliberately scoped to Authority Engineering.
SERP-Discovery is a distinct product with its own data sources (search APIs) and its own
repo. Build it when TalkingToad's loop (audit → GSC validation) is proven and there's a
need to drive *what to build* rather than *fix what exists*.

*Parked 2026-06-01 per user instruction — "create something for serp-discovery (a separate
repo) and park that."*

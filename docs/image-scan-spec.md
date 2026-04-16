# Image Intelligence & Optimization Specification v2.0

## Purpose
Define a comprehensive, production-grade specification for a **dual-purpose Python engine** that:
1. **Audits** images for Technical SEO, Accessibility, and Semantic (GEO) alignment
2. **Executes** automated fixes (compression, resizing, conversion)

---

## 1. SYSTEM OVERVIEW

### 1.1 Pipeline Architecture
```
Crawler → Parser → Image Extractor → Image Analyzer → Scoring Engine → Issue Engine → Output
```

### 1.2 Core Principles
- Treat images as **semantic + performance + accessibility** objects
- Avoid binary checks where possible; prefer **scoring + classification**
- Separate data collection from analysis logic

---

## 2. DATA MODEL

### 2.1 Image Object Schema
```json
{
  "url": "string",
  "page_url": "string",
  "alt": "string|null",
  "title": "string|null",
  "filename": "string",
  "format": "jpeg|png|webp|avif|svg|gif|unknown",
  "width": "int|null",
  "height": "int|null",
  "rendered_width": "int|null",
  "rendered_height": "int|null",
  "file_size_bytes": "int|null",
  "content_length_header": "int|null",
  "load_time_ms": "int|null",
  "http_status": "int",
  "is_lazy_loaded": "boolean",
  "has_srcset": "boolean",
  "srcset_candidates": ["string"],
  "is_decorative": "boolean",
  "in_viewport": "boolean",
  "is_lcp_candidate": "boolean",
  "surrounding_text": "string",
  "page_topic_embedding": "vector|null",
  "alt_embedding": "vector|null",
  "image_embedding": "vector|null"
}
```

---

## 3. PARSER REQUIREMENTS

### 3.1 Extract
- `<img src>`
- `srcset`
- `sizes`
- `alt`, `title`
- CSS background images (optional v2)

### 3.2 Normalize URLs
- Resolve relative paths
- Remove query noise where appropriate

### 3.3 Decorative Detection Heuristics
Set `is_decorative = true` if:
- `alt == ""`
- `role="presentation"`
- `aria-hidden="true"`
- `width/height < 32px` AND repeated usage

---

## 4. IMAGE FETCHER

### 4.1 Requirements
- Fetch **actual image bytes** (HEAD not sufficient)
- Capture:
  - final byte size
  - response headers
  - load time

### 4.2 Constraints
- Timeout: configurable (default 5s)
- Max size: configurable (default 5MB)

---

## 5. ANALYSIS MODULES

### 5.1 ALT TEXT ANALYSIS (Accessibility)

| Issue Code | Condition | Severity |
|------------|-----------|----------|
| `IMG_ALT_MISSING` | alt is null OR empty string (non-decorative only) | critical |
| `IMG_ALT_QUALITY` | length < 5 (too short) OR > 125 (stuffing) OR generic terms ("pic", "image", "photo") | warning |
| `IMG_ALT_DUP_FILENAME` | alt equals filename (normalized) | warning |
| `IMG_ALT_MISUSED` | decorative images with meaningful content OR non-decorative with empty alt | warning |

### 5.2 SIZE & PERFORMANCE

| Issue Code | Condition |
|------------|-----------|
| `IMG_OVERSIZED` | file_size_bytes > threshold (default 200KB) |
| `IMG_SLOW_LOAD` | load_time_ms > threshold (default 1000ms) |
| `IMG_OVERSCALED` | intrinsic_width / rendered_width > 2 |
| `IMG_POOR_COMPRESSION` | BPP = file_size_bytes / (width * height) > 0.5 |

### 5.3 FORMAT ANALYSIS

| Issue Code | Condition |
|------------|-----------|
| `IMG_FORMAT_LEGACY` | format in [jpeg, png, gif] AND file_size_bytes > threshold |

### 5.4 RESPONSIVE IMAGES

| Issue Code | Condition |
|------------|-----------|
| `IMG_NO_SRCSET` | has_srcset == false AND rendered_width < intrinsic_width |

### 5.5 BROKEN IMAGES

| Issue Code | Condition |
|------------|-----------|
| `IMG_BROKEN` | http_status >= 400 |

### 5.6 INDEXABILITY

| Issue Code | Condition |
|------------|-----------|
| `IMG_NOT_INDEXABLE` | blocked by robots.txt OR x-robots-tag: noindex |

### 5.7 LCP ANALYSIS

| Issue Code | Condition |
|------------|-----------|
| `IMG_LCP_TOO_LARGE` | is_lcp_candidate == true AND file_size_bytes > threshold |
| `IMG_LCP_NOT_PRELOADED` | LCP image lacks preload or priority hints |

### 5.8 DUPLICATE DETECTION

| Issue Code | Condition |
|------------|-----------|
| `IMG_DUPLICATE_CONTENT` | identical hash across multiple URLs |

### 5.9 SEMANTIC (GEO) - Phase 4

| Issue Code | Condition |
|------------|-----------|
| `IMG_ALT_CONTEXT_MISMATCH` | cosine_similarity(alt_embedding, page_topic_embedding) < threshold |
| `IMG_SEMANTIC_DRIFT` | cosine_similarity(image_embedding, page_topic_embedding) < threshold |
| `IMG_ALT_NO_ENTITIES` | no named entities detected in alt text |

---

## 6. EXECUTION MODULE (ImageOptimizer)

### 6.1 Trigger Conditions
The `ImageOptimizer` class is triggered when an image is flagged for ANY of:
- `IMG_OVERSIZED`
- `IMG_OVERSCALED`
- `IMG_POOR_COMPRESSION`
- `IMG_FORMAT_LEGACY`

### 6.2 Optimization Pipeline

```
1. BACKUP & SUFFIX
   └── Save original to /backup/{job_id}/
   └── New filename: {original}-small.webp

2. SMART RESIZE
   └── Target width = MIN(rendered_width, 1200px)
   └── NO-UPSCALE RULE: Never resize image "up"
   └── Maintain aspect ratio

3. NEXT-GEN CONVERSION
   └── Convert to WebP
   └── Quality: 80
   └── Method: 6 (best compression)

4. NEGATIVE COMPRESSION CHECK
   └── If optimized > original: DISCARD optimized, keep original
   └── Log warning

5. VERIFICATION
   └── Re-run IMG_POOR_COMPRESSION check on result
   └── Confirm BPP < 0.5

6. CLEAN-AND-REPLACE
   └── Verify {name}-small.webp exists
   └── Delete heavy original from server

7. DUAL SAVE
   └── Copy 1: Server Production Path (WordPress uploads)
   └── Copy 2: Local Archive Path (backup)
```

### 6.3 Safety Rules

| Rule | Description |
|------|-------------|
| **No-Upscale** | Never resize an image larger than its intrinsic dimensions |
| **Negative Compression** | If WebP is larger than original, discard and keep original |
| **Post-Verification** | After optimization, re-check compression metrics |
| **Backup First** | Always backup before any destructive operation |
| **Atomic Operations** | Verify new file exists before deleting old |

### 6.4 Output Schema
```json
{
  "original_url": "string",
  "optimized_url": "string",
  "original_size_kb": 450,
  "optimized_size_kb": 120,
  "savings_percent": 73,
  "original_dimensions": "2000x1500",
  "new_dimensions": "1200x900",
  "format_change": "png → webp",
  "backup_path": "/backup/job123/image.png",
  "status": "success|skipped|failed",
  "skip_reason": "negative_compression|no_upscale|already_optimal"
}
```

---

## 7. SCORING ENGINE

### 7.1 Image SEO Score (0–100)
```
score =
  0.30 * accessibility_score +   # Alt presence and semantic quality
  0.30 * performance_score +     # Size, BPP, Load Time
  0.20 * semantic_score +        # Alignment with page entities/topic
  0.20 * technical_score         # Format (WebP), Responsive (srcset)
```

### 7.2 Subscores

| Category | Weight | Components |
|----------|--------|------------|
| **Accessibility** | 30% | Alt presence, alt quality, decorative detection |
| **Performance** | 30% | File size, BPP, load time, overscaling |
| **Semantic** | 20% | Entity presence, alt-page alignment (GEO) |
| **Technical** | 20% | Format (WebP/AVIF), srcset, indexability |

### 7.3 Deductions

| Issue | Score Deduction |
|-------|-----------------|
| `IMG_ALT_MISSING` | -50 accessibility |
| `IMG_ALT_QUALITY` | -25 accessibility |
| `IMG_ALT_MISUSED` | -20 accessibility |
| `IMG_OVERSIZED` | -30 performance |
| `IMG_OVERSCALED` | -20 performance |
| `IMG_POOR_COMPRESSION` | -20 performance |
| `IMG_SLOW_LOAD` | -25 performance |
| `IMG_FORMAT_LEGACY` | -15 technical |
| `IMG_NO_SRCSET` | -15 technical |
| `IMG_BROKEN` | -50 technical |
| `IMG_SEMANTIC_DRIFT` | -30 semantic |
| `IMG_ALT_NO_ENTITIES` | -20 semantic |

---

## 7. ISSUE OUTPUT FORMAT
```json
{
  "issue_code": "IMG_OVERSIZED",
  "severity": "high|medium|low",
  "image_url": "string",
  "page_url": "string",
  "details": {
    "file_size": 345678,
    "threshold": 200000
  },
  "recommendation": "Compress image or use WebP/AVIF"
}
```

---

## 8. CONFIGURATION
```json
{
  "max_image_size_kb": 200,
  "slow_load_threshold_ms": 1000,
  "bpp_threshold": 0.5,
  "alt_min_length": 5,
  "alt_max_length": 125,
  "similarity_threshold": 0.6,
  "overscale_ratio": 2.0,
  "legacy_format_threshold_kb": 50
}
```

---

## 9. IMPLEMENTATION PHASES

### Phase 1 (Core) - HIGH PRIORITY
- [ ] Actual file size measurement (replace Content-Length)
- [ ] ALT validation improvements (quality checks)
- [ ] srcset detection
- [ ] overscaled detection
- [ ] Image data model (ImageInfo class)

### Phase 2 (Performance)
- [ ] Compression scoring (BPP)
- [ ] Format detection (legacy vs next-gen)
- [ ] Load time tracking

### Phase 3 (Advanced SEO)
- [ ] LCP detection
- [ ] Indexability checks
- [ ] Duplicate hashing

### Phase 4 (GEO / AI)
- [ ] Embeddings infrastructure
- [ ] Semantic similarity
- [ ] Entity extraction

---

## 10. TECHNICAL CONSTRAINTS

### 10.1 Current Limitations
- No browser rendering (Playwright/Puppeteer) - cannot detect:
  - Actual rendered dimensions
  - LCP candidates
  - Lazy loading failures
- Semantic scoring depends on AI API availability

### 10.2 Performance Considerations
- Parallel image fetching required
- Cache image hashes + metadata
- Avoid re-fetching identical URLs
- Cap total images per job

---

## 11. EXISTING IMPLEMENTATION GAP ANALYSIS

### Currently Implemented
- `IMG_BROKEN` - HTTP status >= 400
- `IMG_OVERSIZED` - Content-Length check (unreliable)
- `IMG_ALT_MISSING` - Missing or empty alt

### Missing (Phase 1 Priority)
- Actual byte size measurement
- Alt quality checks (short, long, generic, filename)
- srcset detection
- Decorative image detection
- Overscaled detection

### Missing (Phase 2+)
- Format analysis
- Compression scoring
- Load time tracking
- LCP analysis
- Duplicate detection
- Semantic analysis

---

## 12. OPEN QUESTIONS

1. **Rendered dimensions**: Without a browser, how do we detect rendered size?
   - Option A: Parse `width`/`height` attributes + CSS
   - Option B: Skip overscaled detection without browser

2. **LCP detection**: Requires browser rendering - defer to Phase 3?

3. **Image fetching cost**: Full GET for every image vs sampling?

4. **Embedding models**: Use existing Gemini/OpenAI or add dedicated image model?

5. **Scoring engine**: Implement now or defer to later phase?

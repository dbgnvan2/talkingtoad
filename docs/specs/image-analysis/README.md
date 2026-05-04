# Image Analysis & Optimization Specifications

Image Intelligence Engine, GEO-optimized metadata generation, and image optimization workflows.

## Specifications

| Version | Status | File | Description |
|---------|--------|------|-------------|
| v1.9 | Implemented | [v1.9-image-intelligence-engine.md](v1.9-image-intelligence-engine.md) | 3-level image data architecture (scan, fetch, AI analysis). 14 image issue codes. Accessibility and performance scoring |
| v1.9.1 | Implemented | [v1.9.1-geo-optimization-spec.md](v1.9.1-geo-optimization-spec.md) | GEO-optimized metadata generation. Entity-rich alt text and long descriptions for AI Overviews. Triple-context input model |
| v1.9.1 | Implemented | [v1.9.1-geo-optimization-prompt.md](v1.9.1-geo-optimization-prompt.md) | Master prompt for GEO analysis (Gemini/OpenAI). 80–125 char alt text, 150–300 word descriptions, entity density requirements |

## Key Features

- **Level 1: Scan Details** — Instant HTML attribute extraction, decorative detection
- **Level 2: Fetch** — WordPress Media Library integration, image file analysis
- **Level 3: AI Analysis** — Vision model analysis, alt text generation, quality scoring
- **GEO Optimization** — Entity-rich metadata for AI Overviews and social sharing
- **Image Optimization** — WebP conversion, EXIF GPS injection, SEO filename generation, batch processing

## Implementation Status

✅ Level 1 & 2 image scanning (v1.9)  
✅ GEO-optimized metadata (v1.9.1)  
✅ Image optimization workflows (v1.9.1)  
⏳ Image optimization UI refinements (ongoing)

## Related Documentation

- Architecture: `../../architecture/architecture.md`
- Issue Codes (image): `../../reference/issue-codes.md#image-codes`
- API: `../../api/api.md`

## Configuration

Image analysis settings are configured per-job:

```python
{
  "enable_image_analysis": True,
  "image_fetch_timeout_ms": 5000,
  "image_ai_model": "gemini-1.5-flash",  # or openai
  "geo_config": {
    "org_name": "Living Systems Counselling",
    "primary_location": "Vancouver",
    "topic_entities": ["Bowen Theory", "Systems Thinking"]
  }
}
```

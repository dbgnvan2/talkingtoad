# Specification: GEO-Advanced Image Metadata Generator

## 1. Objective
To generate semantically aligned, entity-rich Alt Text and Long Descriptions that satisfy both Accessibility (WCAG 2.2) and GEO (Generative Engine Optimization) standards.

## 2. Input Architecture (The "Triple-Context" Packet)
The AI Agent must receive three distinct data points for every request:
1. **The Image Bytes:** High-resolution version for multimodal analysis.
2. **Page Context:** The 300 characters of text *preceding* and *following* the image, plus the H1 of the page.
3. **Global Settings:** The organization's `ORG_NAME`, `PRIMARY_LOCATION`, and `TOPIC_ENTITIES`.

## 3. Output Requirements
The tool must return a JSON object with two fields:
* `alt_text`: Strictly 80–125 characters. No fluff ("image of"). Must contain 1 local entity and 1 topic entity.
* `long_description`: 150–300 words. Structured for AI training data (Capturing purpose, mood, and detailed location context).

## 4. Logic Constraints
* **Entity Mapping:** If the page context mentions "Differentiation," the Alt text must prioritize that term over a generic "Counselling" term.
* **Geo-Distribution:** Access the `LOCATION_POOL` (from settings). If the Primary Location is used in the H1, use a Secondary or "Service Area" location in the Alt text to build a broader GEO-authority map.
* **LCP Prioritization:** If the image is flagged as the Largest Contentful Paint (LCP), the description must lead with a factual summary suitable for a Google "AI Overview" snippet.

## 5. Configuration Settings
```json
{
  "org_identity": {
    "name": "Living Systems Counselling",
    "topic_entities": ["Bowen Theory", "Systems Thinking", "Relationship Health"]
  },
  "geo_matrix": {
    "primary": "Vancouver",
    "pool": ["North Vancouver", "Lower Mainland", "British Columbia", "Burnaby"]
  },
  "api_preferences": {
    "model": "gemini-1.5-pro",
    "temperature": 0.4,
    "max_tokens": 500
  }
}
```

# GEO Image AI Frontend Integration Guide

## Overview

The GEO (Generative Engine Optimization) Image AI frontend is now fully integrated! Users can generate AI-powered, entity-rich metadata for images with page context, review and edit the suggestions in a modal, and apply them to the database.

## Components Added

### 1. GeoAnalysisModal.jsx
**Purpose**: Display AI-generated metadata in an editable modal

**Features**:
- Shows AI analysis context (subject, theme, geographic anchor, entities used)
- Editable alt text field with character count validation (80-125 chars)
- Editable long description field with word count validation (150-300 words)
- Real-time validation feedback (too short/too long/good)
- Comparison with current alt text
- Image preview
- Save/Cancel buttons

**Location**: `frontend/src/components/GeoAnalysisModal.jsx`

### 2. GeoSettingsModal.jsx
**Purpose**: Configure GEO settings per domain

**Features**:
- Organization name (required)
- Primary location (required)
- Topic entities (at least 1 required, dynamic list with add/remove)
- Location pool (at least 1 required, dynamic list with add/remove)
- Validation before saving
- Help text explaining how GEO works

**Location**: `frontend/src/components/GeoSettingsModal.jsx`

### 3. Updated ImageAnalysisPanel.jsx
**Changes**:
- Replaced "AI Analyze" with "🤖 GEO AI" button
- Added GEO configuration check before analysis
- Prompts user to configure GEO if not set up
- Shows GeoAnalysisModal with results
- Applies edited metadata to database
- Updates scores after saving

**Location**: `frontend/src/components/ImageAnalysisPanel.jsx`

### 4. Updated api.js
**New function**:
- `saveGeoSettings(config)` - POST to `/api/geo/settings`

**Existing functions used**:
- `getGeoSettings(domain)` - GET from `/api/geo/settings`
- `analyzeImageWithGeo(jobId, imageUrl)` - POST to `/api/ai/image/analyze-geo`
- `applyGeoMetadata(jobId, imageUrl, altText, longDescription)` - POST to `/api/ai/image/apply-geo-metadata`

**Location**: `frontend/src/api.js`

## User Flow

### First Time: Configure GEO

1. **Start a crawl** of a WordPress site (e.g., livingsystems.ca)
2. **Go to Images tab** and click on an image
3. **Click "🤖 GEO AI" button**
4. **Prompted**: "GEO is not configured for [domain]. Would you like to configure it now?"
5. **Click "OK"** to open GEO Settings Modal
6. **Fill in configuration**:
   - Organization Name: "Living Systems Counselling"
   - Primary Location: "Vancouver"
   - Topic Entities: "Bowen Theory", "Systems Thinking", "Family Systems"
   - Location Pool: "Burnaby", "Richmond", "North Vancouver", "Surrey"
7. **Click "Save Configuration"**
8. **GEO is now configured** for this domain

### Using GEO Analysis

1. **Click "🤖 GEO AI" button** on any image
2. **Backend analyzes**:
   - Loads image file
   - Reads page H1 and surrounding text from crawl data
   - Applies GEO prompt with org identity + location pool + topic entities
   - Generates alt text (80-125 chars with entities)
   - Generates long description (150-300 words, GEO-rich)
3. **Modal opens** showing:
   - AI analysis context (subject, theme, geographic anchor)
   - Entities used
   - Editable alt text with validation
   - Editable long description with validation
   - Current alt text for comparison
4. **User reviews and edits** the suggestions
5. **Click "Apply to Database"**
6. **Metadata is saved** to image record
7. **Scores are recalculated** and updated in the UI
8. **Modal closes** and scores refresh

### Page Context Integration

The backend automatically includes page context in the analysis:
- **H1 heading** from the page where the image appears
- **Surrounding text** (±200 chars around the image) captured during scan
- **Global GEO settings** (org name, locations, topics)

This "triple-context packet" ensures the AI generates semantically aligned metadata that connects the image to the page content and geographic/topic entities.

## Backend Endpoints Used

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/geo/settings?domain={domain}` | Retrieve GEO config for domain |
| POST | `/api/geo/settings` | Save GEO config for domain |
| POST | `/api/ai/image/analyze-geo` | Analyze image with GEO context |
| POST | `/api/ai/image/apply-geo-metadata` | Apply edited metadata to DB |

## Testing Checklist

- [ ] Configure GEO settings for a domain
- [ ] Run GEO analysis on an image
- [ ] Verify modal shows all AI context fields
- [ ] Edit alt text and description
- [ ] Verify character/word count validation
- [ ] Save metadata to database
- [ ] Verify scores update correctly
- [ ] Try analyzing without configuration (should prompt)
- [ ] Verify page context is being used (check if alt text relates to page H1)

## Example GEO Output

**Input**:
- Image: Two people in a clinical setting
- Page H1: "Understanding Family Cutoff in Bowen Theory"
- Org: Living Systems Counselling
- Location Pool: Vancouver, Burnaby, Richmond
- Topics: Bowen Theory, Systems Thinking

**AI Generated**:
- **Alt Text**: "Clinical session addressing family cutoff dynamics at Living Systems Counselling in Burnaby" (95 chars)
- **Long Description**: "This image depicts a clinical counselling session focused on family systems theory. At Living Systems Counselling in Burnaby, therapists help clients understand emotional cutoff patterns using Bowen Theory principles..." (150-300 words with entity density)

## Notes

- **GEO config is domain-specific**: Each domain needs its own configuration
- **Page context is automatic**: The backend pulls H1 and surrounding text from scan data
- **Validation is enforced**: Alt text must be 80-125 chars, description must be 150-300 words
- **Scores update after apply**: The system re-analyzes the image with new metadata and updates all scores
- **Modal allows editing**: Users can improve AI suggestions before applying

## Next Steps

To enable **WordPress updating**, integrate the GEO metadata with the WP REST API update flow:
1. Add "Apply to WordPress" button in GeoAnalysisModal
2. Call `updateImageMeta` with alt text and description
3. Use two-step WP API upload for new images (future feature)

## Architecture

This implementation follows the **3-level image intelligence architecture**:

1. **Level 1 (Scan)**: HTML + HEAD requests → basic metadata
2. **Level 2 (Fetch)**: WordPress API + image file → full metadata
3. **Level 3 (GEO AI)**: Vision model + page context → optimized metadata

The GEO AI frontend integration operates at Level 3, using data from Levels 1 and 2 to generate semantically rich, entity-dense metadata optimized for AI search engines.

# TalkingToad — Project TODO & Technical Debt

This file tracks infrastructure improvements, testing gaps, and future features that aren't part of the current milestone but are critical for long-term stability.

## ⚠️ CRITICAL CONSTRAINTS

**DO NOT IMPLEMENT URL CHANGES VIA WP API:**
- The WordPress REST API is NOT reliable for operations that change URLs (slugs, permalinks, redirects)
- Modifying URLs can corrupt the WP database and break internal link structures
- Any URL-related fixes must be manual or use WP admin interface directly

**DO NOT AUTOMATE IMAGE LINK UPDATES IN POSTS/PAGES:**
- When images are renamed/optimized/replaced, the user MUST manually update links in posts/pages
- The WP backend database structure for post content and media references is too complex and risky to automate
- DO NOT attempt to "be helpful" by automatically updating post content with new image URLs

## 🔴 High Priority: GEO & Image Intelligence

- [ ] **Orphaned Content Detection:**
    - [ ] Add ability to list suspected orphaned pages (pages with no internal links pointing to them)
    - [ ] Add ability to list suspected orphaned images (images not used on any crawled page)
- [ ] **Image Download & Optimization Module:**
    - [ ] Build module to download image from site
    - [ ] Apply SEO/GEO fixes (resize, compress, rename)
    - [ ] Generate GEO-optimized alt text and description
    - [ ] Add geo-tagging metadata (EXIF GPS data)
    - [ ] **Two-Step WP API Upload:**
        - [ ] Step 1: POST binary to `/wp-json/wp/v2/media` with `Content-Disposition` header → get Media ID
        - [ ] Step 2: POST metadata to `/wp-json/wp/v2/media/{id}` with alt_text, caption, description, title
    - [ ] **Pre-upload Validation:**
        - [ ] Ensure file size under server limit (check PHP max upload, target <2MB for safety)
        - [ ] Verify EXIF GPS data is present before upload
        - [ ] Standardize naming: strip "Screenshot", use `{keyword}-{city}.jpg` pattern
    - [ ] **Security:** Use WordPress Application Passwords (not main login)
    - [ ] **User Workflow:** Download → Optimize → Preview metadata → Upload via API → Success confirmation
    - [ ] **Goal:** 100% consistent, zero-manual-entry media library uploads with AI-generated SEO/GEO metadata

## 🔴 High Priority: Stability & QA
- [ ] **Frontend Component Testing:** Set up Vitest and React Testing Library.
    - [ ] Add "smoke tests" for `Results.jsx` to ensure it handles null/loading states without crashing.
    - [ ] Test the `ExportReportModal` and `LLMSTxtGenerator` components.
- [ ] **API Error Boundaries:** Implement a React Error Boundary around the main `Results` view to catch and report crashes rather than showing a white screen.
- [ ] **End-to-End (E2E) Testing:** Set up Playwright to test the full "Start Crawl -> View Results -> Export PDF" happy path.

## 🟡 Medium Priority: UX & Polish
- [ ] **Persistent Settings:** Save the user's preferred PDF export options (Help Text ON/OFF) in localStorage.
- [ ] **Real-time Log Streaming:** Instead of just a progress bar, show a "Live Console" during the crawl for power users.

## 🟢 Low Priority: Tech Debt
- [ ] **Type Safety:** Migrate `Results.jsx` and other large components to TypeScript.
- [ ] **CSS Refactoring:** Clean up duplicate Tailwind classes in `Results.jsx` into shared base components.

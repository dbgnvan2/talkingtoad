# Image Analysis: Scan vs Fetch

## What the SCAN detects (Automatic during crawl)

### Data Sources
- **HTML parsing:** Alt text, title from `<img>` tags
- **HTTP HEAD requests:** File size, content-type (fast, just headers)

### Issues Detected

**✅ Can detect during scan:**
- `IMG_ALT_MISSING` - Image has no alt text
- `IMG_ALT_TOO_SHORT` - Alt text < 5 characters
- `IMG_ALT_TOO_LONG` - Alt text > 125 characters
- `IMG_ALT_GENERIC` - Alt text uses generic terms ("image", "photo", "picture")
- `IMG_ALT_DUP_FILENAME` - Alt text duplicates the filename
- `IMG_OVERSIZED` - File size > 200KB (from HEAD request)
- `IMG_FORMAT_LEGACY` - JPEG/PNG/GIF > 50KB (should use WebP/AVIF)

**❌ Cannot detect during scan:**
- `IMG_SLOW_LOAD` - Requires actual image download to measure load time
- `IMG_OVERSCALED` - Requires intrinsic dimensions (not in HTML)
- `IMG_POOR_COMPRESSION` - Requires intrinsic dimensions to calculate bytes/pixel
- `IMG_NO_SRCSET` - Can detect presence but not quality without intrinsic dimensions
- `IMG_DUPLICATE_CONTENT` - Requires content hashing of actual image file
- `IMG_BROKEN` - Scan doesn't download images, only gets file size via HEAD

### Scores During Scan
- **Accessibility:** Accurate (based on alt text from HTML)
- **Performance:** Partial (can flag oversized files, but not compression quality)
- **Technical:** Partial (srcset detection incomplete without dimensions)
- **Semantic:** Limited (no intrinsic dimensions to compare with rendered size)
- **Overall:** Conservative estimate based on available data

### Why Limited?
- **Speed:** Crawling hundreds of pages with hundreds of images must be fast
- **Compatibility:** Works on ANY website (not just WordPress)
- **No API calls:** WordPress API would slow crawl 10x+

---

## What FETCH adds (Manual button)

### Data Sources
- **WordPress REST API:** Caption, description, WP alt text, WP title
- **Image file download:** Intrinsic dimensions, exact file size, load time
- **Content hashing:** MD5 hash for duplicate detection

### Additional Issues Detected

**✅ Can now detect:**
- `IMG_SLOW_LOAD` - Load time > 1000ms
- `IMG_OVERSCALED` - Intrinsic size > 2x rendered size
- `IMG_POOR_COMPRESSION` - Bytes per pixel > 0.5
- `IMG_NO_SRCSET` - Missing srcset when scaled down significantly
- `IMG_DUPLICATE_CONTENT` - Same content hash as another image
- `IMG_BROKEN` - HTTP 4xx/5xx status

### Additional Data Available
- **WordPress fields:**
  - Caption (WP media caption field)
  - Description (WP media description field)
  - WP Alt Text (may differ from HTML alt if manually edited in WP)
  - WP Title (media title in WordPress)
- **Image file data:**
  - Intrinsic width and height (actual image dimensions)
  - Exact file size (byte-accurate, not estimated from headers)
  - Load time in milliseconds
  - Content hash for duplicate detection
  - HTTP status code

### Scores After Fetch
- **Accessibility:** Same as scan (based on alt text)
- **Performance:** Complete and accurate (has load time, compression ratio)
- **Technical:** Complete (can detect broken images, duplicates)
- **Semantic:** Accurate (can compare intrinsic vs rendered dimensions)
- **Overall:** Accurate final score

### When to Use Fetch
1. **After initial scan:** Get complete data for problematic images
2. **After fixing in WordPress:** Verify your changes were saved correctly
3. **Before exporting reports:** Ensure report has complete, accurate data
4. **Batch processing:** Select multiple images, click "Fetch All" for efficiency

---

## Summary Table

| Issue Code | Scan | Fetch | Requires |
|------------|------|-------|----------|
| IMG_ALT_MISSING | ✅ | ✅ | HTML alt attribute |
| IMG_ALT_TOO_SHORT | ✅ | ✅ | HTML alt attribute |
| IMG_ALT_TOO_LONG | ✅ | ✅ | HTML alt attribute |
| IMG_ALT_GENERIC | ✅ | ✅ | HTML alt attribute |
| IMG_ALT_DUP_FILENAME | ✅ | ✅ | HTML alt attribute |
| IMG_OVERSIZED | ✅ | ✅ | File size (HEAD request) |
| IMG_FORMAT_LEGACY | ✅ | ✅ | Content-type (HEAD request) |
| IMG_SLOW_LOAD | ❌ | ✅ | Image download + timing |
| IMG_OVERSCALED | ❌ | ✅ | Intrinsic dimensions |
| IMG_POOR_COMPRESSION | ❌ | ✅ | Intrinsic dimensions + file size |
| IMG_NO_SRCSET | Partial | ✅ | Intrinsic dimensions |
| IMG_DUPLICATE_CONTENT | ❌ | ✅ | Content hash |
| IMG_BROKEN | ❌ | ✅ | Image download + HTTP status |

---

## WordPress-Specific Notes

### Scan (HTML only)
- Gets alt text as rendered in HTML (may differ from WP Media Library if theme modifies it)
- No access to WordPress-specific fields (caption, description)
- Works on non-WordPress sites too

### Fetch (WordPress API + Image file)
- Gets canonical data from WordPress Media Library
- Includes caption and description fields
- Can verify if WP alt text matches HTML alt text
- **Requires WordPress site** - won't work on static HTML sites

### After Updating WordPress
Use Fetch to verify your changes:
1. Update alt text in WordPress (via WP admin or Fix Manager)
2. Click "Fetch" button on the image
3. Scores re-calculate with new data
4. Verify the alt text was saved correctly

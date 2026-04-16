/**
 * API client — all calls to the TalkingToad backend.
 * Uses relative /api/* paths; Vite proxies to localhost:8000 in dev,
 * and Vercel routes them to the Python serverless functions in prod.
 */

const TOKEN = import.meta.env.VITE_AUTH_TOKEN || ''

export function authHeaders(extra = {}) {
  const h = { 'Content-Type': 'application/json', ...extra }
  if (TOKEN) h['Authorization'] = `Bearer ${TOKEN}`
  return h
}

async function checkResponse(res) {
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const data = await res.json()
      msg = data.error?.message || msg
    } catch (_) {}
    throw new Error(msg)
  }
  return res.json()
}

export async function startCrawl(targetUrl, settings = {}) {
  const body = { target_url: targetUrl }
  if (Object.keys(settings).length) body.settings = settings
  const res = await fetch('/api/crawl/start', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body),
  })
  return checkResponse(res)
}

export async function getStatus(jobId) {
  const res = await fetch(`/api/crawl/${jobId}/status`, {
    headers: authHeaders(),
  })
  return checkResponse(res)
}

export async function cancelCrawl(jobId) {
  const res = await fetch(`/api/crawl/${jobId}/cancel`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return checkResponse(res)
}

export async function getResults(jobId, { page = 1, limit = 50, severity } = {}) {
  const params = new URLSearchParams({ page, limit })
  if (severity) params.set('severity', severity)
  const res = await fetch(`/api/crawl/${jobId}/results?${params}`, {
    headers: authHeaders(),
  })
  return checkResponse(res)
}

export async function getResultsByCategory(jobId, category, { page = 1, limit = 50, severity } = {}) {
  const params = new URLSearchParams({ page, limit })
  if (severity) params.set('severity', severity)
  const res = await fetch(`/api/crawl/${jobId}/results/${category}?${params}`, {
    headers: authHeaders(),
  })
  return checkResponse(res)
}

export async function getPages(jobId, { page = 1, limit = 50, minSeverity } = {}) {
  const params = new URLSearchParams({ page, limit })
  if (minSeverity) params.set('min_severity', minSeverity)
  const res = await fetch(`/api/crawl/${jobId}/pages?${params}`, {
    headers: authHeaders(),
  })
  return checkResponse(res)
}

export async function getPageIssues(jobId, url) {
  const params = new URLSearchParams({ url })
  const res = await fetch(`/api/crawl/${jobId}/pages/issues?${params}`, {
    headers: authHeaders(),
  })
  return checkResponse(res)
}

export async function scanPage(url) {
  const params = new URLSearchParams({ url })
  const res = await fetch(`/api/crawl/scan-page?${params}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return checkResponse(res)
}

export async function rescanUrl(jobId, url) {
  const params = new URLSearchParams({ url })
  const res = await fetch(`/api/crawl/${jobId}/rescan-url?${params}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return checkResponse(res)
}

export async function markFixed(jobId, pageUrl, codes) {
  const params = new URLSearchParams({ url: pageUrl, codes: codes.join(',') })
  const res = await fetch(`/api/crawl/${jobId}/mark-fixed?${params}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return checkResponse(res)
}

export async function getFixHistory(jobId) {
  const res = await fetch(`/api/crawl/${jobId}/fix-history`, {
    headers: authHeaders(),
  })
  return checkResponse(res)
}

export async function getRecentJobs(limit = 10) {
  const res = await fetch(`/api/crawl/recent?limit=${limit}`, {
    headers: authHeaders(),
  })
  return checkResponse(res)
}

export async function getPredefinedCodes() {
  const res = await fetch('/api/fixes/predefined-codes', { headers: authHeaders() })
  return checkResponse(res)
}

export async function bulkTrimTitles(jobId) {
  const params = new URLSearchParams({ job_id: jobId })
  const res = await fetch(`/api/fixes/bulk-trim-titles?${params}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return checkResponse(res)
}

export async function trimTitleOne(pageUrl) {
  const params = new URLSearchParams({ page_url: pageUrl })
  const res = await fetch(`/api/fixes/trim-title-one?${params}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return checkResponse(res)
}

export async function convertHeadingToBold(pageUrl, headingText = null, level = 4) {
  const params = new URLSearchParams({ page_url: pageUrl, level })
  if (headingText) params.set('heading_text', headingText)
  const res = await fetch(`/api/fixes/heading-to-bold?${params}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return checkResponse(res)
}

export async function findHeading(jobId, headingText, level = null) {
  const params = new URLSearchParams({ job_id: jobId, heading_text: headingText })
  if (level != null) params.set('level', level)
  const res = await fetch(`/api/fixes/find-heading?${params}`, { headers: authHeaders() })
  return checkResponse(res)
}

export async function analyzeHeadingSources(pageUrl, jobId = null) {
  const params = new URLSearchParams({ page_url: pageUrl })
  if (jobId) params.set('job_id', jobId)
  const res = await fetch(`/api/fixes/analyze-heading-sources?${params}`, { headers: authHeaders() })
  return checkResponse(res)
}

export async function bulkReplaceHeading(jobId, headingText, fromLevel, toLevel = null) {
  const params = new URLSearchParams({ job_id: jobId, heading_text: headingText, from_level: fromLevel })
  if (toLevel != null) params.set('to_level', toLevel)
  const res = await fetch(`/api/fixes/bulk-replace-heading?${params}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return checkResponse(res)
}

export async function changeHeadingLevel(pageUrl, headingText, fromLevel, toLevel) {
  const params = new URLSearchParams({
    page_url: pageUrl,
    heading_text: headingText,
    from_level: fromLevel,
    to_level: toLevel,
  })
  const res = await fetch(`/api/fixes/change-heading-level?${params}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return checkResponse(res)
}

export async function getVerifiedLinks() {
  const res = await fetch('/api/verified-links', { headers: authHeaders() })
  return checkResponse(res)
}

export async function addVerifiedLink(url, jobId = null) {
  const body = { url }
  if (jobId) body.job_id = jobId
  const res = await fetch('/api/verified-links', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body),
  })
  return checkResponse(res)
}

export async function removeVerifiedLink(url) {
  const params = new URLSearchParams({ url })
  const res = await fetch(`/api/verified-links?${params}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  return checkResponse(res)
}

export async function getSuppressedCodes() {
  const res = await fetch('/api/suppressed-codes', { headers: authHeaders() })
  return checkResponse(res)
}

export async function addSuppressedCode(code) {
  const res = await fetch('/api/suppressed-codes', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ code }),
  })
  return checkResponse(res)
}

export async function removeSuppressedCode(code) {
  const params = new URLSearchParams({ code })
  const res = await fetch(`/api/suppressed-codes?${params}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  return checkResponse(res)
}

export async function getExemptAnchorUrls() {
  const res = await fetch('/api/exempt-anchor-urls', { headers: authHeaders() })
  return checkResponse(res)
}

export async function addExemptAnchorUrl(url, note = '') {
  const res = await fetch('/api/exempt-anchor-urls', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ url, note }),
  })
  return checkResponse(res)
}

export async function getImageInfo(imageUrl) {
  const params = new URLSearchParams({ image_url: imageUrl })
  const res = await fetch(`/api/fixes/image-info?${params}`, { headers: authHeaders() })
  return checkResponse(res)
}

export async function updateImageMeta(imageUrl, { altText, title, caption, jobId, wpCredentials } = {}) {
  const params = new URLSearchParams({ image_url: imageUrl })
  if (jobId    !== undefined && jobId    !== null) params.set('job_id',   jobId)
  if (altText  !== undefined && altText  !== null) params.set('alt_text', altText)
  if (title    !== undefined && title    !== null) params.set('title',    title)
  if (caption  !== undefined && caption  !== null) params.set('caption',  caption)

  const options = {
    method: 'POST',
    headers: authHeaders(),
  }

  // If WordPress credentials are provided, send them in the body
  if (wpCredentials) {
    options.body = JSON.stringify({ wp_credentials: wpCredentials })
  }

  const res = await fetch(`/api/fixes/update-image-meta?${params}`, options)
  return checkResponse(res)
}

export async function refreshImageFromWP(imageUrl, jobId, wpCredentials = null) {
  const params = new URLSearchParams({ image_url: imageUrl, job_id: jobId })

  const options = {
    method: 'POST',
    headers: authHeaders(),
  }

  if (wpCredentials) {
    options.body = JSON.stringify({ wp_credentials: wpCredentials })
  }

  const res = await fetch(`/api/fixes/refresh-image-from-wp?${params}`, options)
  return checkResponse(res)
}

export async function optimizeImage(jobId, imageUrl, targetWidth = null, newFilename = null) {
  const params = new URLSearchParams({ job_id: jobId, image_url: imageUrl })
  if (targetWidth) params.set('target_width', targetWidth)
  if (newFilename) params.set('new_filename', newFilename)
  const res = await fetch(`/api/fixes/optimize-image?${params}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return checkResponse(res)
}

export async function removeExemptAnchorUrl(url) {
  const params = new URLSearchParams({ url })
  const res = await fetch(`/api/exempt-anchor-urls?${params}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  return checkResponse(res)
}

export async function downloadCsv(jobId, category) {
  const url = category
    ? `/api/crawl/${jobId}/export/csv/${category}`
    : `/api/crawl/${jobId}/export/csv`
  const h = {}
  if (TOKEN) h['Authorization'] = `Bearer ${TOKEN}`
  const res = await fetch(url, { headers: h })
  if (!res.ok) throw new Error(`Export failed: HTTP ${res.status}`)
  const blob = await res.blob()
  const objectUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = objectUrl
  a.download = category ? `crawl-${category}.csv` : 'crawl-full.csv'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(objectUrl)
}

export async function downloadPdfReport(jobId, { includeHelp = true, includePages = true, summaryOnly = false } = {}) {
  const params = new URLSearchParams({
    include_help: includeHelp,
    include_pages: includePages,
    summary_only: summaryOnly
  })
  const url = `/api/crawl/${jobId}/export/pdf?${params}`
  const h = authHeaders()
  const res = await fetch(url, { headers: h })
  if (!res.ok) throw new Error(`PDF Export failed: HTTP ${res.status}`)
  const blob = await res.blob()
  const objectUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = objectUrl
  a.download = `TalkingToad-Audit-${jobId.slice(0, 8)}.pdf`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(objectUrl)
}

export async function downloadExcelReport(jobId) {
  const url = `/api/crawl/${jobId}/export/excel`
  const h = authHeaders()
  const res = await fetch(url, { headers: h })
  if (!res.ok) throw new Error(`Excel Export failed: HTTP ${res.status}`)
  const blob = await res.blob()
  const objectUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = objectUrl
  a.download = `TalkingToad-Audit-${jobId.slice(0, 8)}.xlsx`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(objectUrl)
}

export async function analyzeWithAi(jobId, pageUrl, type) {
  const res = await fetch('/api/ai/analyze', {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ job_id: jobId, page_url: pageUrl, analysis_type: type })
  })
  return checkResponse(res)
}

export async function testAI() {
  const res = await fetch('/api/ai/test', {
    headers: authHeaders(),
  })
  return checkResponse(res)
}

// v1.9image: Image Analysis API
export async function getImages(jobId, { page = 1, limit = 50, sortBy = 'score' } = {}) {
  const params = new URLSearchParams({ page, limit, sort_by: sortBy })
  const res = await fetch(`/api/crawl/${jobId}/images?${params}`, {
    headers: authHeaders(),
  })
  return checkResponse(res)
}

export async function getImagesSummary(jobId) {
  const res = await fetch(`/api/crawl/${jobId}/images/summary`, {
    headers: authHeaders(),
  })
  return checkResponse(res)
}

export async function fetchImageDetails(jobId, imageUrl) {
  const params = new URLSearchParams({ image_url: imageUrl })
  const res = await fetch(`/api/crawl/${jobId}/images/fetch?${params}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return checkResponse(res)
}

// v1.9image: AI Image Analysis
export async function analyzeImageWithAI(jobId, imageUrl) {
  const params = new URLSearchParams({ image_url: imageUrl })
  const res = await fetch(`/api/crawl/${jobId}/images/analyze-ai?${params}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return checkResponse(res)
}

// AI Page Advisor
export async function getPageAdvisor(jobId, pageUrl) {
  const res = await fetch('/api/ai/page-advisor', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ job_id: jobId, page_url: pageUrl })
  })
  return checkResponse(res)
}

// AI Site Advisor
export async function getSiteAdvisor(jobId) {
  const res = await fetch('/api/ai/site-advisor', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ job_id: jobId })
  })
  return checkResponse(res)
}

// Export AI Image Analysis as PDF
export async function downloadAIImagePDF(jobId, aiResults = null) {
  const url = `/api/crawl/${jobId}/export/ai-images-pdf`
  const h = authHeaders()

  // If we have AI results from the modal, send them as POST
  const options = aiResults ? {
    method: 'POST',
    headers: h,
    body: JSON.stringify({ ai_results: aiResults })
  } : {
    method: 'GET',
    headers: h
  }

  const res = await fetch(url, options)
  if (!res.ok) throw new Error(`PDF Export failed: HTTP ${res.status}`)
  const blob = await res.blob()

  // Try to use File System Access API for Save As dialog
  if (window.showSaveFilePicker) {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: `AI-Image-Analysis-${jobId.slice(0, 8)}.pdf`,
        types: [{
          description: 'PDF Document',
          accept: { 'application/pdf': ['.pdf'] }
        }]
      })
      const writable = await handle.createWritable()
      await writable.write(blob)
      await writable.close()
      return
    } catch (err) {
      // User cancelled or API not available, fall through to default
      if (err.name !== 'AbortError') {
        console.warn('Save picker failed:', err)
      }
    }
  }

  // Fallback: open in new tab (user can right-click save)
  const objectUrl = URL.createObjectURL(blob)
  window.open(objectUrl, '_blank')
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
}

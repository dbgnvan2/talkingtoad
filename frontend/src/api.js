/**
 * API client — all calls to the TalkingToad backend.
 * Uses relative /api/* paths; Vite proxies to localhost:8000 in dev,
 * and Vercel routes them to the Python serverless functions in prod.
 */

const TOKEN = import.meta.env.VITE_AUTH_TOKEN || ''

function authHeaders(extra = {}) {
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

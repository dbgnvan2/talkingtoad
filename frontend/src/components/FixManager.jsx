import { useState, useEffect, useCallback } from 'react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const STATUS_COLOURS = {
  pending:  'bg-gray-100 text-gray-600',
  approved: 'bg-blue-100 text-blue-700',
  applied:  'bg-green-100 text-green-700',
  failed:   'bg-red-100 text-red-700',
  skipped:  'bg-amber-100 text-amber-700',
}

const FIELD_HINTS = {
  seo_title:        { max: 60,  placeholder: 'Write a clear page title (30–60 characters)…' },
  meta_description: { max: 160, placeholder: 'Write a page summary (70–160 characters)…' },
  og_title:         { max: 90,  placeholder: 'Social share title…' },
  og_description:   { max: 200, placeholder: 'Social share description…' },
  indexable:        { max: null, placeholder: 'Will be set to "index" automatically' },
}

function authHeader() {
  const token = import.meta.env.VITE_AUTH_TOKEN
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function apiFetch(path, opts = {}, timeoutMs = 30_000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(`${API}${path}`, {
      headers: { 'Content-Type': 'application/json', ...authHeader(), ...opts.headers },
      signal: controller.signal,
      ...opts,
    })
    return res
  } finally {
    clearTimeout(timer)
  }
}

// ── Single fix row ──────────────────────────────────────────────────────────

function FixRow({ fix, onUpdate }) {
  const [value, setValue] = useState(fix.proposed_value || '')
  const [saving, setSaving] = useState(false)
  const hint = FIELD_HINTS[fix.field] || {}
  const isApplied = fix.status === 'applied'
  const isIndexable = fix.field === 'indexable'
  const charCount = value.length
  const overLimit = hint.max && charCount > hint.max

  async function patch(updates) {
    setSaving(true)
    try {
      const res = await apiFetch(`/api/fixes/${fix.id}`, {
        method: 'PATCH',
        body: JSON.stringify(updates),
      })
      if (res.ok) {
        const updated = await res.json()
        onUpdate(updated)
      }
    } finally {
      setSaving(false)
    }
  }

  function handleApprove() {
    patch({ proposed_value: value, status: 'approved' })
  }

  function handleSkip() {
    patch({ status: 'skipped' })
  }

  function handleReset() {
    patch({ status: 'pending', proposed_value: value })
  }

  return (
    <div className={`border rounded-lg p-4 space-y-2 ${isApplied ? 'bg-green-50 border-green-200' : 'bg-white border-gray-200'}`}>
      {/* Header row */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-mono bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
          {fix.issue_code}
        </span>
        <span className="text-sm font-semibold text-gray-800">{fix.label}</span>
        <span className={`ml-auto text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_COLOURS[fix.status] || STATUS_COLOURS.pending}`}>
          {fix.status}
        </span>
      </div>

      {/* Current value */}
      {fix.current_value && (
        <div className="text-xs text-gray-500">
          <span className="font-medium">Current:</span>{' '}
          <span className="italic">{fix.current_value}</span>
        </div>
      )}

      {/* Input or applied value */}
      {isApplied ? (
        <div className="text-sm text-green-700 font-medium">
          Applied: {fix.proposed_value}
        </div>
      ) : isIndexable ? (
        <div className="text-sm text-gray-600 bg-gray-50 rounded px-3 py-2">
          This will re-enable search engine indexing for this page.
        </div>
      ) : (
        <div className="space-y-1">
          <textarea
            className={`w-full border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-400 ${overLimit ? 'border-red-400' : 'border-gray-300'}`}
            rows={2}
            placeholder={hint.placeholder || 'Enter new value…'}
            value={value}
            disabled={fix.status === 'applied' || fix.status === 'skipped'}
            onChange={e => setValue(e.target.value)}
          />
          {hint.max && (
            <div className={`text-xs text-right ${overLimit ? 'text-red-500 font-medium' : 'text-gray-400'}`}>
              {charCount} / {hint.max}
            </div>
          )}
        </div>
      )}

      {/* Error message */}
      {fix.status === 'failed' && fix.error && (
        <div className="text-xs text-red-600 bg-red-50 rounded px-2 py-1">
          {fix.error}
        </div>
      )}

      {/* Action buttons */}
      {!isApplied && (
        <div className="flex gap-2 pt-1">
          {fix.status !== 'skipped' && fix.status !== 'approved' && (
            <button
              onClick={handleApprove}
              disabled={saving || (!isIndexable && !value.trim()) || overLimit}
              className="text-xs px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
            >
              {saving ? 'Saving…' : 'Approve'}
            </button>
          )}
          {fix.status === 'approved' && (
            <button
              onClick={handleReset}
              disabled={saving}
              className="text-xs px-3 py-1.5 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 font-medium"
            >
              Unapprove
            </button>
          )}
          {(fix.status === 'failed' || fix.status === 'skipped') && (
            <button
              onClick={handleReset}
              disabled={saving}
              className="text-xs px-3 py-1.5 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 font-medium"
            >
              Reset
            </button>
          )}
          {fix.status !== 'skipped' && (
            <button
              onClick={handleSkip}
              disabled={saving}
              className="text-xs px-3 py-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded"
            >
              Skip
            </button>
          )}
        </div>
      )}
    </div>
  )
}

// ── Page group ─────────────────────────────────────────────────────────────

function PageGroup({ pageUrl, fixes, onUpdate }) {
  const path = (() => { try { return new URL(pageUrl).pathname } catch { return pageUrl } })()
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <div className="h-px flex-1 bg-gray-200" />
        <span className="text-xs font-mono text-gray-500 truncate max-w-sm" title={pageUrl}>{path}</span>
        <div className="h-px flex-1 bg-gray-200" />
      </div>
      {fixes.map(fix => (
        <FixRow key={fix.id} fix={fix} onUpdate={onUpdate} />
      ))}
    </div>
  )
}

// ── Main Fix Manager ────────────────────────────────────────────────────────

export default function FixManager({ jobId }) {
  const [fixes, setFixes] = useState([])
  const [seoPlugin, setSeoPlugin] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [applying, setApplying] = useState(false)
  const [applyResult, setApplyResult] = useState(null)
  const [error, setError] = useState(null)
  const [generated, setGenerated] = useState(false)

  // Load existing fixes on mount
  useEffect(() => {
    apiFetch(`/api/fixes/${jobId}`)
      .then(r => r.ok ? r.json() : [])
      .then(data => {
        if (data.length > 0) {
          setFixes(data)
          setGenerated(true)
        }
      })
      .catch(() => setError('Could not load existing fixes — check your connection and refresh.'))
  }, [jobId])

  const handleUpdate = useCallback((updated) => {
    setFixes(prev => prev.map(f => f.id === updated.id ? updated : f))
  }, [])

  async function handleGenerate() {
    setGenerating(true)
    setError(null)
    setApplyResult(null)
    try {
      const res = await apiFetch(`/api/fixes/generate/${jobId}`, { method: 'POST' }, 120_000)
      const data = await res.json()
      if (!res.ok) {
        setError(data.error?.message || 'Failed to generate fixes.')
        return
      }
      setFixes(data.fixes)
      setSeoPlugin(data.seo_plugin)
      setGenerated(true)
      if (data.fixes.length === 0) {
        setError(data.message)
      }
    } catch (e) {
      setError('Could not connect to the API.')
    } finally {
      setGenerating(false)
    }
  }

  async function handleApply() {
    if (!window.confirm(`Apply ${approvedCount} approved fix${approvedCount !== 1 ? 'es' : ''} to WordPress? This will update live content.`)) return
    setApplying(true)
    setApplyResult(null)
    setError(null)
    try {
      const res = await apiFetch(`/api/fixes/apply/${jobId}`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) {
        setError(data.error?.message || 'Apply failed.')
        return
      }
      setApplyResult(data)
      // Refresh fixes list to pick up applied/failed statuses
      const refreshed = await apiFetch(`/api/fixes/${jobId}`)
      if (refreshed.ok) setFixes(await refreshed.json())
    } catch (e) {
      setError('Could not connect to the API.')
    } finally {
      setApplying(false)
    }
  }

  async function handleClear() {
    if (!window.confirm('Clear all fixes and start over? This cannot be undone.')) return
    await apiFetch(`/api/fixes/${jobId}`, { method: 'DELETE' })
    setFixes([])
    setGenerated(false)
    setApplyResult(null)
    setError(null)
    setSeoPlugin(null)
  }

  // Group fixes by page
  const byPage = fixes.reduce((acc, fix) => {
    ;(acc[fix.page_url] = acc[fix.page_url] || []).push(fix)
    return acc
  }, {})

  const approvedCount = fixes.filter(f => f.status === 'approved').length
  const appliedCount  = fixes.filter(f => f.status === 'applied').length
  const failedCount   = fixes.filter(f => f.status === 'failed').length
  const pendingCount  = fixes.filter(f => f.status === 'pending').length

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-lg font-bold text-gray-900">Fix Manager</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Review issues found in this crawl and apply fixes directly to WordPress.
            {seoPlugin && (
              <span className="ml-2 text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full font-medium">
                {seoPlugin === 'yoast' ? 'Yoast SEO' : 'Rank Math'}
              </span>
            )}
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          {generated && (
            <button
              onClick={handleClear}
              className="text-sm px-4 py-2 border border-gray-300 text-gray-600 rounded-lg hover:bg-gray-50"
            >
              Clear &amp; Regenerate
            </button>
          )}
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="text-sm px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 font-medium"
          >
            {generating ? 'Connecting to WordPress…' : generated ? 'Refresh Fixes' : 'Load Fixes from WordPress'}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Apply result banner */}
      {applyResult && (
        <div className={`rounded-lg px-4 py-3 text-sm border ${applyResult.failed > 0 ? 'bg-amber-50 border-amber-200 text-amber-800' : 'bg-green-50 border-green-200 text-green-800'}`}>
          {applyResult.failed > 0 ? (
            <>
              Applied {applyResult.applied} fix{applyResult.applied !== 1 ? 'es' : ''}, then stopped on a failure.
              Fix the error below and click Apply again to retry.
            </>
          ) : (
            <>All {applyResult.applied} fix{applyResult.applied !== 1 ? 'es' : ''} applied successfully.</>
          )}
        </div>
      )}

      {/* Stats bar */}
      {fixes.length > 0 && (
        <div className="flex gap-4 text-sm flex-wrap">
          <span className="text-gray-500">{fixes.length} total</span>
          {pendingCount > 0 && <span className="text-gray-500">{pendingCount} pending</span>}
          {approvedCount > 0 && <span className="text-blue-600 font-medium">{approvedCount} approved</span>}
          {appliedCount > 0  && <span className="text-green-600 font-medium">{appliedCount} applied</span>}
          {failedCount > 0   && <span className="text-red-600 font-medium">{failedCount} failed</span>}

          {approvedCount > 0 && (
            <button
              onClick={handleApply}
              disabled={applying}
              className="ml-auto text-sm px-4 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 font-medium"
            >
              {applying ? 'Applying…' : `Apply ${approvedCount} Approved Fix${approvedCount !== 1 ? 'es' : ''}`}
            </button>
          )}
        </div>
      )}

      {/* Generating spinner */}
      {generating && (
        <div className="text-center py-12 text-gray-500">
          <div className="inline-block w-8 h-8 border-4 border-indigo-300 border-t-indigo-600 rounded-full animate-spin mb-3" />
          <p className="text-sm">Connecting to WordPress to load current values for fixable issues…</p>
        </div>
      )}

      {/* Empty state */}
      {!generating && generated && fixes.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          <p className="text-2xl mb-2">No fixes needed</p>
          <p className="text-sm">No fixable issues were found in this crawl, or all have been resolved.</p>
        </div>
      )}

      {/* Not yet generated */}
      {!generating && !generated && (
        <div className="text-center py-16 text-gray-400 border-2 border-dashed border-gray-200 rounded-xl">
          <p className="text-lg font-medium mb-2">Ready to fix issues</p>
          <p className="text-sm max-w-sm mx-auto">
            Click <strong>Load Fixes from WordPress</strong> to connect to WordPress
            and prepare the fixable issues from this crawl for review and one-click apply.
          </p>
        </div>
      )}

      {/* Fix list grouped by page */}
      {!generating && fixes.length > 0 && (
        <div className="space-y-6">
          {Object.entries(byPage).map(([pageUrl, pageFixes]) => (
            <PageGroup
              key={pageUrl}
              pageUrl={pageUrl}
              fixes={pageFixes}
              onUpdate={handleUpdate}
            />
          ))}
        </div>
      )}

    </div>
  )
}

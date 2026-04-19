/**
 * FixInlinePanel — inline WordPress fix editor for a single issue row.
 *
 * Fetches the current WordPress value on mount, shows an editable textarea
 * with an auto-proposed value, and applies the fix via POST /api/fixes/apply-one.
 */
import { useState, useEffect, useRef } from 'react'

// Maps issue_code → field name (mirrors _CODE_TO_FIELD in wp_fixer.py)
const CODE_TO_FIELD = {
  TITLE_MISSING:       'seo_title',
  TITLE_TOO_SHORT:     'seo_title',
  TITLE_TOO_LONG:      'seo_title',
  META_DESC_MISSING:   'meta_description',
  META_DESC_TOO_SHORT: 'meta_description',
  META_DESC_TOO_LONG:  'meta_description',
  OG_TITLE_MISSING:    'og_title',
  OG_DESC_MISSING:     'og_description',
  NOINDEX_META:        'indexable',
  NOT_IN_SITEMAP:      'sitemap_include',
  SCHEMA_MISSING:      'schema_article_type',
  TITLE_H1_MISMATCH:   'seo_title',
}

export const FIXABLE_CODES = new Set(Object.keys(CODE_TO_FIELD))

const FIELD_LABELS = {
  seo_title:           'SEO Title',
  meta_description:    'Meta Description',
  og_title:            'Social Share Title',
  og_description:      'Social Share Description',
  indexable:           'Search Engine Indexing',
  sitemap_include:     'Sitemap Inclusion',
  schema_article_type: 'Schema Markup',
}

// Human-readable descriptions for predefined (one-click) fixes
const PREDEFINED_DESCRIPTIONS = {
  sitemap_include:     'This page is not in your XML sitemap. Clicking Apply will force Yoast to include it.',
  schema_article_type: 'No structured data found. Clicking Apply will set the Yoast schema article type to "Article", which triggers schema generation.',
}

const FIELD_LIMITS = {
  seo_title:        { warn: 60 },
  meta_description: { warn: 160 },
  og_title:         { warn: 60 },
  og_description:   { warn: 160 },
}

function autoPropose(issueCode, currentValue) {
  if (!currentValue) return ''
  if (issueCode === 'TITLE_TOO_LONG')      return currentValue.slice(0, 57).trimEnd() + '…'
  if (issueCode === 'META_DESC_TOO_LONG')  return currentValue.slice(0, 157).trimEnd() + '…'
  return currentValue
}

const TOKEN = import.meta.env.VITE_AUTH_TOKEN || ''

function authHeaders(extra = {}) {
  const h = { 'Content-Type': 'application/json', ...extra }
  if (TOKEN) h['Authorization'] = `Bearer ${TOKEN}`
  return h
}

export default function FixInlinePanel({ jobId, pageUrl, issueCode, issueExtra, predefinedValue, onClose }) {
  const field = CODE_TO_FIELD[issueCode]
  const fieldLabel = FIELD_LABELS[field] ?? field
  const limits = FIELD_LIMITS[field]
  const isPredefined = predefinedValue != null

  const [loading,       setLoading]       = useState(!isPredefined)
  const [fetchError,    setFetchError]    = useState(null)
  const [currentValue,  setCurrentValue]  = useState(null)
  const [proposedValue, setProposedValue] = useState(isPredefined ? predefinedValue : '')
  const [applying,      setApplying]      = useState(false)
  const [applyError,    setApplyError]    = useState(null)
  const [applied,       setApplied]       = useState(false)
  const textareaRef = useRef(null)

  useEffect(() => {
    if (issueCode === 'TITLE_H1_MISMATCH') return  // handled by MismatchFixPanel
    if (isPredefined) return   // no need to fetch current WP value for one-click fixes
    if (!field) {
      setFetchError(`No fix available for issue code: ${issueCode}`)
      setLoading(false)
      return
    }
    const params = new URLSearchParams({ job_id: jobId, page_url: pageUrl, field })
    fetch(`/api/fixes/wp-value?${params}`, { headers: authHeaders() })
      .then(async res => {
        const data = await res.json().catch(() => ({}))
        if (!res.ok) throw new Error(data.error?.message || `HTTP ${res.status}`)
        return data
      })
      .then(data => {
        const cur = data.current_value ?? ''
        setCurrentValue(cur)
        const proposed = autoPropose(issueCode, cur)
        setProposedValue(proposed || cur)
        setLoading(false)
      })
      .catch(err => {
        setFetchError(err.message)
        setLoading(false)
      })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!loading && !fetchError && textareaRef.current) {
      textareaRef.current.focus()
      textareaRef.current.select()
    }
  }, [loading, fetchError])

  // Special dual-editor for title/heading mismatch — after hooks
  if (issueCode === 'TITLE_H1_MISMATCH') {
    return <MismatchFixPanel jobId={jobId} pageUrl={pageUrl} issueExtra={issueExtra} onClose={onClose} />
  }

  async function handleApply() {
    if (!proposedValue.trim() && field !== 'indexable') return
    setApplying(true)
    setApplyError(null)
    try {
      const res = await fetch('/api/fixes/apply-one', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          job_id: jobId,
          page_url: pageUrl,
          field,
          proposed_value: proposedValue,
          issue_code: issueCode,
        }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.error?.message || `HTTP ${res.status}`)
      if (!data.success) throw new Error(data.error || 'Apply failed — check WordPress credentials.')
      setApplied(true)
    } catch (err) {
      setApplyError(err.message)
    } finally {
      setApplying(false)
    }
  }

  const charCount  = proposedValue.length
  const overLimit  = limits && charCount > limits.warn
  const isIndexable = field === 'indexable'
  const predefinedDesc = PREDEFINED_DESCRIPTIONS[field]

  return (
    <div className="mx-4 mb-2 mt-0.5 bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-amber-800 uppercase tracking-wide">
          Fix — {fieldLabel}
        </span>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 text-xl leading-none"
          title="Close"
        >
          &times;
        </button>
      </div>

      {/* Loading */}
      {loading && (
        <p className="text-xs text-amber-700 py-2">Loading current WordPress value…</p>
      )}

      {/* Fetch error */}
      {fetchError && (
        <p className="text-xs text-red-600 py-2">Error: {fetchError}</p>
      )}

      {/* Success */}
      {applied && (
        <div className="flex items-center gap-2 py-2">
          <span className="text-green-600 text-base">✓</span>
          <span className="text-sm text-green-700 font-medium">Applied to WordPress.</span>
          <button onClick={onClose} className="ml-auto text-xs text-gray-500 hover:text-gray-700 underline">
            Close
          </button>
        </div>
      )}

      {/* Predefined one-click fix */}
      {isPredefined && !applied && (
        <>
          <p className="text-xs text-gray-700 mb-3">
            {predefinedDesc || `This will set the value to "${predefinedValue}" in WordPress.`}
          </p>
          {applyError && <p className="text-xs text-red-600 mb-2">{applyError}</p>}
          <div className="flex items-center gap-2">
            <button
              onClick={handleApply}
              disabled={applying}
              className="px-3 py-1.5 text-xs font-medium bg-amber-600 text-white rounded hover:bg-amber-700 disabled:opacity-50 transition-colors"
            >
              {applying ? 'Applying…' : 'Apply to WordPress'}
            </button>
            <button onClick={onClose} className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700">
              Cancel
            </button>
          </div>
        </>
      )}

      {/* Edit form (text/textarea fields) */}
      {!isPredefined && !loading && !fetchError && !applied && (
        <>
          {/* Current value */}
          {!isIndexable && (
            <div className="mb-2">
              <p className="text-xs text-gray-500 mb-1">Current WordPress value:</p>
              <p className="text-xs bg-white border border-gray-200 rounded px-2 py-1.5 text-gray-600 break-words min-h-[1.75rem]">
                {currentValue || <em className="text-gray-400">empty</em>}
              </p>
            </div>
          )}

          {/* New value */}
          {isIndexable ? (
            <div className="mb-2 text-xs text-gray-700">
              <p className="mb-1.5">
                This page is set to <strong>noindex</strong>. Clicking Apply will re-enable indexing
                (sets Yoast/Rank Math to "use site default").
              </p>
            </div>
          ) : (
            <div className="mb-2">
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs text-gray-500">New value:</p>
                {limits && (
                  <span className={`text-xs font-mono ${overLimit ? 'text-red-600 font-semibold' : 'text-gray-400'}`}>
                    {charCount} / {limits.warn}
                  </span>
                )}
              </div>
              <textarea
                ref={textareaRef}
                className={`w-full border rounded px-2 py-1.5 text-xs text-gray-800 resize-none focus:outline-none focus:ring-1 ${
                  overLimit
                    ? 'border-red-300 focus:ring-red-300'
                    : 'border-gray-300 focus:ring-amber-400 focus:border-amber-400'
                }`}
                rows={field === 'meta_description' || field === 'og_description' ? 3 : 2}
                value={proposedValue}
                onChange={e => setProposedValue(e.target.value)}
                placeholder={`Enter new ${fieldLabel}…`}
              />
            </div>
          )}

          {applyError && (
            <p className="text-xs text-red-600 mb-2">{applyError}</p>
          )}

          <div className="flex items-center gap-2">
            <button
              onClick={handleApply}
              disabled={applying || (!isIndexable && !proposedValue.trim())}
              className="px-3 py-1.5 text-xs font-medium bg-amber-600 text-white rounded hover:bg-amber-700 disabled:opacity-50 transition-colors"
            >
              {applying ? 'Applying…' : 'Apply to WordPress'}
            </button>
            <button
              onClick={onClose}
              className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700"
            >
              Cancel
            </button>
          </div>
        </>
      )}
    </div>
  )
}


/**
 * MismatchFixPanel — dual editor for TITLE_H1_MISMATCH issues.
 *
 * Shows both the SEO title and content H1 side by side, lets the user
 * edit either or both, and applies changes to WordPress.
 */
function MismatchFixPanel({ jobId, pageUrl, issueExtra, onClose }) {
  const currentTitle = issueExtra?.title || ''
  const currentH1    = issueExtra?.h1 || ''

  const [wpTitle,      setWpTitle]      = useState(null)
  const [newTitle,     setNewTitle]     = useState('')
  const [newH1,        setNewH1]        = useState(currentH1)
  const [loading,      setLoading]      = useState(true)
  const [applying,     setApplying]     = useState(null) // 'title' | 'h1' | 'both' | null
  const [titleResult,  setTitleResult]  = useState(null) // 'success' | error string
  const [h1Result,     setH1Result]     = useState(null)
  const [fetchError,   setFetchError]   = useState(null)

  // Fetch current WP SEO title value
  useEffect(() => {
    const params = new URLSearchParams({ job_id: jobId, page_url: pageUrl, field: 'seo_title' })
    fetch(`/api/fixes/wp-value?${params}`, { headers: authHeaders() })
      .then(async res => {
        const data = await res.json().catch(() => ({}))
        if (!res.ok) throw new Error(data.error?.message || `HTTP ${res.status}`)
        return data
      })
      .then(data => {
        const cur = data.current_value ?? currentTitle
        setWpTitle(cur)
        setNewTitle(cur)
        setLoading(false)
      })
      .catch(err => {
        setFetchError(err.message)
        setNewTitle(currentTitle)
        setLoading(false)
      })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function applyTitle() {
    if (!newTitle.trim()) return
    setApplying('title')
    setTitleResult(null)
    try {
      const res = await fetch('/api/fixes/apply-one', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          job_id: jobId,
          page_url: pageUrl,
          field: 'seo_title',
          proposed_value: newTitle.trim(),
          issue_code: 'TITLE_H1_MISMATCH',
        }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok || !data.success) throw new Error(data.error?.message || data.error || 'Failed')
      setTitleResult('success')
    } catch (err) {
      setTitleResult(err.message)
    } finally {
      setApplying(null)
    }
  }

  async function applyH1() {
    if (!newH1.trim() || newH1.trim() === currentH1) return
    setApplying('h1')
    setH1Result(null)
    try {
      const params = new URLSearchParams({
        page_url: pageUrl,
        old_text: currentH1,
        new_text: newH1.trim(),
        level: '1',
      })
      const res = await fetch(`/api/fixes/change-heading-text?${params}`, {
        method: 'POST',
        headers: authHeaders(),
      })
      const data = await res.json().catch(() => ({}))
      if (!data.success) throw new Error(data.error || 'Failed')
      setH1Result('success')
    } catch (err) {
      setH1Result(err.message)
    } finally {
      setApplying(null)
    }
  }

  async function applyBoth() {
    setApplying('both')
    setTitleResult(null)
    setH1Result(null)
    // Apply title first, then H1
    if (newTitle.trim() && newTitle.trim() !== (wpTitle || currentTitle)) {
      try {
        const res = await fetch('/api/fixes/apply-one', {
          method: 'POST',
          headers: authHeaders(),
          body: JSON.stringify({
            job_id: jobId,
            page_url: pageUrl,
            field: 'seo_title',
            proposed_value: newTitle.trim(),
            issue_code: 'TITLE_H1_MISMATCH',
          }),
        })
        const data = await res.json().catch(() => ({}))
        if (!res.ok || !data.success) throw new Error(data.error?.message || data.error || 'Failed')
        setTitleResult('success')
      } catch (err) {
        setTitleResult(err.message)
      }
    }
    if (newH1.trim() && newH1.trim() !== currentH1) {
      try {
        const params = new URLSearchParams({
          page_url: pageUrl,
          old_text: currentH1,
          new_text: newH1.trim(),
          level: '1',
        })
        const res = await fetch(`/api/fixes/change-heading-text?${params}`, {
          method: 'POST',
          headers: authHeaders(),
        })
        const data = await res.json().catch(() => ({}))
        if (!data.success) throw new Error(data.error || 'Failed')
        setH1Result('success')
      } catch (err) {
        setH1Result(err.message)
      }
    }
    setApplying(null)
  }

  const titleCharCount = newTitle.length
  const titleOver = titleCharCount > 60

  return (
    <div className="mx-4 mb-2 mt-0.5 bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-amber-800 uppercase tracking-wide">
          Fix — Title & Heading Mismatch
        </span>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
      </div>

      {loading && <p className="text-xs text-amber-700 py-2">Loading current values…</p>}
      {fetchError && <p className="text-xs text-yellow-600 py-1">Could not fetch WP title: {fetchError}</p>}

      {!loading && (
        <div className="space-y-4">
          {/* SEO Title editor */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-bold text-gray-700">SEO Title</label>
              <span className={`text-xs font-mono ${titleOver ? 'text-red-600 font-semibold' : 'text-gray-400'}`}>
                {titleCharCount} / 60
              </span>
            </div>
            <p className="text-xs text-gray-400 mb-1">Current: <span className="text-gray-600">{wpTitle || currentTitle || <em>empty</em>}</span></p>
            <textarea
              className={`w-full border rounded px-2 py-1.5 text-xs text-gray-800 resize-none focus:outline-none focus:ring-1 ${
                titleOver ? 'border-red-300 focus:ring-red-300' : 'border-gray-300 focus:ring-amber-400'
              }`}
              rows={2}
              value={newTitle}
              onChange={e => setNewTitle(e.target.value)}
              placeholder="Enter new SEO title…"
            />
            {titleResult && (
              <p className={`text-xs mt-1 ${titleResult === 'success' ? 'text-green-600' : 'text-red-600'}`}>
                {titleResult === 'success' ? '✓ Title updated in WordPress' : titleResult}
              </p>
            )}
            <button
              onClick={applyTitle}
              disabled={applying || !newTitle.trim()}
              className="mt-1 px-3 py-1 text-xs font-medium bg-amber-600 text-white rounded hover:bg-amber-700 disabled:opacity-50"
            >
              {applying === 'title' ? 'Applying…' : 'Apply Title'}
            </button>
          </div>

          {/* H1 Heading editor */}
          <div>
            <label className="text-xs font-bold text-gray-700 block mb-1">Content H1 Heading</label>
            <p className="text-xs text-gray-400 mb-1">Current: <span className="text-gray-600">{currentH1 || <em>none</em>}</span></p>
            <textarea
              className="w-full border border-gray-300 rounded px-2 py-1.5 text-xs text-gray-800 resize-none focus:outline-none focus:ring-1 focus:ring-amber-400"
              rows={2}
              value={newH1}
              onChange={e => setNewH1(e.target.value)}
              placeholder="Enter new H1 heading text…"
            />
            {h1Result && (
              <p className={`text-xs mt-1 ${h1Result === 'success' ? 'text-green-600' : 'text-red-600'}`}>
                {h1Result === 'success' ? '✓ Heading updated in WordPress' : h1Result}
              </p>
            )}
            <button
              onClick={applyH1}
              disabled={applying || !newH1.trim() || newH1.trim() === currentH1}
              className="mt-1 px-3 py-1 text-xs font-medium bg-amber-600 text-white rounded hover:bg-amber-700 disabled:opacity-50"
            >
              {applying === 'h1' ? 'Applying…' : 'Apply Heading'}
            </button>
          </div>

          {/* Apply Both */}
          <div className="pt-3 border-t border-amber-200 flex items-center gap-2">
            <button
              onClick={applyBoth}
              disabled={applying}
              className="px-4 py-1.5 text-xs font-bold bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              {applying === 'both' ? 'Applying…' : 'Apply Both to WordPress'}
            </button>
            <button onClick={onClose} className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700">
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

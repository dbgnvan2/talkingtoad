/**
 * FixBrokenLinkPanel — inline broken link fixer.
 *
 * Looks up which source page(s) contain the broken URL, then lets the user
 * enter a replacement URL and apply it to one source page at a time.
 */
import { useState, useEffect, useRef } from 'react'

export const FIXABLE_LINK_CODES = new Set([
  'BROKEN_LINK_404',
  'BROKEN_LINK_410',
  'BROKEN_LINK_5XX',
])

const TOKEN = import.meta.env.VITE_AUTH_TOKEN || ''

function authHeaders(extra = {}) {
  const h = { 'Content-Type': 'application/json', ...extra }
  if (TOKEN) h['Authorization'] = `Bearer ${TOKEN}`
  return h
}

function shortenUrl(url) {
  try {
    const u = new URL(url)
    return u.hostname + u.pathname
  } catch {
    return url
  }
}

export default function FixBrokenLinkPanel({ jobId, brokenUrl, onClose }) {
  const [loading,      setLoading]      = useState(true)
  const [fetchError,   setFetchError]   = useState(null)
  const [sources,      setSources]      = useState([])
  const [selectedSrc,  setSelectedSrc]  = useState(null)
  const [newUrl,       setNewUrl]       = useState('')
  const [applying,     setApplying]     = useState(false)
  const [applyError,   setApplyError]   = useState(null)
  const [appliedSrcs,  setAppliedSrcs]  = useState(new Set())
  const [rescanning,   setRescanning]   = useState(null) // URL being rescanned
  const [rescannedSrcs, setRescannedSrcs] = useState(new Set())
  const inputRef = useRef(null)

  useEffect(() => {
    const params = new URLSearchParams({ job_id: jobId, target_url: brokenUrl })
    fetch(`/api/fixes/link-sources?${params}`, { headers: authHeaders() })
      .then(async res => {
        const data = await res.json().catch(() => ({}))
        if (!res.ok) throw new Error(data.error?.message || `HTTP ${res.status}`)
        return data
      })
      .then(data => {
        setSources(data)
        if (data.length === 1) setSelectedSrc(data[0].source_url)
        setLoading(false)
      })
      .catch(err => {
        setFetchError(err.message)
        setLoading(false)
      })
  }, [jobId, brokenUrl])

  useEffect(() => {
    if (!loading && !fetchError && inputRef.current) {
      inputRef.current.focus()
    }
  }, [loading, fetchError])

  async function handleApply() {
    if (!selectedSrc || !newUrl.trim()) return
    setApplying(true)
    setApplyError(null)
    try {
      const res = await fetch('/api/fixes/replace-link', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          job_id: jobId,
          source_url: selectedSrc,
          old_url: brokenUrl,
          new_url: newUrl.trim(),
        }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.error?.message || `HTTP ${res.status}`)
      if (!data.success) throw new Error(data.error || 'Replace failed.')
      setAppliedSrcs(prev => new Set([...prev, selectedSrc]))
      // If more source pages remain, auto-advance; otherwise stay on success
      const remaining = sources.filter(s => !appliedSrcs.has(s.source_url) && s.source_url !== selectedSrc)
      setSelectedSrc(remaining.length ? remaining[0].source_url : null)
    } catch (err) {
      setApplyError(err.message)
    } finally {
      setApplying(false)
    }
  }

  async function handleRescan(sourceUrl) {
    setRescanning(sourceUrl)
    try {
      const params = new URLSearchParams({ url: sourceUrl })
      const res = await fetch(`/api/crawl/${jobId}/rescan-url?${params}`, {
        method: 'POST',
        headers: authHeaders(),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.error?.message || `HTTP ${res.status}`)
      }
      setRescannedSrcs(prev => new Set([...prev, sourceUrl]))
    } catch (err) {
      alert('Rescan failed: ' + err.message)
    } finally {
      setRescanning(null)
    }
  }

  const allDone = sources.length > 0 && sources.every(s => appliedSrcs.has(s.source_url))

  return (
    <div className="mx-4 mb-2 mt-0.5 bg-orange-50 border border-orange-200 rounded-lg p-3 text-sm shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-orange-800 uppercase tracking-wide">
          Broken Link
        </span>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none" title="Close">
          &times;
        </button>
      </div>

      {/* Broken URL + visit link */}
      <div className="mb-3 bg-red-50 border border-red-200 rounded px-2 py-2">
        <p className="text-xs text-red-500 mb-0.5 font-medium">Broken URL</p>
        <div className="flex items-start gap-2">
          <p className="text-xs font-mono text-red-700 break-all flex-1">{brokenUrl}</p>
          <a
            href={brokenUrl}
            target="_blank"
            rel="noopener noreferrer"
            title="Open in new tab to verify it is broken"
            className="flex-shrink-0 text-xs text-blue-600 hover:text-blue-800 underline whitespace-nowrap mt-0.5"
          >
            Visit ↗
          </a>
        </div>
      </div>

      {loading && <p className="text-xs text-orange-700 py-2">Looking up which pages link here…</p>}
      {fetchError && <p className="text-xs text-red-600 py-2">Error: {fetchError}</p>}

      {allDone && (
        <div className="flex items-center gap-2 py-1">
          <span className="text-green-600">✓</span>
          <span className="text-sm text-green-700 font-medium">All source pages updated.</span>
          <button onClick={onClose} className="ml-auto text-xs text-gray-500 hover:text-gray-700 underline">Close</button>
        </div>
      )}

      {!loading && !fetchError && !allDone && (
        <>
          {/* Source page — the page on THIS SITE that contains the broken link */}
          <div className="mb-3">
            <p className="text-xs font-semibold text-gray-700 mb-1">
              {sources.length === 0
                ? 'Source page unknown'
                : sources.length === 1
                  ? 'Found on this page:'
                  : `Found on ${sources.length} pages — select which to fix:`}
            </p>
            {sources.length === 0 && (
              <p className="text-xs text-gray-500 italic">
                Source page data is only available after a fresh crawl. Run a new crawl to enable fixing.
              </p>
            )}
            {sources.length > 1 && (
              <div className="space-y-1">
                {sources.map(s => {
                  const done = appliedSrcs.has(s.source_url)
                  const rescanned = rescannedSrcs.has(s.source_url)
                  const isRescanning = rescanning === s.source_url
                  return (
                    <label
                      key={s.source_url}
                      className={`flex items-center gap-2 px-2 py-1.5 rounded border cursor-pointer text-xs transition-colors ${
                        done
                          ? 'border-green-200 bg-green-50 text-green-700'
                          : selectedSrc === s.source_url
                            ? 'border-orange-400 bg-orange-100 text-orange-900'
                            : 'border-gray-200 bg-white text-gray-700 hover:border-orange-300'
                      }`}
                    >
                      <input
                        type="radio"
                        name="source_page"
                        value={s.source_url}
                        checked={selectedSrc === s.source_url}
                        disabled={done}
                        onChange={() => setSelectedSrc(s.source_url)}
                        className="flex-shrink-0"
                      />
                      <span className="truncate flex-1" title={s.source_url}>
                        {shortenUrl(s.source_url)}
                        {s.link_text && <span className="text-gray-400 ml-1">— "{s.link_text}"</span>}
                      </span>
                      <button
                        onClick={e => { e.stopPropagation(); e.preventDefault(); handleRescan(s.source_url) }}
                        disabled={isRescanning}
                        className={`flex-shrink-0 text-xs px-2 py-0.5 rounded ${
                          rescanned
                            ? 'bg-green-100 text-green-700'
                            : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                        } disabled:opacity-50`}
                        title="Rescan this page to confirm fix"
                      >
                        {isRescanning ? '...' : rescanned ? '✓ Rescanned' : 'Rescan'}
                      </button>
                      <a
                        href={s.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={e => e.stopPropagation()}
                        className="flex-shrink-0 text-blue-400 hover:text-blue-600 text-xs"
                        title="Open in new tab"
                      >↗</a>
                      {done && <span className="flex-shrink-0 text-green-600">✓</span>}
                    </label>
                  )
                })}
              </div>
            )}
            {sources.length === 1 && (
              <div className="flex items-center gap-2 bg-white border border-gray-200 rounded px-2 py-1.5">
                <span className="text-xs text-gray-700 truncate flex-1" title={sources[0].source_url}>
                  {shortenUrl(sources[0].source_url)}
                  {sources[0].link_text && <span className="text-gray-400 ml-1">— "{sources[0].link_text}"</span>}
                </span>
                <button
                  onClick={() => handleRescan(sources[0].source_url)}
                  disabled={rescanning === sources[0].source_url}
                  className={`flex-shrink-0 text-xs px-2 py-0.5 rounded ${
                    rescannedSrcs.has(sources[0].source_url)
                      ? 'bg-green-100 text-green-700'
                      : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                  } disabled:opacity-50`}
                  title="Rescan this page to confirm fix"
                >
                  {rescanning === sources[0].source_url ? '...' : rescannedSrcs.has(sources[0].source_url) ? '✓ Rescanned' : 'Rescan'}
                </button>
                <a
                  href={sources[0].source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-shrink-0 text-xs text-blue-500 hover:text-blue-700"
                  title="Open source page in new tab"
                >
                  ↗
                </a>
              </div>
            )}
          </div>

          {sources.length > 0 && (
            <>
              {/* Replacement URL input */}
              <div className="mb-2">
                <p className="text-xs text-gray-500 mb-1">Replace with URL:</p>
                <input
                  ref={inputRef}
                  type="url"
                  className="w-full border border-gray-300 rounded px-2 py-1.5 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-orange-400 focus:border-orange-400"
                  placeholder="https://example.com/new-page"
                  value={newUrl}
                  onChange={e => setNewUrl(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleApply()}
                />
              </div>

              {applyError && <p className="text-xs text-red-600 mb-2">{applyError}</p>}

              <div className="flex items-center gap-2">
                <button
                  onClick={handleApply}
                  disabled={applying || !selectedSrc || !newUrl.trim()}
                  className="px-3 py-1.5 text-xs font-medium bg-orange-600 text-white rounded hover:bg-orange-700 disabled:opacity-50 transition-colors"
                >
                  {applying ? 'Replacing…' : 'Replace in WordPress'}
                </button>
                <button onClick={onClose} className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700">
                  Cancel
                </button>
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}

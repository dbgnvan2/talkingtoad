import React, { useState, useEffect, useCallback } from 'react'
import { getFixFocus, toggleFixFocusItem, verifyFixFocusPage, regenerateFixFocus } from '../api.js'

// Fix Focus — a curated, tickable worklist of the highest-priority fixes, split
// into SEO and AI/GEO, grouped by page and capped. Saved with the crawl (loads
// from the persisted snapshot; no re-scan) with a per-page Verify button that
// re-scans one page and marks its items verified / still-present.
// Spec: docs/pending/2026-08-13_fix-focus-checklist.md

const V4 = {
  what: 'A short checklist of the fixes that matter most, in two lists — SEO and AI/GEO — grouped by page (top 10 each) so you can work through them and tick them off.',
  why: 'A full report has hundreds of items. This turns it into a finite worklist a person can actually finish, highest-impact first.',
  goodBad: 'A ticked item means you did the work; press "Verify page" to have the crawler re-check that page — items it confirms fixed turn green, ones it still sees are flagged "still present".',
  mislead: 'The list is a snapshot frozen when generated, so it stays stable while you work. After fixing things, use Regenerate to rebuild it from the latest scan.',
  how: 'Work down each list; tick items as you fix them; Verify a page when done; Regenerate when you want a fresh list.',
}

const STATUS_STYLE = {
  open: 'text-gray-500',
  checked: 'text-indigo-600',
  verified: 'text-emerald-600 font-semibold',
  still_present: 'text-red-600 font-semibold',
}
const STATUS_LABEL = {
  open: '', checked: 'checked', verified: 'verified ✓', still_present: 'still present',
}

function FocusSection({ title, focus, jobId, onChange }) {
  const [verifyingUrl, setVerifyingUrl] = useState(null)
  if (!focus || !focus.pages) return null

  const toggle = async (pageUrl, item) => {
    const next = item.status !== 'checked'
    await toggleFixFocusItem(jobId, pageUrl, item.issue_code, next)
    onChange()
  }
  const verify = async (pageUrl) => {
    setVerifyingUrl(pageUrl)
    try {
      await verifyFixFocusPage(jobId, pageUrl)
      onChange()
    } finally {
      setVerifyingUrl(null)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between">
        <h4 className="font-bold text-sm text-gray-800">{title}</h4>
        <span className="text-xs text-gray-500">
          {focus.pages_shown} of {focus.pages_total} pages
          {focus.items_hidden > 0 && ` · ${focus.items_hidden} more items on hidden pages`}
        </span>
      </div>
      {focus.pages.length === 0 && (
        <p className="text-xs text-gray-400">No high-priority fixes in this focus.</p>
      )}
      {focus.pages.map((page) => (
        <div key={page.url} className="border border-gray-200 rounded-xl p-3">
          <div className="flex items-center justify-between gap-2">
            <a href={page.url} target="_blank" rel="noreferrer"
               className="text-xs font-medium text-indigo-700 truncate hover:underline">
              {page.url}
            </a>
            <button
              onClick={() => verify(page.url)}
              disabled={verifyingUrl === page.url}
              className="text-xs px-2 py-1 rounded bg-indigo-50 text-indigo-700 hover:bg-indigo-100 disabled:opacity-50 whitespace-nowrap"
            >
              {verifyingUrl === page.url ? 'Verifying…' : 'Verify page'}
            </button>
          </div>
          <ul className="mt-2 space-y-1">
            {page.items.map((item) => (
              <li key={item.issue_code} className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={item.status === 'checked' || item.status === 'verified'}
                  onChange={() => toggle(page.url, item)}
                  aria-label={`Mark ${item.issue_code} fixed`}
                />
                <span className={STATUS_STYLE[item.status] || 'text-gray-600'}>
                  {item.human_description}
                </span>
                {item.quick_win && (
                  <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 text-[10px]">
                    quick win
                  </span>
                )}
                {STATUS_LABEL[item.status] && (
                  <span className={`text-[10px] ${STATUS_STYLE[item.status]}`}>
                    {STATUS_LABEL[item.status]}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

export default function FixFocusPanel({ jobId }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [data, setData] = useState(null)
  const [showHelp, setShowHelp] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await getFixFocus(jobId, 'all'))
    } catch (e) {
      setError(e.message || 'Failed to load Fix Focus')
    } finally {
      setLoading(false)
    }
  }, [jobId])

  useEffect(() => { load() }, [load])

  const regenerate = async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await regenerateFixFocus(jobId))
    } catch (e) {
      setError(e.message || 'Failed to regenerate')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white border border-indigo-200 rounded-2xl p-5 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-bold text-indigo-900 text-sm">Fix Focus</h3>
            <button
              onClick={() => setShowHelp(h => !h)}
              aria-label="Learn more about Fix Focus"
              className="text-indigo-400 hover:text-indigo-700 text-xs font-bold"
            >
              {showHelp ? 'Hide help' : '?'}
            </button>
          </div>
          <p className="text-xs text-indigo-700 mt-1">
            The highest-priority fixes, split into SEO and AI/GEO — a checklist you can work through.
          </p>
        </div>
        <button
          onClick={regenerate}
          disabled={loading}
          className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-50 whitespace-nowrap"
        >
          Regenerate
        </button>
      </div>

      {showHelp && (
        <div className="text-xs text-gray-600 bg-indigo-50 rounded-xl p-3 space-y-1">
          <p><strong>What it is:</strong> {V4.what}</p>
          <p><strong>Why it matters:</strong> {V4.why}</p>
          <p><strong>Good vs. bad:</strong> {V4.goodBad}</p>
          <p><strong>How it can mislead:</strong> {V4.mislead}</p>
          <p><strong>How to use it:</strong> {V4.how}</p>
        </div>
      )}

      {loading && <p className="text-xs text-gray-500">Loading…</p>}
      {error && <p className="text-xs text-red-600">{error}</p>}

      {data && !loading && (
        <div className="grid md:grid-cols-2 gap-5">
          <FocusSection title="SEO" focus={data.seo} jobId={jobId} onChange={load} />
          <FocusSection title="AI / GEO" focus={data.geo} jobId={jobId} onChange={load} />
        </div>
      )}
    </div>
  )
}

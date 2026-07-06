import React, { useState } from 'react'
import { getPagePriority } from '../api.js'

// Page Priority Work Queue — ranks crawled pages by the Authority Matrix
// (health x GSC performance, via the M6.3 refresh trigger) so the user knows
// which pages to work on first. Additive panel; render data as text.

const BUCKET_STYLES = {
  'Vulnerable Star': 'bg-red-100 text-red-700',
  'Traffic Decay': 'bg-orange-100 text-orange-700',
  'Stale': 'bg-amber-100 text-amber-700',
  'Low Health': 'bg-yellow-100 text-yellow-700',
  'Hidden Gem': 'bg-emerald-100 text-emerald-700',
  'OK': 'bg-gray-100 text-gray-500',
}

const V4 = {
  what: 'Ranks every crawled page by how much it matters (Google Search traffic) against how well it is built (health score), so you know which pages to improve first.',
  why: 'Your most valuable pages are not always your healthiest. This puts the high-impact, structurally-weak pages at the top of the queue.',
  goodBad: 'A "Vulnerable Star" (earns traffic but weak structure) is the #1 thing to fix; a "Hidden Gem" (healthy but no traffic) is an opportunity to re-target, not a fire.',
  mislead: 'GSC data lags ~2-3 days and a low-traffic site shows thin data — without GSC connected, pages are ranked by health alone. Buckets are heuristics, not verdicts.',
  how: 'Connect GSC and ingest performance for richer ranking; then work down the list from the top.',
}

export default function PagePriorityPanel({ jobId }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [pages, setPages] = useState(null)
  const [showHelp, setShowHelp] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getPagePriority(jobId)
      setPages(data.pages || [])
    } catch (e) {
      setError(e.message || 'Failed to load page priority')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white border border-indigo-200 rounded-2xl p-5 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-bold text-indigo-900 text-sm">Page Priority Work Queue</h3>
            <button
              onClick={() => setShowHelp(h => !h)}
              aria-label="Learn more about the page priority queue"
              className="text-indigo-400 hover:text-indigo-700 text-xs font-bold"
            >
              {showHelp ? 'Hide help' : '?'}
            </button>
          </div>
          <p className="text-xs text-indigo-700 mt-1">
            Which pages to improve first — ranked by traffic value vs. structural health.
          </p>
        </div>
        {pages && !loading ? (
          <button
            onClick={() => setPages(null)}
            className="px-4 py-2 text-sm font-bold bg-gray-100 text-gray-600 rounded-xl hover:bg-gray-200"
          >
            Hide
          </button>
        ) : (
          <button
            onClick={load}
            disabled={loading}
            className="px-4 py-2 text-sm font-bold bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-50"
          >
            {loading ? 'Ranking…' : '▶ Rank pages'}
          </button>
        )}
      </div>

      {showHelp && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4 text-xs text-indigo-900 space-y-2">
          <p><strong>What it is:</strong> {V4.what}</p>
          <p><strong>Why it&apos;s useful:</strong> {V4.why}</p>
          <p><strong>Good vs bad:</strong> {V4.goodBad}</p>
          <p><strong>How it can mislead:</strong> {V4.mislead}</p>
          <p><strong>How to use:</strong> {V4.how}</p>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">{error}</div>
      )}

      {pages && pages.length === 0 && !loading && (
        <p className="text-sm text-gray-400 py-4 text-center">No pages to rank yet.</p>
      )}

      {pages && pages.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b border-gray-200">
                <th className="py-2 pr-3">#</th>
                <th className="py-2 pr-3">Priority</th>
                <th className="py-2 pr-3">Page</th>
                <th className="py-2 pr-3 text-right">Health</th>
                <th className="py-2 pr-3 text-right">Clicks</th>
                <th className="py-2 pr-3 text-right">Impr.</th>
              </tr>
            </thead>
            <tbody>
              {pages.map((p) => (
                <tr key={p.url} className="border-b border-gray-100 last:border-0">
                  <td className="py-2 pr-3 text-gray-400">{p.priority_rank}</td>
                  <td className="py-2 pr-3">
                    <span className={`text-[10px] px-2 py-1 rounded-full font-bold uppercase ${BUCKET_STYLES[p.bucket] || 'bg-gray-100 text-gray-500'}`}>
                      {p.bucket}
                    </span>
                  </td>
                  <td className="py-2 pr-3 max-w-xs truncate text-gray-700" title={p.url}>{p.url}</td>
                  <td className="py-2 pr-3 text-right font-mono">{p.health_score}</td>
                  <td className="py-2 pr-3 text-right font-mono text-gray-600">{p.gsc ? p.gsc.clicks : '—'}</td>
                  <td className="py-2 pr-3 text-right font-mono text-gray-600">{p.gsc ? p.gsc.impressions : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-gray-400 mt-2">
            Dashes mean no Google Search Console data for that page — connect GSC for traffic-aware ranking.
          </p>
        </div>
      )}
    </div>
  )
}

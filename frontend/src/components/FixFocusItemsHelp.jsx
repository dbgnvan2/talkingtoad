import { useState, useEffect, useCallback } from 'react'
import { getFixFocus } from '../api.js'
import { getIssueHelp } from '../data/issueHelp.js'

// Fix Focus Items Help — a deduped glossary for the current Fix Focus checklist.
// Each DISTINCT issue code (across SEO + AI/GEO, however many pages it appears on)
// is explained exactly once: its plain-English "what it is" and the fix steps,
// from issueHelp.js. Sits beside FixFocusPanel on the Summary dashboard.
// Spec: docs/pending/2026-08-13_fix-focus-summary-and-help.md (FFS2)

export default function FixFocusItemsHelp({ jobId }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [items, setItems] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getFixFocus(jobId, 'all')
      // Collect distinct codes across both focuses; keep the highest priority_rank
      // occurrence and a human_description fallback for codes with no help entry.
      const byCode = new Map()
      for (const focus of ['seo', 'geo']) {
        const f = data && data[focus]
        if (!f || !f.pages) continue
        for (const page of f.pages) {
          for (const it of page.items) {
            const cur = byCode.get(it.issue_code)
            if (!cur || it.priority_rank > cur.priority_rank) {
              byCode.set(it.issue_code, {
                priority_rank: it.priority_rank,
                human_description: it.human_description,
              })
            }
          }
        }
      }
      const list = Array.from(byCode.entries())
        .map(([code, meta]) => ({ code, ...meta, help: getIssueHelp(code) }))
        .sort((a, b) => (b.priority_rank - a.priority_rank) || a.code.localeCompare(b.code))
      setItems(list)
    } catch (e) {
      setError(e.message || 'Failed to load item help')
    } finally {
      setLoading(false)
    }
  }, [jobId])

  useEffect(() => { load() }, [load])

  return (
    <div className="bg-white border border-indigo-200 rounded-2xl p-5 space-y-3">
      <h3 className="font-bold text-indigo-900 text-sm">Fix Focus Items Help</h3>
      <p className="text-xs text-indigo-700">
        What each item on your Fix Focus list means and how to fix it — each item shown once.
      </p>

      {loading && <p className="text-xs text-gray-500">Loading…</p>}
      {error && <p className="text-xs text-red-600">{error}</p>}
      {items && !loading && items.length === 0 && (
        <p className="text-xs text-gray-400">No Fix Focus items yet.</p>
      )}

      {items && !loading && items.length > 0 && (
        <ul className="space-y-3">
          {items.map((item) => {
            const title = (item.help && item.help.title) || item.human_description || item.code
            return (
              <li key={item.code} className="border border-gray-100 rounded-xl p-3">
                <p className="font-semibold text-gray-800 text-sm">{title}</p>
                {item.help && item.help.definition && (
                  <div className="mt-1">
                    <p className="text-[10px] font-semibold text-indigo-700 uppercase tracking-wide">What it is</p>
                    <p className="text-xs text-gray-700 leading-relaxed">{item.help.definition}</p>
                  </div>
                )}
                {item.help && item.help.fix && (
                  <div className="mt-1">
                    <p className="text-[10px] font-semibold text-emerald-700 uppercase tracking-wide">How to fix</p>
                    <p className="text-xs text-gray-700 leading-relaxed">{item.help.fix}</p>
                  </div>
                )}
                {!item.help && (
                  <p className="text-xs text-gray-500 mt-1">No detailed help entry for this item yet.</p>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

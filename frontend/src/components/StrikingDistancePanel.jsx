import { useEffect, useState } from 'react'
import { getStrikingDistance } from '../api.js'
import Spinner from './Spinner.jsx'

// Phase 4 U4.1 (PB3) — pages one rewrite away from page one. Read-only: the
// operator opens the page (where the rewriter lives) or copies the brief.
// Spec: docs/pending/2026-09-02_phase4-user-value.md#U4.1
export default function StrikingDistancePanel({ jobId, onPageClick, refreshKey = null }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(null)

  useEffect(() => {
    setData(null); setError(null)
    getStrikingDistance(jobId).then(setData).catch(e => setError(e.message))
  }, [jobId, refreshKey])

  async function copy(row) {
    try { await navigator.clipboard.writeText(row.rewrite_brief); setCopied(row.url) } catch { setCopied(null) }
  }

  if (error) return <div className="bg-white border border-red-200 rounded-2xl p-4 text-sm text-red-700" data-testid="striking-error">Could not load striking-distance pages: {error}</div>
  if (!data) return <div className="py-6"><Spinner /></div>
  // A response missing its shape (a proxy error page, a mocked fetch) must not
  // take the whole Results tree down.
  const pages = Array.isArray(data.pages) ? data.pages : []
  const b = data.basis || {}
  const band = `${b.band?.position_min ?? '?'}–${b.band?.position_max ?? '?'}`

  return (
    <section className="bg-white border border-gray-200 rounded-2xl p-5" data-testid="striking-distance">
      <div className="flex items-start justify-between gap-4 mb-2">
        <div>
          <h3 className="font-bold text-gray-800">Striking distance</h3>
          <p className="text-xs text-gray-500 mt-1">
            Pages ranking {band} with at least {b.impressions_min} monthly impressions — one rewrite away from page one.
            Open the page to use the Content Rewriter, or copy the brief.
          </p>
        </div>
      </div>
      {pages.length === 0 ? (
        <p className="text-sm text-gray-500" data-testid="striking-empty">
          {b.pages_with_ledger === 0
            ? `No Search Console data for this site yet (${b.pages_crawled} pages crawled, none with a ledger row). Attach a GSC priority file or ingest a performance bundle to see striking-distance pages.`
            : `None of the ${b.pages_with_ledger} pages with Search Console data rank in the ${band} band with ${b.impressions_min}+ impressions.`}
        </p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {pages.map(row => (
            <li key={row.url} className="py-3 flex flex-wrap items-center gap-3" data-testid="striking-row">
              <div className="flex-1 min-w-[16rem]">
                <button onClick={() => onPageClick?.(row.url)} className="font-mono text-xs text-blue-600 hover:underline text-left break-all">{row.url}</button>
                <p className="text-xs text-gray-600 mt-1">
                  Position <span className="font-bold">{row.position}</span> · {row.impressions} impressions · {row.clicks} clicks · health {row.health_score}
                  {row.target_query
                    ? <> · target: <span className="font-semibold">“{row.target_query}”</span></>
                    : <> · <span className="italic text-gray-400">no query in the seed file</span></>}
                </p>
              </div>
              <div className="flex gap-2">
                <button onClick={() => onPageClick?.(row.url)} className="text-xs font-bold px-3 py-1.5 rounded-full bg-green-50 text-green-700 hover:bg-green-100">Open page</button>
                <button onClick={() => copy(row)} className="text-xs font-bold px-3 py-1.5 rounded-full bg-white border border-gray-300 text-gray-700 hover:bg-gray-50" data-testid={`copy-${row.url}`}>
                  {copied === row.url ? 'Copied' : 'Copy brief'}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

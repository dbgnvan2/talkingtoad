import { useEffect, useState } from 'react'
import { getCrawlComparison } from '../api.js'

// Phase 4 U4.2 — compare with the previous scan of the same site. A delta
// earned under different rules (info detail, partial analysis) is struck
// through with the reason, never shown bare.
// Spec: docs/pending/2026-09-02_phase4-user-value.md#U4.2
export default function ComparisonCard({ jobId, refreshKey = null }) {
  const [cmp, setCmp] = useState(null)
  useEffect(() => {
    setCmp(null)
    getCrawlComparison(jobId).then(setCmp).catch(() => setCmp({ comparison_available: false }))
    // refreshKey: the summary's health score — a re-check changes it, and a
    // card still showing the old number beside the new one would contradict it.
  }, [jobId, refreshKey])

  if (!cmp || !cmp.comparison_available || !cmp.current || !cmp.previous) return null
  const when = cmp.previous.crawled_at ? new Date(cmp.previous.crawled_at).toLocaleDateString() : 'an earlier scan'
  const d = cmp.delta || {}
  const sign = n => (n > 0 ? `+${n}` : `${n}`)
  const ok = cmp.comparable !== false

  return (
    <div className="bg-white border border-gray-200 rounded-2xl px-5 py-4" data-testid="comparison-card">
      <p className="text-xs font-bold uppercase tracking-widest text-gray-500 mb-2">Compared with {when}</p>
      <div className="flex flex-wrap gap-6 text-sm">
        <div>
          <span className="text-gray-500">Health </span>
          <span className="font-bold">{cmp.previous.health_score} → {cmp.current.health_score}</span>{' '}
          <span data-testid="health-delta" className={ok ? (d.health_score >= 0 ? 'text-green-700 font-bold' : 'text-red-700 font-bold') : 'line-through text-gray-400'}>
            ({sign(d.health_score ?? 0)})
          </span>
        </div>
        <div>
          <span className="text-gray-500">Issues </span>
          <span className="font-bold">{cmp.previous.total_issues} → {cmp.current.total_issues}</span>{' '}
          <span className={ok ? 'text-gray-700' : 'line-through text-gray-400'}>({sign(d.total_issues ?? 0)})</span>
        </div>
        <div>
          <span className="text-gray-500">Critical </span><span className="font-bold">{sign(d.critical ?? 0)}</span>
          <span className="text-gray-500 ml-3">Warnings </span><span className="font-bold">{sign(d.warning ?? 0)}</span>
        </div>
      </div>
      {!ok && (
        <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mt-3" data-testid="comparison-reason">
          Not comparable: {cmp.reason}. The two scans measured different things, so the health delta is struck through.
        </p>
      )}
    </div>
  )
}

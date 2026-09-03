import { useState } from 'react'
import { runWpAudit } from '../api.js'

// Phase 4 U4.4 — run the read-only WordPress configuration audit from the app.
// AP1-AP3 (2026-09-03): Site Health, plugin overlaps and inactive themes have
// always been in the payload and reached only the PDF, so the audit's most
// actionable output was invisible in the app (P25/P16). Each block renders only
// when it has content — a heading over an empty list reads as 'checked, all
// clear', and Site Health can simply fail to load (see `not_inspected`).
// Spec: docs/functional-specification.md §7.8
export default function WpAuditPanel({ jobId, initial = null }) {
  const [report, setReport] = useState(initial)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function run() {
    setBusy(true); setError(null)
    try { setReport(await runWpAudit(jobId)) } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  return (
    <section className="bg-white border border-gray-200 rounded-2xl p-5" data-testid="wp-audit">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-bold text-gray-800">WordPress configuration</h3>
          <p className="text-xs text-gray-500 mt-1">Reads the site's plugins, theme and updates through the WordPress API. Read-only; needs the stored admin credentials for this site.</p>
        </div>
        <button onClick={run} disabled={busy} className="text-xs font-bold px-3 py-1.5 rounded-full bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 shrink-0">
          {busy ? 'Reading…' : report ? 'Run again' : 'Run WordPress audit'}
        </button>
      </div>
      {error && <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mt-3" data-testid="wp-audit-error">{error}</p>}
      {report && (
        <div className="mt-4 text-sm" data-testid="wp-audit-report">
          <p className="text-gray-700">
            <span className="font-bold">{report.plugins_total}</span> plugins · <span className="font-bold">{report.plugins_active}</span> active · <span className="font-bold">{report.plugins_inactive}</span> inactive
          </p>
          {report.pending_updates?.length > 0 ? (
            <div className="mt-3">
              <p className="text-xs font-bold uppercase tracking-widest text-amber-700">Pending updates</p>
              <ul className="mt-1 space-y-1">
                {report.pending_updates.map(p => <li key={p.slug} className="text-gray-700">{p.name} <span className="text-gray-400">{p.version} → {p.new_version}</span></li>)}
              </ul>
            </div>
          ) : <p className="mt-3 text-xs text-green-700">No pending plugin updates.</p>}
          {report.inactive_plugins?.length > 0 && (
            <div className="mt-3">
              <p className="text-xs font-bold uppercase tracking-widest text-gray-500">Inactive plugins (consider removing)</p>
              <ul className="mt-1 space-y-1">{report.inactive_plugins.map(p => <li key={p.slug} className="text-gray-700">{p.name}</li>)}</ul>
            </div>
          )}
          {report.site_health?.length > 0 && (
            <div className="mt-3">
              <p className="text-xs font-bold uppercase tracking-widest text-gray-500">WordPress Site Health says</p>
              <ul className="mt-1 space-y-1">
                {report.site_health.map((h, i) => {
                  // The status is preserved by `parse_site_health` precisely so a
                  // critical can be told from a recommendation. The PDF dropped it
                  // and printed them identically; this must not.
                  const critical = String(h.status).toLowerCase() === 'critical'
                  return (
                    <li
                      key={`${h.label}-${i}`}
                      data-testid={critical ? 'wp-health-critical' : 'wp-health-recommended'}
                      className={critical ? 'text-red-700 font-semibold' : 'text-amber-700'}
                    >
                      {h.label}
                      <span className="text-gray-400 text-xs"> · {h.source}</span>
                    </li>
                  )
                })}
              </ul>
            </div>
          )}
          {report.overlaps?.length > 0 && (
            <div className="mt-3">
              <p className="text-xs font-bold uppercase tracking-widest text-gray-500">Two plugins doing one job</p>
              <ul className="mt-1 space-y-2">
                {report.overlaps.map(o => (
                  <li key={o.responsibility} className="text-gray-700">
                    <span className="font-semibold">{o.responsibility}</span>
                    <span className="text-gray-500"> — {o.plugins.join(', ')}</span>
                    {o.why_one_owner && <p className="text-xs text-gray-500 mt-0.5">{o.why_one_owner}</p>}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {report.inactive_themes?.length > 0 && (
            <div className="mt-3">
              <p className="text-xs font-bold uppercase tracking-widest text-gray-500">Inactive themes (consider removing)</p>
              <ul className="mt-1 space-y-1">{report.inactive_themes.map(t => <li key={t} className="text-gray-700">{t}</li>)}</ul>
            </div>
          )}
          {report.not_inspected?.length > 0 && (
            <p className="mt-3 text-xs text-gray-500">Not inspected: {report.not_inspected.join('; ')}.</p>
          )}
        </div>
      )}
    </section>
  )
}

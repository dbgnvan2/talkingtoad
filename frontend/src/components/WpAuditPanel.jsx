import { useState } from 'react'
import { runWpAudit } from '../api.js'

// Phase 4 U4.4 — run the read-only WordPress configuration audit from the app.
// Spec: docs/pending/2026-09-02_phase4-user-value.md#U4.4
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
          {report.not_inspected?.length > 0 && (
            <p className="mt-3 text-xs text-gray-500">Not inspected: {report.not_inspected.join('; ')}.</p>
          )}
        </div>
      )}
    </section>
  )
}

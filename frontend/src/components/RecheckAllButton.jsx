import { useEffect, useRef, useState } from 'react'
import { getRecheckAllStatus, startRecheckAll } from '../api.js'

// Phase 4 U4.3 — re-check every stored page of this scan in place. Distinct
// from Rescan (a fresh crawl, a new job). Polls progress and refreshes the
// summary when finished.
// Spec: docs/pending/2026-09-02_phase4-user-value.md#U4.3
export const RECHECK_POLL_MS = 2000

export default function RecheckAllButton({ jobId, onFinished }) {
  const [prog, setProg] = useState(null)
  const [error, setError] = useState(null)
  const [starting, setStarting] = useState(false)
  const timer = useRef(null)
  const wasRunning = useRef(false)

  useEffect(() => () => clearTimeout(timer.current), [])

  async function poll() {
    try {
      const s = await getRecheckAllStatus(jobId)
      setProg(s)
      if (s.running) {
        wasRunning.current = true
        timer.current = setTimeout(poll, RECHECK_POLL_MS)
      } else if (wasRunning.current) {
        wasRunning.current = false
        onFinished?.(s)
      }
    } catch (e) {
      // A failed poll must not leave the button disabled for ever.
      setError(e.message); setProg(p => (p ? { ...p, running: false } : p)); wasRunning.current = false
    }
  }

  async function start() {
    if (starting) return
    setStarting(true); setError(null)
    try {
      await startRecheckAll(jobId)
      wasRunning.current = true
      setProg({ running: true, done: 0, total: null })
      timer.current = setTimeout(poll, RECHECK_POLL_MS)
    } catch (e) { setError(e.message) } finally { setStarting(false) }
  }

  const running = starting || prog?.running
  return (
    <span className="inline-flex items-center gap-2">
      <button
        onClick={start}
        disabled={running}
        title="Re-fetch every page of this scan and update its findings and score in place. To discover new pages, use Rescan on the home page."
        className="px-3 py-1.5 bg-white border border-gray-300 rounded-lg text-xs font-bold shadow-sm disabled:opacity-60"
        data-testid="recheck-all"
      >
        {running ? (prog ? `Re-checking ${prog.done ?? 0}${prog.total != null ? ` / ${prog.total}` : ''}` : 'Starting…') : 'Re-check all pages'}
      </button>
      {error && <span className="text-red-600 text-xs" data-testid="recheck-error">{error}</span>}
    </span>
  )
}

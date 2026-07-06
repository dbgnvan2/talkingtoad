import { useEffect, useState } from 'react'
import { testLlmConnection, gscStatus } from '../api'

/**
 * ConnectionsPanel — modal that tests the app's two external integrations:
 *   1. LLM / AI provider  -> GET /api/ai/test
 *   2. Google Search Console -> GET /api/gsc/status
 *
 * Each row has its own idle/loading/success/error state. Mirrors SettingsPanel's
 * modal shell and adds a11y (role="dialog", aria-modal, Escape + backdrop close).
 *
 * Spec: docs/pending/2026-07-06_connections-panel.md
 */
export default function ConnectionsPanel({ onClose }) {
  // Hooks must run before any early return (react-hooks/rules-of-hooks).
  const [llm, setLlm] = useState({ status: 'idle', message: '', sample: '' })
  const [gsc, setGsc] = useState({ status: 'idle', data: null, error: '' })

  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  async function handleTestLlm() {
    setLlm({ status: 'loading', message: '', sample: '' })
    try {
      const data = await testLlmConnection()
      if (data.success) {
        setLlm({ status: 'success', message: data.message || 'AI connection successful!', sample: data.sample || '' })
      } else {
        setLlm({ status: 'error', message: data.message || 'AI connection failed.', sample: '' })
      }
    } catch (err) {
      setLlm({ status: 'error', message: err.message || 'AI connection failed.', sample: '' })
    }
  }

  async function handleTestGsc() {
    setGsc({ status: 'loading', data: null, error: '' })
    try {
      const data = await gscStatus()
      setGsc({ status: 'success', data, error: '' })
    } catch (err) {
      setGsc({ status: 'error', data: null, error: err.message || 'GSC check failed.' })
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label="Connections" className="bg-white rounded-3xl shadow-2xl max-w-md w-full p-8" onClick={e => e.stopPropagation()}>
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-xl font-black text-gray-800">Connections</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl" aria-label="Close connections">&times;</button>
        </div>

        <div className="space-y-6">
          {/* LLM / AI provider */}
          <ConnectionRow
            title="LLM / AI provider"
            desc="Runs a real round-trip against the configured AI provider."
            buttonLabel="Test connection"
            loading={llm.status === 'loading'}
            onTest={handleTestLlm}
          >
            {llm.status === 'success' && (
              <div className="text-sm text-green-700 bg-green-50 border border-green-100 rounded-lg p-3">
                <p className="font-bold">✓ {llm.message}</p>
                {llm.sample && (
                  <p className="mt-1 text-xs text-green-800 break-words">Sample: {llm.sample}</p>
                )}
              </div>
            )}
            {llm.status === 'error' && (
              <div className="text-sm text-red-700 bg-red-50 border border-red-100 rounded-lg p-3">
                <p className="font-bold">✗ {llm.message}</p>
              </div>
            )}
          </ConnectionRow>

          {/* Google Search Console */}
          <ConnectionRow
            title="Google Search Console"
            desc="Checks whether GSC OAuth is configured and connected."
            buttonLabel="Test connection"
            loading={gsc.status === 'loading'}
            onTest={handleTestGsc}
          >
            {gsc.status === 'success' && gsc.data && (
              gsc.data.configured === false ? (
                <div className="text-sm text-amber-700 bg-amber-50 border border-amber-100 rounded-lg p-3">
                  <p className="font-bold">GSC not configured</p>
                  <p className="mt-1 text-xs text-amber-800">
                    OAuth environment variables are unset on the server, so GSC is disabled.
                  </p>
                </div>
              ) : gsc.data.connected ? (
                <div className="text-sm text-green-700 bg-green-50 border border-green-100 rounded-lg p-3">
                  <p className="font-bold">✓ Connected</p>
                  <p className="mt-1 text-xs text-green-800">
                    {(gsc.data.properties?.length ?? 0)} propert{(gsc.data.properties?.length === 1) ? 'y' : 'ies'} available.
                  </p>
                </div>
              ) : (
                <div className="text-sm text-amber-700 bg-amber-50 border border-amber-100 rounded-lg p-3">
                  <p className="font-bold">Configured but not connected</p>
                  <p className="mt-1 text-xs text-amber-800">
                    The GSC OAuth client is set up on the server, but no Google account is linked
                    yet. Linking is a one-time step and lives on a crawl's Results page:
                  </p>
                  <ol className="mt-2 text-xs text-amber-800 list-decimal list-outside pl-4 space-y-1">
                    <li>
                      Run a crawl of your site first — Search Console data is matched page by page,
                      so there must be a crawl to attach it to.
                    </li>
                    <li>
                      On that crawl's Results page, scroll to the{' '}
                      <span className="font-semibold">Google Search Console</span> panel and click{' '}
                      <span className="font-semibold">Connect</span>.
                    </li>
                    <li>
                      Sign in with a Google account that has Search Console access to this site, and
                      grant consent on Google's screen.
                    </li>
                    <li>
                      You'll return connected. Choose your property to pull in performance data, then
                      re-run this test to confirm it shows{' '}
                      <span className="font-semibold">Connected</span>.
                    </li>
                  </ol>
                  <p className="mt-2 text-xs text-amber-800">
                    The link is shared for the whole app, so you only do this once — not per crawl.
                  </p>
                </div>
              )
            )}
            {gsc.status === 'error' && (
              <div className="text-sm text-red-700 bg-red-50 border border-red-100 rounded-lg p-3">
                <p className="font-bold">✗ {gsc.error}</p>
              </div>
            )}
          </ConnectionRow>
        </div>

        <div className="flex mt-8 pt-6 border-t border-gray-100">
          <button
            onClick={onClose}
            className="flex-1 py-3 bg-green-600 text-white rounded-xl text-sm font-bold shadow-lg hover:bg-green-700 transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  )
}

function ConnectionRow({ title, desc, buttonLabel, loading, onTest, children }) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between items-start gap-3">
        <div>
          <p className="font-bold text-gray-800">{title}</p>
          <p className="text-xs text-gray-400">{desc}</p>
        </div>
        <button
          onClick={onTest}
          disabled={loading}
          className="shrink-0 px-4 py-2 text-sm font-bold text-white bg-green-600 rounded-xl shadow hover:bg-green-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed inline-flex items-center gap-2"
        >
          {loading && (
            <span
              className="inline-block w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin"
              role="status"
              aria-label="Testing"
            />
          )}
          {loading ? 'Testing…' : buttonLabel}
        </button>
      </div>
      {children}
    </div>
  )
}

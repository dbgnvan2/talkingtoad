import { useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ProgressBar from '../components/ProgressBar.jsx'
import { usePolling, isTerminal } from '../hooks/usePolling.js'
import { getStatus, cancelCrawl } from '../api.js'

export default function Progress() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const [status, setStatus] = useState(null)
  const [cancelling, setCancelling] = useState(false)
  const [cancelError, setCancelError] = useState(null)

  const fetchStatus = useCallback(() => getStatus(jobId), [jobId])

  usePolling(
    fetchStatus,
    data => {
      setStatus(data)
      if (data.status === 'complete') {
        navigate(`/results/${jobId}`)
      }
    },
    data => isTerminal(data.status)
  )

  async function handleCancel() {
    setCancelling(true)
    setCancelError(null)
    try {
      await cancelCrawl(jobId)
      setStatus(s => ({ ...s, status: 'cancelled' }))
    } catch (err) {
      setCancelError(err.message)
    } finally {
      setCancelling(false)
    }
  }

  const pct = progress(status)
  const eta = etaString(status)

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-lg">
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8 space-y-6">
          <div className="text-center">
            <h2 className="text-xl font-semibold text-gray-800">
              {statusHeading(status?.status)}
            </h2>
            {status?.target_url && (
              <p className="mt-1 text-sm text-gray-500 truncate">{status.target_url}</p>
            )}
          </div>

          <ProgressBar pct={pct} />

          <div className="flex justify-between text-sm text-gray-600">
            <span>
              {status?.pages_crawled ?? 0} page{status?.pages_crawled !== 1 ? 's' : ''} crawled
              {status?.pages_total ? ` of ${status.pages_total}` : ''}
            </span>
            {eta && <span>{eta}</span>}
          </div>

          {status?.current_url && (
            <p className="text-xs text-gray-400 truncate">
              Crawling: {status.current_url}
            </p>
          )}

          {cancelError && (
            <p className="text-sm text-red-600 bg-red-50 rounded px-3 py-2">{cancelError}</p>
          )}

          {status?.status === 'failed' && (
            <p className="text-sm text-red-600 bg-red-50 rounded px-3 py-2">
              The crawl failed. Please try again.
            </p>
          )}

          {status?.status === 'cancelled' && (
            <p className="text-sm text-amber-600 bg-amber-50 rounded px-3 py-2">
              Crawl was cancelled.
            </p>
          )}

          <div className="flex gap-3">
            {isActive(status?.status) && (
              <button
                onClick={handleCancel}
                disabled={cancelling}
                className="flex-1 border border-gray-300 text-gray-700 rounded-lg py-2 text-sm hover:bg-gray-50 disabled:opacity-50"
              >
                {cancelling ? 'Cancelling…' : 'Cancel crawl'}
              </button>
            )}
            {isTerminal(status?.status) && status?.status !== 'complete' && (
              <button
                onClick={() => navigate('/')}
                className="flex-1 bg-green-600 text-white rounded-lg py-2 text-sm hover:bg-green-700"
              >
                Start a new crawl
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function statusHeading(s) {
  if (!s) return 'Starting crawl…'
  if (s === 'queued') return 'Queued — starting soon…'
  if (s === 'running') return 'Crawling your site…'
  if (s === 'complete') return 'Crawl complete — loading results…'
  if (s === 'failed') return 'Crawl failed'
  if (s === 'cancelled') return 'Crawl cancelled'
  return 'Crawling…'
}

function isActive(s) {
  return s === 'queued' || s === 'running'
}

function progress(status) {
  if (!status || !status.pages_total || status.pages_crawled == null) return null
  if (status.pages_total === 0) return null
  return Math.round((status.pages_crawled / status.pages_total) * 100)
}

function etaString(status) {
  if (!status || !status.pages_total || !status.pages_crawled) return null
  if (status.pages_crawled < 5) return null
  if (!status.started_at) return null
  const elapsed = (Date.now() - new Date(status.started_at).getTime()) / 1000
  const rate = status.pages_crawled / elapsed
  if (rate <= 0) return null
  const remaining = (status.pages_total - status.pages_crawled) / rate
  if (remaining < 5) return null
  const mins = Math.ceil(remaining / 60)
  return mins <= 1 ? 'about 1 minute left' : `about ${mins} minutes left`
}

import { useState, useEffect, useRef } from 'react'
import { startBatchOptimize, getBatchStatus, pauseBatch, resumeBatch, cancelBatch } from '../api'

/**
 * Panel for batch image optimization.
 *
 * Shows progress, controls (pause/resume/cancel), and results.
 */
export default function BatchOptimizePanel({ jobId, selectedImages, onClose, onComplete }) {
  const [status, setStatus] = useState(null)
  const [batchId, setBatchId] = useState(null)
  const [error, setError] = useState(null)
  const [starting, setStarting] = useState(false)
  const pollRef = useRef(null)

  // Options
  const [targetWidth, setTargetWidth] = useState(1200)
  const [applyGps, setApplyGps] = useState(true)
  const [generateGeoMetadata, setGenerateGeoMetadata] = useState(true)
  const [parallelLimit, setParallelLimit] = useState(3)

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
      }
    }
  }, [])

  const startPolling = (id) => {
    pollRef.current = setInterval(async () => {
      try {
        const data = await getBatchStatus(id)
        setStatus(data)

        // Stop polling when done
        if (data.status === 'completed' || data.status === 'cancelled') {
          clearInterval(pollRef.current)
          pollRef.current = null
          if (onComplete) onComplete(data)
        }
      } catch (err) {
        console.error('Failed to get batch status:', err)
      }
    }, 2000)
  }

  const handleStart = async () => {
    setStarting(true)
    setError(null)
    try {
      const imageUrls = selectedImages.map(img => img.url || img)
      const result = await startBatchOptimize(jobId, imageUrls, {
        targetWidth,
        applyGps,
        generateGeoMetadata,
        parallelLimit,
      })

      setBatchId(result.batch_id)
      setStatus({
        status: 'running',
        total: imageUrls.length,
        completed: 0,
        failed: 0,
        progress_percent: 0,
        results: [],
      })

      startPolling(result.batch_id)
    } catch (err) {
      setError(err.message)
    } finally {
      setStarting(false)
    }
  }

  const handlePause = async () => {
    try {
      const data = await pauseBatch(batchId)
      setStatus(data)
    } catch (err) {
      setError(err.message)
    }
  }

  const handleResume = async () => {
    try {
      const data = await resumeBatch(batchId)
      setStatus(data)
      startPolling(batchId)
    } catch (err) {
      setError(err.message)
    }
  }

  const handleCancel = async () => {
    if (!confirm('Are you sure you want to cancel this batch?')) return
    try {
      const data = await cancelBatch(batchId)
      setStatus(data)
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    } catch (err) {
      setError(err.message)
    }
  }

  const isRunning = status?.status === 'running'
  const isPaused = status?.status === 'paused'
  const isDone = status?.status === 'completed' || status?.status === 'cancelled'

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 p-6 rounded-t-xl">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-2xl font-black text-gray-800">Batch Optimize</h2>
              <p className="text-sm text-gray-600 mt-1">
                {!status && `${selectedImages.length} images selected`}
                {status && `${status.status} - ${status.completed + status.failed}/${status.total}`}
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
            >
              ×
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Error */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="text-red-800 font-medium">Error</p>
              <p className="text-red-700 text-sm mt-1">{error}</p>
            </div>
          )}

          {/* Pre-start options */}
          {!status && (
            <div className="space-y-4">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-sm font-bold text-blue-900 mb-2">
                  Ready to optimize {selectedImages.length} images
                </p>
                <p className="text-xs text-blue-700">
                  Each image will be: resized, converted to WebP, GPS injected, and uploaded to WordPress.
                </p>
              </div>

              {/* Options */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Target Width
                  </label>
                  <input
                    type="number"
                    value={targetWidth}
                    onChange={(e) => setTargetWidth(parseInt(e.target.value) || 1200)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    min={200}
                    max={2000}
                    step={100}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Parallel Limit
                  </label>
                  <select
                    value={parallelLimit}
                    onChange={(e) => setParallelLimit(parseInt(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  >
                    <option value={1}>1 at a time</option>
                    <option value={2}>2 at a time</option>
                    <option value={3}>3 at a time</option>
                    <option value={5}>5 at a time</option>
                  </select>
                </div>
              </div>

              <div className="space-y-2">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={applyGps}
                    onChange={(e) => setApplyGps(e.target.checked)}
                    className="rounded border-gray-300 text-blue-600"
                  />
                  <span className="text-sm text-gray-700">Inject GPS coordinates</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={generateGeoMetadata}
                    onChange={(e) => setGenerateGeoMetadata(e.target.checked)}
                    className="rounded border-gray-300 text-purple-600"
                  />
                  <span className="text-sm text-gray-700">Generate AI alt text & description</span>
                </label>
              </div>
            </div>
          )}

          {/* Progress */}
          {status && (
            <div className="space-y-4">
              {/* Progress bar */}
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="font-medium text-gray-700">
                    {status.status === 'completed' ? 'Complete' :
                     status.status === 'cancelled' ? 'Cancelled' :
                     status.status === 'paused' ? 'Paused' : 'Processing...'}
                  </span>
                  <span className="text-gray-500">{status.progress_percent}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                  <div
                    className={`h-full transition-all duration-300 ${
                      status.status === 'cancelled' ? 'bg-red-500' :
                      status.status === 'completed' ? 'bg-green-500' :
                      status.status === 'paused' ? 'bg-amber-500' : 'bg-blue-500'
                    }`}
                    style={{ width: `${status.progress_percent}%` }}
                  />
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-4 text-center">
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-2xl font-bold text-gray-800">{status.total}</p>
                  <p className="text-xs text-gray-500">Total</p>
                </div>
                <div className="bg-green-50 rounded-lg p-3">
                  <p className="text-2xl font-bold text-green-600">{status.completed}</p>
                  <p className="text-xs text-gray-500">Completed</p>
                </div>
                <div className="bg-red-50 rounded-lg p-3">
                  <p className="text-2xl font-bold text-red-600">{status.failed}</p>
                  <p className="text-xs text-gray-500">Failed</p>
                </div>
              </div>

              {/* Results list */}
              {status.results && status.results.length > 0 && (
                <div className="border border-gray-200 rounded-lg max-h-64 overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 sticky top-0">
                      <tr>
                        <th className="text-left px-3 py-2 font-medium text-gray-600">Image</th>
                        <th className="text-left px-3 py-2 font-medium text-gray-600">Status</th>
                        <th className="text-left px-3 py-2 font-medium text-gray-600">Size</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {status.results.map((r) => (
                        <tr key={r.image_url} className={r.success ? '' : 'bg-red-50'}>
                          <td className="px-3 py-2 truncate max-w-[200px]" title={r.image_url}>
                            {r.image_url.split('/').pop()}
                          </td>
                          <td className="px-3 py-2">
                            {r.success ? (
                              <span className="text-green-600 font-medium">✓</span>
                            ) : (
                              <span className="text-red-600" title={r.error}>✗</span>
                            )}
                          </td>
                          <td className="px-3 py-2 text-gray-600">
                            {r.file_size_kb ? `${r.file_size_kb.toFixed(1)} KB` : '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-white border-t border-gray-200 p-6 rounded-b-xl flex gap-3">
          {!status && (
            <>
              <button
                onClick={onClose}
                className="flex-1 border border-gray-300 text-gray-700 rounded-lg py-2 text-sm hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleStart}
                disabled={starting}
                className="flex-1 bg-blue-600 text-white rounded-lg py-2 text-sm hover:bg-blue-700 disabled:opacity-50"
              >
                {starting ? 'Starting...' : 'Start Batch'}
              </button>
            </>
          )}

          {status && !isDone && (
            <>
              {isRunning && (
                <button
                  onClick={handlePause}
                  className="flex-1 bg-amber-500 text-white rounded-lg py-2 text-sm hover:bg-amber-600"
                >
                  Pause
                </button>
              )}
              {isPaused && (
                <button
                  onClick={handleResume}
                  className="flex-1 bg-green-600 text-white rounded-lg py-2 text-sm hover:bg-green-700"
                >
                  Resume
                </button>
              )}
              <button
                onClick={handleCancel}
                className="flex-1 bg-red-600 text-white rounded-lg py-2 text-sm hover:bg-red-700"
              >
                Cancel
              </button>
            </>
          )}

          {isDone && (
            <button
              onClick={onClose}
              className="flex-1 bg-gray-600 text-white rounded-lg py-2 text-sm hover:bg-gray-700"
            >
              Close
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

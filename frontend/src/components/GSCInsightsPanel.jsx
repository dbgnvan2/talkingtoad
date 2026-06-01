import { useState, useEffect, useCallback } from 'react'
import { gscStatus, gscConnectUrl, gscDisconnect, gscIngest } from '../api'

const V4_EXPLAINER = {
  what: 'Connects Google Search Console to show how your pages actually perform in Google (clicks, impressions, position) including AI surfaces.',
  why: "It's the reality check \u2014 it tells you which technically-healthy pages actually earn traffic, so you fix the pages that matter, and whether your GEO work is being cited.",
  goodVsBad: 'A healthy page with high impressions but low clicks = a title/answerability problem to fix; a healthy page with zero traffic = a "Hidden Gem" to re-target.',
  misleading: 'GSC data lags ~2\u20133 days and a brand-new/low-traffic site may show zero rows \u2014 absence of data is not a failure.',
  howToUse: 'Connect \u2192 pick your siteOwner property \u2192 Ingest \u2192 review the flagged pages.',
}

function GSCInsightsPanel({ jobId }) {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [ingesting, setIngesting] = useState(false)
  const [ingestDone, setIngestDone] = useState(false)
  const [selectedProperty, setSelectedProperty] = useState(null)
  const [performanceData, setPerformanceData] = useState({})
  const [showExplainer, setShowExplainer] = useState(false)

  const fetchStatus = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await gscStatus()
      setStatus(data)
      if (data.connected && data.properties?.length > 0) {
        const siteOwner = data.properties.find(p => p.permissionLevel === 'siteOwner')
        setSelectedProperty(siteOwner || data.properties[0])
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStatus()
  }, [fetchStatus])

  const handleDisconnect = async () => {
    try {
      await gscDisconnect()
      setStatus({ connected: false, properties: [], configured: true })
      setSelectedProperty(null)
      setPerformanceData({})
      setIngestDone(false)
    } catch (err) {
      setError(err.message)
    }
  }

  const handleIngest = async () => {
    if (!selectedProperty || !jobId) return
    setIngesting(true)
    setError(null)
    try {
      await gscIngest(selectedProperty.siteUrl, jobId)
      setIngestDone(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setIngesting(false)
    }
  }

  // Loading skeleton
  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-gray-200 rounded w-1/3"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
        </div>
      </div>
    )
  }

  // 503 / not configured — quiet empty state
  if (status && !status.configured) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-500">Google Search Console</h3>
        <p className="text-sm text-gray-400 mt-2">GSC not configured</p>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-red-600">Google Search Console</h3>
        <p className="text-sm text-red-500 mt-2">Error: {error}</p>
        <button
          onClick={fetchStatus}
          className="mt-2 text-sm text-blue-600 hover:text-blue-800"
        >
          Retry
        </button>
      </div>
    )
  }

  // Not connected — show Connect button
  if (!status || !status.connected) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900">Google Search Console</h3>
        <p className="text-sm text-gray-600 mt-2">
          Connect to see how your pages perform in Google Search.
        </p>
        <a
          href={gscConnectUrl()}
          className="inline-block mt-3 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700"
        >
          Connect Google Search Console
        </a>
      </div>
    )
  }

  // Connected — full panel
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Google Search Console</h3>
        <button
          onClick={() => setShowExplainer(!showExplainer)}
          className="text-sm text-blue-600 hover:text-blue-800"
          aria-label="Learn more about GSC Insights"
        >
          {showExplainer ? 'Hide' : 'Learn more'} ?
        </button>
      </div>

      {showExplainer && (
        <div className="mb-4 p-3 bg-blue-50 rounded text-sm text-gray-700 space-y-2">
          <p><strong>What it is:</strong> {V4_EXPLAINER.what}</p>
          <p><strong>Why it's useful:</strong> {V4_EXPLAINER.why}</p>
          <p><strong>Good vs bad:</strong> {V4_EXPLAINER.goodVsBad}</p>
          <p><strong>How it can mislead:</strong> {V4_EXPLAINER.misleading}</p>
          <p><strong>How to use:</strong> {V4_EXPLAINER.howToUse}</p>
        </div>
      )}

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">Property</label>
          <select
            value={selectedProperty?.siteUrl || ''}
            onChange={(e) => {
              const prop = status.properties.find(p => p.siteUrl === e.target.value)
              setSelectedProperty(prop)
            }}
            className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md"
          >
            {status.properties.map(prop => (
              <option key={prop.siteUrl} value={prop.siteUrl}>
                {prop.siteUrl} {prop.permissionLevel === 'siteOwner' ? '(Owner)' : ''}
              </option>
            ))}
          </select>
        </div>

        <div className="flex space-x-3">
          <button
            onClick={handleIngest}
            disabled={ingesting || !selectedProperty || !jobId}
            className="px-4 py-2 bg-green-600 text-white text-sm font-medium rounded hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {ingesting ? 'Ingesting...' : 'Ingest Performance Data'}
          </button>
          <button
            onClick={handleDisconnect}
            className="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded hover:bg-red-700"
          >
            Disconnect
          </button>
        </div>

        {ingestDone && Object.keys(performanceData).length === 0 && (
          <div className="p-3 bg-green-50 border border-green-200 rounded text-sm text-green-700">
            Performance data ingested successfully. Use the page audit panel to view per-page GSC metrics.
          </div>
        )}

        {Object.keys(performanceData).length > 0 && (
          <div className="mt-4">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Page Performance</h4>
            <div className="space-y-2">
              {Object.entries(performanceData).map(([url, data]) => (
                <div key={url} className="p-3 bg-gray-50 rounded">
                  <p className="text-sm font-medium text-gray-900 truncate">{url}</p>
                  {data.error ? (
                    <p className="text-sm text-red-500 mt-1">Error: {data.error}</p>
                  ) : (
                    <>
                      <div className="mt-1 grid grid-cols-3 gap-2 text-sm">
                        <div>
                          <span className="text-gray-500">Clicks:</span>{' '}
                          <span className="font-medium">{data.clicks || 0}</span>
                        </div>
                        <div>
                          <span className="text-gray-500">Impressions:</span>{' '}
                          <span className="font-medium">{data.impressions || 0}</span>
                        </div>
                        <div>
                          <span className="text-gray-500">Position:</span>{' '}
                          <span className="font-medium">{data.position?.toFixed(1) || 'N/A'}</span>
                        </div>
                      </div>
                      {data.reviewFlag && (
                        <div className="mt-2 p-2 bg-yellow-50 border border-yellow-200 rounded">
                          <p className="text-xs text-yellow-800">
                            <strong>Review for Improvements:</strong> {data.reviewFlag}
                          </p>
                        </div>
                      )}
                    </>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default GSCInsightsPanel

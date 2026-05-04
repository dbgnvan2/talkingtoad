import React, { useState } from 'react'
import { getOrphanedMedia } from '../api.js'

export default function OrphanedImagesPanel({ jobId, domain }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleScan() {
    setLoading(true)
    setError(null)
    try {
      const result = await getOrphanedMedia(jobId)
      setData(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-800">{domain ? `Orphaned Images - ${domain}` : 'Orphaned Images'}</h2>
          <p className="text-sm text-gray-500 mt-1">Images in the WordPress Media Library that are not referenced on any crawled page.</p>
        </div>
        <button
          onClick={handleScan}
          disabled={loading}
          className="px-5 py-2.5 bg-purple-600 text-white font-bold rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center gap-2"
        >
          {loading ? (
            <>
              <span className="animate-spin">&#8635;</span>
              Scanning WordPress...
            </>
          ) : (
            <>Scan Media Library</>
          )}
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl">
          <p className="text-red-700 font-medium">Error: {error}</p>
        </div>
      )}

      {!data && !loading && !error && (
        <div className="py-20 text-center bg-white rounded-2xl border border-gray-100">
          <p className="text-5xl mb-4">🖼</p>
          <p className="text-gray-400 font-medium">Click "Scan Media Library" to compare WordPress images against crawled pages.</p>
        </div>
      )}

      {data && (
        <div className="space-y-4">
          {/* Stats bar */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-white p-4 rounded-xl border border-gray-200 text-center">
              <p className="text-2xl font-bold text-gray-800">{data.orphaned_media?.length + (data.count - (data.orphaned_media?.length || 0)) || data.count}</p>
              <p className="text-xs text-gray-500 uppercase font-bold">Total WP Media</p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-red-200 text-center">
              <p className="text-2xl font-bold text-red-600">{data.count}</p>
              <p className="text-xs text-red-500 uppercase font-bold">Orphaned</p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-green-200 text-center">
              <p className="text-2xl font-bold text-green-600">{(data.orphaned_media?.length + (data.count - (data.orphaned_media?.length || 0)) || 0) - data.count}</p>
              <p className="text-xs text-green-500 uppercase font-bold">In Use</p>
            </div>
          </div>

          {data.count === 0 ? (
            <div className="py-12 bg-white rounded-2xl border border-green-200 text-center">
              <p className="text-green-600 text-2xl mb-2">✓</p>
              <p className="text-green-700 font-medium">All WordPress media images are referenced on at least one crawled page.</p>
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 bg-gray-50">
                <p className="text-sm font-bold text-gray-700">{data.count} orphaned image{data.count !== 1 ? 's' : ''}</p>
              </div>
              <div className="divide-y divide-gray-100 max-h-[600px] overflow-y-auto">
                {(data.orphaned_media || []).map(item => (
                  <div key={item.id} className="flex items-center gap-4 px-6 py-3 hover:bg-gray-50">
                    <img
                      src={item.url}
                      alt={item.alt_text || ''}
                      className="w-14 h-14 object-cover rounded-lg border border-gray-200 flex-shrink-0"
                      onError={e => { e.target.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"><rect fill="%23f3f4f6"/></svg>' }}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-bold text-gray-800 truncate">{item.title}</p>
                      <p className="text-xs font-mono text-gray-400 truncate">{item.url.split('/').pop()}</p>
                      <div className="flex items-center gap-3 mt-0.5">
                        <span className="text-xs text-gray-400">{item.mime_type}</span>
                        {item.file_size_kb && <span className="text-xs text-gray-400">{item.file_size_kb} KB</span>}
                        {item.dimensions && <span className="text-xs text-gray-400">{item.dimensions}</span>}
                        {item.post_parent === 0 && <span className="text-xs text-red-500 font-bold">Unattached</span>}
                      </div>
                    </div>
                    <a
                      href={item.admin_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-3 py-1.5 text-xs font-bold bg-purple-100 text-purple-700 rounded-lg hover:bg-purple-200 flex-shrink-0"
                    >
                      Edit in WP
                    </a>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

import React, { useState, useEffect } from 'react'
import { getOrphanedPages } from '../api.js'
import Spinner from './Spinner.jsx'

export default function OrphanedPagesPanel({ jobId, domain, onPageClick }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getOrphanedPages(jobId).then(setData).catch(() => setData({ count: 0, pages: [] })).finally(() => setLoading(false))
  }, [jobId])

  if (loading) return <div className="py-20"><Spinner /></div>

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-800">{domain ? `Orphaned Pages - ${domain}` : 'Orphaned Pages'}</h2>
        <p className="text-sm text-gray-500 mt-1">Pages discovered during the crawl that have no internal links pointing to them. Search engines may not find these pages.</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white p-4 rounded-xl border border-amber-200 text-center">
          <p className="text-2xl font-bold text-amber-600">{data.count}</p>
          <p className="text-xs text-amber-500 uppercase font-bold">Orphaned Pages</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-gray-200 text-center">
          <p className="text-xs text-gray-500 mt-2">These pages are reachable only via the sitemap or direct URL — no other page on your site links to them.</p>
        </div>
      </div>

      {data.count === 0 ? (
        <div className="py-12 bg-white rounded-2xl border border-green-200 text-center">
          <p className="text-green-600 text-2xl mb-2">✓</p>
          <p className="text-green-700 font-medium">All crawled pages have at least one internal link pointing to them.</p>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 bg-gray-50">
            <p className="text-sm font-bold text-gray-700">{data.count} orphaned page{data.count !== 1 ? 's' : ''}</p>
          </div>
          <div className="divide-y divide-gray-100 max-h-[600px] overflow-y-auto">
            {data.pages.map((issue, idx) => (
              <div key={issue.page_url} className="flex items-center gap-4 px-6 py-3 hover:bg-gray-50">
                <span className="text-amber-500 font-bold text-sm w-8 text-center flex-shrink-0">{idx + 1}</span>
                <div className="flex-1 min-w-0">
                  <button
                    onClick={() => onPageClick?.(issue.page_url)}
                    className="text-sm font-mono text-blue-600 hover:underline truncate block text-left w-full"
                  >
                    {issue.page_url}
                  </button>
                  {issue.extra?.title && (
                    <p className="text-xs text-gray-400 truncate">{issue.extra.title}</p>
                  )}
                </div>
                <a
                  href={issue.page_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-3 py-1.5 text-xs font-bold bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 flex-shrink-0"
                >
                  Visit
                </a>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

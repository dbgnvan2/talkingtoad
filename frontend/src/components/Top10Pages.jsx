import React, { useState, useEffect } from 'react'
import { getPages } from '../api.js'

export default function Top10Pages({ jobId, onPageClick }) {
  const [pages, setPages] = useState(null)

  useEffect(() => {
    getPages(jobId, { limit: 10 })
      .then(d => {
        const sorted = (d.pages || []).sort((a, b) => {
          const aTotal = (a.issue_counts?.critical || 0) + (a.issue_counts?.warning || 0) + (a.issue_counts?.info || 0)
          const bTotal = (b.issue_counts?.critical || 0) + (b.issue_counts?.warning || 0) + (b.issue_counts?.info || 0)
          if ((b.issue_counts?.critical || 0) !== (a.issue_counts?.critical || 0)) {
            return (b.issue_counts?.critical || 0) - (a.issue_counts?.critical || 0)
          }
          if ((b.issue_counts?.warning || 0) !== (a.issue_counts?.warning || 0)) {
            return (b.issue_counts?.warning || 0) - (a.issue_counts?.warning || 0)
          }
          return bTotal - aTotal
        })
        setPages(sorted.slice(0, 10))
      })
      .catch(() => setPages([]))
  }, [jobId])

  if (!pages || pages.length === 0) return null

  const pagesWithIssues = pages.filter(p =>
    (p.issue_counts?.critical || 0) + (p.issue_counts?.warning || 0) + (p.issue_counts?.info || 0) > 0
  )

  if (pagesWithIssues.length === 0) return null

  return (
    <section>
      <h2 className="text-base font-black text-gray-400 uppercase tracking-widest mb-4">Top 10 Pages to Fix</h2>
      <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-sm">
        <table className="min-w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-4 py-3 text-left text-[9px] font-black text-gray-400 uppercase tracking-widest">Page</th>
              <th className="px-4 py-3 text-center text-[9px] font-black text-gray-400 uppercase tracking-widest w-24">Critical</th>
              <th className="px-4 py-3 text-center text-[9px] font-black text-gray-400 uppercase tracking-widest w-24">Warning</th>
              <th className="px-4 py-3 text-center text-[9px] font-black text-gray-400 uppercase tracking-widest w-24">Info</th>
              <th className="px-4 py-3 text-center text-[9px] font-black text-gray-400 uppercase tracking-widest w-20">Total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {pagesWithIssues.map((p, idx) => {
              const total = (p.issue_counts?.critical || 0) + (p.issue_counts?.warning || 0) + (p.issue_counts?.info || 0)
              let pathname = p.url
              try { pathname = new URL(p.url).pathname || '/' } catch (_e) { /* ignore invalid URLs */ }

              return (
                <tr
                  key={p.url}
                  onClick={() => onPageClick(p.url)}
                  className="hover:bg-green-50 cursor-pointer transition-colors group"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-black text-gray-300 w-5">{idx + 1}</span>
                      <span className="text-xs font-mono text-gray-600 group-hover:text-blue-600 truncate max-w-md" title={p.url}>
                        {pathname}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center">
                    {p.issue_counts?.critical > 0 && (
                      <span className="inline-block bg-red-100 text-red-700 px-2 py-0.5 rounded-full text-[10px] font-black">
                        {p.issue_counts.critical}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {p.issue_counts?.warning > 0 && (
                      <span className="inline-block bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full text-[10px] font-black">
                        {p.issue_counts.warning}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {p.issue_counts?.info > 0 && (
                      <span className="inline-block bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full text-[10px] font-black">
                        {p.issue_counts.info}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className="text-sm font-black text-gray-800">{total}</span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}

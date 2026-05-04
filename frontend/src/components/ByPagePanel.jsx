import React, { useState, useEffect } from 'react'
import { getPages } from '../api.js'
import Spinner from './Spinner.jsx'

export default function ByPagePanel({ jobId, domain, onPageClick }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    getPages(jobId, { limit: 200 }).then(setData).catch(() => setData({ pages: [] }))
  }, [jobId])

  if (!data) return <Spinner />

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-gray-800">{domain ? `By Page - ${domain}` : 'By Page'}</h2>
      <div className="bg-white border border-gray-200 rounded-3xl overflow-hidden shadow-sm">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr><th className="px-6 py-5 text-left font-bold text-gray-400 uppercase tracking-widest text-[9px]">Page URL</th><th className="px-6 py-5 text-center font-bold text-gray-400 uppercase tracking-widest text-[9px]">Issues Found</th></tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {data.pages.map(p => (
            <tr key={p.url} onClick={() => onPageClick(p.url)} className="hover:bg-green-50/30 cursor-pointer transition-colors group">
              <td className="px-6 py-4 font-mono text-xs text-gray-600 truncate max-w-lg group-hover:text-blue-600">{p.url}</td>
              <td className="px-6 py-4">
                <div className="flex justify-center gap-2">
                  {p.issue_counts.critical > 0 && <span className="bg-red-100 text-red-700 px-2.5 py-0.5 rounded-full text-[10px] font-black">{p.issue_counts.critical}</span>}
                  {p.issue_counts.warning > 0 && <span className="bg-amber-100 text-amber-700 px-2.5 py-0.5 rounded-full text-[10px] font-black">{p.issue_counts.warning}</span>}
                  {p.issue_counts.info > 0 && <span className="bg-blue-100 text-blue-700 px-2.5 py-0.5 rounded-full text-[10px] font-black">{p.issue_counts.info}</span>}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  )
}

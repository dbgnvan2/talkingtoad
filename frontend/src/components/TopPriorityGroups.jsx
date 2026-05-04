import React, { useState, useEffect } from 'react'
import { getResults } from '../api.js'
import SeverityBadge from './SeverityBadge.jsx'

export default function TopPriorityGroups({ jobId, onPageClick }) {
  const [groups, setGroups] = useState(null)

  useEffect(() => {
    getResults(jobId, { limit: 5 }).then(d => {
      const g = d.issues.reduce((acc, iss) => {
        if (!acc[iss.issue_code]) acc[iss.issue_code] = { ...iss, count: 0, pages: [] }
        acc[iss.issue_code].count++; acc[iss.issue_code].pages.push(iss.page_url)
        return acc
      }, {})
      setGroups(Object.values(g).sort((a,b) => b.priority_rank - a.priority_rank).slice(0,5))
    }).catch(() => setGroups([]))
  }, [jobId])

  if (!groups?.length) return null

  return (
    <section>
      <h2 className="text-base font-black text-gray-400 uppercase tracking-widest mb-4">Top 5 Priority Fixes</h2>
      <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
        {groups.map(g => (
          <button key={g.issue_code} onClick={() => onPageClick(g.pages[0])} className="text-left bg-white border border-gray-200 rounded-2xl p-5 hover:border-green-400 hover:shadow-md transition-all shadow-sm group">
            <SeverityBadge severity={g.severity} />
            <p className="text-xs font-bold text-gray-800 mt-3 line-clamp-2 group-hover:text-green-700">{g.human_description || g.issue_code}</p>
            <p className="text-[10px] font-black text-gray-400 mt-1 uppercase tracking-tighter">{g.count} pages affected</p>
          </button>
        ))}
      </div>
    </section>
  )
}

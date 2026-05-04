import React, { useState, useEffect, useMemo } from 'react'
import { getResults } from '../api.js'
import SeverityBadge from './SeverityBadge.jsx'
import IssueHelpPanel from './IssueHelpPanel.jsx'
import Spinner from './Spinner.jsx'

export default function SeverityPanel({ jobId, severity, domain, onPageClick, onBack }) {
  const [data, setData] = useState(null)
  const [expandedCode, setExpandedCode] = useState(null)

  const labels = { critical: 'Critical Issues', warning: 'Warnings', info: 'Info Notices' }

  useEffect(() => {
    setData(null)
    getResults(jobId, { severity, limit: 100 })
      .then(d => setData(d))
      .catch(() => setData({ issues: [] }))
  }, [jobId, severity])

  const sortedGroups = useMemo(() => {
    if (!data?.issues) return []
    const groups = data.issues.reduce((acc, iss) => {
      if (!acc[iss.issue_code]) acc[iss.issue_code] = { ...iss, count: 0, pages: [] }
      acc[iss.issue_code].count++
      if (iss.page_url && !acc[iss.issue_code].pages.includes(iss.page_url)) {
        acc[iss.issue_code].pages.push(iss.page_url)
      }
      return acc
    }, {})
    return Object.values(groups).sort((a, b) => (b.priority_rank || 0) - (a.priority_rank || 0))
  }, [data])

  if (!data) return <div className="py-20"><Spinner /></div>

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 mb-6">
        <button onClick={onBack} className="text-xs font-bold text-green-600 uppercase tracking-widest hover:underline">← Back to Summary</button>
        <h2 className="text-xl font-bold text-gray-800">{labels[severity]}{domain ? ` - ${domain}` : ''}</h2>
      </div>
      {sortedGroups.length === 0 ? (
        <div className="py-12 bg-white rounded-2xl border border-gray-100 text-center text-gray-400 font-medium font-serif italic">No {severity} issues found.</div>
      ) : (
        sortedGroups.map(group => (
          <div key={group.issue_code} className="bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-sm hover:border-gray-300 transition-colors">
            <button
              onClick={() => setExpandedCode(expandedCode === group.issue_code ? null : group.issue_code)}
              className="w-full flex items-center justify-between px-6 py-5"
            >
              <div className="flex items-center gap-4">
                <SeverityBadge severity={group.severity} />
                <div className="text-left">
                  <p className="font-bold text-gray-800 leading-none text-base">{group.human_description || group.issue_code}</p>
                  <p className="text-sm font-bold text-gray-400 mt-1 uppercase tracking-widest">{group.count} Affected Pages</p>
                </div>
              </div>
              <span className="text-gray-600 text-xl font-black">{expandedCode === group.issue_code ? '▲' : '▼'}</span>
            </button>

            {expandedCode === group.issue_code && (
              <div className="px-6 pb-6 border-t border-gray-50 pt-6 space-y-8">
                <IssueHelpPanel issueCode={group.issue_code} />
                <div>
                  <h4 className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-4">Affected Pages</h4>
                  <div className="grid grid-cols-1 gap-2">
                    {group.pages.map(url => (
                      <button key={url} onClick={() => onPageClick(url)} className="text-left p-3 rounded-xl border border-gray-100 hover:bg-green-50 hover:border-green-200 transition-all font-mono text-xs text-blue-600 truncate flex justify-between items-center group">
                        <span>{url}</span>
                        <span className="text-sm font-black text-green-600 uppercase">Inspect →</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        ))
      )}
    </div>
  )
}

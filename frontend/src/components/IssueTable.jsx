import { useState } from 'react'
import SeverityBadge from './SeverityBadge.jsx'
import IssueHelpPanel from './IssueHelpPanel.jsx'
import { getIssueHelp } from '../data/issueHelp.js'

export default function IssueTable({ issues, pagination, page, onPage, severity, onSeverity, onUrlClick }) {
  const [expandedHelp, setExpandedHelp] = useState(null)

  function toggleHelp(key) {
    setExpandedHelp(prev => prev === key ? null : key)
  }

  return (
    <div>
      {/* Filters */}
      <div className="flex items-center gap-4 mb-4">
        <label className="text-sm text-gray-600">
          Severity:
          <select
            className="ml-2 border border-gray-300 rounded px-2 py-1 text-sm"
            value={severity}
            onChange={e => { onSeverity(e.target.value); onPage(1) }}
          >
            <option value="">All</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>
        </label>
        {pagination && (
          <span className="ml-auto text-sm text-gray-500">
            {pagination.total_issues} issue{pagination.total_issues !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="min-w-full text-sm divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">URL</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Severity</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Issue</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Description</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Recommendation</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600 w-8"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {issues.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                  No issues found.
                </td>
              </tr>
            )}
            {issues.map((issue, i) => {
              const helpKey = `${page}-${i}`
              const isOpen = expandedHelp === helpKey
              const hasHelp = !!getIssueHelp(issue.issue_code)

              return (
                <>
                  <tr key={helpKey} className="hover:bg-gray-50">
                    <td className="px-4 py-3 max-w-xs">
                      <button
                        className="text-blue-600 hover:underline truncate block max-w-xs text-left"
                        title={issue.page_url}
                        onClick={() => onUrlClick?.(issue.page_url)}
                      >
                        {shortenUrl(issue.page_url)}
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <SeverityBadge severity={issue.severity} />
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-700 whitespace-nowrap">
                      {issue.issue_code}
                    </td>
                    <td className="px-4 py-3 text-gray-700">{issue.description}</td>
                    <td className="px-4 py-3 text-gray-600">{issue.recommendation}</td>
                    <td className="px-4 py-3 text-center">
                      {hasHelp && (
                        <button
                          onClick={() => toggleHelp(helpKey)}
                          title={isOpen ? 'Hide help' : 'Show detailed help'}
                          className={`w-6 h-6 rounded-full text-xs font-bold border transition-colors ${
                            isOpen
                              ? 'bg-blue-600 text-white border-blue-600'
                              : 'bg-white text-blue-600 border-blue-300 hover:bg-blue-50'
                          }`}
                        >
                          ?
                        </button>
                      )}
                    </td>
                  </tr>
                  {isOpen && (
                    <tr key={`${helpKey}-help`} className="bg-blue-50">
                      <td colSpan={6} className="px-6 py-4">
                        <IssueHelpPanel issueCode={issue.issue_code} />
                      </td>
                    </tr>
                  )}
                </>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pagination && pagination.total_pages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <button
            className="px-3 py-1.5 text-sm border border-gray-300 rounded disabled:opacity-40"
            disabled={page <= 1}
            onClick={() => onPage(page - 1)}
          >
            Previous
          </button>
          <span className="text-sm text-gray-600">
            Page {page} of {pagination.total_pages}
          </span>
          <button
            className="px-3 py-1.5 text-sm border border-gray-300 rounded disabled:opacity-40"
            disabled={page >= pagination.total_pages}
            onClick={() => onPage(page + 1)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}

function shortenUrl(url) {
  try {
    const u = new URL(url)
    return u.pathname + u.search || '/'
  } catch {
    return url
  }
}

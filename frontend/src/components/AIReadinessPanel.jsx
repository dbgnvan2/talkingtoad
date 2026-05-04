import React, { useState, useEffect, useMemo } from 'react'
import { getResultsByCategory } from '../api.js'
import SeverityBadge from './SeverityBadge.jsx'
import IssueHelpPanel from './IssueHelpPanel.jsx'
import Spinner from './Spinner.jsx'
import { getIssueHelp } from '../data/issueHelp.js'

const ISSUE_GROUPS = {
  ai_bot: {
    label: 'AI Bot Access',
    icon: '🤖',
    issues: [
      'AI_BOT_SEARCH_BLOCKED',
      'AI_BOT_TRAINING_DISALLOWED',
      'AI_BOT_USER_FETCH_BLOCKED',
      'AI_BOT_DEPRECATED_DIRECTIVE',
      'AI_BOT_NO_AI_DIRECTIVES',
      'AI_BOT_BLANKET_DISALLOW',
      'AI_BOT_TABLE_STALE',
    ],
  },
  schema: {
    label: 'Schema Typing',
    icon: '📋',
    issues: [
      'SCHEMA_TYPE_MISMATCH',
      'SCHEMA_DEPRECATED_TYPE',
      'SCHEMA_TYPE_CONFLICT',
    ],
  },
  extractability: {
    label: 'Content Extractability',
    icon: '📄',
    issues: [
      'CONTENT_NOT_EXTRACTABLE_NO_TEXT',
      'CONTENT_THIN',
      'CONTENT_UNSTRUCTURED',
      'CONTENT_IMAGE_HEAVY',
    ],
  },
  citation: {
    label: 'Citation & Attribution',
    icon: '📚',
    issues: [
      'CITATIONS_MISSING_SUBSTANTIAL_CONTENT',
      'CITATIONS_ORPHANED',
      'CITATIONS_SOURCES_INACCESSIBLE',
    ],
  },
  heading_structure: {
    label: 'Heading Structure for AI',
    icon: '🗂️',
    issues: [
      'BLOG_SECTIONS_MISSING',
      'CONVERSATIONAL_H2_MISSING',
    ],
  },
}

export default function AIReadinessPanel({ jobId, domain, onPageClick, onShowHelp }) {
  const [data, setData] = useState(null)
  const [expandedCode, setExpandedCode] = useState(null)
  const [selectedIssue, setSelectedIssue] = useState(null)

  useEffect(() => {
    setData(null)
    getResultsByCategory(jobId, 'ai_readiness')
      .then(setData)
      .catch(() => setData({ issues: [] }))
  }, [jobId])

  const groups = useMemo(() => {
    if (!data?.issues) return {}

    const grouped = {}
    for (const [groupKey, groupDef] of Object.entries(ISSUE_GROUPS)) {
      grouped[groupKey] = {}
      for (const code of groupDef.issues) {
        grouped[groupKey][code] = { count: 0, pages: [] }
      }
    }

    for (const issue of data.issues) {
      for (const [groupKey, groupDef] of Object.entries(ISSUE_GROUPS)) {
        if (groupDef.issues.includes(issue.issue_code)) {
          grouped[groupKey][issue.issue_code].count++
          grouped[groupKey][issue.issue_code].pages.push({
            url: issue.page_url,
            severity: issue.severity,
            extra: issue.extra,
          })
          break
        }
      }
    }

    return grouped
  }, [data])

  if (!data) {
    return (
      <div className="py-20">
        <Spinner />
      </div>
    )
  }

  if (selectedIssue) {
    return (
      <IssueHelpPanel
        issueCode={selectedIssue}
        onClose={() => setSelectedIssue(null)}
      />
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-800">
          AI Readiness{domain ? ` - ${domain}` : ''}
        </h2>
        <button
          onClick={() => onShowHelp?.()}
          className="px-3 py-1.5 text-xs font-bold bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition-all"
          title="View category help"
        >
          ℹ️ Help
        </button>
      </div>

      {/* Group cards */}
      {Object.entries(ISSUE_GROUPS).map(([groupKey, groupDef]) => {
        const groupIssues = groups[groupKey] || {}
        const totalCount = Object.values(groupIssues).reduce((sum, g) => sum + g.count, 0)
        const hasIssues = totalCount > 0

        return (
          <div
            key={groupKey}
            className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm"
          >
            {/* Group Header */}
            <button
              onClick={() => setExpandedCode(expandedCode === groupKey ? null : groupKey)}
              className="w-full flex items-center justify-between hover:bg-gray-50 p-2 -m-2 rounded-lg transition-all"
            >
              <div className="flex items-center gap-4 flex-1 text-left">
                <span className="text-2xl">{groupDef.icon}</span>
                <div>
                  <p className="font-bold text-gray-800">{groupDef.label}</p>
                  <p className="text-xs text-gray-500">{totalCount} issue{totalCount !== 1 ? 's' : ''}</p>
                </div>
              </div>
              <span className="text-gray-400 text-xl font-bold">
                {expandedCode === groupKey ? '▼' : '▶'}
              </span>
            </button>

            {/* Expanded content */}
            {expandedCode === groupKey && (
              <div className="mt-4 pt-4 border-t border-gray-200 space-y-3">
                {groupDef.issues.map((issueCode) => {
                  const issueData = groupIssues[issueCode]
                  const help = getIssueHelp(issueCode)

                  if (issueData.count === 0) {
                    return (
                      <div
                        key={issueCode}
                        className="p-3 bg-gray-50 rounded-lg opacity-50"
                      >
                        <p className="text-sm font-semibold text-gray-500">
                          {help?.title || issueCode}
                        </p>
                        <p className="text-xs text-gray-400">Not found</p>
                      </div>
                    )
                  }

                  return (
                    <div
                      key={issueCode}
                      className="p-3 bg-gray-50 rounded-lg border border-gray-200 hover:border-gray-300 transition-all"
                    >
                      {/* Issue header */}
                      <button
                        onClick={() => setSelectedIssue(issueCode)}
                        className="w-full text-left hover:bg-white p-2 -m-2 rounded transition-all"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex-1 min-w-0">
                            <p className="font-semibold text-gray-800 text-sm">
                              {help?.title || issueCode}
                            </p>
                            <p className="text-xs text-gray-600 mt-1 line-clamp-2">
                              {help?.definition}
                            </p>
                          </div>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            {help?.confidence && (
                              <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-indigo-100 text-indigo-700 uppercase whitespace-nowrap">
                                {help.confidence}
                              </span>
                            )}
                            <SeverityBadge severity={help?.severity || 'info'} />
                            <span className="text-sm font-bold text-gray-700 bg-white px-2 py-0.5 rounded">
                              {issueData.count}
                            </span>
                          </div>
                        </div>
                      </button>

                      {/* Affected pages */}
                      <details className="mt-2">
                        <summary className="text-xs font-bold text-gray-600 cursor-pointer hover:text-gray-800 uppercase tracking-widest">
                          Affected pages ({issueData.pages.length})
                        </summary>
                        <div className="mt-2 space-y-1">
                          {issueData.pages.map((page, idx) => (
                            <button
                              key={idx}
                              onClick={() => onPageClick?.(page.url)}
                              className="block w-full text-left text-xs font-mono text-blue-600 hover:text-blue-800 hover:underline truncate p-1 hover:bg-blue-50 rounded"
                              title={page.url}
                            >
                              {page.url}
                            </button>
                          ))}
                        </div>
                      </details>

                      {/* Impact description */}
                      {help?.impact && (
                        <p className="text-xs text-gray-700 mt-2 p-2 bg-white rounded border border-gray-100">
                          <span className="font-bold">Impact: </span>
                          {help.impact}
                        </p>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )
      })}

      {/* Empty state */}
      {Object.values(groups).every(g => Object.values(g).every(i => i.count === 0)) && (
        <div className="p-8 text-center bg-green-50 border border-green-200 rounded-2xl">
          <p className="text-lg font-bold text-green-800">✓ All AI Readiness checks passed!</p>
          <p className="text-sm text-green-700 mt-1">Your site is well-prepared for AI systems.</p>
        </div>
      )}
    </div>
  )
}

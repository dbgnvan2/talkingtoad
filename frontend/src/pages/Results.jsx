import { useState, useEffect, useCallback, useRef, forwardRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import IssueTable from '../components/IssueTable.jsx'
import SeverityBadge from '../components/SeverityBadge.jsx'
import IssueHelpPanel from '../components/IssueHelpPanel.jsx'
import FixManager from '../components/FixManager.jsx'
import { getIssueHelp } from '../data/issueHelp.js'
import { getResults, getResultsByCategory, getPages, getPageIssues, downloadCsv } from '../api.js'

const CATEGORIES = [
  { key: 'broken_link',   label: 'Broken Links' },
  { key: 'metadata',      label: 'Metadata' },
  { key: 'heading',       label: 'Headings' },
  { key: 'redirect',      label: 'Redirects' },
  { key: 'crawlability',  label: 'Crawlability' },
  { key: 'duplicate',     label: 'Duplicates' },
  { key: 'sitemap',       label: 'Sitemap' },
  { key: 'security',      label: 'Security' },
  { key: 'url_structure', label: 'URL Structure' },
]

// Tab indices: 0=Summary, 1–N=categories, N+1=By Page, N+2=Fix Manager
const TAB_SUMMARY    = 0
const TAB_BY_PAGE    = CATEGORIES.length + 1
const TAB_FIX_MGR    = CATEGORIES.length + 2

export default function Results() {
  const { jobId } = useParams()
  const navigate  = useNavigate()
  const [activeTab, setActiveTab] = useState(TAB_SUMMARY)
  const [summary, setSummary] = useState(null)
  const [summaryError, setSummaryError] = useState(null)
  const [csvError, setCsvError] = useState(null)
  // For "navigate to By Page for a URL" from a category tab
  const [jumpToUrl, setJumpToUrl] = useState(null)

  // Load summary on mount
  useEffect(() => {
    getResults(jobId, { page: 1, limit: 5 })
      .then(d => setSummary(d))
      .catch(err => setSummaryError(err.message))
  }, [jobId])

  function handleUrlClick(url) {
    setJumpToUrl(url)
    setActiveTab(TAB_BY_PAGE)
  }

  function clearJumpUrl() {
    setJumpToUrl(null)
  }

  async function handleCsvDownload(category) {
    setCsvError(null)
    try {
      await downloadCsv(jobId, category)
    } catch (err) {
      setCsvError('CSV export failed — please try again.')
    }
  }

  const tabs = [
    'Summary',
    ...CATEGORIES.map(c => c.label),
    'By Page',
    'Fix Manager',
  ]

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Crawl Results</h1>
          {summary && (
            <p className="text-sm text-gray-500 mt-0.5 truncate max-w-lg">
              {summary.job?.target_url}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => handleCsvDownload(null)}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            Export all CSV
          </button>
          <button
            onClick={() => navigate('/')}
            className="px-3 py-1.5 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700"
          >
            New crawl
          </button>
        </div>
      </div>

      {/* CSV error */}
      {csvError && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
          {csvError}
        </div>
      )}

      {/* Tab bar */}
      <div className="border-b border-gray-200 mb-6 overflow-x-auto">
        <div className="flex gap-0 min-w-max">
          {tabs.map((label, i) => {
            const count = tabCount(summary, i)
            return (
              <button
                key={i}
                onClick={() => { setActiveTab(i); clearJumpUrl() }}
                className={`px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                  activeTab === i
                    ? 'border-green-600 text-green-700'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                {label}
                {count != null && count > 0 && (
                  <span className="ml-1.5 bg-gray-100 text-gray-600 rounded-full px-1.5 py-0.5 text-xs">
                    {count}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* Tab content */}
      {activeTab === TAB_SUMMARY && (
        <SummaryTab
          summary={summary}
          error={summaryError}
          jobId={jobId}
          onCategoryClick={i => setActiveTab(i + 1)}
          onPageClick={handleUrlClick}
        />
      )}
      {activeTab >= 1 && activeTab <= CATEGORIES.length && (
        <CategoryTab
          jobId={jobId}
          category={CATEGORIES[activeTab - 1].key}
          onUrlClick={handleUrlClick}
        />
      )}
      {activeTab === TAB_BY_PAGE && (
        <ByPageTab jobId={jobId} jumpToUrl={jumpToUrl} onJumpConsumed={clearJumpUrl} />
      )}
      {activeTab === TAB_FIX_MGR && (
        <FixManager jobId={jobId} />
      )}
    </div>
  )
}

// ── Summary tab ────────────────────────────────────────────────────────────

function SummaryTab({ summary, error, jobId, onCategoryClick, onPageClick }) {
  const [activeSeverity, setActiveSeverity]     = useState(null)
  const [sevIssues, setSevIssues]               = useState(null)
  const [sevLoading, setSevLoading]             = useState(false)
  const [showScoreBreakdown, setShowScoreBreakdown] = useState(false)
  const sevPanelRef   = useRef(null)
  const scorePanelRef = useRef(null)

  useEffect(() => {
    if (!activeSeverity) { setSevIssues(null); return }
    setSevLoading(true)
    setSevIssues(null)
    getResults(jobId, { severity: activeSeverity, page: 1, limit: 20 })
      .then(d => { setSevIssues(d.issues); setSevLoading(false) })
      .catch(() => setSevLoading(false))
  }, [jobId, activeSeverity])

  // Scroll to the severity panel when it opens
  useEffect(() => {
    if (activeSeverity && sevPanelRef.current) {
      sevPanelRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [activeSeverity, sevIssues])

  // Scroll to the score breakdown when it opens
  useEffect(() => {
    if (showScoreBreakdown && scorePanelRef.current) {
      scorePanelRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [showScoreBreakdown])

  function toggleSeverity(sev) {
    setActiveSeverity(prev => prev === sev ? null : sev)
  }

  if (error) return <ErrorMsg msg={error} />
  if (!summary) return <Spinner />

  const { summary: s, issues: rawTopIssues } = summary
  // Sort by priority_rank descending so the highest-priority fix is always first
  const topIssues = rawTopIssues
    ? [...rawTopIssues].sort((a, b) => (b.priority_rank ?? 0) - (a.priority_rank ?? 0))
    : rawTopIssues
  if (!s) return <p className="text-gray-500">No summary available.</p>

  return (
    <div className="space-y-8">
      {/* Health score + pages overview */}
      <div>
        <div className="grid grid-cols-3 gap-4">
          <HealthScoreCard
            score={s.health_score ?? null}
            open={showScoreBreakdown}
            onToggle={() => setShowScoreBreakdown(o => !o)}
          />
          <StatCard label="Pages crawled" value={s.pages_crawled ?? 0} color="text-gray-800" />
          <StatCard
            label="HTTP errors (4xx/5xx)"
            value={s.pages_with_errors ?? 0}
            color={s.pages_with_errors > 0 ? 'text-red-600' : 'text-gray-800'}
            note={s.pages_with_errors === 0 ? 'No internal pages returned an error status' : null}
          />
        </div>

        {/* Health score breakdown panel — full width below grid */}
        {showScoreBreakdown && (
          <ScoreBreakdownPanel ref={scorePanelRef} summary={s} score={s.health_score ?? null} />
        )}
      </div>

      {/* Severity totals — clickable */}
      <div>
        <p className="text-xs text-gray-400 mb-2">Click a severity level to see those issues</p>
        <div className="grid grid-cols-3 gap-4">
          <SeverityCard
            label="Critical" value={s.by_severity?.critical ?? 0}
            color="text-red-600" borderActive="border-red-400 bg-red-50"
            active={activeSeverity === 'critical'}
            onClick={() => toggleSeverity('critical')}
          />
          <SeverityCard
            label="Warning" value={s.by_severity?.warning ?? 0}
            color="text-amber-600" borderActive="border-amber-400 bg-amber-50"
            active={activeSeverity === 'warning'}
            onClick={() => toggleSeverity('warning')}
          />
          <SeverityCard
            label="Info" value={s.by_severity?.info ?? 0}
            color="text-blue-600" borderActive="border-blue-400 bg-blue-50"
            active={activeSeverity === 'info'}
            onClick={() => toggleSeverity('info')}
          />
        </div>
      </div>

      {/* Severity-filtered issues panel */}
      {activeSeverity && (
        <div ref={sevPanelRef} className="bg-white border border-gray-200 rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-700 capitalize">
              {activeSeverity} issues
            </h2>
            <button
              onClick={() => setActiveSeverity(null)}
              className="text-xs text-gray-400 hover:text-gray-600"
            >
              ✕ close
            </button>
          </div>
          {sevLoading && <Spinner />}
          {!sevLoading && sevIssues && sevIssues.length === 0 && (
            <p className="text-sm text-gray-400">No {activeSeverity} issues found.</p>
          )}
          {!sevLoading && sevIssues && sevIssues.length > 0 && (
            <div className="space-y-2">
              {sevIssues.map((issue, i) => (
                <div key={i} className="flex items-start gap-3 border border-gray-100 rounded-lg px-3 py-2.5">
                  <SeverityBadge severity={issue.severity} />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-gray-800">{issue.issue_code}</p>
                    <p className="text-xs text-gray-500 truncate">{issue.description}</p>
                    {issue.page_url && (
                      <p className="text-xs text-blue-500 truncate mt-0.5">{issue.page_url}</p>
                    )}
                  </div>
                </div>
              ))}
              {(s.by_severity?.[activeSeverity] ?? 0) > 20 && (
                <p className="text-xs text-gray-400 pt-1">
                  Showing 20 of {s.by_severity[activeSeverity]} — use the category tabs above for the full list.
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* By category */}
      <div>
        <h2 className="text-base font-semibold text-gray-700 mb-3">Issues by category</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {CATEGORIES.map((cat, i) => {
            const count = s.by_category?.[cat.key] ?? 0
            return (
              <button
                key={cat.key}
                onClick={() => onCategoryClick(i)}
                className="text-left bg-white border border-gray-200 rounded-lg p-4 hover:border-green-400 transition-colors"
              >
                <p className="text-lg font-bold text-gray-800">{count}</p>
                <p className="text-sm text-gray-500">{cat.label}</p>
              </button>
            )
          })}
        </div>
      </div>

      {/* Top 10 pages to fix */}
      <TopPagesPanel jobId={jobId} onPageClick={onPageClick} />

      {/* Top 5 Priority Fixes */}
      {topIssues && topIssues.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-semibold text-gray-700">Top 5 Priority Fixes</h2>
            <button
              onClick={() => handleCsvDownload(null)}
              className="text-sm text-gray-500 hover:text-gray-700 underline"
            >
              Export full CSV
            </button>
          </div>
          <p className="text-xs text-gray-400 mb-2">Click an issue to see all issues on that page</p>
          <div className="space-y-2">
            {topIssues.map((issue, i) => (
              <button
                key={i}
                onClick={() => issue.page_url && onPageClick(issue.page_url)}
                disabled={!issue.page_url}
                className="w-full text-left flex items-start gap-3 bg-white border border-gray-200 rounded-lg px-4 py-3 hover:border-green-400 hover:bg-green-50 transition-colors disabled:cursor-default disabled:hover:border-gray-200 disabled:hover:bg-white"
              >
                <SeverityBadge severity={issue.severity} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-gray-800">{issue.issue_code}</p>
                    {issue.priority_rank > 0 && (
                      <span className="text-xs font-semibold px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 border border-gray-200"
                            title="Priority score">
                        P{issue.priority_rank}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 truncate">{issue.description}</p>
                  {issue.page_url && (
                    <p className="text-xs text-blue-500 truncate mt-0.5">{issue.page_url}</p>
                  )}
                </div>
                {issue.page_url && (
                  <span className="flex-shrink-0 text-xs text-gray-400 self-center">→</span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {s.total_issues === 0 && (
        <div className="text-center py-12 text-gray-400">
          <p className="text-4xl mb-3">🐸</p>
          <p className="font-medium">No issues found — great work!</p>
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value, color, note }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 text-center">
      <p className={`text-3xl font-bold ${color}`}>{value}</p>
      <p className="text-sm text-gray-500 mt-1">{label}</p>
      {note && <p className="text-xs text-gray-400 mt-1 leading-tight">{note}</p>}
    </div>
  )
}

function SeverityCard({ label, value, color, borderActive, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-xl p-5 text-center border-2 transition-all ${
        active ? borderActive : 'border-gray-200 bg-white hover:border-gray-300'
      }`}
    >
      <p className={`text-3xl font-bold ${color}`}>{value}</p>
      <p className="text-sm text-gray-500 mt-1">{label}</p>
      <p className="text-xs text-gray-400 mt-1">{active ? 'click to close ▲' : 'click to filter ▼'}</p>
    </button>
  )
}

function TopPagesPanel({ jobId, onPageClick }) {
  const [pages, setPages] = useState(null)

  useEffect(() => {
    getPages(jobId, { page: 1, limit: 10 })
      .then(d => setPages(d.pages.filter(p => (p.issue_counts?.total ?? 0) > 0)))
      .catch(() => setPages([]))
  }, [jobId])

  if (!pages || pages.length === 0) return null

  return (
    <div>
      <h2 className="text-base font-semibold text-gray-700 mb-3">Top 10 pages to fix first</h2>
      <div className="rounded-lg border border-gray-200 overflow-hidden">
        <table className="min-w-full text-sm divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500">Page</th>
              <th className="px-3 py-2.5 text-center text-xs font-medium text-red-600 whitespace-nowrap">Critical</th>
              <th className="px-3 py-2.5 text-center text-xs font-medium text-amber-600 whitespace-nowrap">Warning</th>
              <th className="px-3 py-2.5 text-center text-xs font-medium text-blue-600 whitespace-nowrap">Info</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {pages.map((p, i) => (
              <tr
                key={p.url}
                className="hover:bg-gray-50 cursor-pointer"
                onClick={() => onPageClick(p.url)}
              >
                <td className="px-4 py-2.5">
                  <span className="text-xs text-gray-400 mr-2">{i + 1}.</span>
                  <span className="text-xs text-blue-600 hover:underline break-all">{p.url}</span>
                </td>
                <td className="px-3 py-2.5 text-center text-xs font-semibold text-red-600">
                  {p.issue_counts?.critical > 0 ? p.issue_counts.critical : '—'}
                </td>
                <td className="px-3 py-2.5 text-center text-xs font-semibold text-amber-600">
                  {p.issue_counts?.warning > 0 ? p.issue_counts.warning : '—'}
                </td>
                <td className="px-3 py-2.5 text-center text-xs text-blue-500">
                  {p.issue_counts?.info > 0 ? p.issue_counts.info : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-gray-400 mt-2">Click a row to see all issues for that page.</p>
    </div>
  )
}

function HealthScoreCard({ score, open, onToggle }) {
  const grade = getGrade(score)
  const color =
    score === null ? 'text-gray-400'
    : score >= 90  ? 'text-green-600'
    : score >= 75  ? 'text-green-500'
    : score >= 60  ? 'text-amber-500'
    :                'text-red-600'

  const gradeColor =
    grade === 'A' ? 'text-green-600 bg-green-50 border-green-200'
    : grade === 'B' ? 'text-green-500 bg-green-50 border-green-200'
    : grade === 'C' ? 'text-amber-600 bg-amber-50 border-amber-200'
    : grade === 'F' ? 'text-red-600 bg-red-50 border-red-200'
    : 'text-gray-400 bg-gray-50 border-gray-200'

  return (
    <button
      onClick={onToggle}
      className={`w-full bg-white border-2 rounded-xl p-5 text-center transition-all ${
        open ? 'border-green-400 bg-green-50' : 'border-gray-200 hover:border-gray-300'
      }`}
    >
      <div className="flex items-center justify-center gap-3">
        <p className={`text-3xl font-bold ${color}`}>{score ?? '—'}</p>
        {grade && (
          <span className={`text-2xl font-bold px-2.5 py-0.5 rounded-lg border ${gradeColor}`}>
            {grade}
          </span>
        )}
      </div>
      <p className="text-sm text-gray-500 mt-1">Health score</p>
      <p className="text-xs text-gray-400 mt-1">{open ? 'click to close ▲' : 'click for breakdown ▼'}</p>
    </button>
  )
}

const ScoreBreakdownPanel = forwardRef(function ScoreBreakdownPanel({ summary, score }, ref) {
  const color =
    score === null ? 'text-gray-400'
    : score >= 80  ? 'text-green-600'
    : score >= 50  ? 'text-amber-500'
    :                'text-red-600'

  const grade = getGrade(score)
  const band =
    score === null ? null
    : score >= 90  ? { label: `Grade A — Excellent`, tip: 'Your site is in great shape. Keep it up!' }
    : score >= 75  ? { label: `Grade B — Good`,      tip: 'Good overall, with room to improve. Address Search Hindrance issues next.' }
    : score >= 60  ? { label: `Grade C — Fair`,      tip: 'There are important issues to fix. Focus on Visibility Blockers first.' }
    :                { label: `Grade F — Needs Work`, tip: 'Your site has significant visibility problems. Start with the highest-priority issues immediately.' }

  const pages    = Math.max(1, summary?.pages_crawled ?? 1)
  const critical = summary?.by_severity?.critical ?? 0
  const warning  = summary?.by_severity?.warning  ?? 0
  const info     = summary?.by_severity?.info     ?? 0

  return (
    <div ref={ref} className="mt-3 bg-white border border-gray-200 rounded-xl p-5 space-y-4">
      {/* Band label */}
      {band && (
        <div>
          <p className={`text-lg font-bold ${color}`}>{score} / 100 — {band.label}</p>
          <p className="text-sm text-gray-500 mt-0.5">{band.tip}</p>
        </div>
      )}

      {/* How the score works */}
      <div className="rounded-lg bg-gray-50 border border-gray-100 px-4 py-3 text-xs text-gray-500 space-y-1">
        <p className="font-semibold text-gray-600">How the score is calculated</p>
        <p>Each issue has an <strong>impact score</strong> (1–10) based on how badly it affects SEO and visitors.</p>
        <p><strong>Page health</strong> = 100 − sum of all impact scores on that page (minimum 0).</p>
        <p><strong>Site health</strong> = average page health across all {pages} crawled page{pages !== 1 ? 's' : ''}.</p>
      </div>

      {/* Issue summary */}
      <div>
        <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">Issues found</p>
        <div className="flex gap-4 text-xs">
          <span className="font-semibold text-red-600">{critical} critical</span>
          <span className="font-semibold text-amber-600">{warning} warnings</span>
          <span className="font-semibold text-blue-600">{info} info</span>
        </div>
      </div>

      {/* What to fix */}
      {score !== null && score < 100 && (
        <div>
          <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">
            How to improve your score
          </p>
          <ul className="text-xs text-gray-500 space-y-1 list-disc list-inside">
            <li>
              Use the <span className="font-medium text-gray-600">category tabs</span> to see all issues.
              Each issue shows a <span className="font-medium text-gray-600">P-score</span> (priority rank) —
              higher means fix it first.
            </li>
            {critical > 0 && (
              <li>
                Fixing <span className="font-semibold text-red-600">{critical} critical issue{critical !== 1 ? 's' : ''}</span> will
                have the biggest impact on your score (highest impact scores).
              </li>
            )}
            {critical === 0 && warning === 0 && info === 0 && (
              <li>No issues found — your score is already at its best!</li>
            )}
          </ul>
        </div>
      )}
    </div>
  )
})

// ── Category tab ───────────────────────────────────────────────────────────

const SEV_ORDER = { critical: 0, warning: 1, info: 2 }

// ── v1.5 helper functions ─────────────────────────────────────────────────

/** Convert 0–100 health score to a letter grade (A / B / C / F). */
function getGrade(score) {
  if (score === null || score === undefined) return null
  if (score >= 90) return 'A'
  if (score >= 75) return 'B'
  if (score >= 60) return 'C'
  return 'F'
}

/** Return the non-technical mission impact label for a given impact value (1–10). */
function getMissionImpactLabel(impact) {
  if (!impact) return null
  if (impact >= 9) return { text: 'Visibility Blocker', color: 'text-red-600 bg-red-50 border-red-200' }
  if (impact >= 6) return { text: 'Search Hindrance',  color: 'text-amber-700 bg-amber-50 border-amber-200' }
  return                  { text: 'Best Practice',     color: 'text-blue-600 bg-blue-50 border-blue-200' }
}

function groupIssues(issues) {
  const map = new Map()
  for (const issue of issues) {
    if (!map.has(issue.issue_code)) {
      map.set(issue.issue_code, {
        code: issue.issue_code,
        severity: issue.severity,
        description: issue.description,
        recommendation: issue.recommendation,
        priority_rank: issue.priority_rank ?? 0,
        impact: issue.impact ?? 0,
        effort: issue.effort ?? 0,
        human_description: issue.human_description ?? '',
        pages: [],
      })
    }
    map.get(issue.issue_code).pages.push(issue.page_url)
  }
  return [...map.values()].sort((a, b) => {
    // Primary: priority_rank descending (highest priority first)
    const pd = b.priority_rank - a.priority_rank
    if (pd !== 0) return pd
    // Secondary: severity
    const sd = SEV_ORDER[a.severity] - SEV_ORDER[b.severity]
    return sd !== 0 ? sd : b.pages.length - a.pages.length
  })
}

function CategoryTab({ jobId, category, onUrlClick }) {
  const [allIssues, setAllIssues] = useState(null)
  const [severity, setSeverity] = useState('')
  const [quickWins, setQuickWins] = useState(false)
  const [error, setError] = useState(null)
  const [expandedCode, setExpandedCode] = useState(null)

  useEffect(() => {
    setError(null)
    setAllIssues(null)
    setExpandedCode(null)
    // Fetch all issues for this category in one shot (limit=5000 cap from API)
    getResultsByCategory(jobId, category, { page: 1, limit: 5000, severity: severity || undefined })
      .then(d => setAllIssues(d.issues))
      .catch(err => setError(err.message))
  }, [jobId, category, severity])

  if (error) return <ErrorMsg msg={error} />
  if (!allIssues) return <Spinner />

  const allGroups = groupIssues(allIssues)
  // Quick Wins: Impact ≥7 AND Effort ≤2
  const groups = quickWins
    ? allGroups.filter(g => g.impact >= 7 && g.effort <= 2)
    : allGroups
  const totalIssues = allIssues.length

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="font-semibold text-gray-700 capitalize">{category.replace(/_/g, ' ')} issues</h2>
          <p className="text-xs text-gray-400 mt-0.5">{totalIssues} issue{totalIssues !== 1 ? 's' : ''} across {allGroups.length} type{allGroups.length !== 1 ? 's' : ''}</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Quick Wins filter */}
          <button
            onClick={() => setQuickWins(v => !v)}
            title="Show only high-impact issues that are easy to fix (Impact ≥7, Effort ≤2)"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
              quickWins
                ? 'bg-green-600 text-white border-green-600'
                : 'bg-white text-green-700 border-green-400 hover:bg-green-50'
            }`}
          >
            ⚡ Quick Wins{quickWins && groups.length > 0 ? ` (${groups.length})` : ''}
          </button>
          <label className="text-sm text-gray-600 flex items-center gap-1.5">
            Severity:
            <select
              className="border border-gray-300 rounded px-2 py-1 text-sm"
              value={severity}
              onChange={e => setSeverity(e.target.value)}
            >
              <option value="">All</option>
              <option value="critical">Critical</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </select>
          </label>
          <button
            onClick={() => handleCsvDownload(category)}
            className="text-sm text-gray-500 hover:text-gray-700 underline"
          >
            Export CSV
          </button>
        </div>
      </div>

      {/* Quick Wins context banner */}
      {quickWins && (
        <div className="mb-3 flex items-start gap-2 bg-green-50 border border-green-200 rounded-lg px-3 py-2 text-xs text-green-800">
          <span className="text-base leading-none mt-0.5">⚡</span>
          <span>
            <strong>Quick Wins filter active</strong> — showing issues with high impact (≥7) that are straightforward to fix (Effort ≤2).
            {groups.length === 0 ? ' No quick wins found in this category.' : ` ${groups.length} issue type${groups.length !== 1 ? 's' : ''} match.`}
          </span>
        </div>
      )}

      {/* Grouped issue list */}
      {groups.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-8">
          {quickWins ? 'No quick wins in this category — try another or turn off the filter.' : 'No issues found.'}
        </p>
      ) : (
        <div className="space-y-2">
          {groups.map(group => (
            <IssueGroup
              key={group.code}
              group={group}
              expanded={expandedCode === group.code}
              onToggle={() => setExpandedCode(c => c === group.code ? null : group.code)}
              onUrlClick={onUrlClick}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function IssueGroup({ group, expanded, onToggle, onUrlClick }) {
  const help = getIssueHelp(group.code)
  const [showHelp, setShowHelp] = useState(false)
  const [pageOffset, setPageOffset] = useState(0)
  const PAGE_SIZE = 20

  const visiblePages = group.pages.slice(pageOffset, pageOffset + PAGE_SIZE)
  const totalPages = group.pages.length

  const severityColors = {
    critical: 'text-red-600 bg-red-50 border-red-200',
    warning:  'text-amber-600 bg-amber-50 border-amber-200',
    info:     'text-blue-600 bg-blue-50 border-blue-200',
  }
  const badgeColor = severityColors[group.severity] ?? 'text-gray-600 bg-gray-50 border-gray-200'
  const missionLabel = getMissionImpactLabel(group.impact)

  return (
    <div className={`rounded-xl border transition-colors ${expanded ? 'border-green-300 bg-white' : 'border-gray-200 bg-white hover:border-gray-300'}`}>
      {/* Group header — always visible, click to expand */}
      <button
        className="w-full text-left px-4 py-3.5 flex items-center gap-3"
        onClick={onToggle}
      >
        <span className="text-gray-400 text-xs w-3 flex-shrink-0">{expanded ? '▼' : '▶'}</span>
        <SeverityBadge severity={group.severity} />
        <div className="flex-1 min-w-0">
          {/* Human-first label + technical code */}
          <div className="flex items-baseline gap-2">
            {group.human_description ? (
              <span className="text-sm font-semibold text-gray-800 truncate">{group.human_description}</span>
            ) : (
              <span className="font-mono text-xs text-gray-700 font-medium">{group.code}</span>
            )}
            {group.human_description && (
              <span className="font-mono text-xs text-gray-400 flex-shrink-0">{group.code}</span>
            )}
          </div>
          <span className="block text-xs text-gray-500 truncate leading-tight mt-0.5">{group.description}</span>
        </div>
        {/* Mission impact label */}
        {missionLabel && (
          <span className={`flex-shrink-0 text-xs font-medium px-2 py-0.5 rounded border ${missionLabel.color}`}
                title={`Impact level ${group.impact}/10`}>
            {missionLabel.text}
          </span>
        )}
        {group.priority_rank > 0 && (
          <span className="flex-shrink-0 text-xs font-semibold px-2 py-0.5 rounded bg-gray-100 text-gray-500 border border-gray-200"
                title={`Priority score: ${group.priority_rank} (impact × 10 − effort × 2)`}>
            P{group.priority_rank}
          </span>
        )}
        <span className={`flex-shrink-0 text-xs font-semibold px-2.5 py-1 rounded-full border ${badgeColor}`}>
          {totalPages} page{totalPages !== 1 ? 's' : ''}
        </span>
        {help && (
          <button
            onClick={e => { e.stopPropagation(); setShowHelp(v => !v) }}
            title={showHelp ? 'Hide help' : 'Show detailed help'}
            className={`flex-shrink-0 w-5 h-5 rounded-full text-xs font-bold border transition-colors ${
              showHelp
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-white text-blue-600 border-blue-300 hover:bg-blue-50'
            }`}
          >
            ?
          </button>
        )}
      </button>

      {/* Help panel */}
      {showHelp && (
        <div className="px-4 pb-3 border-t border-gray-100">
          <IssueHelpPanel issueCode={group.code} />
        </div>
      )}

      {/* Drilled-in page list */}
      {expanded && (
        <div className="border-t border-gray-100">
          {/* Recommendation */}
          <p className="px-4 py-2.5 text-xs text-gray-500 bg-gray-50 border-b border-gray-100">
            {group.recommendation}
          </p>

          {/* Page list */}
          <ul className="divide-y divide-gray-100">
            {visiblePages.map((pageUrl, i) => (
              <li key={i} className="flex items-center gap-2 px-4 py-2 hover:bg-gray-50">
                <span className="text-xs text-gray-300 w-8 text-right flex-shrink-0">
                  {pageOffset + i + 1}.
                </span>
                <button
                  className="text-xs text-blue-600 hover:underline text-left truncate flex-1"
                  title={pageUrl}
                  onClick={() => onUrlClick?.(pageUrl)}
                >
                  {shortenUrl(pageUrl)}
                </button>
              </li>
            ))}
          </ul>

          {/* Sub-pagination */}
          {totalPages > PAGE_SIZE && (
            <div className="flex items-center justify-between px-4 py-2.5 border-t border-gray-100 bg-gray-50">
              <button
                className="text-xs text-gray-500 hover:text-gray-700 disabled:opacity-40"
                disabled={pageOffset === 0}
                onClick={() => setPageOffset(o => Math.max(0, o - PAGE_SIZE))}
              >
                ← Previous
              </button>
              <span className="text-xs text-gray-400">
                {pageOffset + 1}–{Math.min(pageOffset + PAGE_SIZE, totalPages)} of {totalPages}
              </span>
              <button
                className="text-xs text-gray-500 hover:text-gray-700 disabled:opacity-40"
                disabled={pageOffset + PAGE_SIZE >= totalPages}
                onClick={() => setPageOffset(o => o + PAGE_SIZE)}
              >
                Next →
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── By Page tab ────────────────────────────────────────────────────────────

function ByPageTab({ jobId, jumpToUrl, onJumpConsumed }) {
  const [data, setData] = useState(null)
  const [page, setPage] = useState(1)
  const [minSeverity, setMinSeverity] = useState('')
  const [search, setSearch] = useState('')
  const [expandedUrl, setExpandedUrl] = useState(null)
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    setError(null)
    getPages(jobId, { page, limit: 50, minSeverity: minSeverity || undefined })
      .then(setData)
      .catch(err => setError(err.message))
  }, [jobId, page, minSeverity])

  useEffect(() => { load() }, [load])

  // Handle jump-to-url from a category tab
  useEffect(() => {
    if (jumpToUrl) {
      setExpandedUrl(jumpToUrl)
      onJumpConsumed()
    }
  }, [jumpToUrl, onJumpConsumed])

  function toggleRow(url) {
    setExpandedUrl(u => u === url ? null : url)
  }

  const filtered = data
    ? data.pages.filter(p => !search || p.url.toLowerCase().includes(search.toLowerCase()))
    : []

  if (error) return <ErrorMsg msg={error} />
  if (!data) return <Spinner />

  return (
    <div>
      {/* Filters */}
      <div className="flex flex-wrap gap-4 mb-4">
        <input
          type="text"
          placeholder="Filter by URL…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 w-64"
        />
        <label className="flex items-center gap-2 text-sm text-gray-600">
          Min severity:
          <select
            className="border border-gray-300 rounded px-2 py-1.5 text-sm"
            value={minSeverity}
            onChange={e => { setMinSeverity(e.target.value); setPage(1) }}
          >
            <option value="">All</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning or above</option>
            <option value="info">Info or above</option>
          </select>
        </label>
        {data.pagination && (
          <span className="ml-auto text-sm text-gray-500 self-center">
            {data.pagination.total_pages > 1
              ? `${data.pages.length} of ${data.pagination.total_items ?? '?'} pages`
              : `${data.pages.length} page${data.pages.length !== 1 ? 's' : ''}`}
          </span>
        )}
      </div>

      {/* Pages table */}
      <div className="rounded-lg border border-gray-200 overflow-hidden">
        <table className="min-w-full text-sm divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">URL</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600 whitespace-nowrap">Status</th>
              <th className="px-4 py-3 text-center font-medium text-red-600 whitespace-nowrap">Critical</th>
              <th className="px-4 py-3 text-center font-medium text-amber-600 whitespace-nowrap">Warning</th>
              <th className="px-4 py-3 text-center font-medium text-blue-600 whitespace-nowrap">Info</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
                  {search ? 'No pages match your filter.' : 'No pages found.'}
                </td>
              </tr>
            )}
            {filtered.map(p => (
              <>
                <tr
                  key={p.url}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => toggleRow(p.url)}
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="text-gray-400 text-xs">{expandedUrl === p.url ? '▼' : '▶'}</span>
                      <span className="text-blue-600 hover:underline truncate max-w-sm" title={p.url}>
                        {p.url}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <StatusBadge code={p.status_code} />
                  </td>
                  <td className="px-4 py-3 text-center font-medium text-red-600">
                    {p.issue_counts?.critical ?? 0}
                  </td>
                  <td className="px-4 py-3 text-center font-medium text-amber-600">
                    {p.issue_counts?.warning ?? 0}
                  </td>
                  <td className="px-4 py-3 text-center font-medium text-blue-600">
                    {p.issue_counts?.info ?? 0}
                  </td>
                </tr>
                {expandedUrl === p.url && (
                  <tr key={`${p.url}-detail`}>
                    <td colSpan={5} className="bg-gray-50 px-6 py-4 border-t border-gray-100">
                      <PageDetail jobId={jobId} pageUrl={p.url} />
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {data.pagination && data.pagination.total_pages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <button
            className="px-3 py-1.5 text-sm border border-gray-300 rounded disabled:opacity-40"
            disabled={page <= 1}
            onClick={() => setPage(p => p - 1)}
          >
            Previous
          </button>
          <span className="text-sm text-gray-600">
            Page {page} of {data.pagination.total_pages}
          </span>
          <button
            className="px-3 py-1.5 text-sm border border-gray-300 rounded disabled:opacity-40"
            disabled={page >= data.pagination.total_pages}
            onClick={() => setPage(p => p + 1)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}

// ── Page detail panel ──────────────────────────────────────────────────────

function PageDetail({ jobId, pageUrl }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [expandedHelp, setExpandedHelp] = useState(null)

  useEffect(() => {
    setData(null)
    setError(null)
    setExpandedHelp(null)
    getPageIssues(jobId, pageUrl)
      .then(setData)
      .catch(err => setError(err.message))
  }, [jobId, pageUrl])

  function toggleHelp(key) {
    setExpandedHelp(prev => prev === key ? null : key)
  }

  if (error) return <p className="text-sm text-red-500">{error}</p>
  if (!data) return <p className="text-sm text-gray-400">Loading…</p>

  if (data.total_issues === 0) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <span>No issues on this page.</span>
        <a href={pageUrl} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline ml-2">
          View live page
        </a>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-700">
          {data.total_issues} issue{data.total_issues !== 1 ? 's' : ''}
        </span>
        <a href={pageUrl} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-500 hover:underline">
          View live page
        </a>
      </div>
      {Object.entries(data.by_category).map(([cat, issues]) => (
        <div key={cat}>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 capitalize">
            {cat.replace('_', ' ')}
          </p>
          <div className="space-y-1.5">
            {issues.map((issue, i) => {
              const helpKey = `${cat}-${i}`
              const isOpen = expandedHelp === helpKey
              const hasHelp = !!getIssueHelp(issue.issue_code)
              return (
                <div key={i}>
                  <div className="flex items-start gap-3 bg-white rounded border border-gray-200 px-3 py-2.5">
                    <SeverityBadge severity={issue.severity} />
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-gray-700">{issue.issue_code} — {issue.description}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{issue.recommendation}</p>
                    </div>
                    {hasHelp && (
                      <button
                        onClick={() => toggleHelp(helpKey)}
                        title={isOpen ? 'Hide help' : 'Show detailed help'}
                        className={`flex-shrink-0 w-5 h-5 rounded-full text-xs font-bold border transition-colors ${
                          isOpen
                            ? 'bg-blue-600 text-white border-blue-600'
                            : 'bg-white text-blue-600 border-blue-300 hover:bg-blue-50'
                        }`}
                      >
                        ?
                      </button>
                    )}
                  </div>
                  {isOpen && (
                    <div className="mt-1 ml-1">
                      <IssueHelpPanel issueCode={issue.issue_code} />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Helpers ────────────────────────────────────────────────────────────────

function shortenUrl(url) {
  try {
    const u = new URL(url)
    return u.pathname + u.search || '/'
  } catch {
    return url ?? ''
  }
}

function StatusBadge({ code }) {
  if (!code) return <span className="text-gray-400">—</span>
  const color = code < 300 ? 'text-green-700' : code < 400 ? 'text-amber-600' : 'text-red-600'
  return <span className={`font-mono font-medium ${color}`}>{code}</span>
}

function Spinner() {
  return (
    <div className="flex justify-center py-12">
      <div className="w-8 h-8 rounded-full border-4 border-gray-200 border-t-green-500 animate-spin" />
    </div>
  )
}

function ErrorMsg({ msg }) {
  return (
    <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-600">
      {msg}
    </div>
  )
}

function tabCount(summary, tabIndex) {
  if (!summary?.summary) return null
  if (tabIndex === TAB_SUMMARY) return null
  if (tabIndex === TAB_BY_PAGE) return null
  if (tabIndex === TAB_FIX_MGR) return null
  const cat = CATEGORIES[tabIndex - 1]
  return summary.summary.by_category?.[cat.key] ?? null
}

import { useState, useEffect, useCallback, useRef, forwardRef, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import IssueTable from '../components/IssueTable.jsx'
import SeverityBadge from '../components/SeverityBadge.jsx'
import IssueHelpPanel from '../components/IssueHelpPanel.jsx'
import FixManager from '../components/FixManager.jsx'
import FixInlinePanel, { FIXABLE_CODES } from '../components/FixInlinePanel.jsx'
import FixBrokenLinkPanel, { FIXABLE_LINK_CODES } from '../components/FixBrokenLinkPanel.jsx'
import { getIssueHelp } from '../data/issueHelp.js'
import { getResults, getResultsByCategory, getPages, getPageIssues, downloadCsv, rescanUrl, markFixed, authHeaders, getVerifiedLinks, addVerifiedLink, removeVerifiedLink, getPredefinedCodes, bulkTrimTitles, trimTitleOne, convertHeadingToBold, changeHeadingLevel, findHeading, bulkReplaceHeading, getFixHistory, getSuppressedCodes, addSuppressedCode, removeSuppressedCode, getExemptAnchorUrls, addExemptAnchorUrl, removeExemptAnchorUrl, getImageInfo, updateImageMeta, analyzeHeadingSources } from '../api.js'

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

// Tab indices: 0=Summary, 1–N=categories, N+1=By Page, N+2=Fix Manager, N+3=History
const TAB_SUMMARY    = 0
const TAB_BY_PAGE    = CATEGORIES.length + 1
const TAB_FIX_MGR    = CATEGORIES.length + 2
const TAB_HISTORY    = CATEGORIES.length + 3

export default function Results() {
  const { jobId } = useParams()
  const navigate  = useNavigate()
  const [activeTab, setActiveTab] = useState(TAB_SUMMARY)
  const [summary, setSummary] = useState(null)
  const [summaryError, setSummaryError] = useState(null)
  const [csvError, setCsvError] = useState(null)
  // For "navigate to By Page for a URL" from a category tab
  const [jumpToUrl, setJumpToUrl] = useState(null)
  // Verified links: Map<url, verified_at>
  const [verifiedLinks, setVerifiedLinks] = useState(new Map())
  // Predefined fix codes: Map<issue_code, fixed_value>
  const [predefinedCodes, setPredefinedCodes] = useState(new Map())
  // Suppressed issue codes: Set<string>
  const [suppressedCodes, setSuppressedCodes] = useState(new Set())
  // Exempt anchor URLs: Set<string> — hrefs excluded from LINK_EMPTY_ANCHOR
  const [exemptAnchorUrls, setExemptAnchorUrls] = useState(new Set())

  // Load summary + verified links + predefined codes + suppressed codes + exempt anchor URLs on mount
  useEffect(() => {
    getResults(jobId, { page: 1, limit: 5 })
      .then(d => setSummary(d))
      .catch(err => setSummaryError(err.message))
    getVerifiedLinks()
      .then(list => setVerifiedLinks(new Map(list.map(v => [v.url, v.verified_at]))))
      .catch(() => {})
    getPredefinedCodes()
      .then(obj => setPredefinedCodes(new Map(Object.entries(obj))))
      .catch(() => {})
    getSuppressedCodes()
      .then(codes => setSuppressedCodes(new Set(codes)))
      .catch(() => {})
    getExemptAnchorUrls()
      .then(list => setExemptAnchorUrls(new Set(list.map(e => e.url))))
      .catch(() => {})
  }, [jobId])

  async function handleExemptAnchor(url) {
    await addExemptAnchorUrl(url)
    setExemptAnchorUrls(prev => new Set([...prev, url]))
  }

  async function handleUnexemptAnchor(url) {
    await removeExemptAnchorUrl(url)
    setExemptAnchorUrls(prev => { const s = new Set(prev); s.delete(url); return s })
  }

  async function handleSuppress(code) {
    await addSuppressedCode(code)
    setSuppressedCodes(prev => new Set([...prev, code]))
    refreshSummary()
  }

  async function handleUnsuppress(code) {
    await removeSuppressedCode(code)
    setSuppressedCodes(prev => { const s = new Set(prev); s.delete(code); return s })
    refreshSummary()
  }

  async function handleVerify(url) {
    const result = await addVerifiedLink(url, jobId)
    setVerifiedLinks(prev => new Map([...prev, [url, result.verified_at]]))
    refreshSummary()
  }

  async function handleUnverify(url) {
    try {
      await removeVerifiedLink(url)
      setVerifiedLinks(prev => { const m = new Map(prev); m.delete(url); return m })
    } catch (_) {}
  }

  function refreshSummary() {
    getResults(jobId, { page: 1, limit: 5 })
      .then(d => setSummary(d))
      .catch(() => {})
  }

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
    'Fix History',
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
          suppressedCodes={suppressedCodes}
          onUnsuppress={handleUnsuppress}
          exemptAnchorUrls={exemptAnchorUrls}
          onUnexemptAnchor={handleUnexemptAnchor}
        />
      )}
      {activeTab >= 1 && activeTab <= CATEGORIES.length && (
        <CategoryTab
          jobId={jobId}
          category={CATEGORIES[activeTab - 1].key}
          onUrlClick={handleUrlClick}
          verifiedLinks={verifiedLinks}
          onVerify={handleVerify}
          onUnverify={handleUnverify}
          onRescanComplete={refreshSummary}
          predefinedCodes={predefinedCodes}
          onBulkTrimTitles={() => bulkTrimTitles(jobId)}
          suppressedCodes={suppressedCodes}
          onSuppress={handleSuppress}
          onUnsuppress={handleUnsuppress}
          exemptAnchorUrls={exemptAnchorUrls}
          onExemptAnchor={handleExemptAnchor}
        />
      )}
      {activeTab === TAB_BY_PAGE && (
        <ByPageTab jobId={jobId} jumpToUrl={jumpToUrl} onJumpConsumed={clearJumpUrl} onRescanComplete={refreshSummary}
          onNavigateToCategory={cat => {
            const idx = CATEGORIES.findIndex(c => c.key === cat)
            if (idx >= 0) setActiveTab(idx + 1)
          }}
        />
      )}
      {activeTab === TAB_FIX_MGR && (
        <FixManager jobId={jobId} />
      )}
      {activeTab === TAB_HISTORY && (
        <FixHistoryTab jobId={jobId} />
      )}
    </div>
  )
}

// ── Summary tab ────────────────────────────────────────────────────────────

function SummaryTab({ summary, error, jobId, onCategoryClick, onPageClick, suppressedCodes, onUnsuppress, exemptAnchorUrls, onUnexemptAnchor }) {
  const [activeSeverity, setActiveSeverity]     = useState(null)
  const [sevIssues, setSevIssues]               = useState(null)
  const [sevLoading, setSevLoading]             = useState(false)
  const [showScoreBreakdown, setShowScoreBreakdown] = useState(false)
  const [focusedPageUrl, setFocusedPageUrl]     = useState(null)
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

  const { summary: s } = summary
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
          <ScoreBreakdownPanel ref={scorePanelRef} summary={s} score={s.health_score ?? null} suppressedCodes={suppressedCodes} onUnsuppress={onUnsuppress} exemptAnchorUrls={exemptAnchorUrls} onUnexemptAnchor={onUnexemptAnchor} />
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

      {/* Severity-filtered issues panel — grouped by issue code */}
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
            <SeverityGroupedList issues={sevIssues} onPageClick={onPageClick} totalCount={s.by_severity?.[activeSeverity] ?? 0} severity={activeSeverity} />
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

      {/* Top 5 Priority Issue Groups */}
      <TopPriorityGroups jobId={jobId} onPageFocus={setFocusedPageUrl} />

      {/* Top 10 pages to fix */}
      <TopPagesPanel jobId={jobId} onPageClick={setFocusedPageUrl} />

      {s.total_issues === 0 && (
        <div className="text-center py-12 text-gray-400">
          <p className="text-4xl mb-3">🐸</p>
          <p className="font-medium">No issues found — great work!</p>
        </div>
      )}

      {/* Page focus panel — slide-over showing full page details */}
      {focusedPageUrl && (
        <PageFocusPanel
          jobId={jobId}
          pageUrl={focusedPageUrl}
          onClose={() => setFocusedPageUrl(null)}
        />
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

// Groups issues by issue_code; each group shows its pages as clickable links
function SeverityGroupedList({ issues, onPageClick, totalCount, severity }) {
  // Build map: issue_code -> { description, severity, pages[] }
  const groups = []
  const seen = new Map()
  for (const issue of issues) {
    const code = issue.issue_code
    if (!seen.has(code)) {
      seen.set(code, { description: issue.description, severity: issue.severity, pages: [] })
      groups.push(code)
    }
    if (issue.page_url) {
      seen.get(code).pages.push(issue.page_url)
    }
  }

  return (
    <div className="space-y-3">
      {groups.map(code => {
        const g = seen.get(code)
        return (
          <div key={code} className="border border-gray-100 rounded-lg overflow-hidden">
            {/* Issue header */}
            <div className="flex items-center gap-3 px-3 py-2.5 bg-gray-50">
              <SeverityBadge severity={g.severity} />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold text-gray-800">{code}</p>
                <p className="text-xs text-gray-500">{g.description}</p>
              </div>
              <span className="flex-shrink-0 text-xs text-gray-400">
                {g.pages.length} page{g.pages.length !== 1 ? 's' : ''}
              </span>
            </div>
            {/* Affected pages — each is a button to jump to By Page */}
            {g.pages.length > 0 && (
              <div className="divide-y divide-gray-50">
                {g.pages.map((url, j) => (
                  <button
                    key={j}
                    onClick={() => onPageClick(url)}
                    className="w-full text-left px-4 py-2 text-xs text-blue-600 hover:bg-blue-50 hover:text-blue-800 flex items-center gap-2 transition-colors"
                  >
                    <span className="flex-1 truncate">{url}</span>
                    <span className="flex-shrink-0 text-gray-400">→</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )
      })}
      {totalCount > 20 && (
        <p className="text-xs text-gray-400 pt-1">
          Showing top 20 of {totalCount} — use the category tabs above for the full list.
        </p>
      )}
    </div>
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

// Top 5 priority issue GROUPS (not individual issues)
function TopPriorityGroups({ jobId, onPageFocus }) {
  const [groups, setGroups] = useState(null)
  const [expandedCode, setExpandedCode] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Fetch all issues to group them
    getResults(jobId, { page: 1, limit: 500 })
      .then(d => {
        if (!d.issues || d.issues.length === 0) {
          setGroups([])
          setLoading(false)
          return
        }
        // Group issues by issue_code
        const map = new Map()
        for (const issue of d.issues) {
          if (!map.has(issue.issue_code)) {
            map.set(issue.issue_code, {
              code: issue.issue_code,
              category: issue.category,
              severity: issue.severity,
              description: issue.description,
              recommendation: issue.recommendation,
              priority_rank: issue.priority_rank ?? 0,
              human_description: issue.human_description ?? '',
              pages: [],
              extras: new Map(), // pageUrl -> extra data
            })
          }
          const g = map.get(issue.issue_code)
          if (issue.page_url && !g.pages.includes(issue.page_url)) {
            g.pages.push(issue.page_url)
          }
          if (issue.extra) {
            g.extras.set(issue.page_url, issue.extra)
          }
        }
        // Sort by priority_rank descending, take top 5
        const sorted = [...map.values()]
          .sort((a, b) => b.priority_rank - a.priority_rank)
          .slice(0, 5)
        setGroups(sorted)
        setLoading(false)
      })
      .catch(() => { setGroups([]); setLoading(false) })
  }, [jobId])

  if (loading) return <Spinner />
  if (!groups || groups.length === 0) return null

  const severityColors = {
    critical: 'text-red-600 bg-red-50 border-red-200',
    warning:  'text-amber-600 bg-amber-50 border-amber-200',
    info:     'text-blue-600 bg-blue-50 border-blue-200',
  }

  return (
    <div>
      <h2 className="text-base font-semibold text-gray-700 mb-3">Top 5 Priority Fixes</h2>
      <p className="text-xs text-gray-400 mb-2">Click to expand and see affected pages</p>
      <div className="space-y-2">
        {groups.map(group => {
          const isExpanded = expandedCode === group.code
          const badgeColor = severityColors[group.severity] ?? 'text-gray-600 bg-gray-50 border-gray-200'
          return (
            <div key={group.code} className="border border-gray-200 rounded-lg overflow-hidden">
              {/* Group header - clickable to expand */}
              <button
                className={`w-full text-left px-4 py-3 flex items-center gap-3 transition-colors ${
                  isExpanded ? 'bg-green-50 border-b border-green-200' : 'bg-white hover:bg-gray-50'
                }`}
                onClick={() => setExpandedCode(isExpanded ? null : group.code)}
              >
                <span className="text-gray-400 text-xs w-3 flex-shrink-0">{isExpanded ? '▼' : '▶'}</span>
                <SeverityBadge severity={group.severity} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    {group.human_description ? (
                      <span className="text-sm font-semibold text-gray-800">{group.human_description}</span>
                    ) : (
                      <span className="font-mono text-xs text-gray-700 font-medium">{group.code}</span>
                    )}
                    {group.human_description && (
                      <span className="font-mono text-xs text-gray-400">{group.code}</span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 truncate">{group.description}</p>
                </div>
                {group.priority_rank > 0 && (
                  <span className="flex-shrink-0 text-xs font-semibold px-2 py-0.5 rounded bg-gray-100 text-gray-500 border border-gray-200"
                        title={`Priority score: ${group.priority_rank}`}>
                    P{group.priority_rank}
                  </span>
                )}
                <span className={`flex-shrink-0 text-xs font-semibold px-2.5 py-1 rounded-full border ${badgeColor}`}>
                  {group.pages.length} page{group.pages.length !== 1 ? 's' : ''}
                </span>
              </button>

              {/* Expanded page list */}
              {isExpanded && group.pages.length > 0 && (
                <div className="bg-gray-50 px-4 py-2 space-y-1">
                  {group.pages.slice(0, 20).map((pageUrl, i) => {
                    const extra = group.extras.get(pageUrl)
                    return (
                      <div key={pageUrl} className="flex items-start gap-2 py-1">
                        <span className="text-xs text-gray-400 w-5 text-right flex-shrink-0">{i + 1}.</span>
                        <div className="flex-1 min-w-0">
                          <button
                            onClick={() => onPageFocus?.(pageUrl)}
                            className="text-xs text-blue-600 hover:underline text-left break-all"
                            title={pageUrl}
                          >
                            {shortenUrl(pageUrl)}
                          </button>
                          {/* Show extra details inline */}
                          {extra?.title && (group.code.includes('TITLE') || group.code === 'TITLE_META_DUPLICATE_PAIR') && (
                            <p className="text-xs text-gray-500 truncate mt-0.5">
                              <span className="font-medium">Title:</span> "{extra.title}"
                            </p>
                          )}
                          {extra?.description && (group.code.includes('META_DESC') || group.code === 'TITLE_META_DUPLICATE_PAIR') && (
                            <p className="text-xs text-gray-500 truncate mt-0.5">
                              <span className="font-medium">Desc:</span> "{extra.description?.slice(0, 60)}..."
                            </p>
                          )}
                          {extra?.h1_tags && group.code === 'H1_MULTIPLE' && (
                            <p className="text-xs text-gray-500 mt-0.5">
                              <span className="font-medium">H1s:</span> {extra.h1_tags.map((h, j) => `"${h}"`).join(', ')}
                            </p>
                          )}
                        </div>
                        <button
                          onClick={() => onPageFocus?.(pageUrl)}
                          className="flex-shrink-0 text-xs text-indigo-600 hover:text-indigo-800"
                        >
                          Details →
                        </button>
                      </div>
                    )
                  })}
                  {group.pages.length > 20 && (
                    <p className="text-xs text-gray-400 pt-1">
                      ...and {group.pages.length - 20} more pages
                    </p>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
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

const ScoreBreakdownPanel = forwardRef(function ScoreBreakdownPanel({ summary, score, suppressedCodes, onUnsuppress, exemptAnchorUrls, onUnexemptAnchor }, ref) {
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

      {/* Suppressed codes */}
      {suppressedCodes && suppressedCodes.size > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">
            Excluded from score
          </p>
          <div className="flex flex-wrap gap-2">
            {[...suppressedCodes].map(code => (
              <span key={code} className="flex items-center gap-1 bg-gray-100 border border-gray-200 rounded px-2 py-0.5 text-xs text-gray-600">
                <span className="font-mono">{code}</span>
                <button
                  onClick={() => onUnsuppress?.(code)}
                  title="Re-include in score"
                  className="text-gray-400 hover:text-red-500 leading-none ml-0.5"
                >✕</button>
              </span>
            ))}
          </div>
          <p className="text-xs text-gray-400 mt-1.5">
            These issue types are still shown in the issue lists but their impact is not counted in the health score.
          </p>
        </div>
      )}

      {exemptAnchorUrls && exemptAnchorUrls.size > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">
            Exempt icon links (no anchor text expected)
          </p>
          <div className="flex flex-col gap-1">
            {[...exemptAnchorUrls].map(url => (
              <span key={url} className="flex items-center gap-1 bg-blue-50 border border-blue-100 rounded px-2 py-0.5 text-xs text-gray-600">
                <span className="font-mono truncate flex-1" title={url}>{url}</span>
                <button
                  onClick={() => onUnexemptAnchor?.(url)}
                  title="Remove exemption — this link will be flagged again"
                  className="text-gray-400 hover:text-red-500 leading-none ml-0.5 flex-shrink-0"
                >✕</button>
              </span>
            ))}
          </div>
          <p className="text-xs text-gray-400 mt-1.5">
            These URLs are allowed to have no anchor text (e.g. social media icon links). Takes effect on the next crawl.
          </p>
        </div>
      )}
    </div>
  )
})

// ── Category tab ───────────────────────────────────────────────────────────

const SEV_ORDER = { critical: 0, warning: 1, info: 2 }

// Issue codes where the description is unique per page (contains per-page data like offending URLs)
const PER_PAGE_DESC_CODES = new Set(['LINK_EMPTY_ANCHOR', 'BROKEN_LINK'])

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

// Issue codes where page_url is the source page and extra.target_url is the actual broken link
const BROKEN_LINK_CODES = new Set([
  'BROKEN_LINK_404', 'BROKEN_LINK_410', 'BROKEN_LINK_5XX', 'BROKEN_LINK_503',
  'EXTERNAL_LINK_TIMEOUT', 'EXTERNAL_LINK_SKIPPED',
])

function groupIssues(issues) {
  const map = new Map()
  for (const issue of issues) {
    if (!map.has(issue.issue_code)) {
      map.set(issue.issue_code, {
        code: issue.issue_code,
        category: issue.category ?? '',
        severity: issue.severity,
        description: issue.description,
        recommendation: issue.recommendation,
        priority_rank: issue.priority_rank ?? 0,
        impact: issue.impact ?? 0,
        effort: issue.effort ?? 0,
        human_description: issue.human_description ?? '',
        pages: [],
        // For broken link issues: collect the broken URLs separately
        brokenUrls: [],
      })
    }
    // For broken link issues, page_url is the source page and extra.target_url is the broken link
    const isBrokenLink = BROKEN_LINK_CODES.has(issue.issue_code)
    const brokenUrl = isBrokenLink ? issue.extra?.target_url : null

    map.get(issue.issue_code).pages.push(issue.page_url)
    if (brokenUrl) {
      map.get(issue.issue_code).brokenUrls.push(brokenUrl)
    }
    // Always store per-page descriptions so every page can show its own detail
    // (e.g. LINK_EMPTY_ANCHOR embeds the offending hrefs per page)
    if (!map.get(issue.issue_code).pageDescriptions) {
      map.get(issue.issue_code).pageDescriptions = new Map()
    }
    // For broken links, key by the broken URL so the UI can look up descriptions
    const descKey = brokenUrl || issue.page_url
    map.get(issue.issue_code).pageDescriptions.set(descKey, issue.description)
    // Store extra data (e.g. TITLE_H1_MISMATCH stores {title, h1})
    if (issue.extra) {
      if (!map.get(issue.issue_code).pageExtras) {
        map.get(issue.issue_code).pageExtras = new Map()
      }
      map.get(issue.issue_code).pageExtras.set(issue.page_url, issue.extra)
    }
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

function CategoryTab({ jobId, category, onUrlClick, verifiedLinks, onVerify, onUnverify, onRescanComplete, predefinedCodes, onBulkTrimTitles, suppressedCodes, onSuppress, onUnsuppress, exemptAnchorUrls, onExemptAnchor }) {
  const [allIssues, setAllIssues] = useState(null)
  const [severity, setSeverity] = useState('')
  const [quickWins, setQuickWins] = useState(false)
  const [error, setError] = useState(null)
  const [expandedCode, setExpandedCode] = useState(null)
  // fixHistory: Map<issueCode, Map<pageUrl, fixed_at>>
  const [fixHistory, setFixHistory] = useState(new Map())
  // Focused page panel — shows full PageDetail for a single page without leaving category view
  const [focusedPageUrl, setFocusedPageUrl] = useState(null)

  const loadIssues = useCallback(() => {
    setError(null)
    setAllIssues(null)
    getResultsByCategory(jobId, category, { page: 1, limit: 5000, severity: severity || undefined })
      .then(d => setAllIssues(d.issues))
      .catch(err => setError(err.message))
  }, [jobId, category, severity])

  const loadFixHistory = useCallback(() => {
    getFixHistory(jobId).then(records => {
      const map = new Map()
      for (const { issue_code, page_url, fixed_at } of records) {
        if (!map.has(issue_code)) map.set(issue_code, new Map())
        map.get(issue_code).set(page_url, fixed_at)
      }
      setFixHistory(map)
    }).catch(() => {})
  }, [jobId])

  useEffect(() => {
    setExpandedCode(null)
    loadIssues()
    loadFixHistory()
  }, [jobId, category, severity]) // eslint-disable-line react-hooks/exhaustive-deps

  function handlePageRescan() {
    loadIssues()
    loadFixHistory()
    onRescanComplete?.()
  }

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

      {/* Heading Find & Replace — headings category only */}
      {category === 'heading' && (
        <HeadingFindReplacePanel jobId={jobId} onApplied={loadIssues} />
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
              pageDescriptions={group.pageDescriptions ?? new Map()}
              pageExtras={group.pageExtras ?? new Map()}
              jobId={jobId}
              expanded={expandedCode === group.code}
              onToggle={() => setExpandedCode(c => c === group.code ? null : group.code)}
              onUrlClick={onUrlClick}
              onPageFocus={setFocusedPageUrl}
              verifiedLinks={verifiedLinks}
              onVerify={onVerify}
              onUnverify={onUnverify}
              onRescanComplete={onRescanComplete}
              onPageRescan={handlePageRescan}
              predefinedCodes={predefinedCodes}
              onBulkTrimTitles={onBulkTrimTitles}
              fixHistory={fixHistory.get(group.code) ?? new Map()}
              isSuppressed={suppressedCodes?.has(group.code) ?? false}
              onSuppress={onSuppress}
              onUnsuppress={onUnsuppress}
              exemptAnchorUrls={exemptAnchorUrls}
              onExemptAnchor={onExemptAnchor}
            />
          ))}
        </div>
      )}

      {/* Page focus panel — slide-over showing full PageDetail for a single page */}
      {focusedPageUrl && (
        <PageFocusPanel
          jobId={jobId}
          pageUrl={focusedPageUrl}
          onClose={() => setFocusedPageUrl(null)}
          onRescanComplete={() => { handlePageRescan(); onRescanComplete?.() }}
        />
      )}
    </div>
  )
}

// ── Bulk trim button — strips site name from all too-long titles at once ───

// ── Page focus panel ───────────────────────────────────────────────────────
// A right-side slide-over that shows full PageDetail for a single URL,
// keeping the user in the category view (no tab switch needed).

function PageFocusPanel({ jobId, pageUrl, onClose, onRescanComplete }) {
  // Close on Escape key
  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
        aria-hidden="true"
      />
      {/* Panel */}
      <div className="relative z-10 flex flex-col w-full max-w-2xl bg-white shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-200 bg-gray-50 flex-shrink-0">
          <div className="flex-1 min-w-0">
            <p className="text-xs text-gray-400 mb-0.5">Page details</p>
            <p className="text-sm font-medium text-gray-800 break-all leading-snug">{shortenUrl(pageUrl)}</p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <a
              href={pageUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-blue-500 hover:underline"
            >
              View live ↗
            </a>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-700 text-lg leading-none px-1"
              title="Close (Esc)"
            >
              ✕
            </button>
          </div>
        </div>
        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto p-4">
          <PageDetail
            jobId={jobId}
            pageUrl={pageUrl}
            onRescanComplete={onRescanComplete}
          />
        </div>
      </div>
    </div>
  )
}

function BulkTrimButton({ count, onRun }) {
  const [state, setState] = useState('idle') // idle | running | done | error
  const [results, setResults] = useState(null)

  async function handleRun() {
    setState('running')
    try {
      const data = await onRun()
      setResults(data)
      setState('done')
    } catch (err) {
      setResults([{ success: false, error: err.message }])
      setState('error')
    }
  }

  if (state === 'idle') {
    return (
      <button
        onClick={handleRun}
        className="flex-shrink-0 text-xs font-medium px-3 py-1.5 rounded-lg bg-amber-600 text-white hover:bg-amber-700 transition-colors whitespace-nowrap"
        title="Automatically strip the site name from all too-long titles"
      >
        Bulk trim {count} titles
      </button>
    )
  }
  if (state === 'running') {
    return <span className="flex-shrink-0 text-xs text-amber-700 font-medium">Trimming titles…</span>
  }
  const succeeded = results?.filter(r => r.success).length ?? 0
  const failed = results?.filter(r => !r.success).length ?? 0
  return (
    <span className={`flex-shrink-0 text-xs font-medium ${failed ? 'text-amber-700' : 'text-green-700'}`}>
      ✓ {succeeded} trimmed{failed > 0 ? `, ${failed} skipped` : ''}
    </span>
  )
}

// ── Broken link row — expandable, shows source pages + bulk fix + rescan ───

function BrokenLinkRow({ jobId, brokenUrl, index, isFixable, isVerifiable, verifiedAt, onVerify, onUnverify, onRescanComplete }) {
  const [expanded,      setExpanded]      = useState(false)
  const [sources,       setSources]       = useState(null)   // null = not yet loaded
  const [loadingSource, setLoadingSource] = useState(false)
  const [sourceError,   setSourceError]   = useState(null)
  const [newUrl,        setNewUrl]        = useState('')
  const [verifying,     setVerifying]     = useState(false)
  const [verifyError,   setVerifyError]   = useState(null)
  const [applying,      setApplying]      = useState(false)
  const [applyResults,  setApplyResults]  = useState(null)   // {applied:[...], failed:[...]}
  const [rescanning,    setRescanning]    = useState(false)
  const [rescanResults, setRescanResults] = useState(null)
  const inputRef = useRef(null)

  async function handleVerifyClick(e) {
    e.stopPropagation()
    setVerifying(true)
    setVerifyError(null)
    try {
      await onVerify?.(brokenUrl)
      // Auto-load source pages after verifying so user can rescan them
      if (sources === null && jobId) {
        setLoadingSource(true)
        const params = new URLSearchParams({ job_id: jobId, target_url: brokenUrl })
        fetch(`/api/fixes/link-sources?${params}`, { headers: authHeaders() })
          .then(r => r.json())
          .then(d => { setSources(Array.isArray(d) ? d : []); setLoadingSource(false) })
          .catch(() => { setSources([]); setLoadingSource(false) })
        setExpanded(true)
      }
    } catch (err) {
      setVerifyError(err.message || 'Verify failed')
    } finally {
      setVerifying(false)
    }
  }

  function toggle() {
    if (!expanded && sources === null && jobId) {
      setLoadingSource(true)
      setSourceError(null)
      const params = new URLSearchParams({ job_id: jobId, target_url: brokenUrl })
      fetch(`/api/fixes/link-sources?${params}`, { headers: authHeaders() })
        .then(r => r.json())
        .then(d => { setSources(Array.isArray(d) ? d : []); setLoadingSource(false) })
        .catch(e => { setSourceError(e.message); setLoadingSource(false) })
    }
    setExpanded(v => !v)
  }

  async function handleApplyAll() {
    if (!newUrl.trim() || !sources?.length) return
    setApplying(true)
    const applied = [], failed = []
    for (const s of sources) {
      try {
        const res = await fetch('/api/fixes/replace-link', {
          method: 'POST',
          headers: authHeaders(),
          body: JSON.stringify({ job_id: jobId, source_url: s.source_url, old_url: brokenUrl, new_url: newUrl.trim() }),
        })
        const data = await res.json()
        if (data.success) applied.push(s.source_url)
        else failed.push({ url: s.source_url, error: data.error || 'Apply failed' })
      } catch (e) {
        failed.push({ url: s.source_url, error: e.message })
      }
    }
    setApplyResults({ applied, failed })
    setApplying(false)
    // Focus nothing — show rescan prompt
  }

  async function handleRescanAll() {
    if (!applyResults?.applied.length) return
    setRescanning(true)
    const results = []
    for (const url of applyResults.applied) {
      try {
        const params = new URLSearchParams({ url })
        const res = await fetch(`/api/crawl/${jobId}/rescan-url?${params}`, {
          method: 'POST', headers: authHeaders(),
        })
        const data = await res.json()
        results.push({ url, resolved: data.resolved ?? 0, added: data.added ?? 0, error: data.error?.message })
      } catch (e) {
        results.push({ url, error: e.message })
      }
    }
    setRescanResults(results)
    setRescanning(false)
    if (results.some(r => (r.resolved ?? 0) > 0 || (r.added ?? 0) > 0)) {
      onRescanComplete?.()
    }
  }

  async function handleRescanSourcePages(urlList) {
    setRescanning(true)
    const results = []
    for (const url of urlList) {
      try {
        const params = new URLSearchParams({ url })
        const res = await fetch(`/api/crawl/${jobId}/rescan-url?${params}`, {
          method: 'POST', headers: authHeaders(),
        })
        const data = await res.json()
        results.push({ url, resolved: data.resolved ?? 0, added: data.added ?? 0, error: data.error?.message })
      } catch (e) {
        results.push({ url, error: e.message })
      }
    }
    setRescanResults(results)
    setRescanning(false)
    if (results.some(r => (r.resolved ?? 0) > 0 || (r.added ?? 0) > 0)) {
      onRescanComplete?.()
    }
  }

  const hasSources    = sources && sources.length > 0
  const allApplied    = applyResults && sources && applyResults.applied.length >= sources.length
  const someApplied   = applyResults?.applied.length > 0
  const pendingSources = sources?.filter(s => !applyResults?.applied.includes(s.source_url)) ?? []

  return (
    <li className="flex flex-col">
      {/* Row header — div not button because it contains interactive children */}
      <div className="flex items-center gap-2 px-4 py-2.5 hover:bg-gray-50 cursor-pointer" onClick={toggle}>
        <span className="text-xs text-gray-300 w-8 text-right flex-shrink-0">{index + 1}.</span>
        <span className="text-gray-400 text-xs w-3 flex-shrink-0">{expanded ? '▼' : '▶'}</span>
        <span className="text-xs text-gray-700 truncate flex-1 font-mono" title={brokenUrl}>{brokenUrl}</span>
        <a href={brokenUrl} target="_blank" rel="noopener noreferrer"
           onClick={e => e.stopPropagation()}
           className="flex-shrink-0 text-xs text-blue-500 hover:text-blue-700" title="Open in new tab to verify">↗</a>
        {isVerifiable && (
          verifiedAt ? (
            <span className="flex items-center gap-1 flex-shrink-0" onClick={e => e.stopPropagation()}>
              <span className="text-xs text-green-700 font-medium bg-green-50 border border-green-200 rounded px-1.5 py-0.5"
                    title={`Verified on ${verifiedAt}`}>
                Verified {new Date(verifiedAt).toLocaleDateString()}
              </span>
              <button
                onClick={e => { e.stopPropagation(); onUnverify?.(brokenUrl) }}
                title="Remove from verified list"
                className="text-xs text-gray-400 hover:text-red-500 leading-none px-1"
              >✕</button>
            </span>
          ) : (
            <button
              onClick={handleVerifyClick}
              disabled={verifying}
              title="Mark as verified — this link is intentional and correct"
              className="flex-shrink-0 text-xs px-2 py-0.5 rounded border border-green-400 text-green-700 hover:bg-green-50 disabled:opacity-50 transition-colors"
            >
              {verifying ? 'Verifying…' : 'Verify'}
            </button>
          )
        )}
        {verifyError && (
          <span className="flex-shrink-0 text-xs text-red-500" title={verifyError}>Error</span>
        )}
        {allApplied && <span className="flex-shrink-0 text-xs font-medium text-green-600">Fixed ✓</span>}
      </div>

      {/* Expanded panel */}
      {expanded && (
        <div className="border-t border-orange-100 bg-orange-50 px-5 py-3 space-y-3">

          {/* Source pages */}
          <div>
            <p className="text-xs font-semibold text-gray-600 mb-1.5">
              {!jobId              ? 'Sign in required to view source pages.' :
               loadingSource       ? 'Finding pages that link here…' :
               sourceError         ? `Could not load source pages: ${sourceError}` :
               !sources            ? '' :
               sources.length === 0 ? 'Source pages not found — run a new crawl to populate this data.' :
               sources.length === 1 ? 'This broken link is on 1 page:' :
                                      `This broken link is on ${sources.length} pages:`}
            </p>
            {hasSources && (
              <ul className="space-y-1">
                {sources.map(s => {
                  const applied = applyResults?.applied.includes(s.source_url)
                  const fail    = applyResults?.failed.find(f => f.url === s.source_url)
                  const rescan  = rescanResults?.find(r => r.url === s.source_url)
                  return (
                    <li key={s.source_url} className="flex items-center gap-2 text-xs">
                      <span className={`flex-1 truncate ${applied ? 'text-green-700' : 'text-gray-700'}`} title={s.source_url}>
                        {shortenUrl(s.source_url)}
                        {s.link_text && <span className="text-gray-400 ml-1">— "{s.link_text}"</span>}
                      </span>
                      <a href={s.source_url} target="_blank" rel="noopener noreferrer"
                         className="flex-shrink-0 text-blue-400 hover:text-blue-600" title="Open page">↗</a>
                      {applied  && !fail && <span className="flex-shrink-0 text-green-600 font-medium">✓ fixed</span>}
                      {fail     && <span className="flex-shrink-0 text-red-500" title={fail.error}>✗ {fail.error}</span>}
                      {rescan && !rescan.error && (
                        <span className={`flex-shrink-0 font-medium ${rescan.resolved > 0 ? 'text-green-600' : 'text-gray-400'}`}>
                          {rescan.resolved > 0 ? `✓ ${rescan.resolved} resolved` : 'no change'}
                        </span>
                      )}
                    </li>
                  )
                })}
              </ul>
            )}
          </div>

          {/* Fix form — only if fixable, has sources, and not all done */}
          {isFixable && hasSources && !allApplied && (
            <div className="space-y-2">
              <div>
                <p className="text-xs text-gray-500 mb-1">Replace broken URL with:</p>
                <input
                  ref={inputRef}
                  type="url"
                  className="w-full border border-gray-300 rounded px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-orange-400 focus:border-orange-400"
                  placeholder="https://example.com/working-page"
                  value={newUrl}
                  onChange={e => setNewUrl(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') handleApplyAll() }}
                />
              </div>
              {applyResults?.failed.length > 0 && (
                <p className="text-xs text-red-600">
                  {applyResults.failed.length} page{applyResults.failed.length !== 1 ? 's' : ''} failed — see ✗ above.
                </p>
              )}
              <button
                onClick={handleApplyAll}
                disabled={applying || !newUrl.trim()}
                className="px-3 py-1.5 text-xs font-medium bg-orange-600 text-white rounded hover:bg-orange-700 disabled:opacity-50 transition-colors"
              >
                {applying
                  ? 'Applying…'
                  : pendingSources.length === 1
                    ? 'Apply fix'
                    : `Apply fix to all ${pendingSources.length} pages`}
              </button>
            </div>
          )}

          {/* Rescan prompt after fix */}
          {someApplied && !rescanResults && (
            <div className="flex items-center gap-3 pt-1 border-t border-orange-200">
              <span className="text-xs text-green-700">
                ✓ Fixed on {applyResults.applied.length} page{applyResults.applied.length !== 1 ? 's' : ''}.
              </span>
              <button
                onClick={handleRescanAll}
                disabled={rescanning}
                className="text-xs px-2.5 py-1 border border-green-500 text-green-700 rounded hover:bg-green-50 disabled:opacity-50 transition-colors"
              >
                {rescanning ? 'Rescanning…' : `Rescan ${applyResults.applied.length > 1 ? 'all pages' : 'page'} to verify`}
              </button>
            </div>
          )}

          {/* Rescan source pages after verifying */}
          {isVerifiable && verifiedAt && hasSources && !rescanResults && (
            <div className="flex items-center gap-3 pt-1 border-t border-green-200">
              <span className="text-xs text-green-700">✓ Verified. Rescan to confirm issues are cleared.</span>
              <button
                onClick={() => handleRescanSourcePages(sources.map(s => s.source_url))}
                disabled={rescanning}
                className="text-xs px-2.5 py-1 border border-green-500 text-green-700 rounded hover:bg-green-50 disabled:opacity-50 transition-colors"
              >
                {rescanning ? 'Rescanning…' : `Rescan ${sources.length > 1 ? `all ${sources.length} pages` : 'page'}`}
              </button>
            </div>
          )}

          {/* Rescan results */}
          {rescanResults && (
            <div className="pt-1 border-t border-orange-200 space-y-0.5">
              {rescanResults.map(r => (
                <p key={r.url} className={`text-xs ${r.error ? 'text-red-600' : r.resolved > 0 ? 'text-green-700' : 'text-gray-500'}`}>
                  {shortenUrl(r.url)}: {r.error
                    ? `Error — ${r.error}`
                    : r.resolved > 0
                      ? `✓ ${r.resolved} issue${r.resolved !== 1 ? 's' : ''} resolved`
                      : r.added > 0
                        ? `${r.added} new issue${r.added !== 1 ? 's' : ''} found`
                        : 'No change in issues'}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </li>
  )
}


function IssueGroup({ group, pageDescriptions, pageExtras, jobId, expanded, onToggle, onUrlClick, onPageFocus, verifiedLinks, onVerify, onUnverify, onRescanComplete, onPageRescan, predefinedCodes, onBulkTrimTitles, fixHistory, isSuppressed, onSuppress, onUnsuppress, exemptAnchorUrls, onExemptAnchor }) {
  const help = getIssueHelp(group.code)
  const [showHelp, setShowHelp] = useState(false)
  const [pageOffset, setPageOffset] = useState(0)
  const [openFixUrl, setOpenFixUrl] = useState(null)
  // per-page rescan state: Map<url, 'scanning'|'done'|'error'|'nochange'>
  const [rescanStates, setRescanStates] = useState(new Map())
  const PAGE_SIZE = 20
  const isPredefined = predefinedCodes?.has(group.code) ?? false
  const predefinedValue = predefinedCodes?.get(group.code) ?? null
  const isFixable = FIXABLE_CODES.has(group.code) || isPredefined
  const isFixableLink = FIXABLE_LINK_CODES.has(group.code)
  const isBulkTrimmable = group.code === 'TITLE_TOO_LONG'
  // Broken link groups show external URLs — different click/display behaviour
  const isBrokenLink = group.category === 'broken_link'

  async function handleRescanPage(pageUrl) {
    setRescanStates(prev => new Map(prev).set(pageUrl, 'scanning'))
    try {
      const result = await rescanUrl(jobId, pageUrl)
      setRescanStates(prev => new Map(prev).set(pageUrl,
        result.resolved > 0 ? 'done' : result.added > 0 ? 'worse' : 'nochange'
      ))
      onPageRescan?.()
    } catch (_) {
      setRescanStates(prev => new Map(prev).set(pageUrl, 'error'))
    }
  }

  const visiblePages = group.pages.slice(pageOffset, pageOffset + PAGE_SIZE)
  // For broken links, show count of broken URLs; for others, show count of affected pages
  const totalPages = isBrokenLink ? (group.brokenUrls?.length ?? 0) : group.pages.length

  const severityColors = {
    critical: 'text-red-600 bg-red-50 border-red-200',
    warning:  'text-amber-600 bg-amber-50 border-amber-200',
    info:     'text-blue-600 bg-blue-50 border-blue-200',
  }
  const badgeColor = severityColors[group.severity] ?? 'text-gray-600 bg-gray-50 border-gray-200'
  const missionLabel = getMissionImpactLabel(group.impact)

  return (
    <div className={`rounded-xl border transition-colors ${
      isSuppressed
        ? 'border-gray-200 bg-gray-50 opacity-75'
        : expanded ? 'border-green-300 bg-white' : 'border-gray-200 bg-white hover:border-gray-300'
    }`}>
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
        {/* Suppress from score toggle */}
        <button
          onClick={e => {
            e.stopPropagation()
            isSuppressed ? onUnsuppress?.(group.code) : onSuppress?.(group.code)
          }}
          title={isSuppressed
            ? 'Re-include this issue type in the health score'
            : 'Exclude this issue type from the health score calculation'}
          className={`flex-shrink-0 text-xs font-medium px-2 py-0.5 rounded border transition-colors ${
            isSuppressed
              ? 'bg-gray-200 text-gray-500 border-gray-300 hover:bg-red-50 hover:text-red-600 hover:border-red-300'
              : 'bg-white text-gray-400 border-gray-200 hover:bg-gray-100 hover:text-gray-600'
          }`}
        >
          {isSuppressed ? '⊘ Excluded' : '⊘'}
        </button>
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
          {/* Recommendation + bulk actions */}
          <div className="px-4 py-2.5 bg-gray-50 border-b border-gray-100 flex items-center gap-3">
            <p className="text-xs text-gray-500 flex-1">{group.recommendation}</p>
            {isBulkTrimmable && jobId && onBulkTrimTitles && (
              <BulkTrimButton count={totalPages} onRun={onBulkTrimTitles} />
            )}
          </div>

          {/* Page list — broken links show source pages first; others show the affected page */}
          {isBrokenLink ? (
            <BrokenLinkSourceView
              brokenUrls={group.brokenUrls}
              issueCode={group.code}
              jobId={jobId}
              fixHistory={fixHistory}
              onPageRescan={onPageRescan}
              onUrlClick={onPageFocus ?? onUrlClick}
            />
          ) : (
            <>
              <ul className="divide-y divide-gray-100">
                {visiblePages.map((pageUrl, i) => (
                  <PageDetailRow
                    key={pageUrl}
                    index={pageOffset + i}
                    pageUrl={pageUrl}
                    jobId={jobId}
                    issueCode={group.code}
                    pageDescription={(() => {
                      const desc = pageDescriptions?.get(pageUrl)
                      if (!desc) return null
                      // For codes with unique per-page descriptions (e.g. LINK_EMPTY_ANCHOR lists hrefs),
                      // always show. For others, only show when it differs from the group description.
                      return PER_PAGE_DESC_CODES.has(group.code) || desc !== group.description ? desc : null
                    })()}
                    pageExtra={pageExtras?.get(pageUrl) ?? null}
                    fixedAt={fixHistory?.has(pageUrl) ? fixHistory.get(pageUrl) : null}
                    rescanState={rescanStates.get(pageUrl)}
                    onPageFocus={onPageFocus}
                    onRescanPage={handleRescanPage}
                    isFixable={isFixable}
                    openFixUrl={openFixUrl}
                    setOpenFixUrl={setOpenFixUrl}
                    predefinedValue={predefinedValue}
                    exemptAnchorUrls={group.code === 'LINK_EMPTY_ANCHOR' ? exemptAnchorUrls : null}
                    onExemptAnchor={group.code === 'LINK_EMPTY_ANCHOR' ? onExemptAnchor : null}
                  />
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
            </>
          )}
        </div>
      )}
    </div>
  )
}

// ── Page detail row — issue page with Get Details / Rescan / Fix buttons ───

// Map an issue code + page_data → the actual offending text to show the user
function getOffendingContent(issueCode, pageData) {
  if (!pageData) return null
  const p = pageData
  const kb = p.response_size_bytes ? `${(p.response_size_bytes / 1024).toFixed(1)} KB` : null

  const map = {
    TITLE_MISSING:          { label: 'Title', value: null, missing: true },
    TITLE_TOO_LONG:         { label: 'Title', value: p.title },
    TITLE_TOO_SHORT:        { label: 'Title', value: p.title },
    TITLE_DUPLICATE:        { label: 'Title', value: p.title },
    TITLE_META_DUPLICATE_PAIR: { label: 'Title', value: p.title },
    META_DESC_MISSING:      { label: 'Meta description', value: null, missing: true },
    META_DESC_TOO_LONG:     { label: 'Meta description', value: p.meta_description },
    META_DESC_TOO_SHORT:    { label: 'Meta description', value: p.meta_description },
    META_DESC_DUPLICATE:    { label: 'Meta description', value: p.meta_description },
    H1_MISSING:             { label: 'H1', value: null, missing: true },
    H1_MULTIPLE:            { label: 'H1 tags', value: (p.h1_tags || []).map((t, i) => `[${i + 1}] ${t}`).join('\n') },
    H1_DUPLICATE:           { label: 'H1', value: (p.h1_tags || [])[0] },
    HEADING_SKIP:           { label: 'Heading outline', value: (p.headings_outline || []).map(h => `H${h.level}: ${h.text}`).join(' → ') },
    NOINDEX_META:           { label: 'Robots tag', value: p.robots_directive },
    NOINDEX_HEADER:         { label: 'X-Robots-Tag', value: p.robots_directive },
    CANONICAL_EXTERNAL:     { label: 'Canonical URL', value: p.canonical_url },
    CANONICAL_MISSING:      { label: 'Canonical URL', value: null, missing: true },
    REDIRECT_CHAIN:         { label: 'Redirect chain', value: (p.redirect_chain || []).concat(p.redirect_url || []).join(' → ') },
    REDIRECT_LOOP:          { label: 'Redirect chain', value: (p.redirect_chain || []).join(' → ') },
    OG_TITLE_MISSING:       { label: 'OG title', value: null, missing: true },
    OG_DESC_MISSING:        { label: 'OG description', value: null, missing: true },
    OG_TITLE_MISMATCH:      { label: 'OG title', value: p.og_title },
    AMPHTML_BROKEN:         { label: 'AMP URL', value: p.amphtml_url },
    META_REFRESH:           { label: 'Meta refresh URL', value: p.meta_refresh_url },
    PAGE_SIZE_LARGE:        { label: 'Page size', value: kb },
  }
  return map[issueCode] ?? null
}

function TitleH1MismatchPanel({ jobId, pageUrl, pageExtra, onClose, onEditH1 }) {
  const TOKEN = import.meta.env.VITE_AUTH_TOKEN || ''
  const authH = () => {
    const h = { 'Content-Type': 'application/json' }
    if (TOKEN) h['Authorization'] = `Bearer ${TOKEN}`
    return h
  }

  // Seed from pageExtra immediately (stored in the issue record).
  // Fall back to fetching from the page record if extra is absent (old crawls).
  const [crawledTitle, setCrawledTitle] = useState(pageExtra?.title ?? null)
  const [crawledH1,    setCrawledH1]    = useState(pageExtra?.h1    ?? null)
  const [pageError,    setPageError]    = useState(null)

  // WordPress SEO title (editable)
  const [proposed,   setProposed]   = useState('')
  const [wpLoading,  setWpLoading]  = useState(true)
  const [wpError,    setWpError]    = useState(null)
  const [applying,   setApplying]   = useState(false)
  const [applyError, setApplyError] = useState(null)
  const [applied,    setApplied]    = useState(false)

  useEffect(() => {
    // If pageExtra didn't have both values, fetch from the stored page record
    if (!pageExtra?.title || !pageExtra?.h1) {
      const params = new URLSearchParams({ url: pageUrl })
      fetch(`/api/crawl/${jobId}/pages/issues?${params}`, { headers: authH() })
        .then(async r => {
          const d = await r.json().catch(() => ({}))
          if (!r.ok) throw new Error(d.error?.message || `HTTP ${r.status}`)
          return d
        })
        .then(d => {
          setCrawledTitle(d.page_data?.title || '(none)')
          setCrawledH1((d.page_data?.h1_tags ?? [])[0] || '(none)')
        })
        .catch(e => setPageError(`Could not load page data: ${e.message}`))
    }

    // Fetch current WordPress SEO title for editing
    const wpParams = new URLSearchParams({ job_id: jobId, page_url: pageUrl, field: 'seo_title' })
    fetch(`/api/fixes/wp-value?${wpParams}`, { headers: authH() })
      .then(async r => {
        const d = await r.json().catch(() => ({}))
        if (!r.ok) throw new Error(d.error?.message || `HTTP ${r.status}`)
        return d
      })
      .then(d => { setProposed(d.current_value ?? ''); setWpLoading(false) })
      .catch(e => { setWpError(e.message); setWpLoading(false) })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleApply() {
    if (!proposed.trim()) return
    setApplying(true)
    setApplyError(null)
    try {
      const r = await fetch('/api/fixes/apply-one', {
        method: 'POST',
        headers: authH(),
        body: JSON.stringify({ job_id: jobId, page_url: pageUrl, field: 'seo_title', proposed_value: proposed, issue_code: 'TITLE_H1_MISMATCH' }),
      })
      const d = await r.json().catch(() => ({}))
      if (!r.ok || !d.success) throw new Error(d.error?.message || d.error || 'Apply failed')
      setApplied(true)
    } catch (e) {
      setApplyError(e.message)
    } finally {
      setApplying(false)
    }
  }

  const overLimit = proposed.length > 60

  return (
    <div className="mx-4 mb-2 mt-0.5 bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm shadow-sm space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-amber-800 uppercase tracking-wide">Title &amp; H1 Mismatch</span>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
      </div>

      {/* Side-by-side comparison — always rendered, shows values or loading state */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="text-xs font-semibold text-gray-600 mb-1">Page &lt;title&gt; tag</p>
          <p className="text-xs bg-white border border-gray-200 rounded px-2 py-1.5 break-words min-h-[2rem]">
            {crawledTitle ?? <span className="text-gray-400 italic">loading…</span>}
          </p>
        </div>
        <div>
          <p className="text-xs font-semibold text-gray-600 mb-1">Page &lt;h1&gt; heading</p>
          <p className="text-xs bg-white border border-gray-200 rounded px-2 py-1.5 break-words min-h-[2rem]">
            {crawledH1 ?? <span className="text-gray-400 italic">loading…</span>}
          </p>
        </div>
      </div>
      {pageError && <p className="text-xs text-red-500">{pageError}</p>}

      {/* Edit SEO title */}
      <div className="border-t border-amber-200 pt-3">
        <p className="text-xs font-semibold text-gray-700 mb-1">Edit SEO Title in WordPress</p>
        {wpLoading && <p className="text-xs text-amber-700">Loading current WordPress value…</p>}
        {wpError   && <p className="text-xs text-red-600">{wpError}</p>}
        {applied   && <p className="text-xs text-green-700 font-medium">✓ Title updated in WordPress.</p>}
        {!wpLoading && !wpError && !applied && (
          <>
            <textarea
              rows={2}
              value={proposed}
              onChange={e => setProposed(e.target.value)}
              className={`w-full border rounded px-2 py-1.5 text-xs focus:outline-none focus:ring-2 resize-none ${
                overLimit ? 'border-amber-400 focus:ring-amber-400' : 'border-gray-300 focus:ring-green-500'
              }`}
            />
            <div className="flex items-center justify-between mt-1">
              <span className={`text-xs ${overLimit ? 'text-amber-600 font-medium' : 'text-gray-400'}`}>
                {proposed.length} chars{overLimit ? ' — over 60 limit' : ''}
              </span>
              <div className="flex items-center gap-2">
                {applyError && <span className="text-xs text-red-600">{applyError}</span>}
                <button
                  onClick={handleApply}
                  disabled={applying || !proposed.trim()}
                  className="px-3 py-1 text-xs font-medium bg-amber-600 text-white rounded hover:bg-amber-700 disabled:opacity-50 transition-colors"
                >
                  {applying ? 'Saving…' : 'Save Title'}
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Edit H1 */}
      <div className="border-t border-amber-200 pt-3 flex items-center justify-between">
        <p className="text-xs text-gray-600">To change the H1 heading, open the page detail.</p>
        <button
          onClick={() => { onClose(); onEditH1?.() }}
          className="flex-shrink-0 ml-3 text-xs font-medium px-3 py-1 rounded border border-indigo-300 text-indigo-600 bg-white hover:bg-indigo-50 transition-colors"
        >
          Edit H1 →
        </button>
      </div>
    </div>
  )
}

function PageDetailRow({ index, pageUrl, jobId, issueCode, pageDescription, pageExtra, fixedAt, rescanState, onPageFocus, onRescanPage, isFixable, openFixUrl, setOpenFixUrl, predefinedValue, exemptAnchorUrls, onExemptAnchor }) {

  return (
    <li className="flex flex-col border-b border-gray-100 last:border-0">
      <div className="flex items-center gap-2 px-4 py-2 hover:bg-gray-50">
        <span className="text-xs text-gray-300 w-8 text-right flex-shrink-0">{index + 1}.</span>
        <div className="flex-1 min-w-0">
          <button
            className="text-xs text-blue-600 hover:underline text-left break-all w-full"
            title="Open page details"
            onClick={() => onPageFocus?.(pageUrl)}
          >
            {shortenUrl(pageUrl)}
          </button>
          {pageDescription && issueCode !== 'LINK_EMPTY_ANCHOR' && issueCode !== 'TITLE_H1_MISMATCH' && (
            <p className="text-xs text-gray-500 mt-0.5 break-words leading-snug">{pageDescription}</p>
          )}
          {issueCode === 'TITLE_H1_MISMATCH' && (
            <div className="mt-0.5 space-y-0.5">
              {pageExtra?.title && <p className="text-xs text-gray-500"><span className="font-medium text-gray-600">Title:</span> {pageExtra.title}</p>}
              {pageExtra?.h1    && <p className="text-xs text-gray-500"><span className="font-medium text-gray-600">H1:</span> {pageExtra.h1}</p>}
              {!pageExtra?.title && !pageExtra?.h1 && (
                <p className="text-xs text-gray-400 italic">Click Fix to compare title and H1</p>
              )}
            </div>
          )}
          {/* TITLE_DUPLICATE: show the duplicated title and pages that share it */}
          {issueCode === 'TITLE_DUPLICATE' && pageExtra && (
            <div className="mt-1 p-2 bg-amber-50 border border-amber-200 rounded text-xs space-y-1">
              {pageExtra.title && (
                <p className="text-gray-700">
                  <span className="font-semibold text-gray-800">Title:</span>{' '}
                  <span className="italic">"{pageExtra.title}"</span>
                </p>
              )}
              {pageExtra.duplicate_urls?.length > 0 && (
                <div>
                  <span className="font-semibold text-gray-800">Same title on:</span>
                  <div className="flex flex-wrap gap-1 mt-0.5">
                    {pageExtra.duplicate_urls.map(url => (
                      <button
                        key={url}
                        onClick={() => onPageFocus?.(url)}
                        className="text-blue-600 hover:underline hover:bg-blue-50 px-1 rounded"
                        title={url}
                      >
                        {shortenUrl(url)}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          {/* META_DESC_DUPLICATE: show the duplicated description and pages that share it */}
          {issueCode === 'META_DESC_DUPLICATE' && pageExtra && (
            <div className="mt-1 p-2 bg-amber-50 border border-amber-200 rounded text-xs space-y-1">
              {pageExtra.description && (
                <p className="text-gray-700">
                  <span className="font-semibold text-gray-800">Description:</span>{' '}
                  <span className="italic">"{pageExtra.description.length > 100 ? pageExtra.description.slice(0, 100) + '...' : pageExtra.description}"</span>
                </p>
              )}
              {pageExtra.duplicate_urls?.length > 0 && (
                <div>
                  <span className="font-semibold text-gray-800">Same description on:</span>
                  <div className="flex flex-wrap gap-1 mt-0.5">
                    {pageExtra.duplicate_urls.map(url => (
                      <button
                        key={url}
                        onClick={() => onPageFocus?.(url)}
                        className="text-blue-600 hover:underline hover:bg-blue-50 px-1 rounded"
                        title={url}
                      >
                        {shortenUrl(url)}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          {/* TITLE_META_DUPLICATE_PAIR: show both title and description, plus pages */}
          {issueCode === 'TITLE_META_DUPLICATE_PAIR' && pageExtra && (
            <div className="mt-1 p-2 bg-amber-50 border border-amber-200 rounded text-xs space-y-1">
              {pageExtra.title && (
                <p className="text-gray-700">
                  <span className="font-semibold text-gray-800">Title:</span>{' '}
                  <span className="italic">"{pageExtra.title}"</span>
                </p>
              )}
              {pageExtra.description && (
                <p className="text-gray-700">
                  <span className="font-semibold text-gray-800">Description:</span>{' '}
                  <span className="italic">"{pageExtra.description.length > 100 ? pageExtra.description.slice(0, 100) + '...' : pageExtra.description}"</span>
                </p>
              )}
              {pageExtra.duplicate_urls?.length > 0 && (
                <div>
                  <span className="font-semibold text-gray-800">Same title + description on:</span>
                  <div className="flex flex-wrap gap-1 mt-0.5">
                    {pageExtra.duplicate_urls.map(url => (
                      <button
                        key={url}
                        onClick={() => onPageFocus?.(url)}
                        className="text-blue-600 hover:underline hover:bg-blue-50 px-1 rounded"
                        title={url}
                      >
                        {shortenUrl(url)}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          {/* TITLE_TOO_SHORT / TITLE_TOO_LONG: show the actual title */}
          {(issueCode === 'TITLE_TOO_SHORT' || issueCode === 'TITLE_TOO_LONG') && pageExtra?.title && (
            <div className="mt-1 p-2 bg-amber-50 border border-amber-200 rounded text-xs">
              <p className="text-gray-700">
                <span className="font-semibold text-gray-800">Title ({pageExtra.length} chars):</span>{' '}
                <span className="italic">"{pageExtra.title}"</span>
              </p>
            </div>
          )}
          {/* META_DESC_TOO_SHORT / META_DESC_TOO_LONG: show the actual description */}
          {(issueCode === 'META_DESC_TOO_SHORT' || issueCode === 'META_DESC_TOO_LONG') && pageExtra?.description && (
            <div className="mt-1 p-2 bg-amber-50 border border-amber-200 rounded text-xs">
              <p className="text-gray-700">
                <span className="font-semibold text-gray-800">Description ({pageExtra.length} chars):</span>{' '}
                <span className="italic">"{pageExtra.description}"</span>
              </p>
            </div>
          )}
          {/* H1_MULTIPLE: show all H1 tags */}
          {issueCode === 'H1_MULTIPLE' && pageExtra?.h1_tags?.length > 0 && (
            <div className="mt-1 p-2 bg-amber-50 border border-amber-200 rounded text-xs space-y-0.5">
              <p className="font-semibold text-gray-800">Found {pageExtra.count} H1 tags:</p>
              {pageExtra.h1_tags.map((h1, i) => (
                <p key={i} className="text-gray-700 pl-2">
                  <span className="text-gray-400">{i + 1}.</span> "{h1}"
                </p>
              ))}
            </div>
          )}
          {/* HEADING_SKIP: show the heading outline */}
          {issueCode === 'HEADING_SKIP' && pageExtra?.outline?.length > 0 && (
            <div className="mt-1 p-2 bg-amber-50 border border-amber-200 rounded text-xs space-y-0.5">
              <p className="font-semibold text-gray-800">Heading outline:</p>
              {pageExtra.outline.map((h, i) => (
                <p key={i} className={`text-gray-700 pl-2 ${i === pageExtra.skip_at ? 'text-red-600 font-medium' : ''}`}>
                  {h} {i === pageExtra.skip_at && '← skip here'}
                </p>
              ))}
            </div>
          )}
          {/* REDIRECT_301/302: show where it redirects to */}
          {(issueCode === 'REDIRECT_301' || issueCode === 'REDIRECT_302' || issueCode === 'INTERNAL_REDIRECT_301') && pageExtra?.redirect_to && (
            <div className="mt-1 p-2 bg-amber-50 border border-amber-200 rounded text-xs">
              <p className="text-gray-700">
                <span className="font-semibold text-gray-800">Redirects to:</span>{' '}
                <button
                  onClick={() => onPageFocus?.(pageExtra.redirect_to)}
                  className="text-blue-600 hover:underline"
                  title={pageExtra.redirect_to}
                >
                  {shortenUrl(pageExtra.redirect_to)}
                </button>
              </p>
            </div>
          )}
          {/* REDIRECT_CHAIN: show the full chain */}
          {issueCode === 'REDIRECT_CHAIN' && pageExtra?.chain?.length > 0 && (
            <div className="mt-1 p-2 bg-amber-50 border border-amber-200 rounded text-xs space-y-0.5">
              <p className="font-semibold text-gray-800">Redirect chain ({pageExtra.hops} hops):</p>
              <div className="flex flex-wrap items-center gap-1">
                {pageExtra.chain.map((url, i) => (
                  <span key={i} className="flex items-center gap-1">
                    <button
                      onClick={() => onPageFocus?.(url)}
                      className="text-blue-600 hover:underline"
                      title={url}
                    >
                      {shortenUrl(url)}
                    </button>
                    {i < pageExtra.chain.length - 1 && <span className="text-gray-400">→</span>}
                  </span>
                ))}
              </div>
            </div>
          )}
          {/* CANONICAL_EXTERNAL: show the canonical URL */}
          {issueCode === 'CANONICAL_EXTERNAL' && pageExtra?.canonical_url && (
            <div className="mt-1 p-2 bg-amber-50 border border-amber-200 rounded text-xs">
              <p className="text-gray-700">
                <span className="font-semibold text-gray-800">Canonical points to:</span>{' '}
                <a
                  href={pageExtra.canonical_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline"
                  title={pageExtra.canonical_url}
                >
                  {pageExtra.canonical_url}
                </a>
              </p>
            </div>
          )}
          {pageDescription && issueCode === 'LINK_EMPTY_ANCHOR' && (() => {
            // Parse hrefs out of description: "N links with no anchor text: url1, url2..."
            const match = pageDescription.match(/:\s*(.+)$/)
            const hrefs = match ? match[1].split(', ').map(s => s.trim()).filter(Boolean) : []
            return (
              <div className="mt-0.5 space-y-0.5">
                {hrefs.map(href => (
                  <div key={href} className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-xs text-gray-500 font-mono truncate max-w-xs" title={href}>{href}</span>
                    {exemptAnchorUrls?.has(href)
                      ? <span className="text-xs text-green-600 font-medium">✓ Exempt</span>
                      : (
                        <button
                          onClick={() => onExemptAnchor?.(href)}
                          className="text-xs px-1.5 py-0 border border-blue-300 text-blue-600 rounded hover:bg-blue-50 transition-colors"
                          title="Exempt this URL — it will be ignored in future crawls"
                        >Exempt</button>
                      )
                    }
                  </div>
                ))}
              </div>
            )
          })()}
        </div>

        {/* Fixed badge */}
        {fixedAt && rescanState !== 'scanning' && (
          <span className="flex-shrink-0 text-xs text-green-700 font-medium bg-green-50 border border-green-200 rounded px-2 py-0.5 whitespace-nowrap">
            ✓ Fixed {new Date(fixedAt).toLocaleDateString()}
          </span>
        )}

        {/* Rescan state feedback */}
        {rescanState === 'scanning'  && <span className="flex-shrink-0 text-xs text-gray-400">Rescanning…</span>}
        {rescanState === 'nochange'  && <span className="flex-shrink-0 text-xs text-gray-500">No change</span>}
        {rescanState === 'worse'     && <span className="flex-shrink-0 text-xs text-amber-600">New issues found</span>}
        {rescanState === 'done'      && <span className="flex-shrink-0 text-xs text-green-600">Resolved ✓</span>}
        {rescanState === 'error'     && <span className="flex-shrink-0 text-xs text-red-500">Rescan failed</span>}

        {/* Fix button */}
        {isFixable && jobId && (
          <button
            onClick={() => setOpenFixUrl(v => v === pageUrl ? null : pageUrl)}
            title="Fix this issue in WordPress"
            className={`flex-shrink-0 text-xs font-medium px-2 py-0.5 rounded border transition-colors ${
              openFixUrl === pageUrl
                ? 'bg-amber-600 text-white border-amber-600'
                : 'bg-white text-amber-700 border-amber-400 hover:bg-amber-50'
            }`}
          >
            Fix
          </button>
        )}

        {/* Open page detail panel */}
        {jobId && (
          <button
            onClick={() => onPageFocus?.(pageUrl)}
            title="Open full page detail"
            className="flex-shrink-0 text-xs font-medium px-2 py-0.5 rounded border border-indigo-300 text-indigo-600 bg-white hover:bg-indigo-50 transition-colors"
          >
            Details →
          </button>
        )}

        {/* Rescan button */}
        {jobId && (
          <button
            onClick={() => onRescanPage(pageUrl)}
            disabled={rescanState === 'scanning'}
            title="Re-crawl this page and update its issues"
            className="flex-shrink-0 text-xs font-medium px-2 py-0.5 rounded border border-gray-300 text-gray-500 hover:border-green-400 hover:text-green-700 hover:bg-green-50 disabled:opacity-40 transition-colors"
          >
            Rescan
          </button>
        )}
      </div>


      {/* Fix panel */}
      {isFixable && openFixUrl === pageUrl && issueCode === 'TITLE_H1_MISMATCH' && (
        <TitleH1MismatchPanel
          jobId={jobId}
          pageUrl={pageUrl}
          pageExtra={pageExtra}
          onClose={() => setOpenFixUrl(null)}
          onEditH1={() => onPageFocus?.(pageUrl)}
        />
      )}
      {isFixable && openFixUrl === pageUrl && issueCode !== 'TITLE_H1_MISMATCH' && (
        <FixInlinePanel
          jobId={jobId}
          pageUrl={pageUrl}
          issueCode={issueCode}
          predefinedValue={predefinedValue}
          onClose={() => setOpenFixUrl(null)}
        />
      )}
    </li>
  )
}

// ── Broken link source-page view ───────────────────────────────────────────
// Inverts the broken-link data: shows your pages that have broken links,
// with each broken target URL shown as a detail beneath its source page.

function BrokenLinkSourceView({ brokenUrls, issueCode, jobId, fixHistory, onPageRescan, onUrlClick }) {
  const [sourceMap, setSourceMap] = useState(null) // Map<sourceUrl, [{brokenUrl, linkText}]>
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!jobId || !brokenUrls.length) { setLoading(false); return }
    Promise.all(
      brokenUrls.map(brokenUrl => {
        const params = new URLSearchParams({ job_id: jobId, target_url: brokenUrl })
        return fetch(`/api/fixes/link-sources?${params}`, { headers: authHeaders() })
          .then(r => r.json())
          .then(sources => ({ brokenUrl, sources: Array.isArray(sources) ? sources : [] }))
          .catch(() => ({ brokenUrl, sources: [] }))
      })
    ).then(results => {
      const map = new Map()
      for (const { brokenUrl, sources } of results) {
        for (const { source_url, link_text } of sources) {
          if (!map.has(source_url)) map.set(source_url, [])
          map.get(source_url).push({ brokenUrl, linkText: link_text })
        }
      }
      setSourceMap(map)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [jobId, brokenUrls.join(',')]) // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <div className="px-4 py-4"><Spinner /></div>

  if (!sourceMap || sourceMap.size === 0) {
    return (
      <p className="px-4 py-4 text-xs text-gray-400">
        No source pages found — run a new crawl to populate link data.
      </p>
    )
  }

  return (
    <ul className="divide-y divide-gray-100">
      {[...sourceMap.entries()].map(([sourceUrl, brokenLinks], i) => (
        <SourcePageRow
          key={sourceUrl}
          index={i}
          sourceUrl={sourceUrl}
          brokenLinks={brokenLinks}
          issueCode={issueCode}
          jobId={jobId}
          fixedAt={fixHistory?.get(sourceUrl) ?? null}
          onPageRescan={onPageRescan}
          onViewPage={onUrlClick}
        />
      ))}
    </ul>
  )
}

function SourcePageRow({ index, sourceUrl, brokenLinks, issueCode, jobId, fixedAt, onPageRescan, onViewPage }) {
  const [marking, setMarking] = useState(false)
  const [markedAt, setMarkedAt] = useState(fixedAt)
  const [markError, setMarkError] = useState(null)
  const [rescanning, setRescanning] = useState(false)
  const [rescanResult, setRescanResult] = useState(null)

  async function handleMarkFixed() {
    setMarking(true)
    setMarkError(null)
    try {
      await markFixed(jobId, sourceUrl, [issueCode])
      setMarkedAt(new Date().toISOString())
    } catch (e) {
      setMarkError(e.message || 'Could not save')
    } finally {
      setMarking(false)
    }
  }

  async function handleRescan() {
    setRescanning(true)
    setRescanResult(null)
    try {
      const result = await rescanUrl(jobId, sourceUrl)
      setRescanResult(result)
      onPageRescan?.()
    } catch (e) {
      setRescanResult({ error: e.message || 'Rescan failed' })
    } finally {
      setRescanning(false)
    }
  }

  return (
    <li className="flex flex-col px-4 py-2.5 hover:bg-gray-50">
      {/* Source page row */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-300 w-8 text-right flex-shrink-0">{index + 1}.</span>
        <span className="text-xs font-medium text-gray-800 truncate flex-1" title={sourceUrl}>
          {shortenUrl(sourceUrl)}
        </span>
        {/* View all issues on this page in By Page tab */}
        {onViewPage && (
          <button
            onClick={() => onViewPage(sourceUrl)}
            title="View all issues on this page"
            className="flex-shrink-0 text-xs text-purple-600 hover:text-purple-800 font-medium"
          >
            All issues →
          </button>
        )}
        {/* Open page in new tab so user can go fix it */}
        <a
          href={sourceUrl} target="_blank" rel="noopener noreferrer"
          title="Open this page to fix the broken link"
          className="flex-shrink-0 text-xs text-blue-500 hover:text-blue-700 font-medium"
        >
          Open ↗
        </a>
        {/* Mark as Fixed */}
        {markedAt ? (
          <span className="flex-shrink-0 text-xs text-green-700 font-medium bg-green-50 border border-green-200 rounded px-2 py-0.5 whitespace-nowrap">
            ✓ Fixed {new Date(markedAt).toLocaleDateString()}
          </span>
        ) : (
          <button
            onClick={handleMarkFixed}
            disabled={marking}
            title="Mark this page's broken link as fixed"
            className="flex-shrink-0 text-xs font-medium px-2 py-0.5 rounded border border-green-500 text-green-700 hover:bg-green-50 disabled:opacity-50 transition-colors"
          >
            {marking ? 'Saving…' : 'Fixed'}
          </button>
        )}
        {markError && <span className="flex-shrink-0 text-xs text-red-500" title={markError}>!</span>}
        {/* Rescan */}
        <button
          onClick={handleRescan}
          disabled={rescanning}
          title="Re-crawl this page to verify the fix"
          className="flex-shrink-0 text-xs font-medium px-2 py-0.5 rounded border border-gray-300 text-gray-500 hover:border-green-400 hover:text-green-700 hover:bg-green-50 disabled:opacity-40 transition-colors"
        >
          {rescanning ? 'Rescanning…' : 'Rescan'}
        </button>
        {/* Rescan result */}
        {rescanResult && !rescanning && (
          <span className={`flex-shrink-0 text-xs font-medium ${
            rescanResult.error ? 'text-red-500' :
            rescanResult.resolved > 0 ? 'text-green-600' :
            rescanResult.added > 0 ? 'text-amber-600' : 'text-gray-400'
          }`}>
            {rescanResult.error ? `Error` :
             rescanResult.resolved > 0 ? `✓ ${rescanResult.resolved} resolved` :
             rescanResult.added > 0 ? `${rescanResult.added} new` : 'No change'}
          </span>
        )}
      </div>
      {/* Broken links detail — the actual URLs to fix on this page */}
      <div className="mt-1 ml-10 space-y-0.5">
        {brokenLinks.map((bl, j) => (
          <div key={j} className="flex items-center gap-1.5 text-xs">
            <span className="text-red-400 flex-shrink-0">↳</span>
            <a
              href={bl.brokenUrl} target="_blank" rel="noopener noreferrer"
              className="font-mono text-red-600 hover:underline truncate" title={bl.brokenUrl}
            >
              {bl.brokenUrl}
            </a>
            {bl.linkText && (
              <span className="text-gray-400 flex-shrink-0 truncate max-w-[12rem]">— "{bl.linkText}"</span>
            )}
          </div>
        ))}
      </div>
    </li>
  )
}

// ── By Page tab ────────────────────────────────────────────────────────────

function ByPageTab({ jobId, jumpToUrl, onJumpConsumed, onRescanComplete, onNavigateToCategory }) {
  const [data, setData] = useState(null)
  const [page, setPage] = useState(1)
  const [minSeverity, setMinSeverity] = useState('')
  const [search, setSearch] = useState('')
  const [expandedUrl, setExpandedUrl] = useState(null)
  const [error, setError] = useState(null)
  // Multi-select rescan
  const [selectedUrls, setSelectedUrls] = useState(new Set())
  const [rescanning, setRescanning] = useState(false)
  const [rescanProgress, setRescanProgress] = useState(null) // { done, total, resolved, added, errors }

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

  function toggleSelect(e, url) {
    e.stopPropagation()
    setSelectedUrls(prev => {
      const s = new Set(prev)
      s.has(url) ? s.delete(url) : s.add(url)
      return s
    })
  }

  const filtered = data
    ? data.pages.filter(p => !search || p.url.toLowerCase().includes(search.toLowerCase()))
    : []

  const allSelected = filtered.length > 0 && filtered.every(p => selectedUrls.has(p.url))
  const someSelected = filtered.some(p => selectedUrls.has(p.url))

  function toggleSelectAll(e) {
    e.stopPropagation()
    if (allSelected) {
      setSelectedUrls(prev => {
        const s = new Set(prev)
        filtered.forEach(p => s.delete(p.url))
        return s
      })
    } else {
      setSelectedUrls(prev => {
        const s = new Set(prev)
        filtered.forEach(p => s.add(p.url))
        return s
      })
    }
  }

  async function handleRescanSelected() {
    const urls = [...selectedUrls]
    setRescanning(true)
    setRescanProgress({ done: 0, total: urls.length, resolved: 0, added: 0, errors: 0 })
    let totalResolved = 0
    let totalAdded = 0
    let totalErrors = 0
    for (let i = 0; i < urls.length; i++) {
      try {
        const result = await rescanUrl(jobId, urls[i])
        totalResolved += result.resolved ?? 0
        totalAdded += result.added ?? 0
      } catch (_) {
        totalErrors++
      }
      setRescanProgress({ done: i + 1, total: urls.length, resolved: totalResolved, added: totalAdded, errors: totalErrors })
    }
    setRescanning(false)
    setSelectedUrls(new Set())
    load() // refresh the page list with updated issue counts
    if (totalResolved > 0 || totalAdded > 0) onRescanComplete?.()
  }

  if (error) return <ErrorMsg msg={error} />
  if (!data) return <Spinner />

  const colSpan = 6

  return (
    <div>
      {/* Filters + rescan bar */}
      <div className="flex flex-wrap gap-4 mb-4 items-center">
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

        {/* Rescan selected button */}
        {someSelected && !rescanning && (
          <button
            onClick={handleRescanSelected}
            className="px-3 py-1.5 text-sm font-medium bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
          >
            Rescan selected ({selectedUrls.size})
          </button>
        )}
        {rescanning && rescanProgress && (
          <span className="text-sm text-gray-600">
            Rescanning {rescanProgress.done}/{rescanProgress.total}…
          </span>
        )}
        {!rescanning && rescanProgress && (
          <span className={`text-sm ${rescanProgress.errors > 0 ? 'text-amber-700' : 'text-green-700'}`}>
            Done — {rescanProgress.resolved} issue{rescanProgress.resolved !== 1 ? 's' : ''} resolved
            {rescanProgress.added > 0 ? `, ${rescanProgress.added} new` : ''}
            {rescanProgress.errors > 0 ? ` · ${rescanProgress.errors} error${rescanProgress.errors !== 1 ? 's' : ''}` : ''}
          </span>
        )}

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
              <th className="px-3 py-3 w-8">
                <input
                  type="checkbox"
                  checked={allSelected}
                  ref={el => { if (el) el.indeterminate = someSelected && !allSelected }}
                  onChange={toggleSelectAll}
                  className="accent-green-600"
                  title="Select all"
                />
              </th>
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
                <td colSpan={colSpan} className="px-4 py-8 text-center text-gray-400">
                  {search ? 'No pages match your filter.' : 'No pages found.'}
                </td>
              </tr>
            )}
            {filtered.map(p => (
              <>
                <tr
                  key={p.url}
                  className={`hover:bg-gray-50 cursor-pointer ${selectedUrls.has(p.url) ? 'bg-green-50' : ''}`}
                  onClick={() => toggleRow(p.url)}
                >
                  <td className="px-3 py-3" onClick={e => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selectedUrls.has(p.url)}
                      onChange={e => toggleSelect(e, p.url)}
                      className="accent-green-600"
                    />
                  </td>
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
                    <td colSpan={colSpan} className="bg-gray-50 px-6 py-4 border-t border-gray-100">
                      <PageDetail jobId={jobId} pageUrl={p.url} onRescanComplete={() => { onRescanComplete?.(); load() }} onNavigateToCategory={onNavigateToCategory} />
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

function PageDetail({ jobId, pageUrl, onRescanComplete, onNavigateToCategory }) {
  const [data, setData] = useState(null)
  const [pageData, setPageData] = useState(null)
  const [error, setError] = useState(null)
  const [expandedHelp, setExpandedHelp] = useState(null)
  const [openFixCode, setOpenFixCode] = useState(null)
  const [rescanning, setRescanning] = useState(false)
  const [rescanResult, setRescanResult] = useState(null)
  const [showDetails, setShowDetails] = useState(false)
  const [trimState, setTrimState] = useState(null)   // null | 'trimming' | { success, method, error }

  function loadIssues() {
    setData(null)
    setPageData(null)
    setError(null)
    setExpandedHelp(null)
    setOpenFixCode(null)
    getPageIssues(jobId, pageUrl)
      .then(result => {
        setData(result)
        if (result.page_data) setPageData(result.page_data)
      })
      .catch(err => setError(err.message))
  }

  useEffect(() => { loadIssues() }, [jobId, pageUrl]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleRescan() {
    setRescanning(true)
    setRescanResult(null)
    try {
      const result = await rescanUrl(jobId, pageUrl)
      setRescanResult(result)
      // Reload issues from fresh data
      setData({
        url: pageUrl,
        status_code: result.status_code,
        total_issues: result.total_issues,
        by_category: result.by_category,
        page_data: result.page_data,
      })
      if (result.page_data) setPageData(result.page_data)
      setExpandedHelp(null)
      setOpenFixCode(null)
      if (result.resolved > 0 || result.added > 0) {
        onRescanComplete?.()
      }
    } catch (err) {
      setRescanResult({ error: err.message })
    } finally {
      setRescanning(false)
    }
  }

  if (error) return <p className="text-sm text-red-500">{error}</p>
  if (!data) return <p className="text-sm text-gray-400">Loading…</p>

  return (
    <div className="space-y-3">
      {/* Header row */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-sm font-medium text-gray-700">
          {data.total_issues === 0
            ? 'No issues on this page.'
            : `${data.total_issues} issue${data.total_issues !== 1 ? 's' : ''}`}
        </span>
        <a href={pageUrl} target="_blank" rel="noopener noreferrer"
           className="text-sm text-blue-500 hover:underline">
          View live ↗
        </a>
        <div className="ml-auto flex items-center gap-2">
          {pageData && (
            <button
              onClick={() => setShowDetails(v => !v)}
              className={`px-3 py-1 text-xs font-medium border rounded transition-colors ${
                showDetails
                  ? 'bg-indigo-600 text-white border-indigo-600'
                  : 'border-indigo-300 text-indigo-700 hover:bg-indigo-50'
              }`}
              title="Show the actual offending content for each issue"
            >
              {showDetails ? 'Hide details' : 'Show details'}
            </button>
          )}
          <button
            onClick={handleRescan}
            disabled={rescanning}
            className="px-3 py-1 text-xs font-medium border border-green-400 text-green-700 rounded hover:bg-green-50 disabled:opacity-50 transition-colors"
            title="Re-fetch this page and update its issues"
          >
            {rescanning ? 'Rescanning…' : 'Rescan page'}
          </button>
        </div>
      </div>

      {/* Rescan result banner */}
      {rescanResult && !rescanResult.error && (
        <div className={`text-xs rounded px-3 py-2 border ${
          rescanResult.resolved > 0
            ? 'bg-green-50 border-green-200 text-green-800'
            : rescanResult.added > 0
              ? 'bg-amber-50 border-amber-200 text-amber-800'
              : 'bg-gray-50 border-gray-200 text-gray-600'
        }`}>
          {rescanResult.resolved > 0 && `✓ ${rescanResult.resolved} issue${rescanResult.resolved !== 1 ? 's' : ''} resolved. `}
          {rescanResult.added > 0 && `${rescanResult.added} new issue${rescanResult.added !== 1 ? 's' : ''} found. `}
          {rescanResult.resolved === 0 && rescanResult.added === 0 && 'No changes — issues remain.'}
          {rescanResult.resolved > 0 && ' Dashboard counts updated.'}
        </div>
      )}
      {rescanResult?.error && (
        <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
          Rescan failed: {rescanResult.error}
        </p>
      )}

      {/* Issue list */}
      {Object.entries(data.by_category).map(([cat, issues]) => (
        <div key={cat}>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5 capitalize">
            {cat.replace(/_/g, ' ')}
          </p>
          <div className="space-y-1.5">
            {issues.map((issue, i) => {
              const helpKey = `${cat}-${i}`
              const isHelpOpen = expandedHelp === helpKey
              const hasHelp = !!getIssueHelp(issue.issue_code)
              const isFixable = FIXABLE_CODES.has(issue.issue_code)
              const fixKey = `${issue.issue_code}`
              const isFixOpen = openFixCode === fixKey

              return (
                <div key={i}>
                  <div className="flex items-start gap-2 bg-white rounded border border-gray-200 px-3 py-2.5">
                    <SeverityBadge severity={issue.severity} />
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-gray-700 flex items-center gap-2 flex-wrap">
                        <span>{issue.issue_code}</span>
                        {issue.human_description && (
                          <span className="text-gray-400 font-normal">— {issue.human_description}</span>
                        )}
                        {onNavigateToCategory && issue.category && (
                          <button
                            onClick={() => onNavigateToCategory(issue.category)}
                            className="text-indigo-500 hover:text-indigo-700 hover:underline font-normal text-xs"
                            title={`See all pages with ${issue.issue_code} in the ${issue.category} tab`}
                          >
                            See all pages →
                          </button>
                        )}
                      </p>
                      <p className="text-xs text-gray-500 mt-0.5">{issue.recommendation}</p>
                    </div>
                    {issue.issue_code === 'TITLE_TOO_LONG' && (
                      <button
                        onClick={async () => {
                          if (trimState === 'trimming') return
                          setTrimState('trimming')
                          try {
                            const r = await trimTitleOne(pageUrl)
                            setTrimState(r)
                          } catch (e) {
                            setTrimState({ success: false, error: e.message })
                          }
                        }}
                        disabled={trimState === 'trimming' || trimState?.success}
                        title="Strip the site-name suffix from the SEO title"
                        className={`flex-shrink-0 text-xs font-medium px-2 py-0.5 rounded border transition-colors ${
                          trimState?.success
                            ? 'bg-green-600 text-white border-green-600'
                            : 'bg-white text-teal-700 border-teal-400 hover:bg-teal-50 disabled:opacity-50'
                        }`}
                      >
                        {trimState === 'trimming' ? 'Trimming…' : trimState?.success ? '✓ Trimmed' : 'Trim title'}
                      </button>
                    )}
                    {isFixable && jobId && (
                      <button
                        onClick={() => setOpenFixCode(v => v === fixKey ? null : fixKey)}
                        title="Fix this in WordPress"
                        className={`flex-shrink-0 text-xs font-medium px-2 py-0.5 rounded border transition-colors ${
                          isFixOpen
                            ? 'bg-amber-600 text-white border-amber-600'
                            : 'bg-white text-amber-700 border-amber-400 hover:bg-amber-50'
                        }`}
                      >
                        Fix
                      </button>
                    )}
                    {hasHelp && (
                      <button
                        onClick={() => setExpandedHelp(k => k === helpKey ? null : helpKey)}
                        title={isHelpOpen ? 'Hide help' : 'Show detailed help'}
                        className={`flex-shrink-0 w-5 h-5 rounded-full text-xs font-bold border transition-colors ${
                          isHelpOpen
                            ? 'bg-blue-600 text-white border-blue-600'
                            : 'bg-white text-blue-600 border-blue-300 hover:bg-blue-50'
                        }`}
                      >
                        ?
                      </button>
                    )}
                  </div>
                  {isFixOpen && (
                    <div className="mt-1">
                      <FixInlinePanel
                        jobId={jobId}
                        pageUrl={pageUrl}
                        issueCode={issue.issue_code}
                        onClose={() => setOpenFixCode(null)}
                      />
                    </div>
                  )}
                  {isHelpOpen && (
                    <div className="mt-1 ml-1">
                      <IssueHelpPanel issueCode={issue.issue_code} />
                    </div>
                  )}
                  {showDetails && (() => {
                    const detail = pageData ? getOffendingContent(issue.issue_code, pageData) : null
                    if (detail) {
                      return (
                        <div className="mt-1 ml-1 px-3 py-2 bg-indigo-50 border border-indigo-100 rounded text-xs text-gray-700">
                          <span className="font-medium text-indigo-700">{detail.label}:</span>{' '}
                          {detail.missing
                            ? <span className="text-gray-400 italic">(none)</span>
                            : <span className="font-mono break-all whitespace-pre-line">{detail.value}</span>
                          }
                        </div>
                      )
                    }
                    if (issue.description) {
                      return (
                        <div className="mt-1 ml-1 px-3 py-2 bg-indigo-50 border border-indigo-100 rounded text-xs text-gray-700 break-words">
                          {issue.description}
                        </div>
                      )
                    }
                    return null
                  })()}
                </div>
              )
            })}
          </div>
        </div>
      ))}

      {/* Trim result banner */}
      {trimState && trimState !== 'trimming' && (
        <div className={`text-xs rounded px-3 py-2 border ${
          trimState.success
            ? 'bg-teal-50 border-teal-200 text-teal-800'
            : 'bg-red-50 border-red-200 text-red-700'
        }`}>
          {trimState.success
            ? `✓ Title trimmed (${
                trimState.method?.startsWith('variable')
                  ? 'set to %%title%% — site name suffix will no longer appear'
                  : 'suffix stripped from custom title'
              }). Rescan to confirm.`
            : `Trim failed: ${trimState.error}`}
        </div>
      )}

      {/* Heading outline editor */}
      {pageData?.headings_outline?.length > 0 && (
        <HeadingOutlineEditor
          headings={pageData.headings_outline}
          pageUrl={pageUrl}
          jobId={jobId}
          onRescanComplete={onRescanComplete}
        />
      )}
    </div>
  )
}

// ── Image fix panel ───────────────────────────────────────────────────────
// Used for both IMG_OVERSIZED (media library link only) and IMG_ALT_MISSING
// (editable alt text, title, caption).

function ImageFixPanel({ imageUrl, mode }) {
  // mode: 'oversized' | 'alt'
  const [info, setInfo]       = useState(null)   // attachment info from WP
  const [loading, setLoading] = useState(false)
  const [loadErr, setLoadErr] = useState(null)

  // Auto-load for oversized — user just needs the media library link
  useEffect(() => { if (mode === 'oversized') load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const [altText,  setAltText]  = useState('')
  const [title,    setTitle]    = useState('')
  const [caption,  setCaption]  = useState('')
  const [saving,   setSaving]   = useState(false)
  const [saveResult, setSaveResult] = useState(null)

  async function load() {
    setLoading(true)
    setLoadErr(null)
    try {
      const data = await getImageInfo(imageUrl)
      if (!data.success) { setLoadErr(data.error); return }
      setInfo(data)
      setAltText(data.alt_text || '')
      setTitle(data.title || '')
      setCaption(data.caption || '')
    } catch (e) {
      setLoadErr(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    setSaving(true)
    setSaveResult(null)
    try {
      const result = await updateImageMeta(imageUrl, {
        altText:  altText  !== (info?.alt_text  || '') ? altText  : undefined,
        title:    title    !== (info?.title     || '') ? title    : undefined,
        caption:  caption  !== (info?.caption   || '') ? caption  : undefined,
      })
      setSaveResult(result)
      if (result.success) {
        setInfo(prev => ({ ...prev, alt_text: result.alt_text, title: result.title, caption: result.caption }))
      }
    } catch (e) {
      setSaveResult({ success: false, error: e.message })
    } finally {
      setSaving(false)
    }
  }

  const filename = imageUrl.split('/').pop()

  return (
    <div className="mt-1 border border-blue-100 rounded-lg bg-blue-50 overflow-hidden text-xs">
      {/* Header row */}
      <div className="flex items-center justify-between px-3 py-2 bg-blue-100">
        <span className="font-medium text-blue-800 truncate max-w-xs" title={imageUrl}>{filename}</span>
        <div className="flex items-center gap-2 flex-shrink-0 ml-2">
          {info?.admin_url && (
            <a href={info.admin_url} target="_blank" rel="noopener noreferrer"
               className="px-2 py-0.5 bg-white border border-blue-300 text-blue-700 rounded hover:bg-blue-50 transition-colors font-medium">
              Open in Media Library →
            </a>
          )}
          {!info && (
            <button
              onClick={load}
              disabled={loading}
              className="px-2 py-0.5 bg-white border border-blue-300 text-blue-700 rounded hover:bg-blue-50 disabled:opacity-50 transition-colors font-medium"
            >
              {loading ? 'Loading…' : 'Load info'}
            </button>
          )}
        </div>
      </div>

      {loadErr && <p className="px-3 py-2 text-red-600">{loadErr}</p>}

      {/* Alt / title / caption editor — only for alt mode */}
      {info && mode === 'alt' && (
        <div className="px-3 py-2 space-y-2">
          <div>
            <label className="block text-gray-500 mb-0.5">Alt text <span className="text-red-400">*</span></label>
            <input
              type="text"
              value={altText}
              onChange={e => { setAltText(e.target.value); setSaveResult(null) }}
              placeholder="Describe the image for screen readers and search engines"
              className="w-full border border-gray-300 rounded px-2 py-1 text-xs focus:outline-none focus:border-blue-400"
            />
          </div>
          <div>
            <label className="block text-gray-500 mb-0.5">Media title</label>
            <input
              type="text"
              value={title}
              onChange={e => { setTitle(e.target.value); setSaveResult(null) }}
              className="w-full border border-gray-300 rounded px-2 py-1 text-xs focus:outline-none focus:border-blue-400"
            />
          </div>
          <div>
            <label className="block text-gray-500 mb-0.5">Caption</label>
            <input
              type="text"
              value={caption}
              onChange={e => { setCaption(e.target.value); setSaveResult(null) }}
              className="w-full border border-gray-300 rounded px-2 py-1 text-xs focus:outline-none focus:border-blue-400"
            />
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 transition-colors font-medium"
            >
              {saving ? 'Saving…' : 'Save to WordPress'}
            </button>
            {info?.admin_url && (
              <a href={info.admin_url} target="_blank" rel="noopener noreferrer"
                 className="text-blue-600 hover:underline">
                Open in Media Library →
              </a>
            )}
          </div>
          {saveResult && (
            <p className={`text-xs ${saveResult.success ? 'text-green-700' : 'text-red-600'}`}>
              {saveResult.success ? '✓ Saved to WordPress.' : `Error: ${saveResult.error}`}
            </p>
          )}
        </div>
      )}
    </div>
  )
}


// ── Heading Find & Replace ─────────────────────────────────────────────────

function HeadingFindReplacePanel({ jobId, onApplied }) {
  const [open, setOpen]             = useState(true)
  const [searchText, setSearchText] = useState('')
  const [searchLevel, setSearchLevel] = useState('')   // '' = any level
  const [matches, setMatches]       = useState(null)   // null=not searched, []=[results]
  const [searching, setSearching]   = useState(false)
  const [searchError, setSearchError] = useState(null)

  const [toLevel, setToLevel]       = useState('')     // '' = bold
  const [applying, setApplying]     = useState(false)
  const [results, setResults]       = useState(null)   // per-URL apply results
  const [applyError, setApplyError] = useState(null)

  const [rescanning, setRescanning] = useState(false)
  const [rescanResults, setRescanResults] = useState(null) // { [url]: 'ok' | 'err' }

  async function handleRescan() {
    if (!results) return
    const successUrls = results.filter(r => r.success).map(r => r.url)
    if (!successUrls.length) return
    setRescanning(true)
    setRescanResults(null)
    const out = {}
    for (const url of successUrls) {
      try {
        await rescanUrl(jobId, url)
        out[url] = 'ok'
      } catch (e) {
        out[url] = 'err'
      }
    }
    setRescanResults(out)
    setRescanning(false)
    onApplied?.()
  }

  function handleSearchAgain() {
    setMatches(null)
    setResults(null)
    setRescanResults(null)
    setApplyError(null)
  }

  async function handleSearch() {
    if (!searchText.trim()) return
    setSearching(true)
    setSearchError(null)
    setMatches(null)
    setResults(null)
    try {
      const data = await findHeading(jobId, searchText.trim(), searchLevel ? parseInt(searchLevel) : null)
      setMatches(data)
    } catch (e) {
      setSearchError(e.message)
    } finally {
      setSearching(false)
    }
  }

  async function handleApply() {
    if (!matches?.length) return
    const fromLevel = matches[0].level   // all matches share the same level (filtered by search)
    setApplying(true)
    setApplyError(null)
    setResults(null)
    try {
      const data = await bulkReplaceHeading(
        jobId,
        searchText.trim(),
        fromLevel,
        toLevel ? parseInt(toLevel) : null,
      )
      setResults(data)
      onApplied?.()
    } catch (e) {
      setApplyError(e.message)
    } finally {
      setApplying(false)
    }
  }

  const uniqueFromLevels = matches ? [...new Set(matches.map(m => m.level))].sort() : []
  const succeeded       = results?.filter(r => r.success).length ?? 0
  const inShared        = results?.filter(r => r.success && r.shared).length ?? 0
  const classicWidget   = results?.filter(r => !r.success && r.error?.includes('WP Admin')).length ?? 0
  const failed          = results?.filter(r => !r.success && !r.error?.includes('WP Admin')).length ?? 0

  return (
    <div className="mb-4 border border-purple-300 rounded-lg overflow-hidden shadow-sm">
      {/* Toggle header */}
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-4 py-3 bg-purple-100 hover:bg-purple-200 transition-colors text-left"
      >
        <div>
          <span className="text-sm font-bold text-purple-900">✏️ Fix Headings — Find & Replace</span>
          <span className="ml-2 text-xs text-purple-600 font-normal">Search for a heading text, then change its level or convert to bold across all pages</span>
        </div>
        <span className="text-purple-500 text-lg flex-shrink-0 ml-2">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="px-4 py-4 space-y-4 bg-white">

          {/* Search row */}
          <div className="flex items-end gap-2 flex-wrap">
            <div className="flex-1 min-w-48">
              <label className="block text-xs text-gray-500 mb-1">Heading text (exact match)</label>
              <input
                type="text"
                value={searchText}
                onChange={e => { setSearchText(e.target.value); setMatches(null); setResults(null) }}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
                placeholder="e.g. Book a Consultation"
                className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-purple-400"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Level (optional)</label>
              <select
                value={searchLevel}
                onChange={e => { setSearchLevel(e.target.value); setMatches(null) }}
                className="border border-gray-300 rounded px-2 py-1.5 text-sm bg-white focus:outline-none focus:border-purple-400"
              >
                <option value="">Any</option>
                {[1,2,3,4,5,6].map(l => <option key={l} value={l}>H{l}</option>)}
              </select>
            </div>
            <button
              onClick={handleSearch}
              disabled={searching || !searchText.trim()}
              className="px-4 py-1.5 text-sm font-medium bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50 transition-colors"
            >
              {searching ? 'Searching…' : 'Search'}
            </button>
          </div>

          {searchError && <p className="text-sm text-red-600">{searchError}</p>}

          {/* Search results */}
          {matches !== null && matches.length === 0 && (
            <p className="text-sm text-gray-400">No pages found with that heading.</p>
          )}

          {matches?.length > 0 && (
            <div className="space-y-3">
              <p className="text-sm text-gray-600">
                Found on <strong>{matches.length}</strong> page{matches.length !== 1 ? 's' : ''}
                {uniqueFromLevels.length === 1 ? ` as H${uniqueFromLevels[0]}` : ''}.
              </p>

              {/* Affected pages list */}
              <ul className="border border-gray-200 rounded divide-y divide-gray-100 max-h-48 overflow-y-auto">
                {matches.map((m, i) => (
                  <li key={i} className="flex items-center gap-2 px-3 py-1.5 text-xs">
                    <span className="text-gray-400 font-mono font-bold w-6">H{m.level}</span>
                    <span className="flex-1 text-gray-600 truncate" title={m.url}>
                      {m.url.replace(/^https?:\/\/[^/]+/, '')}
                    </span>
                    {results && (() => {
                      const r = results.find(r => r.url === m.url)
                      if (!r) return null
                      if (r.success && r.shared)
                        return <span className="text-green-600 font-medium" title={`Fixed in ${r.location_label} — shared element`}>✓ shared</span>
                      if (r.success) return <span className="text-green-600 font-medium">✓</span>
                      if (r.error?.includes('WP Admin'))
                        return <span className="text-amber-500" title="Not found in any editable location — may be a classic (non-block) widget">⚠ manual</span>
                      return <span className="text-red-500" title={r.error}>✗</span>
                    })()}
                  </li>
                ))}
              </ul>

              {/* Replace controls */}
              {!results && (
                <div className="flex items-end gap-3 flex-wrap">
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Change to</label>
                    <select
                      value={toLevel}
                      onChange={e => setToLevel(e.target.value)}
                      className="border border-gray-300 rounded px-2 py-1.5 text-sm bg-white focus:outline-none focus:border-purple-400"
                    >
                      <option value="">Bold (remove heading)</option>
                      {[1,2,3,4,5,6]
                        .filter(l => uniqueFromLevels.length !== 1 || l !== uniqueFromLevels[0])
                        .map(l => <option key={l} value={l}>H{l}</option>)}
                    </select>
                  </div>
                  <button
                    onClick={handleApply}
                    disabled={applying || uniqueFromLevels.length !== 1}
                    title={uniqueFromLevels.length !== 1 ? 'Headings found at mixed levels — refine your search with a specific level' : ''}
                    className="px-4 py-1.5 text-sm font-medium bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50 transition-colors"
                  >
                    {applying ? 'Applying…' : `Apply to ${matches.length} page${matches.length !== 1 ? 's' : ''}`}
                  </button>
                  {uniqueFromLevels.length !== 1 && (
                    <p className="text-xs text-amber-600 self-center">
                      Headings found at levels {uniqueFromLevels.map(l => `H${l}`).join(', ')} — set a specific level above to apply.
                    </p>
                  )}
                </div>
              )}

              {applyError && <p className="text-sm text-red-600">{applyError}</p>}

              {/* Apply results summary + rescan */}
              {results && (
                <div className="space-y-2">
                  <div className={`text-sm rounded px-3 py-2 border ${
                    failed === 0 ? 'bg-green-50 border-green-200 text-green-800'
                                 : 'bg-amber-50 border-amber-200 text-amber-800'
                  }`}>
                    {succeeded > 0 && `✓ ${succeeded} page${succeeded !== 1 ? 's' : ''} updated. `}
                    {inShared > 0 && `${inShared} fixed in shared widget/pattern (applies to all pages using it). `}
                    {classicWidget > 0 && `${classicWidget} in classic widget — fix manually in WP Admin → Widgets. `}
                    {failed > 0 && `${failed} failed — hover ✗ for details. `}
                  </div>

                  {/* Rescan step */}
                  {succeeded > 0 && !rescanResults && (
                    <button
                      onClick={handleRescan}
                      disabled={rescanning}
                      className="px-4 py-1.5 text-sm font-medium bg-teal-600 text-white rounded hover:bg-teal-700 disabled:opacity-50 transition-colors"
                    >
                      {rescanning
                        ? 'Rescanning pages…'
                        : `Rescan ${succeeded} page${succeeded !== 1 ? 's' : ''} to verify fix`}
                    </button>
                  )}

                  {rescanResults && (() => {
                    const okCount  = Object.values(rescanResults).filter(v => v === 'ok').length
                    const errCount = Object.values(rescanResults).filter(v => v === 'err').length
                    return (
                      <div className="space-y-1">
                        <div className={`text-sm rounded px-3 py-2 border ${
                          errCount === 0 ? 'bg-teal-50 border-teal-200 text-teal-800'
                                        : 'bg-amber-50 border-amber-200 text-amber-800'
                        }`}>
                          {okCount > 0 && `✓ ${okCount} page${okCount !== 1 ? 's' : ''} rescanned. `}
                          {errCount > 0 && `${errCount} rescan failed. `}
                          Search again below to confirm the heading is gone.
                        </div>
                        <button
                          onClick={handleSearchAgain}
                          className="px-3 py-1 text-xs font-medium border border-purple-300 text-purple-700 rounded hover:bg-purple-50 transition-colors"
                        >
                          Search again to confirm
                        </button>
                      </div>
                    )
                  })()}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Heading outline editor ─────────────────────────────────────────────────

function HeadingOutlineEditor({ headings, pageUrl, jobId, onRescanComplete }) {
  // headingStates: { [text]: 'applying' | { success, newLevel, error } }
  const [headingStates, setHeadingStates] = useState({})
  // h4States tracks H4→Bold conversions; kept local so it always resets when editor mounts
  const [h4States, setH4States] = useState({})
  const [rescanning, setRescanning] = useState(false)
  const [rescanDone, setRescanDone] = useState(false)

  // Heading source analysis
  const [sourceAnalysis, setSourceAnalysis] = useState(null)
  const [analyzingSource, setAnalyzingSource] = useState(false)
  const [sourceError, setSourceError] = useState(null)

  // Build a map of heading text → source info
  const sourceMap = useMemo(() => {
    if (!sourceAnalysis?.headings) return {}
    const map = {}
    for (const h of sourceAnalysis.headings) {
      // Key by level + normalized text
      const key = `${h.level}:${h.text.toLowerCase().trim()}`
      map[key] = h
    }
    return map
  }, [sourceAnalysis])

  const getSourceInfo = h => {
    const key = `${h.level}:${h.text.toLowerCase().trim()}`
    return sourceMap[key] || null
  }

  // Merge h4States (for bold conversion) into display
  const getState = h => headingStates[h.text] || h4States?.[h.text] || null

  const anySuccess = Object.values(headingStates).some(s => s?.success)
    || Object.values(h4States || {}).some(s => s?.success)

  async function analyzeSource() {
    setAnalyzingSource(true)
    setSourceError(null)
    try {
      const result = await analyzeHeadingSources(pageUrl, jobId)
      setSourceAnalysis(result)
    } catch (e) {
      setSourceError(e.message)
    } finally {
      setAnalyzingSource(false)
    }
  }

  async function applyLevelChange(h, toLevel) {
    const key = h.text
    setHeadingStates(s => ({ ...s, [key]: 'applying' }))
    try {
      const r = await changeHeadingLevel(pageUrl, h.text, h.level, toLevel)
      setHeadingStates(s => ({ ...s, [key]: { ...r, newLevel: toLevel } }))
    } catch (e) {
      setHeadingStates(s => ({ ...s, [key]: { success: false, error: e.message } }))
    }
  }

  async function applyBold(h) {
    const key = h.text
    setH4States(s => ({ ...s, [key]: 'converting' }))
    try {
      const r = await convertHeadingToBold(pageUrl, h.text, h.level)
      setH4States(s => ({ ...s, [key]: r }))
    } catch (e) {
      setH4States(s => ({ ...s, [key]: { success: false, error: e.message } }))
    }
  }

  async function handleRescan() {
    setRescanning(true)
    try {
      await rescanUrl(jobId, pageUrl)
      setRescanDone(true)
      onRescanComplete?.()
    } catch (e) {
      // ignore — user can retry via the page's own Rescan button
    } finally {
      setRescanning(false)
    }
  }

  // Source label helper
  const getSourceLabel = source => {
    switch (source) {
      case 'post_content': return { label: 'Post', color: 'text-green-600', fixable: true }
      case 'reusable_block': return { label: 'Block', color: 'text-blue-600', fixable: true }
      case 'widget': return { label: 'Widget', color: 'text-amber-600', fixable: false }
      case 'acf_field': return { label: 'ACF', color: 'text-purple-600', fixable: false }
      default: return { label: 'Theme/Plugin', color: 'text-gray-500', fixable: false }
    }
  }

  return (
    <div className="border-t border-purple-100 pt-3 mt-3">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-semibold text-purple-700 uppercase tracking-wide">
          ✏️ Edit Headings
        </p>
        <div className="flex items-center gap-3">
          {!sourceAnalysis && !analyzingSource && (
            <button
              onClick={analyzeSource}
              className="text-xs text-blue-600 hover:text-blue-800 underline"
              title="Check where each heading is stored (post content, widget, theme, etc.)"
            >
              Analyze sources
            </button>
          )}
          {analyzingSource && <span className="text-xs text-gray-400">Analyzing...</span>}
          {sourceError && <span className="text-xs text-red-500" title={sourceError}>Analysis failed</span>}
          <span className="text-xs text-gray-400">Use the dropdown on each row to change its level or convert to bold</span>
        </div>
      </div>

      {/* Debug panel - shows analysis details */}
      {sourceAnalysis?._debug && (
        <details className="mb-2 text-xs bg-gray-50 border border-gray-200 rounded p-2">
          <summary className="cursor-pointer text-gray-600 font-medium">Debug: Analysis Details</summary>
          <div className="mt-2 space-y-2 text-gray-500">
            <p><strong>Post found:</strong> {sourceAnalysis._debug.post_found ? 'Yes' : 'No'}</p>
            <p><strong>Raw content length:</strong> {sourceAnalysis._debug.raw_content_length} chars</p>
            {sourceAnalysis._debug.h_tags_in_raw_content?.length > 0 && (
              <div>
                <strong>H-tags found in raw HTML ({sourceAnalysis._debug.h_tags_in_raw_content.length}):</strong>
                <ul className="ml-4 mt-1 font-mono text-[10px] break-all">
                  {sourceAnalysis._debug.h_tags_in_raw_content.map((tag, i) => (
                    <li key={i}>{tag}</li>
                  ))}
                </ul>
              </div>
            )}
            <div>
              <strong>Headings found in post content ({sourceAnalysis._debug.headings_in_post_content?.length || 0}):</strong>
              <ul className="ml-4 mt-1">
                {sourceAnalysis._debug.headings_in_post_content?.map((h, i) => (
                  <li key={i} className="font-mono">H{h.level}: "{h.text}" → "{h.normalized}"</li>
                ))}
                {!sourceAnalysis._debug.headings_in_post_content?.length && <li className="italic">None</li>}
              </ul>
            </div>
            <div>
              <strong>Crawled headings ({sourceAnalysis._debug.crawled_headings_normalized?.length || 0}):</strong>
              <ul className="ml-4 mt-1">
                {sourceAnalysis._debug.crawled_headings_normalized?.map((h, i) => (
                  <li key={i} className="font-mono">H{h.level}: "{h.text}" → "{h.normalized}"</li>
                ))}
              </ul>
            </div>
          </div>
        </details>
      )}

      <div className="space-y-1">
        {headings.map((h, i) => {
          const state = getState(h)
          const isDone = state?.success
          const isApplying = state === 'applying' || state === 'converting'
          const hasError = state?.error
          const effectiveLevel = isDone && state.newLevel ? state.newLevel : h.level
          const indent = Math.max(0, (effectiveLevel - 1) * 12)

          // Source analysis info
          const srcInfo = getSourceInfo(h)
          const srcLabel = srcInfo ? getSourceLabel(srcInfo.source) : null
          const isFixable = !srcInfo || srcInfo.fixable  // assume fixable if not analyzed

          return (
            <div
              key={i}
              style={{ paddingLeft: indent }}
              className={`flex items-start gap-2 rounded px-2 py-1.5 text-xs ${
                isDone ? 'bg-green-50' : 'bg-white border border-gray-100'
              }`}
            >
              {/* Level badge */}
              <span className={`flex-shrink-0 font-mono font-bold w-6 text-center mt-0.5 ${
                isDone ? 'text-green-600' : 'text-gray-400'
              }`}>
                H{effectiveLevel}
              </span>

              {/* Source badge (if analyzed) */}
              {srcLabel && (
                <span
                  className={`flex-shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded ${srcLabel.color} bg-gray-100`}
                  title={srcInfo.source_details?.note || `Source: ${srcInfo.source}`}
                >
                  {srcLabel.label}
                </span>
              )}

              {/* Heading text + status — wraps freely */}
              <span className={`flex-1 min-w-0 break-words leading-snug ${isDone ? 'text-gray-400 line-through' : 'text-gray-700'}`}>
                {h.text}
              </span>

              {/* Right-side controls column — always visible, anchored to top-right */}
              <div className="flex-shrink-0 flex flex-col items-end gap-1">
                {/* Success label */}
                {isDone && (
                  <span className="text-xs text-green-600 font-medium whitespace-nowrap" title={state.location_label ? `Fixed in ${state.location_label}` : undefined}>
                    {state.newLevel ? `✓ H${h.level}→H${state.newLevel}` : '✓ Bold'}
                    {state.location_label && state.location !== 'post' && (
                      <span className="ml-1 text-amber-600" title={`This heading was in a shared element (${state.location_label}) — the fix applies to all pages that include it`}>
                        {' '}· shared
                      </span>
                    )}
                  </span>
                )}

                {/* Error indicator */}
                {hasError && !isDone && (
                  state.error?.includes('WP Admin')
                    ? <span className="text-amber-600 text-xs text-right" title={state.error}>
                        ⚠ Not found.{' '}
                        <a href="/wp-admin/widgets.php" target="_blank" rel="noopener noreferrer"
                           className="underline hover:text-amber-800">WP Admin →</a>
                      </span>
                    : <span className="text-red-500 text-xs text-right" title={state.error}>⚠ {state.error}</span>
                )}

                {/* Level selector — only when not done and fixable */}
                {!isDone && !isApplying && isFixable && (
                  <select
                    defaultValue=""
                    onChange={e => {
                      const v = e.target.value
                      if (!v) return
                      if (v === 'bold') applyBold(h)
                      else applyLevelChange(h, parseInt(v))
                      e.target.value = ""
                    }}
                    className="text-xs border border-gray-300 rounded px-1 py-0.5 text-gray-600 bg-white cursor-pointer hover:border-purple-400 focus:outline-none focus:border-purple-400"
                    title="Change this heading"
                  >
                    <option value="" disabled>Change…</option>
                    {[1,2,3,4,5,6].filter(l => l !== h.level).map(l => (
                      <option key={l} value={l}>→ H{l}</option>
                    ))}
                    <option value="bold">→ Bold (remove heading)</option>
                  </select>
                )}

                {/* Non-fixable indicator */}
                {!isDone && !isApplying && !isFixable && srcInfo && (
                  <span
                    className="text-xs text-gray-400 italic"
                    title={srcInfo.source_details?.note || `This heading is in a ${srcLabel?.label} and cannot be edited via API`}
                  >
                    Edit in WP Admin
                  </span>
                )}

                {isApplying && (
                  <span className="text-xs text-gray-400">Applying…</span>
                )}
              </div>
            </div>
          )
        })}
      </div>
      <div className="mt-2 flex items-center gap-3">
        {anySuccess && !rescanDone && (
          <button
            onClick={handleRescan}
            disabled={rescanning}
            className="px-3 py-1 text-xs font-medium bg-teal-600 text-white rounded hover:bg-teal-700 disabled:opacity-50 transition-colors"
          >
            {rescanning ? 'Rescanning…' : 'Rescan page to verify fix'}
          </button>
        )}
        {rescanDone && (
          <span className="text-xs text-teal-700 font-medium">✓ Rescan complete — issue counts updated</span>
        )}
        {!anySuccess && (
          <p className="text-xs text-gray-400">Changes write directly to WordPress. Rescan after editing to update issue counts.</p>
        )}
      </div>
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
  if (tabIndex === TAB_HISTORY) return null
  const cat = CATEGORIES[tabIndex - 1]
  return summary.summary.by_category?.[cat.key] ?? null
}

// ── Fix History tab ────────────────────────────────────────────────────────

function FixHistoryTab({ jobId }) {
  const [records, setRecords] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    getFixHistory(jobId)
      .then(setRecords)
      .catch(err => setError(err.message))
  }, [jobId])

  if (error) return <ErrorMsg msg={error} />
  if (!records) return <Spinner />

  if (records.length === 0) {
    return (
      <div className="text-center py-16 text-gray-400">
        <p className="text-sm">No fixes recorded yet.</p>
        <p className="text-xs mt-1">Use the <strong>Rescan</strong> button in any category tab after fixing an issue — resolved issues will appear here with a timestamp.</p>
      </div>
    )
  }

  // Group by date (YYYY-MM-DD)
  const byDate = new Map()
  for (const r of records) {
    const date = r.fixed_at.slice(0, 10)
    if (!byDate.has(date)) byDate.set(date, [])
    byDate.get(date).push(r)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-gray-700">Fix History</h2>
          <p className="text-xs text-gray-400 mt-0.5">{records.length} issue{records.length !== 1 ? 's' : ''} resolved via rescan</p>
        </div>
      </div>

      {[...byDate.entries()].map(([date, items]) => (
        <div key={date}>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            {new Date(date + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
          </p>
          <div className="rounded-lg border border-gray-200 overflow-hidden">
            <table className="min-w-full text-sm divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Time</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Issue</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Page</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {items.map((r, i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-4 py-2 text-xs text-gray-400 whitespace-nowrap">
                      {new Date(r.fixed_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                    </td>
                    <td className="px-4 py-2">
                      <span className="text-xs font-medium text-green-700 bg-green-50 border border-green-200 rounded px-1.5 py-0.5">
                        ✓ {r.issue_code}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-xs text-blue-600 truncate max-w-sm">
                      <a href={r.page_url} target="_blank" rel="noopener noreferrer" className="hover:underline" title={r.page_url}>
                        {shortenUrl(r.page_url)}
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  )
}

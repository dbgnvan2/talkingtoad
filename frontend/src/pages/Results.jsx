import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import SeverityBadge from '../components/SeverityBadge.jsx'
import IssueHelpPanel from '../components/IssueHelpPanel.jsx'
import FixManager from '../components/FixManager.jsx'
import FixInlinePanel, { FIXABLE_CODES } from '../components/FixInlinePanel.jsx'
import SettingsPanel from '../components/SettingsPanel.jsx'
import ImageAnalysisPanel from '../components/ImageAnalysisPanel.jsx'
import CategoryHelpModal from '../components/CategoryHelpModal.jsx'
import { useTheme } from '../contexts/ThemeContext.jsx'
import { getIssueHelp } from '../data/issueHelp.js'
import {
  getResults, getResultsByCategory, getPages, getPageIssues,
  downloadCsv, downloadPdfReport, downloadExcelReport,
  authHeaders, getVerifiedLinks, getPredefinedCodes,
  getSuppressedCodes, getExemptAnchorUrls,
  getImageInfo, updateImageMeta, optimizeImage, analyzeWithAi, testAI,
  rescanUrl, analyzeHeadingSources, changeHeadingLevel, convertHeadingToBold,
  addVerifiedLink, removeVerifiedLink, addSuppressedCode, removeSuppressedCode,
  addExemptAnchorUrl, removeExemptAnchorUrl, markFixed,
  getPageAdvisor, getSiteAdvisor
} from '../api.js'

const IMAGE_FIXABLE_CODES = new Set(['IMG_OVERSIZED', 'IMG_ALT_MISSING'])

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
  { key: 'image',         label: 'Images' },
  { key: 'ai_readiness',  label: 'AI Readiness' },
]

const TAB_SUMMARY    = 0
const TAB_BY_PAGE    = CATEGORIES.length + 1
const TAB_FIX_MGR    = CATEGORIES.length + 2
const TAB_HISTORY    = CATEGORIES.length + 3

export default function Results() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState(TAB_SUMMARY)
  const [activeSeverity, setActiveSeverity] = useState(null) // 'critical', 'warning', or 'info'
  const [summary, setSummary] = useState(null)
  const [summaryError, setSummaryError] = useState(null)
  const [csvError, setCsvError] = useState(null)
  const [focusedPageUrl, setFocusedPageUrl] = useState(null)
  const [showPdfModal, setShowPdfModal] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showCategoryHelp, setShowCategoryHelp] = useState(null) // category key when help modal is open

  const loadSummary = useCallback(() => {
    getResults(jobId)
      .then(res => {
        if (res?.summary) setSummary(res.summary)
        else throw new Error("Invalid response from server")
      })
      .catch(err => setSummaryError(err.message))
  }, [jobId])

  useEffect(() => { loadSummary() }, [loadSummary])

  async function handlePdfDownload(options) {
    try { await downloadPdfReport(jobId, options) } 
    catch (err) { setCsvError('PDF generation failed.') }
  }

  if (summaryError) {
    return (
      <div className="max-w-2xl mx-auto mt-20 p-8 bg-white border border-red-100 rounded-2xl text-center">
        <p className="text-4xl mb-4">⚠️</p>
        <h1 className="text-xl font-bold text-gray-800">Error Loading Results</h1>
        <p className="text-gray-500 mt-2">{summaryError}</p>
        <button onClick={() => navigate('/')} className="mt-6 px-6 py-2 bg-green-600 text-white rounded-xl font-bold">Return Home</button>
      </div>
    )
  }

  if (!summary) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-20 text-center">
        <Spinner />
        <p className="mt-4 text-gray-400 font-bold uppercase tracking-widest animate-pulse">Loading Results...</p>
      </div>
    )
  }

  const tabs = ['Summary', ...CATEGORIES.map(c => c.label), 'By Page', 'Fix Manager', 'Fix History']

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex justify-between items-end mb-8">
        <div>
          <button onClick={() => navigate('/')} className="text-xs font-bold text-green-600 uppercase tracking-widest hover:underline mb-1">← Start New Scan</button>
          <h1 className="text-2xl font-bold text-gray-800">Audit Results</h1>
          <p className="text-sm text-gray-500 font-mono">{summary.target_url?.replace(/^https?:\/\//, '')}</p>
        </div>
        <div className="flex gap-2">
          {csvError && <span className="text-red-600 text-xs self-center mr-2">{csvError}</span>}
          <button onClick={() => setShowSettings(true)} className="px-3 py-1.5 bg-white border border-gray-300 rounded-lg text-xs font-bold shadow-sm" title="Display Settings">⚙</button>
          <button onClick={() => downloadCsv(jobId).catch(() => setCsvError('CSV failed'))} className="px-3 py-1.5 bg-white border border-gray-300 rounded-lg text-xs font-bold shadow-sm">CSV</button>
          <button onClick={() => downloadExcelReport(jobId).catch(() => setCsvError('Excel failed'))} className="px-3 py-1.5 bg-white border border-gray-300 rounded-lg text-xs font-bold shadow-sm">Excel</button>
          <button onClick={() => setShowPdfModal(true)} className="px-3 py-1.5 bg-green-600 text-white rounded-lg text-xs font-bold shadow-sm">PDF Report</button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6 overflow-x-auto flex gap-6 whitespace-nowrap">
        {tabs.map((label, i) => (
          <button
            key={label}
            onClick={() => { setActiveSeverity(null); setActiveTab(i) }}
            className={`pb-3 text-sm font-bold border-b-2 transition-colors ${
              !activeSeverity && activeTab === i ? 'border-green-600 text-green-600' : 'border-transparent text-gray-400 hover:text-gray-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="min-h-[400px]">
        {activeSeverity && (
          <SeverityTab jobId={jobId} severity={activeSeverity} onPageClick={setFocusedPageUrl} onBack={() => setActiveSeverity(null)} />
        )}
        {!activeSeverity && activeTab === TAB_SUMMARY && (
          <SummaryTab summary={summary} onCategoryClick={i => { setActiveSeverity(null); setActiveTab(i + 1) }} onSeverityClick={sev => { setActiveTab(TAB_SUMMARY); setActiveSeverity(sev) }} onPageClick={setFocusedPageUrl} jobId={jobId} onShowPdfModal={() => setShowPdfModal(true)} onShowCategoryHelp={setShowCategoryHelp} />
        )}
        {!activeSeverity && activeTab >= 1 && activeTab <= CATEGORIES.length && (
          CATEGORIES[activeTab - 1].key === 'image'
            ? <ImageAnalysisPanel jobId={jobId} onPageClick={setFocusedPageUrl} onShowHelp={() => setShowCategoryHelp('image')} />
            : <CategoryTab jobId={jobId} category={CATEGORIES[activeTab - 1]} onPageClick={setFocusedPageUrl} onShowHelp={() => setShowCategoryHelp(CATEGORIES[activeTab - 1].key)} />
        )}
        {!activeSeverity && activeTab === TAB_BY_PAGE && (
          <ByPageTab jobId={jobId} onPageClick={setFocusedPageUrl} />
        )}
        {!activeSeverity && activeTab === TAB_FIX_MGR && <FixManager jobId={jobId} />}
        {!activeSeverity && activeTab === TAB_HISTORY && <div className="py-12 text-center text-gray-400">History view coming soon.</div>}
      </div>

      {/* Slide-over Page Audit Panel (The "Right Side Panel") */}
      {focusedPageUrl && (
        <PageFocusPanel jobId={jobId} pageUrl={focusedPageUrl} onClose={() => setFocusedPageUrl(null)} onRescan={() => loadSummary()} />
      )}

      {showPdfModal && (
        <ExportReportModal onClose={() => setShowPdfModal(false)} onDownload={handlePdfDownload} />
      )}

      {showSettings && (
        <SettingsPanel onClose={() => setShowSettings(false)} />
      )}

      {showCategoryHelp && (
        <CategoryHelpModal categoryKey={showCategoryHelp} onClose={() => setShowCategoryHelp(null)} />
      )}
    </div>
  )
}

function SummaryTab({ summary: s, onCategoryClick, onSeverityClick, onPageClick, jobId, onShowPdfModal, onShowCategoryHelp }) {
  const { getFontClass } = useTheme()
  const [aiTesting, setAiTesting] = useState(false)
  const [aiStatus, setAiStatus] = useState(null)
  const [siteRecommendations, setSiteRecommendations] = useState(null)
  const [loadingSiteAI, setLoadingSiteAI] = useState(false)

  async function handleTestAI() {
    setAiTesting(true)
    setAiStatus(null)
    try {
      const result = await testAI()
      setAiStatus({ success: true, message: result.message || 'AI connection successful!' })
    } catch (err) {
      setAiStatus({ success: false, message: 'AI test failed: ' + err.message })
    } finally {
      setAiTesting(false)
    }
  }

  async function handleGetSiteRecommendations() {
    setLoadingSiteAI(true)
    try {
      const result = await getSiteAdvisor(jobId)
      setSiteRecommendations(result.recommendations)
    } catch (err) {
      alert('Failed to get site recommendations: ' + err.message)
    } finally {
      setLoadingSiteAI(false)
    }
  }

  return (
    <div className="space-y-10">
      {/* Quick Actions Bar */}
      <div className="flex flex-wrap items-center gap-3 p-4 bg-gradient-to-r from-green-50 to-indigo-50 rounded-2xl border border-gray-100">
        <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest mr-2">Quick Actions:</span>
        <button
          onClick={onShowPdfModal}
          className="px-4 py-2 bg-green-600 text-white rounded-xl text-xs font-bold shadow-sm hover:bg-green-700 transition-all flex items-center gap-2"
        >
          <span>📄</span> Generate PDF Report
        </button>
        <button
          onClick={handleGetSiteRecommendations}
          disabled={loadingSiteAI}
          className="px-4 py-2 bg-purple-600 text-white rounded-xl text-xs font-bold shadow-sm hover:bg-purple-700 transition-all disabled:opacity-50 flex items-center gap-2"
        >
          <span>🤖</span> {loadingSiteAI ? 'Analyzing...' : 'Site-Wide AI Recommendations'}
        </button>
        <button
          onClick={handleTestAI}
          disabled={aiTesting}
          className="px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-bold shadow-sm hover:bg-indigo-700 transition-all disabled:opacity-50 flex items-center gap-2"
        >
          <span>✨</span> {aiTesting ? 'Testing AI...' : 'Test AI Connection'}
        </button>
        {aiStatus && (
          <span className={`text-xs font-medium px-3 py-1 rounded-full ${aiStatus.success ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
            {aiStatus.message}
          </span>
        )}
      </div>

      {/* Site-Wide AI Recommendations */}
      {siteRecommendations && (
        <SiteRecommendationsPanel recommendations={siteRecommendations} onClose={() => setSiteRecommendations(null)} />
      )}

      {/* 3x2 High-Level Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard label="Health Score" value={s.health_score} color={s.health_score > 80 ? 'text-green-600' : 'text-amber-500'} />
        <StatCard label="Pages Crawled" value={s.pages_crawled} />
        <StatCard label="Total Issues" value={s.total_issues} />
        <SeverityStatCard
          label="Critical Issues"
          value={s.by_severity?.critical || 0}
          severity="critical"
          onClick={() => onSeverityClick('critical')}
        />
        <SeverityStatCard
          label="Warnings"
          value={s.by_severity?.warning || 0}
          severity="warning"
          onClick={() => onSeverityClick('warning')}
        />
        <SeverityStatCard
          label="Info Notices"
          value={s.by_severity?.info || 0}
          severity="info"
          onClick={() => onSeverityClick('info')}
        />
      </div>

      {/* Category Drill-down Boxes */}
      <section>
        <h2 className="font-black text-gray-400 uppercase tracking-widest mb-4" style={getFontClass('headingSize')}>Issues by Category</h2>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {CATEGORIES.map((cat, i) => (
            <div key={cat.key} className="relative bg-white border border-gray-200 rounded-2xl p-5 hover:border-green-400 hover:shadow-md transition-all group">
              <button
                onClick={(e) => { e.stopPropagation(); onCategoryClick(i) }}
                className="w-full text-left"
              >
                <p className="font-black text-gray-800 group-hover:text-green-600" style={{ ...getFontClass('badgeSize'), fontSize: `${getFontClass('badgeSize').fontSize.replace('px', '') * 2}px` }}>{s.by_category?.[cat.key] || 0}</p>
                <p className="font-black text-gray-800 uppercase tracking-wider mt-1 group-hover:text-green-600" style={getFontClass('headingSize')}>{cat.label}</p>
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onShowCategoryHelp?.(cat.key) }}
                className="absolute top-2 right-2 w-5 h-5 flex items-center justify-center rounded-full bg-indigo-100 text-indigo-600 hover:bg-indigo-200 transition-all text-xs font-bold opacity-0 group-hover:opacity-100"
                title={`Learn about ${cat.label}`}
              >
                ?
              </button>
            </div>
          ))}
        </div>
      </section>

      <TopPriorityGroups jobId={jobId} onPageClick={onPageClick} />
      <Top10Pages jobId={jobId} onPageClick={onPageClick} />
      <LLMSTxtGenerator jobId={jobId} />
    </div>
  )
}

function SeverityStatCard({ label, value, severity, onClick }) {
  const { getFontClass } = useTheme()
  const colors = {
    critical: { text: 'text-red-600', hoverBorder: 'hover:border-red-400' },
    warning: { text: 'text-amber-600', hoverBorder: 'hover:border-amber-400' },
    info: { text: 'text-blue-600', hoverBorder: 'hover:border-blue-400' }
  }
  const c = colors[severity]

  return (
    <button
      onClick={onClick}
      disabled={value === 0}
      className={`bg-white border border-gray-200 rounded-3xl p-6 text-center shadow-sm transition-all ${value > 0 ? `${c.hoverBorder} hover:shadow-md cursor-pointer` : 'opacity-60 cursor-default'}`}
    >
      <p className={`font-black uppercase tracking-widest mb-1 ${c.text}`} style={getFontClass('headingSize')}>{label}</p>
      <p className={`font-black ${c.text}`} style={{ ...getFontClass('badgeSize'), fontSize: `${getFontClass('badgeSize').fontSize.replace('px', '') * 2.5}px` }}>{value}</p>
    </button>
  )
}

function SeverityTab({ jobId, severity, onPageClick, onBack }) {
  const [data, setData] = useState(null)
  const [expandedCode, setExpandedCode] = useState(null)

  const labels = { critical: 'Critical Issues', warning: 'Warnings', info: 'Info Notices' }

  useEffect(() => {
    setData(null)
    getResults(jobId, { severity, limit: 100 })
      .then(d => setData(d))
      .catch(() => setData({ issues: [] }))
  }, [jobId, severity])

  if (!data) return <div className="py-20"><Spinner /></div>

  // Group issues by issue_code (subcategories)
  const groups = (data.issues || []).reduce((acc, iss) => {
    if (!acc[iss.issue_code]) acc[iss.issue_code] = { ...iss, count: 0, pages: [] }
    acc[iss.issue_code].count++
    if (iss.page_url && !acc[iss.issue_code].pages.includes(iss.page_url)) {
      acc[iss.issue_code].pages.push(iss.page_url)
    }
    return acc
  }, {})

  const sortedGroups = Object.values(groups).sort((a, b) => (b.priority_rank || 0) - (a.priority_rank || 0))

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 mb-6">
        <button onClick={onBack} className="text-xs font-bold text-green-600 uppercase tracking-widest hover:underline">← Back to Summary</button>
        <h2 className="text-xl font-bold text-gray-800">{labels[severity]} Details</h2>
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

function Top10Pages({ jobId, onPageClick }) {
  const [pages, setPages] = useState(null)

  useEffect(() => {
    getPages(jobId, { limit: 10 })
      .then(d => {
        // Sort by total issues descending
        const sorted = (d.pages || []).sort((a, b) => {
          const aTotal = (a.issue_counts?.critical || 0) + (a.issue_counts?.warning || 0) + (a.issue_counts?.info || 0)
          const bTotal = (b.issue_counts?.critical || 0) + (b.issue_counts?.warning || 0) + (b.issue_counts?.info || 0)
          // Prioritize by critical first, then warning, then total
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

  // Filter to only show pages with issues
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
              try { pathname = new URL(p.url).pathname || '/' } catch {}

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

function CategoryTab({ jobId, category, onPageClick, onShowHelp }) {
  const [data, setData] = useState(null)
  const [expandedCode, setExpandedCode] = useState(null)

  useEffect(() => {
    setData(null)
    getResultsByCategory(jobId, category.key).then(setData).catch(() => setData({ issues: [] }))
  }, [jobId, category.key])

  if (!data) return <div className="py-20"><Spinner /></div>

  const groups = data.issues.reduce((acc, iss) => {
    if (!acc[iss.issue_code]) acc[iss.issue_code] = { ...iss, count: 0, pages: [] }
    acc[iss.issue_code].count++
    acc[iss.issue_code].pages.push(iss.page_url)
    return acc
  }, {})

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-800">{category.label} Details</h2>
        <button
          onClick={onShowHelp}
          className="w-8 h-8 flex items-center justify-center rounded-full bg-indigo-100 text-indigo-600 hover:bg-indigo-200 transition-all font-bold"
          title={`Learn about ${category.label}`}
        >
          ?
        </button>
      </div>
      {Object.values(groups).length === 0 ? (
        <div className="py-12 bg-white rounded-2xl border border-gray-100 text-center text-gray-400 font-medium font-serif italic">No issues found in this category.</div>
      ) : (
        Object.values(groups).map(group => (
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

function PageFocusPanel({ jobId, pageUrl, onClose, onRescan }) {
  const [refreshing, setRefreshing] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const [showSettings, setShowSettings] = useState(false)

  async function handleRefresh() {
    setRefreshing(true)
    try {
      await rescanUrl(jobId, pageUrl)
      setRefreshKey(k => k + 1)
      onRescan?.()
    } catch (err) {
      console.error('Rescan failed:', err)
    } finally {
      setRefreshing(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm transition-opacity" onClick={onClose}></div>
      <div className="relative w-full max-w-2xl bg-gray-50 h-full shadow-2xl flex flex-col animate-slide-in">
        <div className="p-6 bg-white border-b shadow-sm">
          <div className="flex justify-between items-center">
            <div className="min-w-0 pr-4 flex-1">
              <h2 className="text-xl font-bold text-gray-800">Page Audit</h2>
              <p className="text-xs font-mono text-gray-400 truncate mt-1">{pageUrl}</p>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <button
                onClick={() => setShowSettings(!showSettings)}
                className={`w-10 h-10 flex items-center justify-center rounded-full transition-all ${showSettings ? 'bg-indigo-100 text-indigo-600' : 'bg-gray-50 text-gray-400 hover:bg-gray-100'}`}
                title="Settings & Tools"
              >
                ⚙
              </button>
              <button
                onClick={handleRefresh}
                disabled={refreshing}
                className="w-10 h-10 flex items-center justify-center rounded-full bg-green-50 text-green-600 hover:bg-green-100 transition-all disabled:opacity-50"
                title="Refresh page data"
              >
                <span className={refreshing ? 'animate-spin' : ''}>↻</span>
              </button>
              <a
                href={pageUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="w-10 h-10 flex items-center justify-center rounded-full bg-blue-50 text-blue-600 hover:bg-blue-100 transition-all"
                title="Open page in new tab"
              >
                ↗
              </a>
              <button onClick={onClose} className="w-10 h-10 flex items-center justify-center rounded-full bg-gray-100 text-gray-400 hover:text-gray-600 hover:bg-gray-200 transition-all text-2xl font-black">&times;</button>
            </div>
          </div>
          {showSettings && (
            <SettingsToolbar jobId={jobId} pageUrl={pageUrl} onUpdate={() => { setRefreshKey(k => k + 1); onRescan?.() }} />
          )}
        </div>
        <div className="flex-1 overflow-y-auto p-6 scrollbar-thin">
          <PageDetail key={refreshKey} jobId={jobId} pageUrl={pageUrl} onRescan={onRescan} />
        </div>
      </div>
    </div>
  )
}

function SettingsToolbar({ jobId, pageUrl, onUpdate }) {
  const [aiStatus, setAiStatus] = useState(null)
  const [testing, setTesting] = useState(false)
  const [verifiedLinks, setVerifiedLinks] = useState([])
  const [suppressedCodes, setSuppressedCodes] = useState([])
  const [exemptAnchors, setExemptAnchors] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('ai')

  useEffect(() => {
    async function loadSettings() {
      try {
        const [vl, sc, ea] = await Promise.all([
          getVerifiedLinks().catch(() => ({ links: [] })),
          getSuppressedCodes().catch(() => ({ codes: [] })),
          getExemptAnchorUrls().catch(() => ({ urls: [] }))
        ])
        setVerifiedLinks(vl.links || [])
        setSuppressedCodes(sc.codes || [])
        setExemptAnchors(ea.urls || [])
      } finally {
        setLoading(false)
      }
    }
    loadSettings()
  }, [])

  async function handleTestAI() {
    setTesting(true)
    try {
      const result = await testAI()
      setAiStatus(result.message || 'AI connection successful')
    } catch (err) {
      setAiStatus('AI test failed: ' + err.message)
    } finally {
      setTesting(false)
    }
  }

  async function handleRemoveVerified(url) {
    try {
      await removeVerifiedLink(url)
      setVerifiedLinks(prev => prev.filter(l => l.url !== url))
      onUpdate?.()
    } catch (err) {
      alert('Failed to remove: ' + err.message)
    }
  }

  async function handleRemoveSuppressed(code) {
    try {
      await removeSuppressedCode(code)
      setSuppressedCodes(prev => prev.filter(c => c !== code))
      onUpdate?.()
    } catch (err) {
      alert('Failed to remove: ' + err.message)
    }
  }

  async function handleRemoveExempt(url) {
    try {
      await removeExemptAnchorUrl(url)
      setExemptAnchors(prev => prev.filter(e => e.url !== url))
      onUpdate?.()
    } catch (err) {
      alert('Failed to remove: ' + err.message)
    }
  }

  return (
    <div className="mt-4 pt-4 border-t border-gray-100 animate-slide-in">
      <div className="flex gap-2 mb-3">
        {['ai', 'verified', 'suppressed', 'exempt'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`text-[10px] font-bold px-3 py-1 rounded-full uppercase ${
              activeTab === tab ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
            }`}
          >
            {tab === 'ai' ? 'AI Test' : tab === 'verified' ? `Verified (${verifiedLinks.length})` : tab === 'suppressed' ? `Suppressed (${suppressedCodes.length})` : `Exempt (${exemptAnchors.length})`}
          </button>
        ))}
      </div>

      {activeTab === 'ai' && (
        <div className="space-y-2">
          <button
            onClick={handleTestAI}
            disabled={testing}
            className="text-xs font-bold px-4 py-2 bg-indigo-100 text-indigo-700 rounded-lg hover:bg-indigo-200 disabled:opacity-50"
          >
            {testing ? 'Testing...' : 'Test AI Connection'}
          </button>
          {aiStatus && <p className="text-xs text-gray-600">{aiStatus}</p>}
        </div>
      )}

      {activeTab === 'verified' && (
        <div className="max-h-32 overflow-y-auto space-y-1">
          {loading ? <Spinner /> : verifiedLinks.length === 0 ? (
            <p className="text-xs text-gray-400">No verified links</p>
          ) : verifiedLinks.map(link => (
            <div key={link.url} className="flex items-center justify-between p-2 bg-white rounded-lg text-xs">
              <span className="truncate flex-1 text-gray-600 font-mono">{link.url}</span>
              <button onClick={() => handleRemoveVerified(link.url)} className="text-red-500 hover:text-red-700 ml-2">×</button>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'suppressed' && (
        <div className="max-h-32 overflow-y-auto space-y-1">
          {loading ? <Spinner /> : suppressedCodes.length === 0 ? (
            <p className="text-xs text-gray-400">No suppressed issue codes</p>
          ) : suppressedCodes.map(code => (
            <div key={code} className="flex items-center justify-between p-2 bg-white rounded-lg text-xs">
              <span className="text-gray-700 font-mono">{code}</span>
              <button onClick={() => handleRemoveSuppressed(code)} className="text-red-500 hover:text-red-700 ml-2">×</button>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'exempt' && (
        <div className="max-h-32 overflow-y-auto space-y-1">
          {loading ? <Spinner /> : exemptAnchors.length === 0 ? (
            <p className="text-xs text-gray-400">No exempt anchor URLs</p>
          ) : exemptAnchors.map(item => (
            <div key={item.url} className="flex items-center justify-between p-2 bg-white rounded-lg text-xs">
              <span className="truncate flex-1 text-gray-600 font-mono">{item.url}</span>
              <button onClick={() => handleRemoveExempt(item.url)} className="text-red-500 hover:text-red-700 ml-2">×</button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function PageDetail({ jobId, pageUrl, onRescan }) {
  const [data, setData] = useState(null)
  const [openFixCode, setOpenFixCode] = useState(null)
  const [expandedSections, setExpandedSections] = useState({ metadata: false, headings: true, issues: true })
  const [aiRecommendations, setAiRecommendations] = useState(null)
  const [loadingAI, setLoadingAI] = useState(false)

  const load = useCallback(() => {
    getPageIssues(jobId, pageUrl).then(setData).catch(() => {})
  }, [jobId, pageUrl])

  useEffect(() => { load() }, [load])

  const handleGetAIRecommendations = async () => {
    setLoadingAI(true)
    try {
      const result = await getPageAdvisor(jobId, pageUrl)
      setAiRecommendations(result.recommendations)
    } catch (err) {
      alert('Failed to get AI recommendations: ' + err.message)
    } finally {
      setLoadingAI(false)
    }
  }

  if (!data) return <div className="py-20"><Spinner /></div>

  const toggleSection = (section) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }))
  }

  // Flatten issues from by_category into a single list
  const allIssues = Object.entries(data.by_category || {}).flatMap(([cat, issues]) =>
    issues.map(iss => ({ ...iss, category: cat }))
  )

  // Group issues by category for display
  const grouped = allIssues.reduce((acc, iss) => {
    if (!acc[iss.category]) acc[iss.category] = []
    acc[iss.category].push(iss)
    return acc
  }, {})

  const pageData = data.page_data || {}

  return (
    <div className="space-y-6">
      {/* AI Recommendations Button */}
      <div className="flex justify-end">
        <button
          onClick={handleGetAIRecommendations}
          disabled={loadingAI}
          className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-bold hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          {loadingAI ? 'Analyzing...' : 'Get AI Recommendations'}
        </button>
      </div>

      {/* AI Recommendations Display */}
      {aiRecommendations && (
        <AIRecommendationsPanel recommendations={aiRecommendations} onClose={() => setAiRecommendations(null)} />
      )}

      {/* Page Metadata Section */}
      <CollapsibleSection
        title="Page Metadata"
        expanded={expandedSections.metadata}
        onToggle={() => toggleSection('metadata')}
        badge={<span className="text-[9px] px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full font-bold">SEO</span>}
      >
        <div className="space-y-4">
          <MetadataField label="Title" value={pageData.title} limit={60} />
          <MetadataField label="Meta Description" value={pageData.meta_description} limit={160} />
          <MetadataField label="H1 Tags" value={pageData.h1_tags?.join(' | ') || '(none)'} />
          <MetadataField label="Canonical URL" value={pageData.canonical_url} />
          {pageData.og_title && <MetadataField label="OG Title" value={pageData.og_title} />}
          {pageData.og_description && <MetadataField label="OG Description" value={pageData.og_description} />}
          {pageData.robots_directive && <MetadataField label="Robots Directive" value={pageData.robots_directive} />}
          <div className="flex gap-6 text-sm text-gray-500">
            {pageData.word_count != null && <span><strong>Words:</strong> {pageData.word_count}</span>}
            {pageData.response_size_bytes != null && <span><strong>Size:</strong> {Math.round(pageData.response_size_bytes / 1024)} KB</span>}
          </div>
        </div>
      </CollapsibleSection>

      {/* Headings Section */}
      <CollapsibleSection
        title="Headings Structure"
        expanded={expandedSections.headings}
        onToggle={() => toggleSection('headings')}
        badge={pageData.headings_outline?.length > 0 && (
          <span className="text-[9px] px-2 py-0.5 bg-indigo-100 text-indigo-600 rounded-full font-bold">{pageData.headings_outline.length} headings</span>
        )}
      >
        <HeadingsPanel jobId={jobId} pageUrl={pageUrl} headings={pageData.headings_outline || []} onUpdate={() => { load(); onRescan?.() }} />
      </CollapsibleSection>

      {/* Issues Section */}
      <CollapsibleSection
        title="Issues Found"
        expanded={expandedSections.issues}
        onToggle={() => toggleSection('issues')}
        badge={data.total_issues > 0 && (
          <span className="text-[9px] px-2 py-0.5 bg-red-100 text-red-600 rounded-full font-bold">{data.total_issues} issues</span>
        )}
      >
        {Object.keys(grouped).length === 0 ? (
          <div className="py-8 text-center text-gray-400 font-medium">
            <span className="text-2xl block mb-2">✓</span>
            No issues found on this page
          </div>
        ) : (
          <div className="space-y-8">
            {Object.entries(grouped).map(([cat, issues]) => (
              <div key={cat} className="space-y-3">
                <h4 className="text-sm font-black text-gray-400 uppercase tracking-widest ml-1 border-l-2 border-gray-200 pl-2">{cat.replace('_', ' ')}</h4>
                <div className="space-y-3">
                  {issues.map((iss, idx) => (
                    <IssueCard
                      key={`${iss.issue_code}-${idx}`}
                      issue={iss}
                      jobId={jobId}
                      pageUrl={pageUrl}
                      isOpen={openFixCode === `${iss.issue_code}-${idx}`}
                      onToggleFix={() => setOpenFixCode(openFixCode === `${iss.issue_code}-${idx}` ? null : `${iss.issue_code}-${idx}`)}
                      onFixComplete={() => { setOpenFixCode(null); load(); onRescan?.() }}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </CollapsibleSection>
    </div>
  )
}

function CollapsibleSection({ title, expanded, onToggle, badge, children }) {
  const { getFontClass } = useTheme()
  return (
    <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-sm">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="font-bold text-gray-800" style={{ ...getFontClass('headingSize'), fontSize: `${getFontClass('headingSize').fontSize.replace('px', '') * 1.3}px` }}>{title}</span>
          {badge}
        </div>
        <span className="text-gray-600 text-xl font-black">{expanded ? '▲' : '▼'}</span>
      </button>
      {expanded && (
        <div className="px-5 pb-5 border-t border-gray-100 pt-4">
          {children}
        </div>
      )}
    </div>
  )
}

function MetadataField({ label, value, limit }) {
  const { getFontClass } = useTheme()
  const isEmpty = !value || value === '(none)'
  const isOverLimit = limit && value && value.length > limit
  return (
    <div className="mb-1">
      <p className="font-black text-gray-400 uppercase tracking-widest mb-0.5" style={getFontClass('headingSize')}>{label}</p>
      <p className={`${isEmpty ? 'text-gray-300 italic' : isOverLimit ? 'text-amber-600' : 'text-gray-700'}`} style={{ ...getFontClass('bodySize'), fontSize: `${getFontClass('bodySize').fontSize.replace('px', '') * 1.4}px` }}>
        {value || '(empty)'}
        {isOverLimit && <span className="ml-2 font-bold" style={getFontClass('bodySize')}>({value.length}/{limit})</span>}
      </p>
    </div>
  )
}

function HeadingsPanel({ jobId, pageUrl, headings, onUpdate }) {
  const [sources, setSources] = useState(null)
  const [loading, setLoading] = useState(false)
  const [editingIdx, setEditingIdx] = useState(null)
  const [actionLoading, setActionLoading] = useState(false)

  async function loadSources() {
    setLoading(true)
    try {
      const result = await analyzeHeadingSources(pageUrl, jobId)
      setSources(result.headings || [])
    } catch (err) {
      console.error('Failed to analyze headings:', err)
    } finally {
      setLoading(false)
    }
  }

  if (headings.length === 0) {
    return <div className="py-6 text-center text-gray-400 text-sm">No headings found on this page</div>
  }

  async function handleChangeLevel(heading, newLevel) {
    setActionLoading(true)
    try {
      await changeHeadingLevel(pageUrl, heading.text, heading.level, newLevel)
      setEditingIdx(null)
      onUpdate?.()
    } catch (err) {
      alert('Failed to change heading level: ' + err.message)
    } finally {
      setActionLoading(false)
    }
  }

  async function handleConvertToBold(heading) {
    setActionLoading(true)
    try {
      await convertHeadingToBold(pageUrl, heading.text, heading.level)
      setEditingIdx(null)
      onUpdate?.()
    } catch (err) {
      alert('Failed to convert to bold: ' + err.message)
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center mb-2">
        <p className="text-sm text-gray-500">{headings.length} heading{headings.length !== 1 ? 's' : ''} detected</p>
        {!sources && (
          <button
            onClick={loadSources}
            disabled={loading}
            className="text-sm font-bold text-indigo-600 hover:text-indigo-800 disabled:opacity-50"
          >
            {loading ? 'Analyzing...' : 'Analyze Sources →'}
          </button>
        )}
      </div>
      <div className="space-y-2">
        {headings.map((h, idx) => {
          const sourceInfo = sources?.find(s => s.text === h.text && s.level === h.level)
          const isFixable = sourceInfo?.fixable !== false
          const isEditing = editingIdx === idx

          return (
            <div key={idx} className="flex items-start gap-3 p-3 bg-gray-50 rounded-xl group hover:bg-gray-100 transition-colors">
              <span className={`flex-shrink-0 w-10 h-10 flex items-center justify-center rounded-lg text-sm font-black ${
                h.level === 1 ? 'bg-red-100 text-red-700' :
                h.level === 2 ? 'bg-amber-100 text-amber-700' :
                'bg-blue-100 text-blue-700'
              }`}>
                H{h.level}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-base text-gray-800 break-words">{h.text}</p>
                {sourceInfo && (
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-bold ${
                      sourceInfo.source === 'post_content' ? 'bg-green-100 text-green-700' :
                      sourceInfo.source === 'reusable_block' ? 'bg-purple-100 text-purple-700' :
                      sourceInfo.source === 'widget' ? 'bg-amber-100 text-amber-700' :
                      'bg-gray-200 text-gray-600'
                    }`}>
                      {sourceInfo.source === 'post_content' ? 'Post Content' :
                       sourceInfo.source === 'reusable_block' ? 'Reusable Block' :
                       sourceInfo.source === 'widget' ? 'Widget' :
                       sourceInfo.source === 'acf_field' ? 'ACF Field' :
                       'Theme/Plugin'}
                    </span>
                    {!isFixable && <span className="text-xs text-gray-400">(not fixable via API)</span>}
                  </div>
                )}
                {isEditing && isFixable && (
                  <div className="mt-3 p-4 bg-white rounded-lg border border-gray-200 space-y-3">
                    <div>
                      <p className="text-sm font-bold text-gray-500 uppercase mb-2">Change Level To:</p>
                      <div className="flex gap-2 flex-wrap">
                        {[1, 2, 3, 4, 5, 6].filter(l => l !== h.level).map(level => (
                          <button
                            key={level}
                            onClick={() => handleChangeLevel(h, level)}
                            disabled={actionLoading}
                            className="px-4 py-2 text-sm font-bold bg-indigo-50 text-indigo-700 rounded-lg hover:bg-indigo-100 disabled:opacity-50"
                          >
                            H{level}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleConvertToBold(h)}
                        disabled={actionLoading}
                        className="px-4 py-2 text-sm font-bold bg-amber-50 text-amber-700 rounded-lg hover:bg-amber-100 disabled:opacity-50"
                      >
                        Convert to Bold
                      </button>
                      <button
                        onClick={() => setEditingIdx(null)}
                        className="px-4 py-2 text-sm text-gray-500 hover:text-gray-700"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
              {sources && isFixable && !isEditing && (
                <button
                  onClick={() => setEditingIdx(idx)}
                  className="opacity-0 group-hover:opacity-100 flex-shrink-0 text-[10px] font-bold text-indigo-600 hover:text-indigo-800 transition-all"
                >
                  Edit
                </button>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function IssueCard({ issue: iss, jobId, pageUrl, isOpen, onToggleFix, onFixComplete }) {
  const { getFontClass } = useTheme()
  const [showActions, setShowActions] = useState(false)
  const [actionLoading, setActionLoading] = useState(null)
  const [showHelp, setShowHelp] = useState(false)
  const [aiResult, setAiResult] = useState(null)
  const [aiLoading, setAiLoading] = useState(false)

  const canFix = FIXABLE_CODES.has(iss.issue_code) || IMAGE_FIXABLE_CODES.has(iss.issue_code)
  const isBrokenLink = ['BROKEN_LINK_404', 'BROKEN_LINK_410', 'BROKEN_LINK_5XX', 'BROKEN_LINK_503', 'EXTERNAL_LINK_TIMEOUT', 'EXTERNAL_LINK_SKIPPED'].includes(iss.issue_code)
  const isEmptyAnchor = iss.issue_code === 'LINK_EMPTY_ANCHOR'
  const isImageIssue = IMAGE_FIXABLE_CODES.has(iss.issue_code)

  const helpContent = useMemo(() => getIssueHelp(iss.issue_code), [iss.issue_code])

  async function handleVerifyLink() {
    const linkUrl = iss.extra?.link_url || iss.extra?.href
    if (!linkUrl) return alert('No link URL found in issue data')
    setActionLoading('verify')
    try {
      await addVerifiedLink(linkUrl, jobId)
      alert('Link marked as verified. It will be excluded from future scans.')
      onFixComplete?.()
    } catch (err) {
      alert('Failed to verify link: ' + err.message)
    } finally {
      setActionLoading(null)
    }
  }

  async function handleSuppressCode() {
    if (!confirm(`Suppress all "${iss.issue_code}" issues across all scans? This is a global setting.`)) return
    setActionLoading('suppress')
    try {
      await addSuppressedCode(iss.issue_code)
      alert(`Issue code "${iss.issue_code}" suppressed globally.`)
      onFixComplete?.()
    } catch (err) {
      alert('Failed to suppress code: ' + err.message)
    } finally {
      setActionLoading(null)
    }
  }

  async function handleExemptAnchor() {
    const anchorUrl = iss.extra?.href || iss.extra?.link_url
    if (!anchorUrl) return alert('No anchor URL found in issue data')
    setActionLoading('exempt')
    try {
      await addExemptAnchorUrl(anchorUrl, `Exempted from ${pageUrl}`)
      alert('Anchor URL exempted from empty anchor checks.')
      onFixComplete?.()
    } catch (err) {
      alert('Failed to exempt anchor: ' + err.message)
    } finally {
      setActionLoading(null)
    }
  }

  async function handleMarkFixed() {
    setActionLoading('markfixed')
    try {
      await markFixed(jobId, pageUrl, [iss.issue_code])
      alert('Issue marked as manually fixed.')
      onFixComplete?.()
    } catch (err) {
      alert('Failed to mark as fixed: ' + err.message)
    } finally {
      setActionLoading(null)
    }
  }

  async function handleAiAnalyze() {
    setAiLoading(true)
    try {
      const result = await analyzeWithAi(jobId, pageUrl, 'title_meta_optimize')
      setAiResult(result.suggestion || result.result || JSON.stringify(result))
    } catch (err) {
      setAiResult('AI analysis failed: ' + err.message)
    } finally {
      setAiLoading(false)
    }
  }

  return (
    <div className="bg-gray-50 border border-gray-100 rounded-xl p-4 hover:border-gray-200 transition-colors">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          <SeverityBadge severity={iss.severity} />
          <span className="font-bold text-gray-800" style={getFontClass('headingSize')}>{iss.human_description || iss.issue_code}</span>
        </div>
        <div className="flex items-center gap-2">
          {canFix && (
            <button
              onClick={onToggleFix}
              className={`font-black px-4 py-1.5 rounded-full uppercase transition-all ${
                isOpen ? 'bg-gray-800 text-white' : 'bg-green-50 text-green-700 hover:bg-green-100'
              }`}
              style={getFontClass('badgeSize')}
            >
              {isOpen ? 'Close' : 'Fix'}
            </button>
          )}
          <button
            onClick={() => setShowActions(!showActions)}
            className="text-xl font-black px-3 py-1 rounded-full text-gray-500 hover:text-gray-800 hover:bg-gray-200"
            title="More actions"
          >
            •••
          </button>
        </div>
      </div>

      <p className="text-gray-500 leading-relaxed mb-1" style={getFontClass('bodySize')}>{iss.description}</p>
      <p className="font-bold text-green-600 italic" style={getFontClass('bodySize')}>Recommendation: {iss.recommendation}</p>

      {/* Extra data display */}
      {iss.extra && Object.keys(iss.extra).length > 0 && (
        <div className="mt-2 p-3 bg-gray-100 rounded-lg">
          <p className="text-xs font-bold text-gray-400 uppercase mb-1">Details</p>
          {iss.extra.link_url && <p className="text-sm text-gray-600 font-mono truncate">Link: {iss.extra.link_url}</p>}
          {iss.extra.href && <p className="text-sm text-gray-600 font-mono truncate">Href: {iss.extra.href}</p>}
          {iss.extra.image_url && <p className="text-sm text-gray-600 font-mono truncate">Image: {iss.extra.image_url}</p>}
          {iss.extra.size_kb && <p className="text-sm text-gray-600">Size: {iss.extra.size_kb} KB</p>}
          {iss.extra.status_code && <p className="text-sm text-gray-600">Status: {iss.extra.status_code}</p>}
        </div>
      )}

      {/* Actions dropdown */}
      {showActions && (
        <div className="mt-3 p-4 bg-white border border-gray-200 rounded-lg space-y-2 animate-slide-in">
          <p className="text-xs font-black text-gray-400 uppercase mb-2">Actions</p>
          <div className="flex flex-wrap gap-2">
            {isBrokenLink && (
              <button
                onClick={handleVerifyLink}
                disabled={actionLoading === 'verify'}
                className="text-sm font-bold px-4 py-2 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 disabled:opacity-50"
              >
                {actionLoading === 'verify' ? 'Verifying...' : '✓ Mark Link Verified'}
              </button>
            )}
            {isEmptyAnchor && (
              <button
                onClick={handleExemptAnchor}
                disabled={actionLoading === 'exempt'}
                className="text-sm font-bold px-4 py-2 bg-purple-50 text-purple-700 rounded-lg hover:bg-purple-100 disabled:opacity-50"
              >
                {actionLoading === 'exempt' ? 'Exempting...' : 'Exempt This Anchor'}
              </button>
            )}
            <button
              onClick={handleSuppressCode}
              disabled={actionLoading === 'suppress'}
              className="text-sm font-bold px-4 py-2 bg-amber-50 text-amber-700 rounded-lg hover:bg-amber-100 disabled:opacity-50"
            >
              {actionLoading === 'suppress' ? 'Suppressing...' : 'Suppress Issue Type'}
            </button>
            <button
              onClick={handleMarkFixed}
              disabled={actionLoading === 'markfixed'}
              className="text-sm font-bold px-4 py-2 bg-green-50 text-green-700 rounded-lg hover:bg-green-100 disabled:opacity-50"
            >
              {actionLoading === 'markfixed' ? 'Marking...' : 'Mark as Fixed'}
            </button>
            <button
              onClick={() => setShowHelp(!showHelp)}
              className="text-sm font-bold px-4 py-2 bg-gray-50 text-gray-600 rounded-lg hover:bg-gray-100"
            >
              {showHelp ? 'Hide Help' : 'Show Help'}
            </button>
            <button
              onClick={handleAiAnalyze}
              disabled={aiLoading}
              className="text-sm font-bold px-4 py-2 bg-indigo-50 text-indigo-700 rounded-lg hover:bg-indigo-100 disabled:opacity-50"
            >
              {aiLoading ? 'Analyzing...' : '✨ AI Suggestion'}
            </button>
          </div>
        </div>
      )}

      {/* Help content */}
      {showHelp && helpContent && (
        <div className="mt-3 p-3 bg-blue-50 border border-blue-100 rounded-lg animate-slide-in">
          <IssueHelpPanel issueCode={iss.issue_code} />
        </div>
      )}

      {/* AI result */}
      {aiResult && (
        <div className="mt-3 p-4 bg-indigo-50 border border-indigo-100 rounded-lg animate-slide-in">
          <p className="text-xs font-black text-indigo-600 uppercase mb-2">AI Suggestion</p>
          <p className="text-sm text-indigo-900 whitespace-pre-wrap">{aiResult}</p>
          <button onClick={() => setAiResult(null)} className="mt-2 text-sm text-indigo-500 hover:text-indigo-700">Dismiss</button>
        </div>
      )}

      {/* Fix panel */}
      {isOpen && (
        <div className="mt-4 pt-4 border-t border-gray-200 animate-slide-in">
          {isImageIssue ? (
            <ImageFixPanel jobId={jobId} imageUrl={iss.extra?.image_url || pageUrl} issueCode={iss.issue_code} onClose={onFixComplete} />
          ) : (
            <FixInlinePanel jobId={jobId} pageUrl={pageUrl} issueCode={iss.issue_code} onClose={onFixComplete} />
          )}
        </div>
      )}
    </div>
  )
}

function ByPageTab({ jobId, onPageClick }) {
  const [data, setData] = useState(null)
  useEffect(() => {
    getPages(jobId, { limit: 200 }).then(setData).catch(() => setData({ pages: [] }))
  }, [jobId])

  if (!data) return <Spinner />

  return (
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
  )
}

function TopPriorityGroups({ jobId, onPageClick }) {
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

function StatCard({ label, value, color = 'text-gray-800' }) {
  const { getFontClass } = useTheme()
  return (
    <div className="bg-white border border-gray-200 rounded-3xl p-6 text-center shadow-sm">
      <p className={`font-black uppercase tracking-widest mb-1 ${color}`} style={getFontClass('headingSize')}>{label}</p>
      <p className={`font-black ${color}`} style={{ ...getFontClass('badgeSize'), fontSize: `${getFontClass('badgeSize').fontSize.replace('px', '') * 2.5}px` }}>{value}</p>
    </div>
  )
}

function LLMSTxtGenerator({ jobId }) {
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [saveStatus, setSaveStatus] = useState(null)

  useEffect(() => {
    setLoading(true)
    fetch(`/api/utility/generate-llms-txt?job_id=${jobId}`, { headers: authHeaders() })
      .then(r => r.json()).then(d => { setContent(d.content); setLoading(false) })
  }, [jobId])

  async function handleSave() {
    setSaveStatus('saving')
    try {
      await fetch('/api/utility/save-llms-txt', {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: jobId, content })
      })
      setSaveStatus('saved'); setTimeout(() => setSaveStatus(null), 2000)
    } catch { setSaveStatus('error') }
  }

  return (
    <div className="bg-white border border-indigo-100 rounded-3xl p-8 shadow-sm">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
        <div>
          <h3 className="text-lg font-bold text-gray-800">llms.txt AI Index</h3>
          <p className="text-sm text-gray-400">Help Gemini and ChatGPT find your most important content.</p>
        </div>
        <button onClick={handleSave} className={`px-8 py-2.5 rounded-2xl text-sm font-black transition-all shadow-lg active:scale-95 ${saveStatus==='saved' ? 'bg-green-600 text-white shadow-green-100' : 'bg-indigo-600 text-white shadow-indigo-100 hover:bg-indigo-700'}`}>
          {saveStatus==='saving' ? 'Saving...' : saveStatus==='saved' ? '✓ Saved Successfully' : 'Save to Job Data'}
        </button>
      </div>
      <textarea value={content} onChange={e => setContent(e.target.value)} className="w-full h-48 bg-indigo-50/20 border border-indigo-50 rounded-2xl p-5 font-mono text-xs focus:bg-white transition-colors focus:ring-2 focus:ring-indigo-100 focus:outline-none" />
    </div>
  )
}

function ImageFixPanel({ jobId, imageUrl, issueCode, onClose }) {
  const [imageInfo, setImageInfo] = useState(null)
  const [loading, setLoading] = useState(true)
  const [altText, setAltText] = useState('')
  const [title, setTitle] = useState('')
  const [caption, setCaption] = useState('')
  const [targetWidth, setTargetWidth] = useState(1200)
  const [saving, setSaving] = useState(false)
  const [optimizing, setOptimizing] = useState(false)
  const [error, setError] = useState(null)

  const isOversized = issueCode === 'IMG_OVERSIZED'
  const isAltMissing = issueCode === 'IMG_ALT_MISSING'

  useEffect(() => {
    async function loadInfo() {
      try {
        const info = await getImageInfo(imageUrl)
        setImageInfo(info)
        setAltText(info.alt_text || '')
        setTitle(info.title || '')
        setCaption(info.caption || '')
      } catch (err) {
        setError('Failed to load image info: ' + err.message)
      } finally {
        setLoading(false)
      }
    }
    loadInfo()
  }, [imageUrl])

  async function handleSaveMeta() {
    setSaving(true)
    setError(null)
    try {
      await updateImageMeta(imageUrl, { altText, title, caption, jobId })
      alert('Image metadata updated successfully!')
      onClose?.()
    } catch (err) {
      setError('Failed to update: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleOptimize() {
    setOptimizing(true)
    setError(null)
    try {
      const result = await optimizeImage(jobId, imageUrl, targetWidth)
      if (result.success) {
        alert('Image optimized and replaced successfully!')
        onClose?.()
      } else {
        setError(result.error || 'Optimization failed')
      }
    } catch (err) {
      setError('Failed to optimize: ' + err.message)
    } finally {
      setOptimizing(false)
    }
  }

  if (loading) {
    return (
      <div className="bg-blue-50 border border-blue-100 rounded-2xl p-5 text-center">
        <Spinner />
        <p className="text-xs text-blue-600 mt-2">Loading image info...</p>
      </div>
    )
  }

  return (
    <div className="bg-blue-50 border border-blue-100 rounded-2xl p-5 space-y-4">
      <p className="text-base font-black text-blue-800 uppercase tracking-widest">Image Intelligence Engine</p>

      {error && (
        <div className="p-3 bg-red-100 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
      )}

      {/* Image preview and info */}
      {imageInfo && (
        <div className="flex gap-4">
          <img src={imageUrl} alt="" className="w-24 h-24 object-cover rounded-lg border border-blue-200" />
          <div className="text-sm text-gray-600 space-y-1">
            <p><strong>Filename:</strong> {imageInfo.filename || 'Unknown'}</p>
            {imageInfo.width && imageInfo.height && (
              <p><strong>Dimensions:</strong> {imageInfo.width} × {imageInfo.height}</p>
            )}
            {imageInfo.file_size_kb && (
              <p><strong>Size:</strong> {imageInfo.file_size_kb} KB</p>
            )}
            {imageInfo.mime_type && (
              <p><strong>Type:</strong> {imageInfo.mime_type}</p>
            )}
          </div>
        </div>
      )}

      {/* Alt text / metadata editing - always show for all image issues */}
      <div className="space-y-3">
        <p className="text-sm font-bold text-blue-700">Image Metadata</p>
        <div>
          <label className="block text-sm font-bold text-blue-600 uppercase mb-1">Alt Text</label>
          <input
            type="text"
            value={altText}
            onChange={e => setAltText(e.target.value)}
            placeholder="Describe this image for screen readers..."
            className="w-full border border-blue-200 rounded-lg text-base p-3 bg-white focus:ring-2 focus:ring-blue-100 outline-none"
          />
        </div>
        <div>
          <label className="block text-sm font-bold text-blue-600 uppercase mb-1">Title</label>
          <input
            type="text"
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="Image title..."
            className="w-full border border-blue-200 rounded-lg text-base p-3 bg-white focus:ring-2 focus:ring-blue-100 outline-none"
          />
        </div>
        <div>
          <label className="block text-sm font-bold text-blue-600 uppercase mb-1">Caption</label>
          <input
            type="text"
            value={caption}
            onChange={e => setCaption(e.target.value)}
            placeholder="Caption (optional)..."
            className="w-full border border-blue-200 rounded-lg text-base p-3 bg-white focus:ring-2 focus:ring-blue-100 outline-none"
          />
        </div>
        <button
          onClick={handleSaveMeta}
          disabled={saving}
          className="w-full py-3 bg-blue-600 text-white rounded-lg text-base font-bold hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save Metadata'}
        </button>
      </div>

      {/* Optimization (for OVERSIZED) */}
      {isOversized && (
        <div className="pt-4 border-t border-blue-200 space-y-3">
          <p className="text-sm font-bold text-blue-700">Optimize & Compress</p>
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <label className="block text-sm font-bold text-blue-500 uppercase mb-1">Max Width</label>
              <select
                value={targetWidth}
                onChange={e => setTargetWidth(Number(e.target.value))}
                className="w-full border border-blue-200 rounded-lg text-base p-3 bg-white focus:ring-2 focus:ring-blue-100 outline-none"
              >
                <option value={800}>800px</option>
                <option value={1200}>1200px (Recommended)</option>
                <option value={1600}>1600px</option>
                <option value={2000}>2000px</option>
              </select>
            </div>
            <button
              onClick={handleOptimize}
              disabled={optimizing}
              className="px-6 py-3 bg-green-600 text-white rounded-lg text-base font-bold hover:bg-green-700 disabled:opacity-50"
            >
              {optimizing ? 'Optimizing...' : 'Optimize Image'}
            </button>
          </div>
          <p className="text-sm text-blue-500">
            This will resize, convert to WebP, upload to WordPress, and update all references.
          </p>
        </div>
      )}
    </div>
  )
}

function ExportReportModal({ onClose, onDownload }) {
  const [opts, setOpts] = useState({ includeHelp: true, includePages: true, summaryOnly: false })
  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-3xl shadow-2xl max-w-sm w-full p-8" onClick={e => e.stopPropagation()}>
        <h3 className="text-xl font-black text-gray-800 mb-6">PDF Report Options</h3>
        <div className="space-y-5 mb-8">
          <OptionToggle label="Summary Only" desc="Stats and top priority pages only" checked={opts.summaryOnly} onChange={v => setOpts({...opts, summaryOnly: v})} />
          {!opts.summaryOnly && (
            <>
              <OptionToggle label="Help Text" desc="Include 'What it is' boxes" checked={opts.includeHelp} onChange={v => setOpts({...opts, includeHelp: v})} />
              <OptionToggle label="Affected Pages" desc="List URLs for each issue" checked={opts.includePages} onChange={v => setOpts({...opts, includePages: v})} />
            </>
          )}
        </div>
        <div className="flex gap-3">
          <button onClick={onClose} className="flex-1 py-3 text-sm font-bold text-gray-400 hover:text-gray-600 transition-colors">Cancel</button>
          <button onClick={() => { onDownload(opts); onClose() }} className="flex-1 py-3 bg-green-600 text-white rounded-2xl text-sm font-bold shadow-lg shadow-green-100 active:scale-95 transition-all hover:bg-green-700">Generate PDF</button>
        </div>
      </div>
    </div>
  )
}

function OptionToggle({ label, desc, checked, onChange }) {
  return (
    <label className="flex items-start gap-3 cursor-pointer group">
      <input type="checkbox" className="mt-1 accent-green-600 w-4 h-4" checked={checked} onChange={e => onChange(e.target.checked)} />
      <div>
        <span className="block text-sm font-bold text-gray-700 group-hover:text-green-600 transition-colors">{label}</span>
        <span className="block text-[10px] text-gray-400 font-medium">{desc}</span>
      </div>
    </label>
  )
}

function AIRecommendationsPanel({ recommendations, onClose }) {
  // Check if recommendations has the raw_response field (fallback case)
  if (recommendations.raw_response) {
    return (
      <div className="bg-purple-50 border border-purple-200 rounded-2xl p-6">
        <div className="flex items-start justify-between mb-4">
          <h3 className="text-lg font-black text-purple-800">AI Recommendations</h3>
          <button
            onClick={onClose}
            className="w-6 h-6 flex items-center justify-center rounded-full bg-purple-100 text-purple-600 hover:bg-purple-200 transition-all text-xl font-black"
          >
            ×
          </button>
        </div>
        <div className="prose prose-sm max-w-none">
          <pre className="whitespace-pre-wrap text-sm text-gray-700 bg-white p-4 rounded-lg">
            {recommendations.raw_response}
          </pre>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-purple-50 border border-purple-200 rounded-2xl p-6">
      <div className="flex items-start justify-between mb-4">
        <h3 className="text-lg font-black text-purple-800">AI Recommendations</h3>
        <button
          onClick={onClose}
          className="w-6 h-6 flex items-center justify-center rounded-full bg-purple-100 text-purple-600 hover:bg-purple-200 transition-all text-xl font-black"
        >
          ×
        </button>
      </div>

      <div className="space-y-6">
        {/* Title Recommendation */}
        {recommendations.title && (
          <RecommendationItem
            label="Title Tag"
            current={recommendations.title.current}
            suggested={recommendations.title.suggested}
            why={recommendations.title.why}
          />
        )}

        {/* Meta Description Recommendation */}
        {recommendations.meta_description && (
          <RecommendationItem
            label="Meta Description"
            current={recommendations.meta_description.current}
            suggested={recommendations.meta_description.suggested}
            why={recommendations.meta_description.why}
          />
        )}

        {/* H1 Recommendation */}
        {recommendations.h1 && (
          <RecommendationItem
            label="H1 Heading"
            current={recommendations.h1.current}
            suggested={recommendations.h1.suggested}
            why={recommendations.h1.why}
          />
        )}

        {/* H2 Recommendation */}
        {recommendations.h2 && (
          <div className="bg-white rounded-lg p-4">
            <p className="text-sm font-black text-gray-700 mb-2">H2 Headings</p>
            <div className="space-y-2">
              <div>
                <p className="text-xs font-bold text-gray-500 mb-1">Current:</p>
                <ul className="list-disc list-inside text-sm text-gray-700">
                  {(Array.isArray(recommendations.h2.current) ? recommendations.h2.current : [recommendations.h2.current]).map((h2, idx) => (
                    <li key={idx}>{h2}</li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="text-xs font-bold text-gray-500 mb-1">Suggested:</p>
                <ul className="list-disc list-inside text-sm text-gray-800 font-medium">
                  {(Array.isArray(recommendations.h2.suggested) ? recommendations.h2.suggested : [recommendations.h2.suggested]).map((h2, idx) => (
                    <li key={idx}>{h2}</li>
                  ))}
                </ul>
              </div>
              {recommendations.h2.why && (
                <div>
                  <p className="text-xs font-bold text-gray-500 mb-1">Why:</p>
                  <p className="text-sm text-purple-700">{recommendations.h2.why}</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function RecommendationItem({ label, current, suggested, why }) {
  return (
    <div className="bg-white rounded-lg p-4">
      <p className="text-sm font-black text-gray-700 mb-2">{label}</p>
      <div className="space-y-2">
        <div>
          <p className="text-xs font-bold text-gray-500 mb-1">Current:</p>
          <p className="text-sm text-gray-700">{current}</p>
        </div>
        <div>
          <p className="text-xs font-bold text-gray-500 mb-1">Suggested:</p>
          <p className="text-sm text-gray-800 font-medium">{suggested}</p>
        </div>
        {why && (
          <div>
            <p className="text-xs font-bold text-gray-500 mb-1">Why:</p>
            <p className="text-sm text-purple-700">{why}</p>
          </div>
        )}
      </div>
    </div>
  )
}

function SiteRecommendationsPanel({ recommendations, onClose }) {
  // Check if it's an array of recommendations
  const isArray = Array.isArray(recommendations)
  const recs = isArray ? recommendations : []

  return (
    <div className="bg-purple-50 border border-purple-200 rounded-2xl p-6">
      <div className="flex items-start justify-between mb-4">
        <h3 className="text-lg font-black text-purple-800">Site-Wide AI Recommendations</h3>
        <button
          onClick={onClose}
          className="w-6 h-6 flex items-center justify-center rounded-full bg-purple-100 text-purple-600 hover:bg-purple-200 transition-all text-xl font-black"
        >
          ×
        </button>
      </div>

      {!isArray ? (
        <div className="prose prose-sm max-w-none">
          <pre className="whitespace-pre-wrap text-sm text-gray-700 bg-white p-4 rounded-lg">
            {JSON.stringify(recommendations, null, 2)}
          </pre>
        </div>
      ) : (
        <div className="space-y-4">
          {recs.map((rec, idx) => {
            const priorityColor = rec.priority === 'high' ? 'red' : rec.priority === 'medium' ? 'amber' : 'blue'
            return (
              <div key={idx} className="bg-white rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <span className={`flex-shrink-0 text-[10px] px-2 py-1 bg-${priorityColor}-100 text-${priorityColor}-700 rounded-full font-bold uppercase`}>
                    {rec.priority || 'Medium'}
                  </span>
                  <div className="flex-1">
                    <p className="text-sm font-black text-gray-700 mb-1">{rec.category || 'General'}</p>
                    <p className="text-sm text-gray-800">{rec.recommendation}</p>
                    {rec.impact && (
                      <p className="text-xs text-purple-700 mt-2">
                        <strong>Impact:</strong> {rec.impact}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function Spinner() { return <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600 mx-auto" /> }

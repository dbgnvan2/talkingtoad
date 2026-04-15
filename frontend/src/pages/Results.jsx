import React, { useState, useEffect, useCallback, useRef, forwardRef, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import IssueTable from '../components/IssueTable.jsx'
import SeverityBadge from '../components/SeverityBadge.jsx'
import IssueHelpPanel from '../components/IssueHelpPanel.jsx'
import FixManager from '../components/FixManager.jsx'
import FixInlinePanel, { FIXABLE_CODES } from '../components/FixInlinePanel.jsx'
import FixBrokenLinkPanel, { FIXABLE_LINK_CODES } from '../components/FixBrokenLinkPanel.jsx'
import { getIssueHelp } from '../data/issueHelp.js'
import { getResults, getResultsByCategory, getPages, getPageIssues, downloadCsv, downloadPdfReport, downloadExcelReport, rescanUrl, markFixed, authHeaders, getVerifiedLinks, addVerifiedLink, removeVerifiedLink, getPredefinedCodes, bulkTrimTitles, trimTitleOne, convertHeadingToBold, changeHeadingLevel, findHeading, bulkReplaceHeading, getFixHistory, getSuppressedCodes, addSuppressedCode, removeSuppressedCode, getExemptAnchorUrls, addExemptAnchorUrl, removeExemptAnchorUrl, getImageInfo, updateImageMeta, optimizeImage, analyzeHeadingSources, analyzeWithAi, testAI } from '../api.js'

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
  { key: 'ai_readiness',  label: 'AI Readiness' },
]

// Tab indices: 0=Summary, 1–N=categories, N+1=By Page, N+2=Fix Manager, N+3=History
const TAB_SUMMARY    = 0
const TAB_BY_PAGE    = CATEGORIES.length + 1
const TAB_FIX_MGR    = CATEGORIES.length + 2
const TAB_HISTORY    = CATEGORIES.length + 3

export default function Results() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState(TAB_SUMMARY)
  const [summary, setSummary] = useState(null)
  const [summaryError, setSummaryError] = useState(null)
  const [csvError, setCsvError] = useState(null)
  const [jumpToUrl, setJumpToUrl] = useState(null)
  const [verifiedLinks, setVerifiedLinks] = useState(new Set())
  const [predefinedCodes, setPredefinedCodes] = useState(null)
  const [suppressedCodes, setSuppressedCodes] = useState(new Set())
  const [exemptAnchorUrls, setExemptAnchorUrls] = useState(new Set())
  const [showPdfModal, setShowPdfModal] = useState(false)

  const loadSummary = useCallback(() => {
    console.log('Loading results for job:', jobId)
    getResults(jobId)
      .then(res => {
        console.log('API Response:', res)
        if (!res.summary) throw new Error('Missing summary in response')
        setSummary(res.summary)
      })
      .catch(err => {
        console.error('Crawl load error:', err)
        setSummaryError(err.message)
      })
  }, [jobId])

  const loadVerified = useCallback(() => {
    getVerifiedLinks().then(links => setVerifiedLinks(new Set(links.map(l => l.url))))
  }, [])

  const loadSuppressed = useCallback(() => {
    getSuppressedCodes().then(codes => setSuppressedCodes(new Set(codes)))
  }, [])

  const loadExemptAnchors = useCallback(() => {
    getExemptAnchorUrls().then(urls => setExemptAnchorUrls(new Set(urls.map(u => u.url))))
  }, [])

  useEffect(() => {
    loadSummary()
    loadVerified()
    loadSuppressed()
    loadExemptAnchors()
    getPredefinedCodes().then(setPredefinedCodes)
  }, [loadSummary, loadVerified, loadSuppressed, loadExemptAnchors])

  function handleUrlClick(url) {
    setJumpToUrl(url)
    setActiveTab(TAB_BY_PAGE)
  }

  async function handleCsvDownload(category) {
    setCsvError(null)
    try {
      await downloadCsv(jobId, category)
    } catch (err) {
      setCsvError('CSV export failed — please try again.')
    }
  }

  async function handlePdfDownload(options = {}) {
    setCsvError(null)
    try {
      const { includeHelp = true, includePages = true, summaryOnly = false } = options
      await downloadPdfReport(jobId, { includeHelp, includePages, summaryOnly })
    } catch (err) {
      setCsvError('PDF report failed — please try again.')
    }
  }

  async function handleExcelDownload() {
    setCsvError(null)
    try {
      await downloadExcelReport(jobId)
    } catch (err) {
      setCsvError('Excel export failed — please try again.')
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
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
        <div>
          <button
            onClick={() => navigate('/')}
            className="text-xs font-bold text-green-600 uppercase tracking-widest hover:text-green-700 transition-colors mb-1"
          >
            ← Back to start
          </button>
          <h1 className="text-2xl font-bold text-gray-800">
            Audit Results
          </h1>
          {summary?.target_url && (
            <p className="text-sm text-gray-500 font-mono mt-1">
              {summary.target_url.replace(/^https?:\/\//, '')}
            </p>
          )}
        </div>

        {csvError && (
          <div className="bg-red-50 text-red-600 text-xs px-3 py-2 rounded-lg border border-red-100 animate-pulse">
            {csvError}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6 overflow-x-auto">
        <div className="flex gap-6 min-w-max">
          {tabs.map((label, i) => {
            const isActive = activeTab === i
            return (
              <button
                key={label}
                onClick={() => { setActiveTab(i); setJumpToUrl(null) }}
                className={`pb-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                  isActive
                    ? 'border-green-600 text-green-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Tab content */}
      {!summary && !summaryError ? (
        <div className="py-20 text-center">
          <Spinner />
          <p className="text-xs text-gray-400 mt-4 uppercase tracking-widest font-bold animate-pulse">Retrieving saved results...</p>
        </div>
      ) : summaryError ? (
        <div className="py-20 text-center bg-red-50 rounded-2xl border border-red-100">
          <p className="text-3xl mb-4">🚫</p>
          <h2 className="text-lg font-bold text-red-800">Results not found</h2>
          <p className="text-sm text-red-600 mt-1 max-w-sm mx-auto">{summaryError}</p>
          <button 
            onClick={() => navigate('/')}
            className="mt-6 px-6 py-2 bg-red-600 text-white rounded-xl font-bold text-sm hover:bg-red-700 transition-all"
          >
            Start a new scan
          </button>
        </div>
      ) : (
        <>
          {activeTab === TAB_SUMMARY && (
            <SummaryTab
          summary={summary}
          error={summaryError}
          jobId={jobId}
          onCategoryClick={i => setActiveTab(i + 1)}
          onPageClick={handleUrlClick}
          suppressedCodes={suppressedCodes}
          onUnsuppress={loadSuppressed}
          exemptAnchorUrls={exemptAnchorUrls}
          onUnexemptAnchor={loadExemptAnchors}
          onPdfDownload={() => setShowPdfModal(true)}
          onCsvDownload={() => handleCsvDownload()}
          onExcelDownload={handleExcelDownload}
        />
      )}
      {activeTab >= 1 && activeTab <= CATEGORIES.length && (
        <CategoryTab
          jobId={jobId}
          category={CATEGORIES[activeTab - 1].key}
          onUrlClick={handleUrlClick}
          verifiedLinks={verifiedLinks}
          onVerify={loadVerified}
          onUnverify={loadVerified}
          onExemptAnchor={loadExemptAnchors}
          exemptAnchorUrls={exemptAnchorUrls}
        />
      )}
      {activeTab === TAB_BY_PAGE && (
        <ByPageTab
          jobId={jobId}
          jumpToUrl={jumpToUrl}
          onJumpConsumed={() => setJumpToUrl(null)}
          onRescanComplete={loadSummary}
          onNavigateToCategory={cat => {
            const idx = CATEGORIES.findIndex(c => c.key === cat)
            if (idx !== -1) setActiveTab(idx + 1)
          }}
        />
      )}
      {activeTab === TAB_FIX_MGR && (
        <FixManager jobId={jobId} />
      )}
      {activeTab === TAB_HISTORY && (
        <FixHistoryTab jobId={jobId} />
      )}
        </>
      )}

      {showPdfModal && (
        <ExportReportModal
          onClose={() => setShowPdfModal(false)}
          onDownload={handlePdfDownload}
        />
      )}
    </div>
  )
}

function SummaryTab({ summary: s, error, jobId, onCategoryClick, onPageClick, suppressedCodes, onUnsuppress, exemptAnchorUrls, onUnexemptAnchor, onPdfDownload, onCsvDownload, onExcelDownload }) {
  const [activeSeverity, setActiveSeverity] = useState(null)
  const [sevIssues, setSevIssues] = useState(null)
  const [sevLoading, setSevLoading] = useState(false)
  const [focusedPageUrl, setFocusedPageUrl] = useState(null)

  useEffect(() => {
    if (!activeSeverity) { setSevIssues(null); return }
    setSevLoading(true)
    getResults(jobId, { severity: activeSeverity, page: 1, limit: 20 })
      .then(d => { setSevIssues(d.issues); setSevLoading(false) })
      .catch(() => setSevLoading(false))
  }, [jobId, activeSeverity])

  if (error) return <div className="text-red-600">Error loading summary: {error}</div>
  if (!s) return <div className="py-12 flex justify-center"><Spinner /></div>

  function toggleSeverity(sev) {
    setActiveSeverity(prev => prev === sev ? null : sev)
  }

  return (
    <div className="space-y-8">
      {/* 3x2 Grid of Stat Boxes */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard label="Health Score" value={s.health_score} color={s.health_score > 80 ? 'text-green-600' : s.health_score > 50 ? 'text-amber-500' : 'text-red-600'} />
        <StatCard label="Pages Crawled" value={s.pages_crawled} />
        <StatCard label="Total Issues" value={s.total_issues} />
        <StatCard label="Critical Issues" value={s.by_severity?.critical || 0} color="text-red-600" onClick={() => toggleSeverity('critical')} active={activeSeverity === 'critical'} />
        <StatCard label="Warnings" value={s.by_severity?.warning || 0} color="text-amber-500" onClick={() => toggleSeverity('warning')} active={activeSeverity === 'warning'} />
        <StatCard label="Info Notices" value={s.by_severity?.info || 0} color="text-blue-500" onClick={() => toggleSeverity('info')} active={activeSeverity === 'info'} />
      </div>

      {activeSeverity && (
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-700 capitalize">{activeSeverity} issues</h2>
            <button onClick={() => setActiveSeverity(null)} className="text-xs text-gray-400 hover:text-gray-600">✕ close</button>
          </div>
          {sevLoading ? <Spinner /> : <SeverityGroupedList issues={sevIssues || []} onPageClick={onPageClick} />}
        </div>
      )}

      {/* Issues by Category with Export Buttons */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-semibold text-gray-700">Issues by Category</h2>
          <div className="flex gap-2">
            <button onClick={onCsvDownload} className="px-3 py-1.5 bg-white border border-gray-300 text-gray-700 rounded-lg text-xs font-bold hover:bg-gray-50 flex items-center gap-2 shadow-sm transition-all active:scale-95">
              CSV
            </button>
            <button onClick={onExcelDownload} className="px-3 py-1.5 bg-white border border-gray-300 text-gray-700 rounded-lg text-xs font-bold hover:bg-gray-50 flex items-center gap-2 shadow-sm transition-all active:scale-95">
              Excel (Tabbed)
            </button>
            <button onClick={onPdfDownload} className="px-3 py-1.5 bg-green-600 text-white rounded-lg text-xs font-bold hover:bg-green-700 flex items-center gap-2 shadow-sm transition-all active:scale-95">
              PDF Report
            </button>
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {CATEGORIES.map((cat, i) => (
            <button
              key={cat.key}
              onClick={() => onCategoryClick(i)}
              className="text-left bg-white border border-gray-200 rounded-lg p-4 hover:border-green-400 transition-colors"
            >
              <p className="text-lg font-bold text-gray-800">{s.by_category?.[cat.key] || 0}</p>
              <p className="text-xs text-gray-500">{cat.label}</p>
            </button>
          ))}
        </div>
      </div>

      <TopPriorityGroups jobId={jobId} onPageFocus={setFocusedPageUrl} />
      <TopPagesPanel jobId={jobId} onPageClick={setFocusedPageUrl} />
      <LLMSTxtGenerator jobId={jobId} />

      {focusedPageUrl && (
        <PageFocusPanel jobId={jobId} pageUrl={focusedPageUrl} onClose={() => setFocusedPageUrl(null)} />
      )}
    </div>
  )
}

function StatCard({ label, value, color = 'text-gray-800', onClick, active }) {
  return (
    <button
      onClick={onClick}
      disabled={!onClick}
      className={`bg-white border rounded-xl p-5 text-center transition-all ${
        onClick ? 'hover:shadow-md cursor-pointer' : 'cursor-default'
      } ${active ? 'border-green-500 ring-1 ring-green-500' : 'border-gray-200'}`}
    >
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-3xl font-bold ${color}`}>{value}</p>
    </button>
  )
}

function ExportReportModal({ onClose, onDownload }) {
  const [opts, setOpts] = useState({ includeHelp: true, includePages: true, summaryOnly: false })
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-sm w-full p-6">
        <h3 className="text-lg font-bold text-gray-800 mb-4">Export PDF Report</h3>
        <div className="space-y-4 mb-6">
          <label className="flex items-start gap-3 cursor-pointer">
            <input type="checkbox" className="mt-1 accent-green-600" checked={opts.summaryOnly} onChange={e => setOpts({ ...opts, summaryOnly: e.target.checked })} />
            <div>
              <span className="block text-sm font-bold text-gray-700">Summary Only</span>
              <span className="block text-xs text-gray-500">Only dashboard and top pages.</span>
            </div>
          </label>
          {!opts.summaryOnly && (
            <>
              <label className="flex items-start gap-3 cursor-pointer">
                <input type="checkbox" className="mt-1 accent-green-600" checked={opts.includeHelp} onChange={e => setOpts({ ...opts, includeHelp: e.target.checked })} />
                <div>
                  <span className="block text-sm font-bold text-gray-700">Include Help Text</span>
                  <span className="block text-xs text-gray-500">Explains "What it is", "Impact", and "How to fix".</span>
                </div>
              </label>
              <label className="flex items-start gap-3 cursor-pointer">
                <input type="checkbox" className="mt-1 accent-green-600" checked={opts.includePages} onChange={e => setOpts({ ...opts, includePages: e.target.checked })} />
                <div>
                  <span className="block text-sm font-bold text-gray-700">List Affected Pages</span>
                  <span className="block text-xs text-gray-500">Show up to 20 example URLs per issue.</span>
                </div>
              </label>
            </>
          )}
        </div>
        <div className="flex gap-3">
          <button onClick={onClose} className="flex-1 px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 rounded-xl">Cancel</button>
          <button onClick={() => { onDownload(opts); onClose() }} className="flex-1 px-4 py-2 text-sm font-bold text-white bg-green-600 hover:bg-green-700 rounded-xl">Generate PDF</button>
        </div>
      </div>
    </div>
  )
}

function LLMSTxtGenerator({ jobId }) {
  const [loading, setLoading] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [content, setContent] = useState('')
  const [error, setError] = useState(null)
  const [showHelp, setShowHelp] = useState(false)

  const STARTER_TEMPLATE = `# Site Name\n\n> Summary of what your organisation does.\n\n## Core Content\n- [About](https://example.com/about)\n`

  async function handleGenerate() {
    setLoading(true); setError(null)
    try {
      const data = await fetch(`/api/utility/generate-llms-txt?job_id=${jobId}`, { headers: authHeaders() }).then(r => r.json())
      if (data.error) throw new Error(data.error)
      setContent(data.content)
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }

  async function handleTest() {
    setTesting(true); setTestResult(null)
    try {
      const data = await testAI()
      setTestResult(data)
    } catch (e) { setTestResult({ success: false, message: e.message }) } finally { setTesting(false) }
  }

  return (
    <div className="bg-white border border-indigo-200 rounded-xl p-6 shadow-sm">
      <div className="flex items-center gap-3 mb-4">
        <div className="flex-1">
          <h3 className="text-sm font-bold text-gray-800 uppercase tracking-wider">llms.txt Generator</h3>
          <p className="text-xs text-gray-500">Machine-readable index for AI agents.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={handleTest} disabled={testing} className="px-3 py-2 border rounded-lg text-xs font-bold bg-white text-gray-700 hover:bg-gray-50">
            {testing ? 'Testing...' : 'Test AI API'}
          </button>
          <button onClick={handleGenerate} disabled={loading} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs font-bold hover:bg-indigo-700">
            {loading ? 'Generating...' : 'Auto-Generate'}
          </button>
        </div>
      </div>
      {testResult && <div className={`mb-4 p-3 rounded-lg text-xs ${testResult.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-700'}`}>{testResult.message}</div>}
      <textarea value={content} onChange={e => setContent(e.target.value)} className="w-full h-40 bg-gray-50 border rounded-lg p-3 font-mono text-xs" />
    </div>
  )
}

function AIAnalyzePanel({ jobId, pageUrl, onClose }) {
  const [loading, setLoading] = useState(false)
  const [suggestion, setSuggestion] = useState(null)
  const [error, setError] = useState(null)

  async function handleAnalyze(type) {
    setLoading(true); setSuggestion(null); setError(null)
    try {
      const data = await analyzeWithAi(jobId, pageUrl, type)
      if (data.error) throw new Error(data.error)
      setSuggestion(data.suggestion)
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }

  return (
    <div className="mt-1 border border-indigo-100 rounded-lg bg-indigo-50 overflow-hidden text-xs">
      <div className="flex items-center justify-between px-3 py-2 bg-indigo-100">
        <span className="font-medium text-indigo-800">AI Analysis Engine (Gemini)</span>
        <button onClick={onClose} className="text-indigo-400 hover:text-indigo-600">&times;</button>
      </div>
      <div className="p-3">
        <div className="flex gap-2 mb-3">
          <button onClick={() => handleAnalyze('title_meta_optimize')} disabled={loading} className="px-2 py-1 bg-white border border-indigo-300 text-indigo-700 rounded hover:bg-indigo-50">Optimize Title/Meta</button>
          <button onClick={() => handleAnalyze('semantic_alignment')} disabled={loading} className="px-2 py-1 bg-white border border-indigo-300 text-indigo-700 rounded hover:bg-indigo-50">Check Semantics</button>
        </div>
        {loading && <p className="text-indigo-600 animate-pulse">Consulting AI...</p>}
        {error && <p className="text-red-600">Error: {error}</p>}
        {suggestion && <div className="bg-white border rounded p-3 text-gray-800 whitespace-pre-line font-serif text-sm">{suggestion}</div>}
      </div>
    </div>
  )
}

function ImageFixPanel({ jobId, imageUrl, mode, onClose, onFixed }) {
  const [info, setInfo] = useState(null)
  const [loading, setLoading] = useState(false)
  const [loadErr, setLoadErr] = useState(null)
  const [targetWidth, setTargetWidth] = useState(1200)
  const [optimizing, setOptimizing] = useState(false)
  const [saveResult, setSaveResult] = useState(null)

  const originalFilename = imageUrl.split('/').pop()
  const cleanFilename = (name) => name.replace(/\.[^/.]+$/, "").toLowerCase().replace(/_/g, '-').replace(/[^a-z0-9-]/g, '')
  const [newFilename, setNewFilename] = useState(cleanFilename(originalFilename))

  useEffect(() => { if (mode === 'oversized') load() }, [])

  async function load() {
    setLoading(true); setLoadErr(null)
    try {
      const data = await getImageInfo(imageUrl)
      if (!data.success) { setLoadErr(data.error); return }
      setInfo(data)
    } catch (e) { setLoadErr(e.message) } finally { setLoading(false) }
  }

  async function handleOptimize() {
    setOptimizing(true); setSaveResult(null)
    try {
      const result = await optimizeImage(jobId, imageUrl, targetWidth, newFilename)
      if (result.success) { onFixed?.(); onClose?.() }
      else setSaveResult({ success: false, error: result.error || 'Failed' })
    } catch (err) { setSaveResult({ success: false, error: err.message }) } finally { setOptimizing(false) }
  }

  return (
    <div className="mt-1 border border-blue-100 rounded-lg bg-blue-50 overflow-hidden text-xs p-3">
      <div className="flex justify-between mb-2">
        <span className="font-medium text-blue-800 truncate max-w-xs">{originalFilename}</span>
        <button onClick={onClose} className="text-blue-400">&times;</button>
      </div>
      <div className="flex gap-4">
        <div className="w-20 h-20 bg-gray-200 rounded shrink-0 overflow-hidden"><img src={imageUrl} className="w-full h-full object-cover" /></div>
        <div className="flex-grow space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <div><label className="block text-[9px] text-gray-400 font-bold uppercase">New Name</label><input value={newFilename} onChange={e => setNewFilename(cleanFilename(e.target.value))} className="w-full border rounded p-1" /></div>
            <div><label className="block text-[9px] text-gray-400 font-bold uppercase">Width</label><select value={targetWidth} onChange={e => setTargetWidth(Number(e.target.value))} className="w-full border rounded p-1"><option value={800}>800px</option><option value={1200}>1200px</option></select></div>
          </div>
          <button onClick={handleOptimize} disabled={optimizing} className="bg-blue-600 text-white px-4 py-1.5 rounded font-bold">{optimizing ? 'Working...' : 'Optimize & Replace'}</button>
          {saveResult && <p className="text-red-600 text-[10px]">{saveResult.error}</p>}
        </div>
      </div>
    </div>
  )
}

function Spinner() {
  return <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-green-600 mx-auto" />
}

function CategoryTab({ jobId, category, onUrlClick, verifiedLinks, onVerify, onUnverify, onExemptAnchor, exemptAnchorUrls }) {
  const [data, setData] = useState(null)
  const [page, setPage] = useState(1)
  const [severity, setSeverity] = useState('')
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    getResultsByCategory(jobId, category, { page, limit: 50, severity: severity || undefined })
      .then(setData)
      .catch(err => setError(err.message))
  }, [jobId, category, page, severity])

  useEffect(() => { load() }, [load])

  if (error) return <div className="text-red-600 p-4">Error: {error}</div>
  if (!data) return <div className="py-12"><Spinner /></div>

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-gray-800 capitalize">{category.replace('_', ' ')} Issues</h2>
        <div className="flex items-center gap-3">
          <label className="text-xs font-medium text-gray-500">Filter severity:</label>
          <select value={severity} onChange={e => { setSeverity(e.target.value); setPage(1) }} className="text-xs border-gray-300 rounded px-2 py-1">
            <option value="">All</option>
            <option value="critical">Critical Only</option>
            <option value="warning">Warning Only</option>
            <option value="info">Info Only</option>
          </select>
        </div>
      </div>
      <IssueTable issues={data.issues} onPageClick={onUrlClick} verifiedLinks={verifiedLinks} onVerify={onVerify} onUnverify={onUnverify} onExemptAnchor={onExemptAnchor} exemptAnchorUrls={exemptAnchorUrls} />
    </div>
  )
}

function ByPageTab({ jobId, jumpToUrl, onJumpConsumed, onRescanComplete, onNavigateToCategory }) {
  const [data, setData] = useState(null)
  const [page, setPage] = useState(1)
  const [minSeverity, setMinSeverity] = useState('')
  const [search, setSearch] = useState('')
  const [expandedUrl, setExpandedUrl] = useState(null)
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    getPages(jobId, { page, limit: 50, minSeverity: minSeverity || undefined })
      .then(setData)
      .catch(err => setError(err.message))
  }, [jobId, page, minSeverity])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (jumpToUrl && data) {
      setExpandedUrl(jumpToUrl)
      onJumpConsumed()
      const el = document.getElementById(`page-row-${jumpToUrl}`)
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [jumpToUrl, data, onJumpConsumed])

  if (error) return <div className="text-red-600 p-4">Error: {error}</div>
  if (!data) return <div className="py-12"><Spinner /></div>

  const filtered = search.trim() ? data.pages.filter(p => p.url.toLowerCase().includes(search.toLowerCase())) : data.pages

  return (
    <div>
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
        <div className="flex-1 max-w-md relative">
          <input type="text" placeholder="Search pages..." value={search} onChange={e => setSearch(e.target.value)} className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm" />
          <svg className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-xs font-medium text-gray-500 whitespace-nowrap">Min severity:</label>
          <select value={minSeverity} onChange={e => { setMinSeverity(e.target.value); setPage(1) }} className="text-xs border-gray-300 rounded px-2 py-1">
            <option value="">Any issue</option>
            <option value="critical">Critical only</option>
            <option value="warning">Warning or higher</option>
          </select>
        </div>
      </div>
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Page URL</th>
              <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">Issues</th>
              <th className="px-6 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {filtered.map(p => (
              <React.Fragment key={p.url}>
                <tr id={`page-row-${p.url}`} className={`hover:bg-gray-50 transition-colors ${expandedUrl === p.url ? 'bg-green-50/30' : ''}`}>
                  <td className="px-6 py-4 font-mono text-xs break-all max-w-xl text-gray-700">{p.url}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-center">
                    <div className="flex justify-center gap-1.5">
                      {p.issue_counts.critical > 0 && <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded-full text-[10px] font-bold">{p.issue_counts.critical}</span>}
                      {p.issue_counts.warning > 0 && <span className="bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full text-[10px] font-bold">{p.issue_counts.warning}</span>}
                      {p.issue_counts.info > 0 && <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full text-[10px] font-bold">{p.issue_counts.info}</span>}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button onClick={() => setExpandedUrl(expandedUrl === p.url ? null : p.url)} className="text-xs font-bold text-green-600 hover:text-green-700 transition-colors">{expandedUrl === p.url ? 'Close' : 'View Issues'}</button>
                  </td>
                </tr>
                {expandedUrl === p.url && (
                  <tr>
                    <td colSpan="3" className="px-6 py-4 bg-gray-50 border-y border-gray-100"><PageDetail jobId={jobId} pageUrl={p.url} onRescanComplete={onRescanComplete} onNavigateToCategory={onNavigateToCategory} /></td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function PageDetail({ jobId, pageUrl, onRescanComplete, onNavigateToCategory }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [expandedHelp, setExpandedHelp] = useState(null)
  const [openFixCode, setOpenFixCode] = useState(null)

  const load = useCallback(() => {
    getPageIssues(jobId, pageUrl).then(setData).catch(err => setError(err.message))
  }, [jobId, pageUrl])

  useEffect(() => { load() }, [load])

  if (error) return <div className="text-red-600 text-xs">{error}</div>
  if (!data) return <Spinner />

  const grouped = data.issues.reduce((acc, iss) => {
    if (!acc[iss.category]) acc[iss.category] = []
    acc[iss.category].push(iss)
    return acc
  }, {})

  return (
    <div className="space-y-6">
      {Object.entries(grouped).map(([cat, issues]) => (
        <div key={cat}>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">{cat.replace('_', ' ')}</h3>
            <button onClick={() => onNavigateToCategory(cat)} className="text-[10px] font-bold text-blue-600 hover:underline">View All Category Issues →</button>
          </div>
          <div className="space-y-1.5">
            {issues.map((issue, i) => {
              const helpKey = `${cat}-${i}`, isHelpOpen = expandedHelp === helpKey, isImageFixable = IMAGE_FIXABLE_CODES.has(issue.issue_code)
              const isFixable = FIXABLE_CODES.has(issue.issue_code) || isImageFixable, isFixOpen = openFixCode === issue.issue_code
              return (
                <div key={i}>
                  <div className="flex items-start gap-2 bg-white rounded border border-gray-200 px-3 py-2.5 shadow-sm">
                    <SeverityBadge severity={issue.severity} />
                    <div className="flex-1">
                      <p className="text-xs font-bold text-gray-800">{issue.human_description || issue.issue_code.replace('_', ' ').title()}</p>
                      <p className="text-[11px] text-gray-500 mt-0.5 leading-relaxed">{issue.description}</p>
                    </div>
                    <div className="flex gap-1.5 shrink-0">
                      {isFixable && (
                        <button onClick={() => setOpenFixCode(isFixOpen ? null : issue.issue_code)} className={`text-[10px] font-bold px-2 py-1 rounded transition-colors ${isFixOpen ? 'bg-green-600 text-white' : 'bg-green-50 text-green-700 border border-green-200 hover:bg-green-100'}`}>
                          {isFixOpen ? 'Close' : 'Fix'}
                        </button>
                      )}
                      <button onClick={() => setExpandedHelp(isHelpOpen ? null : helpKey)} className={`w-5 h-5 rounded-full text-xs font-bold border ${isHelpOpen ? 'bg-blue-600 text-white' : 'text-blue-600 border-blue-200'}`}>?</button>
                    </div>
                  </div>
                  {isFixOpen && isImageFixable && <ImageFixPanel jobId={jobId} imageUrl={pageUrl} mode={issue.issue_code === 'IMG_OVERSIZED' ? 'oversized' : 'alt'} onClose={() => setOpenFixCode(null)} onFixed={onRescanComplete} />}
                  {isFixOpen && !isImageFixable && <FixInlinePanel jobId={jobId} pageUrl={pageUrl} issueCode={issue.issue_code} onClose={() => setOpenFixCode(null)} />}
                  {isHelpOpen && <div className="mt-1"><IssueHelpPanel code={issue.issue_code} onClose={() => setExpandedHelp(null)} /></div>}
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

function SeverityGroupedList({ issues, onPageClick }) {
  const grouped = issues.reduce((acc, iss) => {
    if (!acc[iss.issue_code]) acc[iss.issue_code] = { ...iss, count: 0, pages: [] }
    acc[iss.issue_code].count++
    acc[iss.issue_code].pages.push(iss.page_url)
    return acc
  }, {})
  return (
    <div className="space-y-4">
      {Object.values(grouped).map(group => (
        <div key={group.issue_code} className="border-b border-gray-100 pb-4 last:border-0">
          <div className="flex items-center gap-2 mb-1.5">
            <SeverityBadge severity={group.severity} />
            <h3 className="text-sm font-bold text-gray-800">{group.human_description || group.issue_code}</h3>
            <span className="text-[10px] font-bold bg-gray-100 text-gray-500 px-1.5 rounded uppercase">{group.count} pages</span>
          </div>
          <p className="text-xs text-gray-500 mb-2 leading-relaxed">{group.description}</p>
          <div className="flex flex-wrap gap-1.5">
            {group.pages.slice(0, 5).map(url => (
              <button key={url} onClick={() => onPageClick(url)} className="text-[10px] text-blue-600 hover:underline truncate max-w-[200px] bg-blue-50 px-1.5 py-0.5 rounded">{url.replace(/^https?:\/\/[^\/]+/, '') || '/'}</button>
            ))}
            {group.count > 5 && <span className="text-[10px] text-gray-400 font-medium">+{group.count - 5} more</span>}
          </div>
        </div>
      ))}
    </div>
  )
}

function TopPagesPanel({ jobId, onPageClick }) {
  const [pages, setPages] = useState(null)
  useEffect(() => {
    getPages(jobId, { page: 1, limit: 10 }).then(d => setPages(d.pages.filter(p => p.issue_counts.total > 0))).catch(() => setPages([]))
  }, [jobId])
  if (!pages?.length) return null
  return (
    <div>
      <h2 className="text-base font-semibold text-gray-700 mb-3">Top 10 pages to fix first</h2>
      <div className="bg-white border rounded-xl overflow-hidden shadow-sm">
        <table className="min-w-full text-xs divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr><th className="px-4 py-2.5 text-left text-gray-500 font-bold">Page</th><th className="px-3 py-2.5 text-center text-red-600">Crit</th><th className="px-3 py-2.5 text-center text-amber-600">Warn</th><th className="px-3 py-2.5 text-center text-blue-600">Info</th></tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {pages.map(p => (
              <tr key={p.url} className="hover:bg-gray-50 cursor-pointer" onClick={() => onPageClick(p.url)}>
                <td className="px-4 py-3 font-mono text-gray-700 truncate max-w-md">{p.url.replace(/^https?:\/\/[^\/]+/, '') || '/'}</td>
                <td className="px-3 py-3 text-center font-bold text-red-600">{p.issue_counts.critical}</td>
                <td className="px-3 py-3 text-center font-bold text-amber-600">{p.issue_counts.warning}</td>
                <td className="px-3 py-3 text-center font-bold text-blue-600">{p.issue_counts.info}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function TopPriorityGroups({ jobId, onPageFocus }) {
  const [groups, setGroups] = useState(null)
  useEffect(() => {
    getResults(jobId, { page: 1, limit: 5 }).then(d => {
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
    <div>
      <h2 className="text-base font-semibold text-gray-700 mb-3">Top 5 Priority Fixes</h2>
      <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
        {groups.map(g => (
          <button key={g.issue_code} onClick={() => onPageFocus(g.pages[0])} className="text-left bg-white border border-gray-200 rounded-xl p-4 hover:border-green-400 transition-colors shadow-sm">
            <SeverityBadge severity={g.severity} />
            <p className="text-xs font-bold text-gray-800 mt-2 line-clamp-2">{g.human_description || g.issue_code}</p>
            <p className="text-[10px] text-gray-500 mt-1 uppercase font-bold tracking-wider">{g.count} pages</p>
          </button>
        ))}
      </div>
    </div>
  )
}

function FixHistoryTab({ jobId }) {
  const [history, setHistory] = useState(null)
  useEffect(() => { getFixHistory(jobId).then(setHistory).catch(() => setHistory([])) }, [jobId])
  if (!history) return <Spinner />
  if (history.length === 0) return <div className="py-12 text-center text-gray-400 text-sm font-medium">No history yet. Fixes applied via the Fix Manager will appear here.</div>
  return (
    <div className="bg-white border rounded-xl overflow-hidden shadow-sm">
      <table className="min-w-full text-xs divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr><th className="px-6 py-3 text-left text-gray-500 uppercase tracking-widest font-bold">Applied At</th><th className="px-6 py-3 text-left text-gray-500 uppercase tracking-widest font-bold">Page</th><th className="px-6 py-3 text-left text-gray-500 uppercase tracking-widest font-bold">Issue</th><th className="px-6 py-3 text-left text-gray-500 uppercase tracking-widest font-bold">Result</th></tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {history.map(h => (
            <tr key={h.id} className="hover:bg-gray-50 transition-colors">
              <td className="px-6 py-4 whitespace-nowrap text-gray-500">{new Date(h.applied_at).toLocaleString()}</td>
              <td className="px-6 py-4 font-mono text-gray-700 truncate max-w-xs" title={h.page_url}>{h.page_url.replace(/^https?:\/\/[^\/]+/, '') || '/'}</td>
              <td className="px-6 py-4 font-bold text-gray-800">{h.issue_code}</td>
              <td className="px-6 py-4">
                <span className={`px-2 py-0.5 rounded-full font-bold uppercase text-[9px] ${h.status === 'success' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>{h.status}</span>
                {h.error && <p className="text-red-500 mt-1 italic">{h.error}</p>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function PageFocusPanel({ jobId, pageUrl, onClose }) {
  const [isOpen, setIsOpen] = useState(false)
  useEffect(() => { setIsOpen(true) }, [])
  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      <div className="absolute inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={() => { setIsOpen(false); setTimeout(onClose, 300) }}></div>
      <div className="fixed inset-y-0 right-0 max-w-full flex">
        <div className={`w-screen max-w-2xl transform transition-transform duration-300 ease-in-out ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}>
          <div className="h-full flex flex-col bg-gray-50 shadow-2xl">
            <div className="px-6 py-4 bg-white border-b border-gray-200 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-gray-800">Page Audit</h2>
                <p className="text-[10px] font-mono text-gray-500 truncate max-w-md" title={pageUrl}>{pageUrl}</p>
              </div>
              <button onClick={() => { setIsOpen(false); setTimeout(onClose, 300) }} className="text-gray-400 hover:text-gray-600 text-xl font-bold">&times;</button>
            </div>
            <div className="flex-1 overflow-y-auto p-6"><PageDetail jobId={jobId} pageUrl={pageUrl} onNavigateToCategory={onClose} /></div>
          </div>
        </div>
      </div>
    </div>
  )
}

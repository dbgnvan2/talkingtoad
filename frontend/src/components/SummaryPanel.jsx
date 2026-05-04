import React, { useState } from 'react'
import { useTheme } from '../contexts/ThemeContext.jsx'
import { getSiteAdvisor, testAI } from '../api.js'
import SiteRecommendationsPanel from './SiteRecommendationsPanel.jsx'
import OrphanedSummaryCards from './OrphanedSummaryCards.jsx'
import TopPriorityGroups from './TopPriorityGroups.jsx'
import Top10Pages from './Top10Pages.jsx'
import LLMSTxtGenerator from './LLMSTxtGenerator.jsx'
import StatCard from './StatCard.jsx'
import Spinner from './Spinner.jsx'

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

const TAB_ORPHAN_IMAGES = CATEGORIES.length + 2
const TAB_ORPHAN_PAGES = CATEGORIES.length + 3

export default function SummaryPanel({ summary, domain, jobId, onCategoryClick, onSeverityClick, onPageClick, onShowPdfModal, onShowCategoryHelp, onShowGeoSettings }) {
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

  if (!summary) {
    return <div className="py-20"><Spinner /></div>
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

      {/* GEO Settings prompt */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex items-center justify-between">
        <div>
          <p className="text-sm font-bold text-blue-800">Configure GEO Settings for better AI analysis</p>
          <p className="text-xs text-blue-600">Set your organization name, location, and topic entities for GEO-optimized image metadata.</p>
        </div>
        <button onClick={() => onShowGeoSettings?.()} className="px-4 py-2 bg-blue-600 text-white text-sm font-bold rounded-lg hover:bg-blue-700 flex-shrink-0 ml-4">
          Configure
        </button>
      </div>

      {/* 3x2 High-Level Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard label="Health Score" value={summary.health_score} color={summary.health_score > 80 ? 'text-green-600' : 'text-amber-500'} />
        <StatCard label="Pages Crawled" value={summary.pages_crawled} />
        <StatCard label="Total Issues" value={summary.total_issues} />
        <SeverityStatCard
          label="Critical Issues"
          value={summary.by_severity?.critical || 0}
          severity="critical"
          onClick={() => onSeverityClick('critical')}
        />
        <SeverityStatCard
          label="Warnings"
          value={summary.by_severity?.warning || 0}
          severity="warning"
          onClick={() => onSeverityClick('warning')}
        />
        <SeverityStatCard
          label="Info Notices"
          value={summary.by_severity?.info || 0}
          severity="info"
          onClick={() => onSeverityClick('info')}
        />
      </div>

      {/* Category Drill-down Boxes */}
      <section>
        <h2 className="font-black text-gray-400 uppercase tracking-widest mb-4" style={getFontClass('headingSize')}>{domain ? `Issues by Category - ${domain}` : 'Issues by Category'}</h2>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {CATEGORIES.map((cat, i) => (
            <div key={cat.key} className="relative bg-white border border-gray-200 rounded-2xl p-5 hover:border-green-400 hover:shadow-md transition-all group">
              <button
                onClick={(e) => { e.stopPropagation(); onCategoryClick(i) }}
                className="w-full text-left"
              >
                <p className="font-black text-gray-800 group-hover:text-green-600" style={{ ...getFontClass('badgeSize'), fontSize: `${getFontClass('badgeSize').fontSize.replace('px', '') * 2}px` }}>{summary.by_category?.[cat.key] || 0}</p>
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

      {/* Orphaned Content Summary */}
      <OrphanedSummaryCards jobId={jobId} onOrphanImagesClick={() => onCategoryClick(TAB_ORPHAN_IMAGES - 1)} onOrphanPagesClick={() => onCategoryClick(TAB_ORPHAN_PAGES - 1)} />

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

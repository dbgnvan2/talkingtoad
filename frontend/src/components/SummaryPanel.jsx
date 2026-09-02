import React, { useState } from 'react'
import { useToast } from '../contexts/ToastContext.jsx'
import { useTheme } from '../contexts/ThemeContext.jsx'
import { getSiteAdvisor, testAI } from '../api.js'
import { INFO_DETAIL_LABELS, INFO_TIER_LABELS } from '../data/infoDetail.js'
import SiteRecommendationsPanel from './SiteRecommendationsPanel.jsx'
import OrphanedSummaryCards from './OrphanedSummaryCards.jsx'
import TopPriorityGroups from './TopPriorityGroups.jsx'
import Top10Pages from './Top10Pages.jsx'
import FixFocusPanel from './FixFocusPanel.jsx'
import FixFocusItemsHelp from './FixFocusItemsHelp.jsx'
import LLMSTxtGenerator from './LLMSTxtGenerator.jsx'
import StrikingDistancePanel from './StrikingDistancePanel.jsx'
import ComparisonCard from './ComparisonCard.jsx'
import WpAuditPanel from './WpAuditPanel.jsx'
import StatCard from './StatCard.jsx'
import Spinner from './Spinner.jsx'
// CATEGORIES (the Issues-by-Category grid) comes from the single source of truth
// registry.CATEGORY_DISPLAY, projected to categories.generated.json (CLN2).
// Regenerate with `python scripts/generate_categories_json.py`.
import CATEGORIES from '../data/categories.generated.json'

const TAB_ORPHAN_IMAGES = CATEGORIES.length + 2
const TAB_ORPHAN_PAGES = CATEGORIES.length + 3

export default function SummaryPanel({ summary, domain, jobId, onCategoryClick, onSeverityClick, onPageClick, onShowPdfModal, onShowCategoryHelp, onShowGeoSettings }) {
  // C2: which analysis groups ran. Absent on legacy audits, which were full
  // scans — so an absent record must never mark a category "not checked".
  // Spec: docs/pending/2026-08-30_analysis-coverage-disclosure.md#C2
  const analysisCoverage = summary?.analysis_coverage ?? null
  const uncheckedCategories = new Set(
    analysisCoverage?.mode === 'partial' ? (analysisCoverage.categories_unchecked || []) : []
  )
  const isUnchecked = (key) => uncheckedCategories.has(key)
  // S2: what the health score was computed over. comparable === false means the
  // number covers only some categories and must not be read as a site score.
  const scoreBasis = summary?.health_score_basis ?? null
  // Info detail (2026-09-01 spec §7.2/7.3): the score follows the scan's level,
  // so whenever the level is not "all" the number carries its scope, and the
  // Info card shows what was counted with what was left out beneath it.
  const infoDetail = summary?.info_detail || 'all'
  const infoExcluded = summary?.info_excluded || 0
  const infoScored = summary?.info_scored ?? (summary?.by_severity?.info || 0)
  const infoByTier = summary?.info_by_tier || {}
  const toast = useToast()
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
      toast.error('Failed to get site recommendations: ' + err.message)
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

      {/* Headline scores: SEO Health + Agent Health (agent-readiness Phase 1),
          plus Site Hygiene (E4) when prevalence was computed. Health is per-page
          quality averaged; Hygiene is how much of the estate one defect touches.
          Spec: docs/pending/2026-08-29_E4-site-prevalence-escalation.md */}
      <div className={`grid grid-cols-1 gap-4 ${summary.site_hygiene_score != null ? 'md:grid-cols-3' : 'md:grid-cols-2'}`}>
        {/* S2: a partial scan scores 100 for categories it never ran, so the
            number must never appear bare — it invites a comparison it cannot
            support. See docs/pending/2026-08-30_score-coverage-basis.md#S2 */}
        <StatCard
          label={scoreBasis?.comparable === false
            ? `Health Score (${scoreBasis.categories_scored.length} of ${scoreBasis.categories_scored.length + scoreBasis.categories_unscored.length} categories)`
            : 'Health Score'}
          value={summary.health_score}
          color={summary.health_score > 80 ? 'text-green-600' : 'text-amber-500'}
          sub={infoDetail !== 'all' ? (
            <span data-testid="score-info-detail">
              scored at {INFO_DETAIL_LABELS[infoDetail] || infoDetail}
              {infoExcluded > 0 ? ` · ${infoExcluded} info notice${infoExcluded === 1 ? '' : 's'} excluded` : ''}
            </span>
          ) : null} />
        <StatCard
          label="Agent Health"
          value={summary.agent_health_score ?? '—'}
          color={(summary.agent_health_score ?? 0) > 80 ? 'text-green-600' : 'text-amber-500'}
        />
        {summary.site_hygiene_score != null && (
          <StatCard
            label="Site Hygiene"
            value={summary.site_hygiene_score}
            color={summary.site_hygiene_score > 80 ? 'text-green-600' : 'text-amber-500'}
          />
        )}
      </div>

      {/* Phase 4 U4.2 — compared with the previous scan of this site */}
      <ComparisonCard jobId={jobId} refreshKey={summary.health_score} />

      {/* E4 — systemic defects: one template or setting is responsible, so one
          fix resolves many pages. Shown only when something actually qualifies.
          Every defect is listed and every row is clickable: a summary that says
          "16 found" and shows five is a dead end, and the whole point of the
          section is that the reader can go and act on each one. */}
      {summary.systemic_count > 0 && (() => {
        const systemic = (summary.prevalence || []).filter((p) => p.tier === 'systemic')
        return (
          <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
            <p className="text-sm font-bold text-amber-900">
              {summary.systemic_count} systemic defect{summary.systemic_count !== 1 ? 's' : ''} found
            </p>
            <p className="text-xs text-amber-800 mt-1">
              These come from one template, theme setting or editorial habit — fixing the cause once resolves many pages. They are listed first in the PDF and Excel exports. Click any row to open that issue and see the affected pages.
            </p>
            <ul className="mt-3 space-y-1">
              {systemic.map((p) => {
                const categoryIndex = CATEGORIES.findIndex((c) => c.key === p.category)
                const clickable = categoryIndex >= 0
                return (
                  <li key={p.code}>
                    <button
                      type="button"
                      disabled={!clickable}
                      onClick={() => clickable && onCategoryClick(categoryIndex, p.code)}
                      title={clickable
                        ? `Open ${p.human_description} in ${CATEGORIES[categoryIndex].label}`
                        : 'This finding has no category view'}
                      className={`w-full text-left px-3 py-2 rounded-lg border transition-all ${
                        clickable
                          ? 'bg-white border-amber-100 hover:border-amber-300 hover:bg-amber-100 cursor-pointer'
                          : 'bg-white border-amber-100 cursor-default'
                      }`}
                    >
                      <span className="text-sm font-semibold text-gray-800">
                        {p.human_description}
                      </span>
                      <span className="text-sm text-gray-600">
                        {' '}— {p.pages_affected} of {p.indexable_pages} indexable pages ({Math.round(p.share * 100)}%)
                      </span>
                      {clickable && (
                        <span className="text-xs text-amber-700 font-bold ml-2">
                          {CATEGORIES[categoryIndex].label} →
                        </span>
                      )}
                    </button>
                  </li>
                )
              })}
            </ul>
            {/* The count and the list come from different fields; if they ever
                disagree the reader must be told, not shown a shorter list. */}
            {systemic.length !== summary.systemic_count && (
              <p className="text-xs text-amber-800 mt-2">
                Showing {systemic.length} of {summary.systemic_count}. The full list is
                in the PDF and Excel exports.
              </p>
            )}
          </div>
        )
      })()}

      {/* High-Level Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard label="Pages Crawled" value={summary.pages_crawled} />
        <StatCard label="Total Issues" value={summary.total_issues}
          sub={infoExcluded > 0 ? <span data-testid="total-found-vs-scored">found · {summary.total_issues - infoExcluded} scored</span> : null} />
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
          value={infoScored}
          severity="info"
          onClick={() => onSeverityClick('info')}
          // Stays clickable when everything was excluded: the reveal lives
          // behind this click, and a `none` scan needs it most.
          clickable={infoScored > 0 || infoExcluded > 0}
          sub={infoExcluded > 0 ? (
            <span data-testid="info-excluded">
              +{infoExcluded} excluded ({['low', 'medium', 'high']
                .filter(t => (infoByTier[t] || 0) > 0 && (t === 'low' || (t === 'medium' && ['key', 'none'].includes(infoDetail)) || (t === 'high' && infoDetail === 'none')))
                .map(t => `${INFO_TIER_LABELS[t]} ${infoByTier[t]}`).join(' · ')})
            </span>
          ) : null}
        />
      </div>

      {/* C2: the banner qualifies every number on this page, so it is not a
          footnote. Two crawls of one site read 1 warning and 118 purely because
          the first ran a single analysis group, and nothing said so. */}
      {analysisCoverage?.mode === 'partial' && (
        <div className="mb-4 px-5 py-4 bg-white border border-blue-200 rounded-2xl">
          <p className="text-blue-700 font-medium">This was a partial scan.</p>
          <p className="text-sm text-gray-600 mt-1">
            {`These categories were not checked and report nothing: ${(analysisCoverage.categories_unchecked || []).map(c => c.replace(/_/g, ' ')).join(', ')}. A category that did not run shows no findings, which is not the same as having none.`}
          </p>
          <p className="text-sm text-gray-600 mt-2">
            {`The health score covers only the categories that ran, so it is not comparable with a full scan of the same site.`}
          </p>
        </div>
      )}

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
                {/* C2: a category that never ran contributes zero findings, and a
                    "0" tile is indistinguishable from a clean category. Show
                    "not checked" instead (P31: absence rendered as a pass). */}
                {isUnchecked(cat.key) ? (
                  <p className="font-black text-gray-400 group-hover:text-green-600" style={{ ...getFontClass('badgeSize'), fontSize: `${getFontClass('badgeSize').fontSize.replace('px', '') * 2}px` }}>&mdash;</p>
                ) : (
                  <p className="font-black text-gray-800 group-hover:text-green-600" style={{ ...getFontClass('badgeSize'), fontSize: `${getFontClass('badgeSize').fontSize.replace('px', '') * 2}px` }}>{summary.by_category?.[cat.key] || 0}</p>
                )}
                <p className="font-black text-gray-800 uppercase tracking-wider mt-1 group-hover:text-green-600" style={getFontClass('headingSize')}>{cat.label}</p>
                {isUnchecked(cat.key) && (
                  <p className="text-xs text-gray-400 mt-1">not checked</p>
                )}
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

      {/* Fix Focus checklist + its deduped item help, beside the Top 5 Priority Fixes */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <FixFocusPanel jobId={jobId} />
        <FixFocusItemsHelp jobId={jobId} />
      </div>

      <Top10Pages jobId={jobId} onPageClick={onPageClick} />
      {/* Phase 4 U4.1 — pages one rewrite away from page one */}
      <StrikingDistancePanel jobId={jobId} onPageClick={onPageClick} refreshKey={summary.health_score} />
      <LLMSTxtGenerator jobId={jobId} />
      {/* Phase 4 U4.4 — the read-only WordPress configuration audit, on demand */}
      <WpAuditPanel jobId={jobId} initial={summary.wp_audit || null} />
    </div>
  )
}

function SeverityStatCard({ label, value, severity, onClick, sub = null, clickable = null }) {
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
      disabled={!(clickable ?? value > 0)}
      className={`bg-white border border-gray-200 rounded-3xl p-6 text-center shadow-sm transition-all ${(clickable ?? value > 0) ? `${c.hoverBorder} hover:shadow-md cursor-pointer` : 'opacity-60 cursor-default'}`}
    >
      <p className={`font-black uppercase tracking-widest mb-1 ${c.text}`} style={getFontClass('headingSize')}>{label}</p>
      <p className={`font-black ${c.text}`} style={{ ...getFontClass('badgeSize'), fontSize: `${getFontClass('badgeSize').fontSize.replace('px', '') * 2.5}px` }}>{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </button>
  )
}

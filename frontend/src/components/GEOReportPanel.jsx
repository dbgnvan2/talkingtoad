import React, { useState, useEffect, useRef } from 'react'
import { generateGeoReport, getGeoAiModel, setGeoAiModel, generateGeoRewritePrompt } from '../api.js'
import { authHeaders } from '../api.js'
import Spinner from './Spinner.jsx'

const TIER_COLORS = {
  Empirical:    'bg-amber-100 text-amber-800 border-amber-300',
  Mechanistic:  'bg-blue-100 text-blue-800 border-blue-300',
  Conventional: 'bg-gray-100 text-gray-700 border-gray-300',
}

const TIER_ICONS = {
  Empirical:    '🏆',
  Mechanistic:  '⚙️',
  Conventional: '💡',
}

const PASS_COLORS = {
  pass: 'text-green-600',
  fail: 'text-red-600',
  info: 'text-blue-600',
}

function TierBadge({ tier }) {
  const cls = TIER_COLORS[tier] || TIER_COLORS.Conventional
  const icon = TIER_ICONS[tier] || '💡'
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border ${cls}`}>
      {icon} {tier}
    </span>
  )
}

function ScoreBar({ score }) {
  const pct = Math.round((score ?? 0) * 100)
  const color = pct >= 70 ? 'bg-green-500' : pct >= 40 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-sm font-bold text-gray-700 w-10 text-right">{pct}%</span>
    </div>
  )
}

function FindingCard({ finding }) {
  const [open, setOpen] = useState(false)
  const passIcon = finding.pass_fail === 'pass' ? '✓' : finding.pass_fail === 'fail' ? '✗' : 'ℹ'
  const passColor = PASS_COLORS[finding.pass_fail] || 'text-gray-600'

  return (
    <div className={`border rounded-xl p-4 ${finding.pass_fail === 'fail' ? 'border-red-200 bg-red-50' : 'border-gray-200 bg-white'}`}>
      <button
        className="w-full flex items-start justify-between gap-3 text-left"
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-base font-bold ${passColor}`}>{passIcon}</span>
            <span className="font-semibold text-gray-800 text-sm">{finding.label}</span>
            <TierBadge tier={finding.evidence_tier} />
          </div>
          {finding.findings?.[0] && (
            <p className="text-xs text-gray-600 mt-1">{finding.findings[0]}</p>
          )}
        </div>
        <span className="text-gray-400 text-sm">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="mt-3 pt-3 border-t border-gray-200 space-y-1">
          {finding.findings?.map((f, i) => (
            <p key={i} className="text-xs text-gray-700">• {f}</p>
          ))}
          {finding.score !== undefined && (
            <div className="mt-2">
              <p className="text-xs text-gray-500 mb-1">Score</p>
              <ScoreBar score={finding.score} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function QueryMatchTable({ rows }) {
  if (!rows?.length) return null
  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200">
      <table className="w-full text-xs">
        <thead className="bg-gray-50">
          <tr>
            <th className="text-left p-3 font-bold text-gray-700">Query</th>
            <th className="text-left p-3 font-bold text-gray-700 w-48">Best Chunk</th>
            <th className="text-center p-3 font-bold text-gray-700 w-20">Answered?</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const color = row.answered === 'Yes' ? 'text-green-600' : row.answered === 'Partial' ? 'text-amber-600' : 'text-red-600'
            return (
              <tr key={i} className="border-t border-gray-100">
                <td className="p-3 text-gray-800">{row.query}</td>
                <td className="p-3 text-gray-600 italic">{row.best_chunk?.slice(0, 100)}{row.best_chunk?.length > 100 ? '…' : ''}</td>
                <td className={`p-3 text-center font-bold ${color}`}>{row.answered}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function ChunkContainedness({ chunks }) {
  if (!chunks?.length) return null
  return (
    <div className="space-y-2">
      {chunks.map((c, i) => (
        <div key={i} className={`flex items-start gap-3 p-3 rounded-lg border ${c.self_contained ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}`}>
          <span className={`font-bold text-base ${c.self_contained ? 'text-green-600' : 'text-red-600'}`}>
            {c.self_contained ? '✓' : '✗'}
          </span>
          <div>
            <p className="text-sm font-semibold text-gray-800">{c.heading}</p>
            <p className="text-xs text-gray-600">{c.reason}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

function JSRenderingSection({ data }) {
  if (!data) return null
  const flags = [
    { key: 'js_rendered_content_differs', label: 'JS-Gated Content', code: 'JS_RENDERED_CONTENT_DIFFERS' },
    { key: 'content_cloaking_detected', label: 'Content Cloaking', code: 'CONTENT_CLOAKING_DETECTED' },
    { key: 'ua_content_differs', label: 'AI Bot Stripping', code: 'UA_CONTENT_DIFFERS' },
  ]
  const anyFlag = flags.some(f => data[f.key])

  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-5">
      <h3 className="font-bold text-gray-800 mb-3 flex items-center gap-2">
        <span>🌐</span> JS Rendering Analysis
        <TierBadge tier="Mechanistic" />
      </h3>
      {data.error && !anyFlag && (
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2">{data.error}</p>
      )}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <p className="text-xs text-gray-500">Raw tokens</p>
          <p className="text-lg font-bold text-gray-800">{data.raw_token_count ?? '—'}</p>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <p className="text-xs text-gray-500">Rendered tokens</p>
          <p className="text-lg font-bold text-gray-800">{data.rendered_token_count ?? '—'}</p>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <p className="text-xs text-gray-500">Topic Jaccard</p>
          <p className="text-lg font-bold text-gray-800">{data.topic_jaccard != null ? data.topic_jaccard.toFixed(2) : '—'}</p>
        </div>
      </div>
      <div className="space-y-2">
        {flags.map(f => (
          <div key={f.key} className={`flex items-center gap-2 p-2 rounded-lg ${data[f.key] ? 'bg-red-50 border border-red-200' : 'bg-green-50 border border-green-200'}`}>
            <span className={`font-bold ${data[f.key] ? 'text-red-600' : 'text-green-600'}`}>
              {data[f.key] ? '✗' : '✓'}
            </span>
            <span className="text-sm text-gray-800">{f.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// RewriteAssist — only shown when overall_score < 0.90
// ---------------------------------------------------------------------------

const PCT = score => `${Math.round((score ?? 0) * 100)}%`

function downloadText(text, filename) {
  const blob = new Blob([text], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function VariantProgressRow({ v, isWinner, originalScore }) {
  const pending = v.projected_score === undefined
  const scoreColor = !pending && v.projected_score >= 0.90
    ? 'text-green-600'
    : !pending && v.projected_score >= 0.70
    ? 'text-amber-600'
    : 'text-red-600'

  return (
    <tr className={`border-t border-gray-100 ${isWinner ? 'bg-green-50' : ''}`}>
      <td className="px-3 py-2 text-center text-xs font-bold text-gray-500">#{v.index + 1}</td>
      <td className="px-3 py-2 text-center">
        {pending
          ? <span className="text-gray-400 text-xs">⏳</span>
          : v.error
          ? <span className="text-red-500 text-xs">Error</span>
          : <span className={`text-sm font-black ${scoreColor}`}>{PCT(v.projected_score)}</span>}
      </td>
      <td className="px-3 py-2 text-center text-xs text-gray-500">
        {pending ? '—' : v.error ? '—' : `${v.issues ?? '?'} issues`}
      </td>
      <td className="px-3 py-2 text-center text-xs">
        {isWinner && !pending
          ? <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded-full font-bold">Winner</span>
          : v.rank ? `#${v.rank}` : '—'}
      </td>
      <td className="px-3 py-2 text-xs text-gray-500 italic truncate max-w-[160px]">
        {v.error
          ? <span className="text-red-500">{v.error}</span>
          : v.preview || '…'}
      </td>
      <td className="px-3 py-2 text-center">
        {!pending && !v.error && v.text && (
          <button
            onClick={() => downloadText(v.text, `rewrite-attempt-${v.index + 1}.md`)}
            className="px-2 py-0.5 text-xs bg-indigo-100 text-indigo-700 rounded hover:bg-indigo-200 whitespace-nowrap"
            title="Download this rewrite as a Markdown file"
          >
            ↓ Download
          </button>
        )}
      </td>
    </tr>
  )
}

function RewriteAssist({ jobId, report }) {
  const [mode, setMode] = useState('prompt')  // 'prompt' | 'rewrite'
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [promptResult, setPromptResult] = useState(null)
  const [variants, setVariants] = useState([])   // live progress rows
  const [winnerResult, setWinnerResult] = useState(null)  // done event
  const [metaInfo, setMetaInfo] = useState(null)  // meta event data
  const [copied, setCopied] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const promptRef = useRef(null)
  const winnerRef = useRef(null)

  const score = Math.round((report.overall_score ?? 0) * 100)

  const handleCopy = (ref) => {
    const content = ref?.current?.value || ref?.current?.textContent || ''
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const handleGenerate = async () => {
    setLoading(true)
    setError(null)
    setPromptResult(null)
    setVariants([])
    setWinnerResult(null)
    setMetaInfo(null)

    try {
      if (mode === 'prompt') {
        const res = await generateGeoRewritePrompt(jobId, { useCachedReport: true })
        setPromptResult(res)
        setLoading(false)
        return
      }

      // Streaming auto-rewrite
      const res = await fetch('/api/ai/geo-rewrite-stream', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ job_id: jobId, tries: 5 }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `Server error ${res.status}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        // Parse complete SSE lines from buffer
        const lines = buffer.split('\n')
        buffer = lines.pop()  // keep incomplete last line

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))

            if (event.type === 'meta') {
              setMetaInfo(event)
              setVariants(Array.from({ length: event.total }, (_, i) => ({ index: i })))
            } else if (event.type === 'variant') {
              setVariants(prev => prev.map(v =>
                v.index === event.index ? { ...v, ...event } : v
              ))
            } else if (event.type === 'done') {
              setWinnerResult(event)
              // Merge final ranks into variant rows
              setVariants(event.variants)
            }
          } catch (_e) { /* malformed SSE line — skip */ }
        }
      }
    } catch (e) {
      setError(e.message || 'Failed')
    } finally {
      setLoading(false)
    }
  }

  const resetMode = (newMode) => {
    setMode(newMode)
    setPromptResult(null)
    setVariants([])
    setWinnerResult(null)
    setMetaInfo(null)
    setError(null)
  }

  return (
    <div className="border border-indigo-200 bg-indigo-50 rounded-2xl p-5 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-lg">✍️</span>
            <h3 className="font-bold text-indigo-900 text-sm">Rewrite Assist</h3>
            <span className="px-2 py-0.5 bg-amber-100 text-amber-700 text-xs font-bold rounded-full">
              {score}% → target 90%
            </span>
          </div>
          <p className="text-xs text-indigo-700 mt-1">
            Get a targeted LLM prompt, or auto-rewrite the page content fetched from the URL.
          </p>
        </div>
        <button
          onClick={() => setExpanded(e => !e)}
          className="text-indigo-400 hover:text-indigo-700 text-sm font-bold"
        >
          {expanded ? '▲ Hide' : '▼ Show'}
        </button>
      </div>

      {expanded && (
        <>
          {/* Mode toggle */}
          <div className="flex gap-1 bg-white border border-indigo-200 rounded-xl p-1 w-fit">
            {[
              { id: 'prompt', label: '📋 Get Prompt' },
              { id: 'rewrite', label: '🤖 Auto-Rewrite (5 tries)' },
            ].map(m => (
              <button
                key={m.id}
                onClick={() => resetMode(m.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                  mode === m.id ? 'bg-indigo-600 text-white shadow-sm' : 'text-indigo-600 hover:bg-indigo-50'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>

          {/* Generate button */}
          <button
            onClick={handleGenerate}
            disabled={loading}
            className="px-4 py-2 text-sm font-bold bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {loading
              ? (mode === 'rewrite' ? `Rewriting… (${variants.filter(v => v.projected_score !== undefined).length}/${variants.length})` : 'Generating…')
              : (mode === 'rewrite' ? '▶ Auto-Rewrite' : '▶ Generate Prompt')}
          </button>

          {error && (
            <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl p-3">{error}</div>
          )}

          {/* Prompt mode results */}
          {promptResult && mode === 'prompt' && (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-3 text-xs text-indigo-700 bg-white border border-indigo-200 rounded-xl p-3">
                <span>🔴 <strong>{promptResult.mandatory_count}</strong> mandatory</span>
                <span>·</span>
                <span>✅ <strong>{promptResult.fixable_count}</strong> fixable without fabrication</span>
                <span>·</span>
                <span>📄 <strong>{promptResult.page_type}</strong></span>
              </div>
              <div className="relative">
                <label className="text-xs font-bold text-indigo-800 block mb-1">System Prompt — paste into your LLM</label>
                <textarea
                  ref={promptRef}
                  readOnly
                  value={promptResult.system_prompt || ''}
                  rows={12}
                  className="w-full text-xs font-mono border border-indigo-200 rounded-xl p-3 bg-white resize-y"
                />
                <button
                  onClick={() => handleCopy(promptRef)}
                  className="absolute top-6 right-2 px-2 py-1 text-xs bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
                >
                  {copied ? '✓ Copied' : 'Copy'}
                </button>
              </div>
              <p className="text-xs text-indigo-600">
                Paste into ChatGPT, Claude, or Gemini — then add your page content after it.
              </p>
            </div>
          )}

          {/* Auto-rewrite: live progress table */}
          {mode === 'rewrite' && variants.length > 0 && (
            <div className="space-y-4">
              <div>
                <h4 className="text-xs font-bold text-indigo-800 mb-1">
                  Projected GEO Score per Attempt
                </h4>
                {metaInfo && (
                  <p className="text-xs text-indigo-500 mb-2">
                    Projected score = 80% query coverage (same questions re-scored) + 20% content quality (stats, citations, quotes, structure).
                    {' '}Original GEO score: <span className="font-bold text-indigo-700">{PCT(metaInfo.current_score)}</span>
                    {!metaInfo.has_query_table && ' · No query table cached — scoring via content signals only'}
                  </p>
                )}
                <div className="overflow-x-auto rounded-xl border border-indigo-200 bg-white">
                  <table className="w-full text-xs">
                    <thead className="bg-indigo-50">
                      <tr>
                        <th className="px-3 py-2 text-center font-bold text-indigo-700 w-16">Try</th>
                        <th className="px-3 py-2 text-center font-bold text-indigo-700 w-24">Content Score</th>
                        <th className="px-3 py-2 text-center font-bold text-indigo-700 w-20">Issues</th>
                        <th className="px-3 py-2 text-center font-bold text-indigo-700 w-20">Rank</th>
                        <th className="px-3 py-2 text-left font-bold text-indigo-700">Preview</th>
                        <th className="px-3 py-2 text-center font-bold text-indigo-700 w-24"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {variants.map(v => (
                        <VariantProgressRow
                          key={v.index}
                          v={v}
                          isWinner={winnerResult && v.index === winnerResult.winner_index}
                          originalScore={report.overall_score}
                        />
                      ))}
                    </tbody>
                  </table>
                </div>

                {winnerResult && (
                  <div className="flex items-center gap-2 mt-2 text-xs text-indigo-700">
                    <span>Winner: try #{(winnerResult.winner_index ?? 0) + 1}</span>
                    <span>·</span>
                    <span className="font-bold text-green-700">{PCT(winnerResult.winner_projected_score)}</span>
                    {winnerResult.improvement?.gain > 0 && (
                      <span className="text-green-600">
                        (+{Math.round((winnerResult.improvement.gain) * 100)}pp vs original {PCT(winnerResult.improvement?.geo_report_score)})
                      </span>
                    )}
                  </div>
                )}
              </div>

              {/* Winner text */}
              {winnerResult?.winner_text && (
                <div className="relative">
                  <label className="text-xs font-bold text-indigo-800 block mb-1">
                    Best Rewrite — try #{(winnerResult.winner_index ?? 0) + 1} (copy into your CMS)
                  </label>
                  <textarea
                    ref={winnerRef}
                    readOnly
                    value={winnerResult.winner_text}
                    rows={14}
                    className="w-full text-xs font-mono border border-indigo-200 rounded-xl p-3 bg-white resize-y"
                  />
                  <button
                    onClick={() => handleCopy(winnerRef)}
                    className="absolute top-6 right-2 px-2 py-1 text-xs bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
                  >
                    {copied ? '✓ Copied' : 'Copy'}
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default function GEOReportPanel({ jobId, domain }) {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [models, setModels] = useState(null)
  const [selectedModel, setSelectedModel] = useState(null)
  const [activeSection, setActiveSection] = useState('findings')

  useEffect(() => {
    getGeoAiModel()
      .then(data => {
        setModels(data)
        setSelectedModel(data.selected)
      })
      .catch(() => {})
  }, [])

  const handleRun = async (forceRefresh = false) => {
    setLoading(true)
    setError(null)
    try {
      const result = await generateGeoReport(jobId, { model: selectedModel, forceRefresh })
      setReport(result.report)
    } catch (e) {
      setError(e.message || 'Analysis failed')
    } finally {
      setLoading(false)
    }
  }

  const handleModelChange = async (modelId) => {
    setSelectedModel(modelId)
    await setGeoAiModel(modelId).catch(() => {})
  }

  const empirical = report?.findings?.filter(f => f.evidence_tier === 'Empirical') ?? []
  const mechanistic = report?.findings?.filter(f => f.evidence_tier === 'Mechanistic') ?? []
  const conventional = report?.findings?.filter(f => f.evidence_tier === 'Conventional') ?? []

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-800">GEO Analysis Report</h2>
          {domain && <p className="text-sm text-gray-500">{domain}</p>}
        </div>
        <div className="flex items-center gap-2">
          {models?.available?.length > 0 && !report && (
            <select
              value={selectedModel || ''}
              onChange={e => handleModelChange(e.target.value)}
              className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 bg-white"
            >
              {models.available.map(m => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </select>
          )}
          <button
            onClick={() => handleRun(false)}
            disabled={loading}
            className="px-4 py-2 text-sm font-bold bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Analyzing…' : report ? 'Re-run' : '▶ Run GEO Analysis'}
          </button>
        </div>
      </div>

      {/* Evidence tier legend */}
      <div className="flex flex-wrap gap-2 text-xs">
        <span className="text-gray-500 font-medium">Evidence tiers:</span>
        <TierBadge tier="Empirical" /> <span className="text-gray-500">= Aggarwal et al. measured</span>
        <TierBadge tier="Mechanistic" /> <span className="text-gray-500">= derived from retrieval mechanics</span>
        <TierBadge tier="Conventional" /> <span className="text-gray-500">= industry advice, unconfirmed</span>
      </div>

      {loading && <div className="py-12"><Spinner /></div>}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">{error}</div>
      )}

      {report && !loading && (
        <>
          {/* Score cards */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-white border border-gray-200 rounded-2xl p-5">
              <p className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">Overall GEO Score</p>
              <p className="text-3xl font-black text-gray-900 mb-2">{Math.round((report.overall_score ?? 0) * 100)}%</p>
              <ScoreBar score={report.overall_score} />
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5">
              <p className="text-xs font-bold text-amber-700 uppercase tracking-wider mb-2">
                🏆 Aggarwal Score (Empirical)
              </p>
              <p className="text-3xl font-black text-amber-800 mb-2">{Math.round((report.aggarwal_score ?? 0) * 100)}%</p>
              <ScoreBar score={report.aggarwal_score} />
              <p className="text-xs text-amber-600 mt-2">Tactics with controlled measurement</p>
            </div>
          </div>

          {/* Rewrite Assist — shown when score < 90% */}
          {(report.overall_score ?? 0) < 0.90 && (
            <RewriteAssist jobId={jobId} report={report} />
          )}

          {/* Section tabs */}
          <div className="flex gap-1 bg-gray-100 rounded-xl p-1">
            {[
              { id: 'findings', label: `Findings (${report.findings?.length ?? 0})` },
              { id: 'query', label: `Query Test (${report.query_match_table?.length ?? 0})` },
              { id: 'chunks', label: `Chunks (${report.chunk_containedness?.length ?? 0})` },
              { id: 'js', label: 'JS Rendering' },
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveSection(tab.id)}
                className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold transition-colors ${
                  activeSection === tab.id ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-600 hover:text-gray-800'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Findings tab */}
          {activeSection === 'findings' && (
            <div className="space-y-4">
              {empirical.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="font-bold text-gray-700 text-sm">🏆 Empirical (Aggarwal et al.)</h3>
                    <span className="text-xs text-gray-400">highest weight</span>
                  </div>
                  <div className="space-y-2">{empirical.map((f, i) => <FindingCard key={i} finding={f} />)}</div>
                </div>
              )}
              {mechanistic.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="font-bold text-gray-700 text-sm">⚙️ Mechanistic</h3>
                    <span className="text-xs text-gray-400">retrieval mechanics</span>
                  </div>
                  <div className="space-y-2">{mechanistic.map((f, i) => <FindingCard key={i} finding={f} />)}</div>
                </div>
              )}
              {conventional.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="font-bold text-gray-700 text-sm">💡 Conventional</h3>
                    <span className="text-xs text-gray-400">industry advice, lower confidence</span>
                  </div>
                  <div className="space-y-2">{conventional.map((f, i) => <FindingCard key={i} finding={f} />)}</div>
                </div>
              )}
              {report.findings?.length === 0 && (
                <p className="text-center text-gray-500 py-8">No findings. Run the analysis to see results.</p>
              )}
            </div>
          )}

          {/* Query match tab */}
          {activeSection === 'query' && (
            <div>
              <p className="text-xs text-gray-500 mb-3">
                The AI generated queries this page should answer, then scored how well the page answers each.
              </p>
              <QueryMatchTable rows={report.query_match_table} />
              {!report.query_match_table?.length && (
                <p className="text-center text-gray-500 py-8">No query test data.</p>
              )}
            </div>
          )}

          {/* Chunk containedness tab */}
          {activeSection === 'chunks' && (
            <div>
              <p className="text-xs text-gray-500 mb-3">
                Each H2/H3 section was tested for self-containedness — can a reader understand it without reading the rest?
              </p>
              <ChunkContainedness chunks={report.chunk_containedness} />
              {!report.chunk_containedness?.length && (
                <p className="text-center text-gray-500 py-8">No chunk data. The page may not have enough H2/H3 sections.</p>
              )}
            </div>
          )}

          {/* JS rendering tab */}
          {activeSection === 'js' && (
            <div className="space-y-4">
              {report.playwright_available ? (
                <JSRenderingSection data={report.js_rendering} />
              ) : (
                <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl">
                  <p className="text-sm font-bold text-amber-800">Playwright not installed</p>
                  <p className="text-xs text-amber-700 mt-1">
                    JS rendering checks require Playwright. Install with:
                  </p>
                  <code className="block text-xs bg-white border border-amber-200 rounded p-2 mt-2 font-mono">
                    pip install playwright && playwright install chromium
                  </code>
                </div>
              )}
            </div>
          )}

          {/* Cached indicator */}
          {report && (
            <div className="flex justify-between items-center pt-2 border-t border-gray-100">
              <p className="text-xs text-gray-400">
                Model: {report.model_used}
                {report.error && ` · Error: ${report.error}`}
              </p>
              <button
                onClick={() => handleRun(true)}
                className="text-xs text-blue-600 hover:underline"
              >
                Force refresh
              </button>
            </div>
          )}
        </>
      )}

      {/* Pre-run state */}
      {!report && !loading && !error && (
        <div className="py-12 text-center bg-gray-50 rounded-2xl border border-gray-200 border-dashed">
          <p className="text-3xl mb-3">🔬</p>
          <p className="font-bold text-gray-700">GEO Analysis not yet run</p>
          <p className="text-sm text-gray-500 mt-1 max-w-sm mx-auto">
            Runs LLM-based checks: query matching, chunk self-containedness, central claim detection,
            and JS rendering comparison.
          </p>
          <button
            onClick={() => handleRun(false)}
            className="mt-4 px-6 py-2 bg-indigo-600 text-white font-bold rounded-xl hover:bg-indigo-700 transition-colors"
          >
            ▶ Run GEO Analysis
          </button>
        </div>
      )}
    </div>
  )
}

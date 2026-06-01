import React, { useState, useEffect, useRef } from 'react'
import { useToast } from '../contexts/ToastContext.jsx'
import { generateGeoReport, getGeoAiModel, setGeoAiModel, generateGeoRewritePrompt, generateGeoFaq, generateEntitySchema } from '../api.js'
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
        {pending ? '—' : v.error ? '—' : (
          <span>
            {`${v.issues ?? '?'} issues`}
            {v.placeholder_issues?.length > 0 && (
              <span
                className="ml-1 text-amber-600"
                title={`Placeholders claimed in GEO NOTES but not embedded in body: ${v.placeholder_issues.join(', ')}`}
              >⚠️</span>
            )}
          </span>
        )}
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

              {/* Knowledge ceiling — queries no rewrite variant could answer */}
              {winnerResult?.knowledge_gaps?.length > 0 && (
                <div className="rounded-xl border border-amber-300 bg-amber-50 p-4">
                  <div className="flex items-start gap-2 mb-2">
                    <span className="text-amber-600 text-base">⚠️</span>
                    <div>
                      <p className="text-xs font-bold text-amber-800">Knowledge Ceiling Detected</p>
                      <p className="text-xs text-amber-700 mt-0.5">
                        The following queries scored "No" across <em>every</em> rewrite attempt.
                        No amount of rewording will address them — the page needs <strong>new content</strong> to answer these:
                      </p>
                    </div>
                  </div>
                  <ul className="mt-2 space-y-1 pl-4">
                    {winnerResult.knowledge_gaps.map((q, idx) => (
                      <li key={idx} className="text-xs text-amber-900 list-disc">{q}</li>
                    ))}
                  </ul>
                </div>
              )}

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

// ---------------------------------------------------------------------------
// GA3: FAQ Schema Generator Card
// ---------------------------------------------------------------------------

function FAQSchemaCard({ domain }) {
  const [mode, setMode] = useState('template')
  const [limit, setLimit] = useState(8)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [copied, setCopied] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [showHelp, setShowHelp] = useState(false)
  const textareaRef = useRef(null)

  const handleGenerate = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await generateGeoFaq(domain, { mode, limit })
      setResult(data)
    } catch (e) {
      setError(e.message || 'FAQ generation failed')
    } finally {
      setLoading(false)
    }
  }

  const handleCopy = () => {
    if (!result) return
    const jsonLd = JSON.stringify(result.faq_block, null, 2)
    navigator.clipboard.writeText(jsonLd).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const jsonLdText = result ? JSON.stringify(result.faq_block, null, 2) : ''

  return (
    <div className="border border-emerald-200 bg-emerald-50 rounded-2xl p-5 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-lg">&#x2753;</span>
            <h3 className="font-bold text-emerald-900 text-sm">FAQ Schema Generator</h3>
            <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs font-bold rounded-full">
              JSON-LD
            </span>
          </div>
          <p className="text-xs text-emerald-700 mt-1">
            Generate Schema.org FAQPage markup from your topics and locations.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowHelp(h => !h)}
            className="text-emerald-400 hover:text-emerald-700 text-xs font-bold"
            title="Learn more"
          >
            {showHelp ? 'Hide help' : '?'}
          </button>
          <button
            onClick={() => setExpanded(e => !e)}
            className="text-emerald-400 hover:text-emerald-700 text-sm font-bold"
          >
            {expanded ? '\u25B2 Hide' : '\u25BC Show'}
          </button>
        </div>
      </div>

      {/* Help / explainer (V4 standard) */}
      {showHelp && (
        <div className="bg-white border border-emerald-200 rounded-xl p-4 text-xs text-emerald-800 space-y-2">
          <p><strong>What it is:</strong> Generates ready-to-paste FAQ schema (JSON-LD) built from your organisation&apos;s topics and locations.</p>
          <p><strong>Why it&apos;s useful:</strong> Long-tail FAQ questions are exactly what AI engines and search match against; structured FAQ markup makes your answers eligible for rich results and AI citation.</p>
          <p><strong>Good vs bad:</strong> A 6+-word, specific question (&quot;What should I expect from grief counselling in Vancouver?&quot;) vs a short head term (&quot;counselling&quot;) that everyone competes for and AI can&apos;t anchor to.</p>
          <p><strong>How it can mislead:</strong> The tool generates <em>anchors</em>, not verified answers &mdash; you must write accurate answers; schema for content you can&apos;t honestly answer can hurt trust.</p>
          <p><strong>How to use:</strong> Paste the JSON-LD into your page&apos;s {'<head>'} or body, then replace the draft answers with real ones.</p>
        </div>
      )}

      {expanded && (
        <>
          {/* Controls */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex gap-1 bg-white border border-emerald-200 rounded-xl p-1">
              {[
                { id: 'template', label: 'Template (free)' },
                { id: 'ai', label: 'AI-enriched' },
              ].map(m => (
                <button
                  key={m.id}
                  onClick={() => setMode(m.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                    mode === m.id ? 'bg-emerald-600 text-white shadow-sm' : 'text-emerald-600 hover:bg-emerald-50'
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
            <label className="flex items-center gap-1 text-xs text-emerald-700">
              Questions:
              <select
                value={limit}
                onChange={e => setLimit(Number(e.target.value))}
                className="border border-emerald-200 rounded px-1 py-0.5 bg-white text-xs"
              >
                {[4, 6, 8, 10, 12].map(n => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </label>
            <button
              onClick={handleGenerate}
              disabled={loading}
              className="px-4 py-2 text-sm font-bold bg-emerald-600 text-white rounded-xl hover:bg-emerald-700 disabled:opacity-50 transition-colors"
            >
              {loading ? 'Generating\u2026' : '\u25B6 Generate FAQ Schema'}
            </button>
          </div>

          {/* Error */}
          {error && (
            <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl p-3">{error}</div>
          )}

          {/* Results */}
          {result && (
            <div className="space-y-3">
              {/* Metadata bar */}
              <div className="flex flex-wrap items-center gap-3 text-xs text-emerald-700 bg-white border border-emerald-200 rounded-xl p-3">
                <span>Mode: <strong>{result.mode_used}</strong></span>
                <span>&middot;</span>
                <span>{result.questions.length} question{result.questions.length !== 1 ? 's' : ''}</span>
                {result.token_usage && (
                  <>
                    <span>&middot;</span>
                    <span>Tokens: {result.token_usage.input}in / {result.token_usage.output}out</span>
                    <span>&middot;</span>
                    <span>${result.token_usage.cost_usd?.toFixed(4)}</span>
                  </>
                )}
              </div>

              {/* Questions list */}
              <div className="bg-white border border-emerald-200 rounded-xl p-3">
                <p className="text-xs font-bold text-emerald-800 mb-2">Generated Questions:</p>
                <ul className="space-y-1">
                  {result.questions.map((q, i) => (
                    <li key={i} className="text-xs text-gray-700 flex items-start gap-2">
                      <span className="text-emerald-500 font-bold">{i + 1}.</span>
                      <span>{q}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* JSON-LD copy box (rendered as TEXT, never dangerouslySetInnerHTML) */}
              <div className="relative">
                <label className="text-xs font-bold text-emerald-800 block mb-1">
                  JSON-LD &mdash; paste into your page
                </label>
                <textarea
                  ref={textareaRef}
                  readOnly
                  value={jsonLdText}
                  rows={Math.min(20, jsonLdText.split('\n').length + 1)}
                  className="w-full text-xs font-mono border border-emerald-200 rounded-xl p-3 bg-white resize-y"
                />
                <button
                  onClick={handleCopy}
                  className="absolute top-6 right-2 px-2 py-1 text-xs bg-emerald-600 text-white rounded-lg hover:bg-emerald-700"
                >
                  {copied ? '\u2713 Copied' : 'Copy'}
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}


// ---------------------------------------------------------------------------
// GA4: Entity Schema Factory Card
// ---------------------------------------------------------------------------

function EntitySchemaCard({ domain }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [copied, setCopied] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [showHelp, setShowHelp] = useState(false)
  const textareaRef = useRef(null)

  const handleGenerate = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await generateEntitySchema(domain)
      setResult(data)
    } catch (e) {
      setError(e.message || 'Entity schema generation failed')
    } finally {
      setLoading(false)
    }
  }

  const handleCopy = () => {
    if (!result) return
    navigator.clipboard.writeText(result.jsonld).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="border border-violet-200 bg-violet-50 rounded-2xl p-5 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-lg">&#x1F3DB;</span>
            <h3 className="font-bold text-violet-900 text-sm">Entity Schema Factory</h3>
            <span className="px-2 py-0.5 bg-violet-100 text-violet-700 text-xs font-bold rounded-full">
              JSON-LD
            </span>
          </div>
          <p className="text-xs text-violet-700 mt-1">
            Generate Schema.org Organization markup linking your entity to Wikipedia/Wikidata.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowHelp(h => !h)}
            className="text-violet-400 hover:text-violet-700 text-xs font-bold"
            title="Learn more"
          >
            {showHelp ? 'Hide help' : '?'}
          </button>
          <button
            onClick={() => setExpanded(e => !e)}
            className="text-violet-400 hover:text-violet-700 text-sm font-bold"
          >
            {expanded ? '\u25B2 Hide' : '\u25BC Show'}
          </button>
        </div>
      </div>

      {/* Help / explainer (V4 standard) */}
      {showHelp && (
        <div className="bg-white border border-violet-200 rounded-xl p-4 text-xs text-violet-800 space-y-2">
          <p><strong>What it is:</strong> Builds ready-to-paste JSON-LD that tells search and AI engines who your organisation is, what services it offers, and which authoritative entity (Wikipedia/Wikidata page) it corresponds to.</p>
          <p><strong>Why it&apos;s useful:</strong> A <code>sameAs</code> link to an authoritative entity is a strong disambiguation signal &mdash; it helps AI engines confidently identify and cite your organisation.</p>
          <p><strong>Good vs bad:</strong> Linking to your real Wikipedia/Wikidata entity vs leaving it blank (no disambiguation) or pointing at an unrelated page (actively misleading).</p>
          <p><strong>How it can mislead:</strong> Schema must match what&apos;s visibly on your page and be truthful; claiming services or an identity you can&apos;t back up can hurt trust and eligibility.</p>
          <p><strong>How to use:</strong> Set your entity URL in GEO settings, generate, paste the JSON-LD into the page <code>{'<head>'}</code>.</p>
        </div>
      )}

      {expanded && (
        <>
          {/* Generate button */}
          <button
            onClick={handleGenerate}
            disabled={loading}
            className="px-4 py-2 text-sm font-bold bg-violet-600 text-white rounded-xl hover:bg-violet-700 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Generating\u2026' : '\u25B6 Generate Entity Schema'}
          </button>

          {/* Error */}
          {error && (
            <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl p-3">{error}</div>
          )}

          {/* Results */}
          {result && (
            <div className="space-y-3">
              {/* Warnings */}
              {result.warnings?.length > 0 && (
                <div className="flex flex-wrap items-center gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-xl p-3">
                  {result.warnings.map((w, i) => (
                    <span key={i}>{w}</span>
                  ))}
                </div>
              )}

              {/* JSON-LD copy box (rendered as TEXT, never dangerouslySetInnerHTML) */}
              <div className="relative">
                <label className="text-xs font-bold text-violet-800 block mb-1">
                  JSON-LD &mdash; paste into your page {'<head>'}
                </label>
                <textarea
                  ref={textareaRef}
                  readOnly
                  value={result.jsonld}
                  rows={Math.min(24, (result.jsonld || '').split('\n').length + 1)}
                  className="w-full text-xs font-mono border border-violet-200 rounded-xl p-3 bg-white resize-y"
                />
                <button
                  onClick={handleCopy}
                  className="absolute top-6 right-2 px-2 py-1 text-xs bg-violet-600 text-white rounded-lg hover:bg-violet-700"
                >
                  {copied ? '\u2713 Copied' : 'Copy'}
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}


export default function GEOReportPanel({ jobId, domain }) {
  const toast = useToast()
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [models, setModels] = useState(null)
  const [selectedModel, setSelectedModel] = useState(null)
  const [activeSection, setActiveSection] = useState('findings')
  const [generatedPrompt, setGeneratedPrompt] = useState(null)
  const [promptLoading, setPromptLoading] = useState(false)
  const [rewriteLoading, setRewriteLoading] = useState(false)
  const [rewriteContent, setRewriteContent] = useState(null)

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

  const handleGeneratePrompt = async () => {
    setPromptLoading(true)
    try {
      const response = await fetch('/api/ai/advisor/prompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ report_markdown: report.report_markdown })
      })
      const data = await response.json()
      setGeneratedPrompt(data.prompt)
    } catch (e) {
      setError('Failed to generate prompt: ' + e.message)
    } finally {
      setPromptLoading(false)
    }
  }

  const handleRewrite = async () => {
    if (!report.report_markdown) {
      setError('No report available to rewrite')
      return
    }

    if (!generatedPrompt) {
      setError('Please generate a rewrite prompt first')
      return
    }

    setRewriteLoading(true)
    setError(null)
    try {
      // Get the job's target URL
      const jobResponse = await fetch(`/api/crawl/${jobId}`)
      if (!jobResponse.ok) {
        throw new Error(`Failed to get job details: ${jobResponse.status}`)
      }
      const jobData = await jobResponse.json()
      const targetUrl = jobData.target_url

      if (!targetUrl) {
        setError('Job has no target URL')
        setRewriteLoading(false)
        return
      }

      // Rewrite the page at that URL
      const response = await fetch('/api/ai/rewrite-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          url: targetUrl,
          prompt: generatedPrompt
        })
      })
      if (!response.ok) {
        throw new Error(`Rewriter failed: ${response.status}`)
      }
      const data = await response.json()
      setRewriteContent(data.rewrite)
      setError(null)
    } catch (e) {
      setError('Failed to rewrite: ' + e.message)
      console.error('Rewrite error:', e)
    } finally {
      setRewriteLoading(false)
    }
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
          {/* Show old score cards only if NOT using new markdown report */}
          {!report.report_markdown && (
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

              {/* Tier 1 structural scores (spec §4.7) */}
              {report.tier1_scores && (
                <div>
                  <p className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">
                    Structural Audit — Tier 1 Heuristics
                  </p>
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { key: 'intro',           label: 'Intro Answer',        desc: 'Direct answer in first 200 words' },
                      { key: 'query_coverage',  label: 'Query Coverage',       desc: 'H1 terms in intro + section headings' },
                      { key: 'independence',    label: 'Section Independence', desc: 'Absence of backward cross-references' },
                      { key: 'section_clarity', label: 'Section Clarity',      desc: 'No vague openers or overlong paragraphs' },
                    ].map(({ key, label, desc }) => {
                      const val = report.tier1_scores[key] ?? 0
                      const color = val >= 80 ? 'text-green-700' : val >= 50 ? 'text-amber-700' : 'text-red-600'
                      const bg    = val >= 80 ? 'bg-green-50 border-green-200' : val >= 50 ? 'bg-amber-50 border-amber-200' : 'bg-red-50 border-red-200'
                      return (
                        <div key={key} className={`border rounded-xl p-3 ${bg}`}>
                          <div className="flex items-center justify-between mb-1">
                            <p className="text-xs font-bold text-gray-700">{label}</p>
                            <p className={`text-lg font-black ${color}`}>{val}%</p>
                          </div>
                          <div className="w-full h-1.5 bg-gray-200 rounded-full overflow-hidden mb-1">
                            <div
                              className={`h-full rounded-full ${val >= 80 ? 'bg-green-500' : val >= 50 ? 'bg-amber-500' : 'bg-red-500'}`}
                              style={{ width: `${val}%` }}
                            />
                          </div>
                          <p className="text-[10px] text-gray-500">{desc}</p>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Rewrite Assist — shown when score < 90% */}
              {(report.overall_score ?? 0) < 0.90 && (
                <RewriteAssist jobId={jobId} report={report} />
              )}
            </>
          )}

          {/* Section tabs */}
          <div className="flex gap-1 bg-gray-100 rounded-xl p-1">
            {[
              report.report_markdown ? { id: 'report', label: 'Quality Report' } : null,
              report.findings?.length > 0 ? { id: 'findings', label: `Findings (${report.findings?.length ?? 0})` } : null,
              report.query_match_table?.length > 0 ? { id: 'query', label: `Query Test (${report.query_match_table?.length ?? 0})` } : null,
              report.chunk_containedness?.length > 0 ? { id: 'chunks', label: `Chunks (${report.chunk_containedness?.length ?? 0})` } : null,
              report.playwright_available ? { id: 'js', label: 'JS Rendering' } : null,
            ].filter(Boolean).map(tab => (
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

          {/* Markdown Report tab */}
          {activeSection === 'report' && report.report_markdown && (
            <div className="space-y-4">
              {/* Report content */}
              <div className="bg-white p-5 rounded-xl border border-gray-200">
                {report.report_markdown.split('\n').map((line, i) => {
                  if (line.startsWith('# ')) return <h1 key={i} className="text-2xl font-bold mb-4 mt-6">{line.slice(2)}</h1>
                  if (line.startsWith('## ')) return <h2 key={i} className="text-xl font-bold mb-3 mt-5">{line.slice(3)}</h2>
                  if (line.startsWith('### ')) return <h3 key={i} className="text-lg font-semibold mb-2 mt-4">{line.slice(4)}</h3>
                  if (line.startsWith('- ')) return <li key={i} className="ml-4 mb-1">{line.slice(2)}</li>
                  if (line.startsWith('**') && line.endsWith('**')) return <p key={i} className="font-bold text-gray-800 mb-2">{line.slice(2, -2)}</p>
                  if (line.trim() === '') return <div key={i} className="mb-2" />
                  return <p key={i} className="mb-3 text-gray-700 leading-relaxed">{line}</p>
                })}
              </div>

              {/* Generate Prompt / Rewrite Section */}
              <div className="bg-blue-50 border border-blue-200 rounded-xl p-5 space-y-3">
                <div className="flex items-center gap-2">
                  <h3 className="font-bold text-blue-900">✨ Generate Rewrite Prompt</h3>
                </div>

                {!generatedPrompt ? (
                  <button
                    onClick={handleGeneratePrompt}
                    disabled={promptLoading}
                    className="w-full bg-blue-600 text-white font-semibold py-2 px-4 rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    {promptLoading ? 'Generating...' : 'Generate Prompt'}
                  </button>
                ) : (
                  <>
                    <div className="bg-white p-3 rounded-lg border border-blue-200 max-h-48 overflow-y-auto text-xs text-gray-700 whitespace-pre-wrap">
                      {generatedPrompt}
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(generatedPrompt)
                          toast.success('Prompt copied!')
                        }}
                        className="flex-1 bg-gray-200 text-gray-800 font-semibold py-2 px-4 rounded-lg hover:bg-gray-300"
                      >
                        Copy Prompt
                      </button>
                      <button
                        onClick={handleRewrite}
                        disabled={rewriteLoading}
                        className="flex-1 bg-green-600 text-white font-semibold py-2 px-4 rounded-lg hover:bg-green-700 disabled:opacity-50"
                      >
                        {rewriteLoading ? 'Rewriting...' : 'Rewrite Page'}
                      </button>
                    </div>
                  </>
                )}
              </div>

              {/* Rewritten Content */}
              {rewriteContent && (
                <div className="bg-green-50 border border-green-200 rounded-xl p-5 space-y-3">
                  <h3 className="font-bold text-green-900">✅ Rewritten Content</h3>
                  <div className="bg-white p-3 rounded-lg border border-green-200 max-h-96 overflow-y-auto text-sm text-gray-700 whitespace-pre-wrap font-mono text-xs">
                    {rewriteContent}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(rewriteContent)
                        toast.success('Rewritten content copied to clipboard!')
                      }}
                      className="flex-1 bg-green-600 text-white font-semibold py-2 px-4 rounded-lg hover:bg-green-700"
                    >
                      Copy Content
                    </button>
                    <button
                      onClick={async () => {
                        try {
                          const handle = await window.showSaveFilePicker({
                            suggestedName: 'rewritten-content.md',
                            types: [{ description: 'Markdown', accept: { 'text/markdown': ['.md'] } }]
                          }).catch(() => null)

                          if (handle) {
                            const writable = await handle.createWritable()
                            await writable.write(rewriteContent)
                            await writable.close()
                            toast.success('File saved successfully!')
                          }
                        } catch (e) {
                          console.error('Save failed:', e)
                          // Fallback to standard download
                          const blob = new Blob([rewriteContent], { type: 'text/markdown' })
                          const url = URL.createObjectURL(blob)
                          const a = document.createElement('a')
                          a.href = url
                          a.download = 'rewritten-content.md'
                          a.click()
                          URL.revokeObjectURL(url)
                        }
                      }}
                      className="flex-1 bg-blue-600 text-white font-semibold py-2 px-4 rounded-lg hover:bg-blue-700"
                    >
                      Download File
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

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

      {/* GA3: FAQ Schema Generator — always available when domain is set */}
      {domain && <FAQSchemaCard domain={domain} />}

      {/* GA4: Entity Schema Factory — always available when domain is set */}
      {domain && <EntitySchemaCard domain={domain} />}
    </div>
  )
}

import { getIssueHelp } from '../data/issueHelp.js'

// Phase 2 (2026-09-02, docs/pending/2026-09-02_phase2-education-layer.md#E2.4):
// the seven-part explainer, in the order the reader meets it — mission impact,
// what it is, why it matters, good vs bad, HOW THIS CAN MISLEAD (the trust-
// builder, with the evidence tier as a badge), how to fix.
const TIER_STYLE = {
  'Established': 'bg-green-100 text-green-800 border-green-200',
  'Measured': 'bg-green-100 text-green-800 border-green-200',
  'Reasonable proxy': 'bg-amber-100 text-amber-800 border-amber-200',
  'Heuristic': 'bg-gray-100 text-gray-700 border-gray-200',
}

export default function IssueHelpPanel({ issueCode }) {
  const help = getIssueHelp(issueCode)
  if (!help) return null
  const gb = help.good_vs_bad && typeof help.good_vs_bad === 'object' ? help.good_vs_bad : null
  const caveat = (help.how_it_can_mislead || '').replace(/^Evidence tier: [^.]+\.\s*/, '')

  return (
    <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 space-y-3 text-sm" data-testid="issue-help">
      <div className="flex items-start justify-between gap-3">
        <p className="font-semibold text-blue-900">{help.title}</p>
        {help.confidence && (
          <span
            data-testid="help-confidence"
            title="Evidence tier — how sure this check can be. Established: a published source confirms the effect. Measured: observed during the crawl. Reasonable proxy: industry consensus. Heuristic: TalkingToad's own judgement."
            className={`shrink-0 rounded border px-2 py-0.5 text-xs font-medium ${TIER_STYLE[help.confidence] || TIER_STYLE.Heuristic}`}
          >
            {help.confidence}
          </span>
        )}
      </div>

      {/* Mission impact — shown first so non-technical staff see it immediately */}
      {help.mission_impact && (
        <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
          <span className="text-amber-600 font-bold text-base leading-none mt-0.5">!</span>
          <p className="text-amber-800 font-medium leading-snug">{help.mission_impact}</p>
        </div>
      )}

      <div>
        <p className="text-xs font-semibold text-blue-700 uppercase tracking-wide mb-1">What it is</p>
        <p className="text-gray-700 leading-relaxed">{help.definition}</p>
      </div>

      <div>
        <p className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-1">Why it matters</p>
        <p className="text-gray-700 leading-relaxed">{help.impact}</p>
      </div>

      {gb && (
        <div data-testid="help-good-vs-bad">
          <p className="text-xs font-semibold text-blue-700 uppercase tracking-wide mb-1">Good vs bad</p>
          <p className="text-gray-700 leading-relaxed"><span className="font-semibold text-green-700">Good:</span> {gb.good}</p>
          <p className="text-gray-700 leading-relaxed"><span className="font-semibold text-red-700">Bad:</span> {gb.bad}</p>
        </div>
      )}

      {help.how_it_can_mislead && (
        <div data-testid="help-mislead" className="bg-white border border-blue-100 rounded-md px-3 py-2">
          <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1">How this can mislead</p>
          <p className="text-gray-700 leading-relaxed">{caveat}</p>
        </div>
      )}

      <div>
        <p className="text-xs font-semibold text-green-700 uppercase tracking-wide mb-1">How to fix</p>
        <p className="text-gray-700 leading-relaxed">{help.fix}</p>
      </div>
    </div>
  )
}

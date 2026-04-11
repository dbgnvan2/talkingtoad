import { getIssueHelp } from '../data/issueHelp.js'

/**
 * Expandable help panel for a single issue code.
 * Shows definition, impact, and fix steps from issueHelp.js.
 */
export default function IssueHelpPanel({ issueCode }) {
  const help = getIssueHelp(issueCode)
  if (!help) return null

  return (
    <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 space-y-3 text-sm">
      <p className="font-semibold text-blue-900">{help.title}</p>

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
        <p className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-1">Impact</p>
        <p className="text-gray-700 leading-relaxed">{help.impact}</p>
      </div>

      <div>
        <p className="text-xs font-semibold text-green-700 uppercase tracking-wide mb-1">How to fix</p>
        <p className="text-gray-700 leading-relaxed">{help.fix}</p>
      </div>
    </div>
  )
}

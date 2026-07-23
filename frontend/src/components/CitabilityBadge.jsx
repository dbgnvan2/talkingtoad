import { memo } from 'react'

// Per-page GEO/AI-citability grade (0–100). Higher = more extractable/citable by
// AI answer engines. Colour ramp follows the app's existing 70/40 threshold idiom
// (see GEOReportPanel): green ≥ 70, amber ≥ 40, red below.
function gradeStyle(grade) {
  if (grade >= 70) return 'bg-green-100 text-green-700 border border-green-200'
  if (grade >= 40) return 'bg-amber-100 text-amber-700 border border-amber-200'
  return 'bg-red-100 text-red-700 border border-red-200'
}

function CitabilityBadge({ grade }) {
  if (grade === null || grade === undefined) {
    return <span className="text-gray-400">—</span>
  }
  return (
    <span
      className={`inline-block rounded px-2 py-0.5 text-xs font-mono font-medium ${gradeStyle(grade)}`}
      title="AI-citability grade (0–100): how extractable and citable this page is to AI answer engines"
    >
      {grade}
    </span>
  )
}

export default memo(CitabilityBadge)

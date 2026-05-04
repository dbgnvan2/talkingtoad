import { memo } from 'react'

/**
 * Determinate when pct is a number 0–100, indeterminate otherwise.
 */
function ProgressBar({ pct }) {
  if (pct == null) {
    return (
      <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
        <div className="h-full bg-green-500 rounded-full animate-pulse w-1/3" />
      </div>
    )
  }
  const clamped = Math.max(0, Math.min(100, pct))
  return (
    <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
      <div
        className="h-full bg-green-500 rounded-full transition-all duration-500"
        style={{ width: `${clamped}%` }}
      />
    </div>
  )
}

export default memo(ProgressBar)

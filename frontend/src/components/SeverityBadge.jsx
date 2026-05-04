import { memo } from 'react'

const STYLES = {
  critical: 'bg-red-100 text-red-700 border border-red-200',
  warning:  'bg-amber-100 text-amber-700 border border-amber-200',
  info:     'bg-blue-100 text-blue-700 border border-blue-200',
}

function SeverityBadge({ severity }) {
  const cls = STYLES[severity] || 'bg-gray-100 text-gray-600 border border-gray-200'
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${cls}`}>
      {severity}
    </span>
  )
}

export default memo(SeverityBadge)

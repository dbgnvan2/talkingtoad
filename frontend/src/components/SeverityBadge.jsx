import { memo } from 'react'

const STYLES = {
  critical: 'bg-red-100 text-red-700 border border-red-200',
  warning:  'bg-amber-100 text-amber-700 border border-amber-200',
  info:     'bg-blue-100 text-blue-700 border border-blue-200',
}

// Info detail (2026-09-01 spec §7.4): an info badge carries its tier
// ("info · Key"); a row the scan excluded from the score (`scored === false`,
// only ever seen after "Show excluded info") is dimmed and says so.
const TIER_LABELS = { high: 'Key', medium: 'Notable', low: 'Low' }

function SeverityBadge({ severity, infoTier = null, scored = true }) {
  const cls = STYLES[severity] || 'bg-gray-100 text-gray-600 border border-gray-200'
  const tier = severity === 'info' && infoTier ? TIER_LABELS[infoTier] : null
  return (
    <span
      className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${cls} ${scored ? '' : 'opacity-50'}`}
      title={scored ? undefined : 'Not counted in the health score — excluded by this scan\'s info detail setting'}
      data-scored={scored ? undefined : 'false'}
    >
      {severity}{tier ? ` · ${tier}` : ''}
    </span>
  )
}

export default memo(SeverityBadge)

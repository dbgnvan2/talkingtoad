// Info detail (2026-09-01 spec §7) — what the scan's level left out of this
// list AND the health score, with a reveal-only toggle.
//
// Distinct from the domain-filter disclosure on purpose: that one says "hidden
// but still scored"; this one says "not part of this audit's score". Revealed
// rows arrive with `scored: false` and render dimmed — the score never moves.
import { INFO_DETAIL_LABELS, INFO_TIER_LABELS } from '../data/infoDetail.js'

export default function InfoDetailDisclosure({ infoFiltered, revealed, onToggle }) {
  const hidden = infoFiltered?.hidden || 0
  const level = infoFiltered?.info_detail
  if (!hidden && !revealed) return null
  const tiers = Object.entries(infoFiltered?.by_tier || {})
    .map(([t, n]) => `${INFO_TIER_LABELS[t] || t} ${n}`).join(' · ')
  return (
    <div data-testid="info-detail-disclosure" className="mb-4 rounded-2xl border border-blue-200 bg-blue-50 px-5 py-4">
      {revealed ? (
        <p className="text-sm font-bold text-blue-900">
          Showing every info notice, including the ones this scan excluded. Dimmed rows are not counted in the health score.
        </p>
      ) : (
        <>
          <p className="text-sm font-bold text-blue-900">
            {hidden} info notice{hidden === 1 ? '' : 's'} excluded by this scan&apos;s info detail setting
            {level ? ` (${INFO_DETAIL_LABELS[level] || level})` : ''}
          </p>
          <p className="text-xs text-blue-800 mt-1">
            Still recorded, but not shown here and not counted in the health score.{tiers ? ` ${tiers}.` : ''}
          </p>
        </>
      )}
      <button
        type="button"
        data-testid="info-detail-toggle"
        onClick={onToggle}
        className="mt-3 text-xs font-bold px-3 py-1.5 rounded-full bg-white border border-blue-300 text-blue-900 hover:bg-blue-100"
      >
        {revealed ? 'Back to scan setting' : 'Show excluded info'}
      </button>
    </div>
  )
}

// Info detail (2026-09-01 spec) — labels for the scan setting and the info
// tiers. Values mirror api/crawler/checkers/registry.py INFO_DETAIL_MIN_IMPACT
// / INFO_TIER_LABELS; the API speaks the keys, the UI speaks the labels.
export const INFO_DETAIL_OPTIONS = [
  { value: 'all', label: 'All info (default)', hint: 'Every info notice is shown and counted.' },
  { value: 'notable', label: 'Notable and key only', hint: 'Leaves out the low-value notices.' },
  { value: 'key', label: 'Key only', hint: 'Only the nine highest-value info notices.' },
  { value: 'none', label: 'Hide info', hint: 'Critical and warning findings define the audit.' },
]
export const INFO_DETAIL_LABELS = Object.fromEntries(INFO_DETAIL_OPTIONS.map(o => [o.value, o.label.replace(' (default)', '')]))
export const INFO_TIER_LABELS = { high: 'Key', medium: 'Notable', low: 'Low' }

import PANEL_HELP from '../data/panelHelp.json'

/**
 * PanelExplainer — the V4 five-part explainer for a non-issue tool.
 *
 * The app explains what META_DESC_TOO_LONG means in seven parts, 170 times over,
 * and said nothing about the four tools that change a nonprofit's site
 * (P7.1). The five labels used to be spelled out inline in GEOReportPanel
 * (twice) and GSCInsightsPanel — three copies in two forms, about to become
 * seven. They are here once; the copy is in panelHelp.json once.
 *
 * The component takes the COPY, not the affordance: how a panel reveals help is
 * a per-panel judgement (a connect-first screen shows it immediately, a modal
 * that opens onto a result should not bury it), what it says is not.
 *
 * Completeness, substance and id validity are pinned by
 * tests/test_panel_help_completeness.py.
 */
export default function PanelExplainer({ id, className = '' }) {
  const entry = PANEL_HELP[id]
  // A missing id renders nothing rather than crashing a working panel; the
  // pytest guard is what stops a typo shipping silently.
  if (!entry) return null

  return (
    <div
      data-testid={`panel-explainer-${id}`}
      className={`bg-white border border-gray-200 rounded-xl p-4 text-xs text-gray-700 space-y-2 ${className}`}
    >
      <p><strong>What it is:</strong> {entry.what}</p>
      <p><strong>Why it&apos;s useful:</strong> {entry.why}</p>
      <p><strong>Good vs bad:</strong> {entry.goodVsBad}</p>
      <p><strong>How it can mislead:</strong> {entry.misleading}</p>
      <p><strong>How to use:</strong> {entry.howToUse}</p>
    </div>
  )
}

export { PANEL_HELP }

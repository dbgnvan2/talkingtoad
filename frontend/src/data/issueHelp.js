/**
 * issueHelp.js — thin loader over issueHelp.json (the single AUTHORED source).
 *
 * Phase 2 of the 2026-09-02 plan (docs/pending/2026-09-02_phase2-education-layer.md):
 * the help text used to exist three times — here as JS, in
 * api/services/issue_help_data.py for the PDF, and in the registry — and the
 * PDF printed an older, narrower copy of what the screen showed. Now:
 *   - issueHelp.json is authored (see docs/explanation-style-guide.md);
 *   - api/services/issue_help_data.py is GENERATED from it by
 *     scripts/generate_issue_help_py.py, with a sync test;
 *   - this module keeps its exports so no importer changed.
 *
 * Each entry: title, mission_impact, definition, impact,
 * good_vs_bad {good, bad}, how_it_can_mislead, fix, confidence,
 * plus category / severity mirrored from the registry (parity-tested).
 * Keyed by issue_code, matching api/crawler/checkers/registry.py _CATALOGUE.
 */
import issueHelpData from './issueHelp.json'

const issueHelp = issueHelpData

export default issueHelp

/**
 * Helper: get help content for a given issue code.
 * Returns null if no help entry exists for the code.
 */
export function getIssueHelp(issueCode) {
  return issueHelp[issueCode] ?? null
}

/**
 * Helper: get all issue codes for a given category.
 */
export function getCodesByCategory(category) {
  return Object.entries(issueHelp)
    .filter(([, v]) => v.category === category)
    .map(([k]) => k)
}

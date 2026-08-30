/**
 * C2 — a category that never ran must render "not checked", not a clean 0.
 *
 * Two full crawls of one site read 1 warning and 118 because the first ran a
 * single analysis group. Nothing on any surface said so, and a 0 tile is
 * indistinguishable from a clean category (P31).
 *
 * Spec: docs/pending/2026-08-30_analysis-coverage-disclosure.md#C2
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen } from '@testing-library/react'
import SummaryPanel from '../SummaryPanel.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

const base = {
  target_url: 'https://example.com', pages_crawled: 10, pages_with_errors: 0,
  total_issues: 3, health_score: 90, agent_health_score: 90,
  by_severity: { critical: 0, warning: 1, info: 2 },
  by_category: { broken_link: 3, metadata: 0, heading: 0 },
}

const props = {
  domain: 'example.com', jobId: 'j', onCategoryClick: vi.fn(),
  onSeverityClick: vi.fn(), onPageClick: vi.fn(), onShowPdfModal: vi.fn(),
}

describe('SummaryPanel analysis coverage', () => {
  beforeEach(() => {
    // SummaryPanel fetches on mount; give every call a resolved response so
    // the assertions are about the coverage rendering, not the network.
    global.fetch.mockReset()
    global.fetch.mockImplementation(() => mockFetchResponse({}))
  })

  it('shows the partial-scan banner naming what did not run', () => {
    renderWithProviders(<SummaryPanel {...props} summary={{
      ...base,
      analysis_coverage: {
        mode: 'partial', groups_enabled: ['link_integrity'],
        groups_disabled: ['seo_essentials'],
        categories_checked: ['broken_link', 'security'],
        categories_unchecked: ['metadata', 'heading'],
      },
    }} />)
    expect(screen.getByText(/This was a partial scan/i)).toBeTruthy()
    expect(screen.getByText(/were not checked and report nothing/i)).toBeTruthy()
  })

  it('renders "not checked" on the TILE, not just in the banner', () => {
    // The first version of this test used getAllByText(/not checked/i), which
    // the BANNER also satisfies ("were not checked and report nothing"). It
    // passed with the tile logic stubbed to false — a test that could not fail
    // against the defect it named (P27). Assert the tile's own marker instead:
    // the em-dash placeholder that replaces the misleading "0".
    const { container } = renderWithProviders(<SummaryPanel {...props} summary={{
      ...base,
      analysis_coverage: {
        mode: 'partial', categories_checked: ['broken_link'],
        categories_unchecked: ['metadata', 'heading'],
      },
    }} />)
    const grid = container.querySelectorAll('.grid .relative')
    const dashes = Array.from(grid).filter(el => el.textContent.includes('\u2014'))
    expect(dashes.length).toBeGreaterThan(0)
    // and the unchecked tiles must NOT show a clean zero
    dashes.forEach(el => expect(el.textContent).not.toMatch(/^0/))
  })

  it('does NOT mark anything not-checked on a full scan', () => {
    renderWithProviders(<SummaryPanel {...props} summary={{
      ...base,
      analysis_coverage: { mode: 'all', categories_checked: [], categories_unchecked: [] },
    }} />)
    expect(screen.queryByText(/not checked/i)).toBeNull()
    expect(screen.queryByText(/This was a partial scan/i)).toBeNull()
  })

  it('treats a legacy audit with no coverage record as a full scan', () => {
    renderWithProviders(<SummaryPanel {...props} summary={base} />)
    expect(screen.queryByText(/not checked/i)).toBeNull()
  })
})

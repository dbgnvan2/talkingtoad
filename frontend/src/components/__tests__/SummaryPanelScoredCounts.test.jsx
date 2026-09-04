/**
 * P5.2 — a category tile is a BUTTON, so its number is a promise about the list
 * it opens, and that list is filtered by the scan's info_detail.
 *
 * Measured before the fix, at info_detail="key": the `metadata` tile read 2 and
 * opened an empty list. The tile rendered `summary.by_category` (every stored
 * row); `/results/{category}` returns only what the level keeps.
 *
 * The count and its caveat ship together. Showing the scored number ALONE is its
 * own P31: at info_detail="none" every tile reads 0, and 0 is what a clean site
 * looks like — which is the mistake this change exists to stop making.
 *
 * Spec: docs/pending/2026-09-04_p5-2-scored-counts-beside-scored-scores.md
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import SummaryPanel from '../SummaryPanel.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

// The shape /api/crawl/{id}/summary returns at info_detail="key" for a site whose
// metadata findings are all below the level's floor.
const scoped = {
  target_url: 'https://example.com', pages_crawled: 10, pages_with_errors: 0,
  total_issues: 5, health_score: 93, agent_health_score: 93,
  by_severity: { critical: 0, warning: 1, info: 4 },
  info_detail: 'key', info_scored: 1, info_excluded: 3,
  info_by_tier: { high: 1, medium: 1, low: 2 },
  by_category:          { metadata: 2, heading: 1, image: 1 },
  by_category_scored:   { metadata: 0, heading: 1, image: 1 },
  by_category_excluded: { metadata: 2, heading: 0, image: 0 },
}

const props = {
  domain: 'example.com', jobId: 'j', onCategoryClick: vi.fn(),
  onSeverityClick: vi.fn(), onPageClick: vi.fn(), onShowPdfModal: vi.fn(),
}

function tile(label) {
  return screen.getByText(label, { selector: 'p' }).closest('div')
}

describe('SummaryPanel category tiles', () => {
  beforeEach(() => {
    global.fetch.mockReset()
    global.fetch.mockImplementation(() => mockFetchResponse({}))
  })

  it('shows the SCORED count, not the stored one', () => {
    renderWithProviders(<SummaryPanel {...props} summary={scoped} />)
    // 2 rows were found under metadata; 0 survive the level, and 0 is what the
    // list behind this tile will contain.
    expect(within(tile('Metadata')).getByText('0')).toBeInTheDocument()
    expect(within(tile('Metadata')).queryByText('2')).not.toBeInTheDocument()
  })

  it('says how many rows the level took off that tile', () => {
    renderWithProviders(<SummaryPanel {...props} summary={scoped} />)
    expect(within(tile('Metadata')).getByText(/2 not scored/)).toBeInTheDocument()
  })

  it('does not put a hint on a tile that lost nothing', () => {
    renderWithProviders(<SummaryPanel {...props} summary={scoped} />)
    expect(within(tile('Headings')).queryByText(/not scored/)).not.toBeInTheDocument()
    expect(within(tile('Headings')).getByText('1')).toBeInTheDocument()
  })

  it('renders a legacy summary with no scored map unchanged', () => {
    // Audits stored before P5.2 carry only `by_category`. Falling back to it is
    // right; falling back to 0 would report every old audit as clean.
    const legacy = { ...scoped }
    delete legacy.by_category_scored
    delete legacy.by_category_excluded
    renderWithProviders(<SummaryPanel {...props} summary={legacy} />)
    expect(within(tile('Metadata')).getByText('2')).toBeInTheDocument()
    expect(within(tile('Metadata')).queryByText(/not scored/)).not.toBeInTheDocument()
  })
})

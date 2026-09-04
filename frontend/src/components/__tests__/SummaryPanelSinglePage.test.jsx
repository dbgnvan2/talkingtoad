/**
 * P6.1 — a single-page scan's Results page must say what it could not check.
 *
 * `/scan-page` creates a real job and sends the caller to /results/{job_id}, so
 * a one-page audit renders on the same panel as a full crawl. Measured before
 * the fix: health_score 100, total_issues 0, and nothing on the page saying that
 * 24 catalogue checks (`needs_full_crawl`) could not run at all.
 *
 * The count goes in the sentence and the names go behind a disclosure — 24 code
 * names above a one-page report is the wall of text that makes the NEXT caveat
 * easier to skip.
 *
 * Spec: docs/pending/2026-09-04_p6-1-a-single-page-scan-scores-100.md §2.4
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SummaryPanel from '../SummaryPanel.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

const CHECKS = [
  'AI_TXT_MISSING', 'ANALYTICS_ID_INCONSISTENT', 'AUTHOR_IDENTITY_INCONSISTENT',
  'META_DESC_DUPLICATE', 'NEAR_DUPLICATE_BODY', 'NOT_IN_SITEMAP', 'ORPHAN_PAGE',
  'TITLE_DUPLICATE', 'WWW_CANONICALIZATION',
]

const base = {
  target_url: 'https://example.com/about', pages_crawled: 1, pages_with_errors: 0,
  total_issues: 0, health_score: 100, agent_health_score: 100,
  by_severity: { critical: 0, warning: 0, info: 0 },
  by_category: {}, by_category_scored: {}, by_category_excluded: {},
}

const singlePage = {
  ...base,
  checks_not_run: CHECKS,
  checks_not_run_reason:
    'These checks compare a page against the rest of the site, so a single-page scan cannot evaluate them.',
  health_score_basis: {
    mode: 'all', categories_scored: [], categories_unscored: [], comparable: true,
    page_scope: 'single_page', pages_scored: 1,
  },
}

const props = {
  domain: 'example.com', jobId: 'j', onCategoryClick: vi.fn(),
  onSeverityClick: vi.fn(), onPageClick: vi.fn(), onShowPdfModal: vi.fn(),
}

describe('SummaryPanel single-page scope', () => {
  beforeEach(() => {
    global.fetch.mockReset()
    global.fetch.mockImplementation(() => mockFetchResponse({}))
  })

  it('states the count without listing every code', () => {
    renderWithProviders(<SummaryPanel {...props} summary={singlePage} />)
    // Exact heading: /single-page scan/i also matches the reason sentence.
    expect(screen.getByText('This was a single-page scan.')).toBeInTheDocument()
    expect(screen.getByText(/9 checks could not run/i)).toBeInTheDocument()
    // Names are behind the disclosure, not in the reader's face. `toBeVisible`,
    // not `toBeInTheDocument`: a collapsed <details> keeps its content in the
    // DOM, so the presence assertion passed against a banner that showed all 24
    // names inline. Visibility is the thing actually claimed.
    expect(screen.getByText(/WWW_CANONICALIZATION/)).not.toBeVisible()
  })

  it('names them on demand', async () => {
    renderWithProviders(<SummaryPanel {...props} summary={singlePage} />)
    await userEvent.click(screen.getByText(/which checks/i))
    expect(screen.getByText(/WWW_CANONICALIZATION/)).toBeInTheDocument()
    expect(screen.getByText(/ORPHAN_PAGE/)).toBeInTheDocument()
  })

  it('says nothing on a full crawl', () => {
    // The other direction. A banner that always rendered would pass both tests
    // above and would put a false caveat on every full audit.
    renderWithProviders(<SummaryPanel {...props} summary={{
      ...base,
      health_score_basis: {
        mode: 'all', categories_scored: [], categories_unscored: [],
        comparable: true, page_scope: 'site', pages_scored: 42,
      },
    }} />)
    expect(screen.queryByText('This was a single-page scan.')).not.toBeInTheDocument()
    expect(screen.queryByText(/checks could not run/i)).not.toBeInTheDocument()
  })

  it('renders a legacy summary with no checks_not_run unchanged', () => {
    renderWithProviders(<SummaryPanel {...props} summary={base} />)
    expect(screen.queryByText(/checks could not run/i)).not.toBeInTheDocument()
  })
})

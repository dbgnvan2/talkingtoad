/**
 * P5.3 — By Page must not render a page whose findings the level excluded as
 * identical to a page with no findings.
 *
 * `issue_counts.info_excluded` has travelled on every /pages row since
 * 2026-09-01 and no component read it (P25). The panel renders a badge per
 * severity `> 0`, so a row of {critical: 0, warning: 0, info: 0, info_excluded: 2}
 * produced NO badges — pixel-identical to a genuinely clean page, while that
 * page's own drawer reports `info_filtered: {hidden: 2}`.
 *
 * Spec: docs/pending/2026-09-04_p5-3-the-filter-agrees-and-says-nothing.md
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, within, waitFor } from '@testing-library/react'
import ByPagePanel from '../ByPagePanel.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

const counts = (o = {}) => ({
  total: 0, critical: 0, warning: 0, info: 0, info_excluded: 0, ...o,
})

// The /pages response at info_detail="key": one page with a real warning, one
// whose only findings were excluded, one genuinely clean.
const response = {
  job_id: 'j',
  pagination: { page: 1, limit: 200, total_pages_crawled: 3, total_pages: 1 },
  pages: [
    { url: 'https://e.com/warn', citability_grade: 'B',
      issue_counts: counts({ total: 1, warning: 1 }) },
    { url: 'https://e.com/lowinfo', citability_grade: 'A',
      issue_counts: counts({ info_excluded: 2 }) },
    { url: 'https://e.com/clean', citability_grade: 'A', issue_counts: counts() },
  ],
  info_filtered: { hidden: 2, by_tier: { low: 2 }, info_detail: 'key', pages_hidden: 0 },
}

const row = (url) => screen.getByText(url).closest('tr')

describe('ByPagePanel', () => {
  beforeEach(() => {
    global.fetch.mockReset()
    global.fetch.mockImplementation(() => mockFetchResponse(response))
  })

  it('does not render an all-excluded page identically to a clean one', async () => {
    renderWithProviders(<ByPagePanel jobId="j" domain="e.com" onPageClick={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('https://e.com/clean')).toBeInTheDocument())

    const excluded = within(row('https://e.com/lowinfo')).getByTestId('not-scored')
    expect(excluded).toHaveTextContent('2')
    // The comparison IS the assertion: the two rows must differ.
    expect(within(row('https://e.com/clean')).queryByTestId('not-scored')).toBeNull()
  })

  it('leaves a page with real findings unchanged', async () => {
    renderWithProviders(<ByPagePanel jobId="j" domain="e.com" onPageClick={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('https://e.com/warn')).toBeInTheDocument())
    const warn = row('https://e.com/warn')
    expect(within(warn).getByText('1')).toBeInTheDocument()
    expect(within(warn).queryByTestId('not-scored')).toBeNull()
  })

  it('states the level when it removed anything', async () => {
    renderWithProviders(<ByPagePanel jobId="j" domain="e.com" onPageClick={vi.fn()} />)
    await waitFor(() => expect(screen.getByText(/not scored at info detail/i)).toBeInTheDocument())
    expect(screen.getByText(/2 info notice/i)).toBeInTheDocument()
  })

  it('says nothing when the level removed nothing', async () => {
    // The other direction: a caveat on a full-detail scan is noise, and an
    // implementation that always renders it would pass the test above.
    global.fetch.mockImplementation(() => mockFetchResponse({
      ...response,
      pages: [response.pages[0], response.pages[2]],
      info_filtered: { hidden: 0, by_tier: {}, info_detail: 'all', pages_hidden: 0 },
    }))
    renderWithProviders(<ByPagePanel jobId="j" domain="e.com" onPageClick={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('https://e.com/warn')).toBeInTheDocument())
    expect(screen.queryByText(/not scored at info detail/i)).toBeNull()
  })

  it('renders a legacy response with no info_filtered', async () => {
    const legacy = { ...response }
    delete legacy.info_filtered
    global.fetch.mockImplementation(() => mockFetchResponse(legacy))
    renderWithProviders(<ByPagePanel jobId="j" domain="e.com" onPageClick={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('https://e.com/warn')).toBeInTheDocument())
    expect(screen.queryByText(/not scored at info detail/i)).toBeNull()
  })
})

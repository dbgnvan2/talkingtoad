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

// Pre-existing coverage (f95dec1, E5/P8), restored after the P5.3 work
// overwrote this file. Flagged by the independent QA gate, not by me — a
// `Write` to a path that already existed, with no read first.
describe('ByPagePanel citability column', () => {
  beforeEach(() => global.fetch.mockReset())

  it('renders a Citability column with the per-page grade (E5)', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse({
      pages: [
        { url: 'https://x/a', status_code: 200, citability_grade: 72,
          issue_counts: counts({ total: 1, warning: 1 }) },
        { url: 'https://x/b', status_code: 200, citability_grade: 30,
          issue_counts: counts() },
      ],
    }))
    renderWithProviders(<ByPagePanel jobId="job1" domain="x" onPageClick={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('https://x/a')).toBeInTheDocument())
    expect(screen.getByText('Citability')).toBeInTheDocument()
    expect(screen.getByText('72')).toBeInTheDocument()
    expect(screen.getByText('30')).toBeInTheDocument()
  })

  it('shows a dash when citability_grade is absent (old crawls, P8)', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse({
      pages: [{ url: 'https://x/a', status_code: 200, issue_counts: counts() }],
    }))
    renderWithProviders(<ByPagePanel jobId="job1" domain="x" onPageClick={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('https://x/a')).toBeInTheDocument())
    expect(screen.getByText('—')).toBeInTheDocument()
  })
})

describe('ByPagePanel', () => {
  beforeEach(() => {
    global.fetch.mockReset()
    global.fetch.mockImplementation(() => mockFetchResponse(response))
  })

  it('does not render an all-excluded page identically to a clean one', async () => {
    renderWithProviders(<ByPagePanel jobId="j" domain="e.com" onPageClick={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('https://e.com/clean')).toBeInTheDocument())

    const excluded = within(row('https://e.com/lowinfo')).getByTestId('not-scored')
    // The wording matters, not just the number: the P5.2 tiles say "+N not
    // scored" and a bare "+2" beside three coloured severity badges reads as a
    // fourth severity. The gate flagged the deviation from spec §3.4.
    expect(excluded).toHaveTextContent('+2 not scored')
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

  it('names the pages a filtered list left out, when there are any', async () => {
    // The `pages_hidden > 0` clause of the sentence had no test: the fixture
    // above always has pages_hidden 0, so the clause could be deleted and every
    // assertion still passed.
    global.fetch.mockImplementation(() => mockFetchResponse({
      ...response,
      info_filtered: { hidden: 2, by_tier: { low: 2 }, info_detail: 'key', pages_hidden: 3 },
    }))
    renderWithProviders(<ByPagePanel jobId="j" domain="e.com" onPageClick={vi.fn()} />)
    await waitFor(() => expect(screen.getByText(/3 pages left out/i)).toBeInTheDocument())
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

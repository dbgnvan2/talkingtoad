/**
 * P5.3 §3.4 — "Top 10 Pages to Fix" filters `critical + warning + info > 0`, so a
 * page whose only findings the level excluded is dropped from the list with
 * nothing saying so.
 *
 * The spec's first draft drove this off `info_filtered.pages_hidden`, which the
 * independent QA gate showed can never fire here: Top10Pages fetches /pages with
 * no `min_severity`, and §3.1 fixes `pages_hidden` at 0 in exactly that case.
 * The signal that IS non-zero is `hidden` — the job-wide count of excluded rows.
 * Spec §3.4 amended to match at the fold.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import Top10Pages from '../Top10Pages.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

const counts = (o = {}) => ({ total: 0, critical: 0, warning: 0, info: 0, info_excluded: 0, ...o })

// The table renders each URL's PATHNAME, not the full URL.
const body = (info_filtered) => ({
  pages: [
    { url: 'https://e.com/warn', issue_counts: counts({ total: 1, warning: 1 }) },
    // Only findings were excluded: dropped by the `total > 0` filter below.
    { url: 'https://e.com/lowinfo', issue_counts: counts({ info_excluded: 2 }) },
  ],
  info_filtered,
})

describe('Top10Pages', () => {
  beforeEach(() => {
    global.fetch.mockReset()
  })

  it('says pages were left out when the level excluded findings', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse(
      body({ hidden: 2, by_tier: { low: 2 }, info_detail: 'key', pages_hidden: 0 })
    ))
    renderWithProviders(<Top10Pages jobId="j" onPageClick={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('/warn')).toBeInTheDocument())
    // Non-zero `hidden` with `pages_hidden` 0 — the exact shape the first draft
    // could not detect.
    expect(screen.getByText(/not scored at info detail/i)).toBeInTheDocument()
    expect(screen.getByText(/key/)).toBeInTheDocument()
  })

  it('says nothing when the level excluded nothing', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse(
      body({ hidden: 0, by_tier: {}, info_detail: 'all', pages_hidden: 0 })
    ))
    renderWithProviders(<Top10Pages jobId="j" onPageClick={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('/warn')).toBeInTheDocument())
    expect(screen.queryByText(/not scored at info detail/i)).toBeNull()
  })

  it('still ranks by the scored count', async () => {
    // The disclosure is the fix, not a change of ranking: a page with nothing
    // chargeable is not a top-issue page and stays out of the table.
    global.fetch.mockImplementation(() => mockFetchResponse(
      body({ hidden: 2, by_tier: { low: 2 }, info_detail: 'key', pages_hidden: 0 })
    ))
    renderWithProviders(<Top10Pages jobId="j" onPageClick={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('/warn')).toBeInTheDocument())
    expect(screen.queryByText('/lowinfo')).toBeNull()
  })

  it('renders a legacy response with no info_filtered', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse(body(undefined)))
    renderWithProviders(<Top10Pages jobId="j" onPageClick={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('/warn')).toBeInTheDocument())
    expect(screen.queryByText(/not scored at info detail/i)).toBeNull()
  })
})

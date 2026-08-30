/**
 * O2 — the orphan panel must distinguish "none found" from "not checked".
 *
 * ORPHAN_PAGE is suppressed when the crawl did not cover the whole site, and a
 * suppressed check returns zero issues. Without these tests the panel renders
 * the green "All crawled pages have at least one internal link" for a scan that
 * never looked — a fabricated all-clear (P31 corollary).
 *
 * Spec: docs/functional-specification.md §4.4 (ORPHAN_PAGE)
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import OrphanedPagesPanel from '../OrphanedPagesPanel.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

const props = { jobId: 'test-job', domain: 'example.com' }

function mockResults({ issues = [], orphan_detection = null }) {
  global.fetch.mockImplementation(() =>
    mockFetchResponse({ issues, summary: { orphan_detection } })
  )
}

describe('OrphanedPagesPanel', () => {
  beforeEach(() => {
    global.fetch.mockReset()
  })

  it('renders the all-clear only when detection actually ran', async () => {
    mockResults({
      issues: [],
      orphan_detection: { status: 'complete', pages_analysed: 272, pages_out_of_scope: 0 },
    })
    renderWithProviders(<OrphanedPagesPanel {...props} />)
    await waitFor(() => {
      expect(screen.getByText(/All crawled pages have at least one internal link/i)).toBeTruthy()
    })
  })

  it('does NOT claim all-clear when detection was skipped by a partial scan', async () => {
    mockResults({
      issues: [],
      orphan_detection: {
        status: 'skipped_partial_scan', pages_analysed: 37, pages_out_of_scope: 235,
      },
    })
    renderWithProviders(<OrphanedPagesPanel {...props} />)
    await waitFor(() => {
      expect(screen.getByText(/Orphan detection was not run/i)).toBeTruthy()
    })
    expect(screen.queryByText(/All crawled pages have at least one internal link/i)).toBeNull()
    expect(screen.getByText(/37 pages were analysed and 235 were not fetched/i)).toBeTruthy()
  })

  it('explains a truncated crawl too', async () => {
    mockResults({
      issues: [],
      orphan_detection: { status: 'skipped_truncated', pages_analysed: 500, pages_out_of_scope: 0 },
    })
    renderWithProviders(<OrphanedPagesPanel {...props} />)
    await waitFor(() => {
      expect(screen.getByText(/stopped at its page limit/i)).toBeTruthy()
    })
    expect(screen.queryByText(/All crawled pages have at least one internal link/i)).toBeNull()
  })

  it('still lists real orphans on a complete crawl', async () => {
    mockResults({
      issues: [
        { issue_code: 'ORPHAN_PAGE', page_url: 'https://example.com/hidden', extra: { title: 'Hidden' } },
      ],
      orphan_detection: { status: 'complete', pages_analysed: 272, pages_out_of_scope: 0 },
    })
    renderWithProviders(<OrphanedPagesPanel {...props} />)
    await waitFor(() => {
      expect(screen.getByText('https://example.com/hidden')).toBeTruthy()
    })
  })

  it('does NOT claim all-clear when the request failed', async () => {
    // A failed fetch tells us nothing about orphans. Before this guard the
    // catch handler returned a bare {count: 0} and the panel printed the green
    // all-clear for a request that never landed.
    global.fetch.mockImplementation(() => Promise.reject(new Error('network down')))
    renderWithProviders(<OrphanedPagesPanel {...props} />)
    await waitFor(() => {
      expect(screen.getByText(/Orphan detection was not run/i)).toBeTruthy()
    })
    expect(screen.queryByText(/All crawled pages have at least one internal link/i)).toBeNull()
  })

  it('does NOT claim all-clear for a single-page scan', async () => {
    mockResults({
      issues: [],
      orphan_detection: {
        status: 'skipped_single_page', pages_analysed: 1, pages_out_of_scope: 0,
      },
    })
    renderWithProviders(<OrphanedPagesPanel {...props} />)
    await waitFor(() => {
      expect(screen.getByText(/single-page scan/i)).toBeTruthy()
    })
    expect(screen.queryByText(/All crawled pages have at least one internal link/i)).toBeNull()
    // Singular agreement — "1 page was", not "1 pages were".
    expect(screen.getByText(/1 page was analysed/i)).toBeTruthy()
  })

  it('explains an UNKNOWN status rather than rendering nothing', async () => {
    // A status this build does not know (server/client skew, or a status added
    // later) must still say the check did not run — silence reads as "nothing
    // to report", which is the same false all-clear by omission.
    mockResults({
      issues: [],
      orphan_detection: {
        status: 'skipped_something_new', pages_analysed: 12, pages_out_of_scope: 3,
      },
    })
    renderWithProviders(<OrphanedPagesPanel {...props} />)
    await waitFor(() => {
      expect(screen.getByText(/Orphan detection was not run/i)).toBeTruthy()
    })
    expect(screen.getByText(/did not cover the whole site/i)).toBeTruthy()
  })

  it('footnotes the all-clear when WordPress archives were skipped', async () => {
    // "complete" is not "saw every anchor" — archives are skipped before their
    // outbound links are read, so an unqualified ✓ over-claims.
    mockResults({
      issues: [],
      orphan_detection: {
        status: 'complete', pages_analysed: 272, pages_out_of_scope: 0, archives_skipped: true,
      },
    })
    renderWithProviders(<OrphanedPagesPanel {...props} />)
    await waitFor(() => {
      expect(screen.getByText(/All crawled pages have at least one internal link/i)).toBeTruthy()
    })
    expect(screen.getByText(/archive pages .* were skipped/i)).toBeTruthy()
    expect(screen.getByText(/may still be listed here/i)).toBeTruthy()
  })

  it('footnotes the all-clear when pages could not be read', async () => {
    // Measured on livingsystems.ca: 5 of 256 pages failed to fetch on a real
    // full crawl. Each is a hole in the link graph — if a hub page times out,
    // everything it links to looks orphaned — so "complete" still needs saying.
    mockResults({
      issues: [],
      orphan_detection: {
        status: 'complete', pages_analysed: 256, pages_out_of_scope: 0,
        archives_skipped: false, pages_links_unread: 5,
      },
    })
    renderWithProviders(<OrphanedPagesPanel {...props} />)
    await waitFor(() => {
      expect(screen.getByText(/All crawled pages have at least one internal link/i)).toBeTruthy()
    })
    expect(screen.getByText(/5 pages could not be read/i)).toBeTruthy()
  })

  it('adds no footnote when coverage really was total', async () => {
    // Adversarial: the footnote must not become unconditional decoration.
    mockResults({
      issues: [],
      orphan_detection: {
        status: 'complete', pages_analysed: 42, pages_out_of_scope: 0,
        archives_skipped: false, pages_links_unread: 0,
      },
    })
    renderWithProviders(<OrphanedPagesPanel {...props} />)
    await waitFor(() => {
      expect(screen.getByText(/All crawled pages have at least one internal link/i)).toBeTruthy()
    })
    expect(screen.queryByText(/may still be listed here/i)).toBeNull()
  })

  it('falls back to the normal view for a legacy job with no coverage record', async () => {
    // Audits crawled before O2 have no orphan_detection; they were full crawls,
    // so the existing rendering is correct and must not regress to "not run".
    mockResults({ issues: [], orphan_detection: null })
    renderWithProviders(<OrphanedPagesPanel {...props} />)
    await waitFor(() => {
      expect(screen.getByText(/All crawled pages have at least one internal link/i)).toBeTruthy()
    })
  })
})

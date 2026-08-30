/**
 * O2 — the Results summary tile is a second surface, and a control that is not
 * asserted is decoration (P25 corollary). A suppressed check returns zero, and
 * a tile that prints "0 Orphaned Pages" states the opposite of the truth.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { OrphanedSummaryCards } from '../Results.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

const props = { jobId: 'test-job', onOrphanImagesClick: () => {}, onOrphanPagesClick: () => {} }

function mockResults(orphan_detection, issues = []) {
  global.fetch.mockImplementation(() =>
    mockFetchResponse({ issues, summary: { orphan_detection } })
  )
}

describe('OrphanedSummaryCards', () => {
  beforeEach(() => { global.fetch.mockReset() })

  it('shows the count when the check actually ran', async () => {
    mockResults(
      { status: 'complete', pages_analysed: 272, pages_out_of_scope: 0 },
      [{ issue_code: 'ORPHAN_PAGE', page_url: 'https://example.com/hidden' }],
    )
    renderWithProviders(<OrphanedSummaryCards {...props} />)
    await waitFor(() => expect(screen.getByText('1')).toBeTruthy())
    expect(screen.getByText(/Pages with no internal links pointing to them/i)).toBeTruthy()
  })

  it('shows "not checked" instead of 0 when the check was suppressed', async () => {
    mockResults({ status: 'skipped_partial_scan', pages_analysed: 37, pages_out_of_scope: 235 })
    renderWithProviders(<OrphanedSummaryCards {...props} />)
    await waitFor(() => expect(screen.getByText(/Not checked/i)).toBeTruthy())
    expect(screen.queryByText('0')).toBeNull()
  })

  it('shows "not checked" when the request failed', async () => {
    global.fetch.mockImplementation(() => Promise.reject(new Error('network down')))
    renderWithProviders(<OrphanedSummaryCards {...props} />)
    await waitFor(() => expect(screen.getByText(/Not checked/i)).toBeTruthy())
  })
})

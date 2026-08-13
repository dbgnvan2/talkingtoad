import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import { renderWithProviders } from '../../test/test-utils.jsx'
import FixFocusPanel from '../FixFocusPanel.jsx'

// FF6.A — the Fix Focus panel renders SEO + AI/GEO sections from the persisted
// snapshot, restores checked/verified state, ticks items, and shows an error.

const SNAPSHOT = {
  seo: {
    pages: [{
      url: 'https://x.org/about',
      page_priority: 64,
      items: [
        { issue_code: 'TITLE_MISSING', human_description: 'Missing title', severity: 'warning', priority_rank: 64, quick_win: true, status: 'open' },
      ],
    }],
    pages_total: 1, pages_shown: 1, items_hidden: 0,
  },
  geo: {
    pages: [{
      url: 'https://x.org/about',
      page_priority: 38,
      items: [
        { issue_code: 'GEO_SUMMARY_BURIED', human_description: 'Summary buried', severity: 'warning', priority_rank: 38, quick_win: false, status: 'verified' },
      ],
    }],
    pages_total: 1, pages_shown: 1, items_hidden: 0,
  },
  generated_at: '2026-08-13T00:00:00+00:00',
  scoring_model_version: 'v',
}

function mockGet(snapshot) {
  global.fetch.mockImplementation(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(snapshot) })
  )
}

describe('FixFocusPanel', () => {
  beforeEach(() => { global.fetch.mockReset() })

  it('loads and renders SEO and AI/GEO sections from the snapshot', async () => {
    mockGet(SNAPSHOT)
    renderWithProviders(<FixFocusPanel jobId="job1" />)
    await waitFor(() => expect(screen.getByText('SEO')).toBeInTheDocument())
    expect(screen.getByText('AI / GEO')).toBeInTheDocument()
    expect(screen.getByText('Missing title')).toBeInTheDocument()
    expect(screen.getByText('Summary buried')).toBeInTheDocument()
    // quick-win badge on the SEO item
    expect(screen.getByText('quick win')).toBeInTheDocument()
  })

  it('restores verified state from the snapshot (checkbox checked)', async () => {
    mockGet(SNAPSHOT)
    renderWithProviders(<FixFocusPanel jobId="job1" />)
    await waitFor(() => expect(screen.getByText('Summary buried')).toBeInTheDocument())
    // the verified GEO item is rendered checked and labelled
    const verifiedBox = screen.getByLabelText('Mark GEO_SUMMARY_BURIED fixed')
    expect(verifiedBox.checked).toBe(true)
    expect(screen.getByText('verified ✓')).toBeInTheDocument()
  })

  it('shows the drop-announcement counter (no silent truncation)', async () => {
    const capped = { ...SNAPSHOT, seo: { ...SNAPSHOT.seo, pages_total: 12, pages_shown: 10, items_hidden: 2 } }
    mockGet(capped)
    renderWithProviders(<FixFocusPanel jobId="job1" />)
    await waitFor(() => expect(screen.getByText(/10 of 12 pages/)).toBeInTheDocument())
    expect(screen.getByText(/2 more items on hidden pages/)).toBeInTheDocument()
  })

  it('ticks an item (calls the toggle endpoint then reloads)', async () => {
    const calls = []
    global.fetch.mockImplementation((url, opts) => {
      calls.push({ url, method: opts?.method })
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(SNAPSHOT) })
    })
    renderWithProviders(<FixFocusPanel jobId="job1" />)
    await waitFor(() => expect(screen.getByText('Missing title')).toBeInTheDocument())
    fireEvent.click(screen.getByLabelText('Mark TITLE_MISSING fixed'))
    await waitFor(() =>
      expect(calls.some(c => c.method === 'POST' && String(c.url).includes('/fix-focus/check'))).toBe(true)
    )
  })

  it('verifies a page (calls verify-page)', async () => {
    const calls = []
    global.fetch.mockImplementation((url, opts) => {
      calls.push({ url: String(url), method: opts?.method })
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(SNAPSHOT) })
    })
    renderWithProviders(<FixFocusPanel jobId="job1" />)
    await waitFor(() => expect(screen.getAllByText('Verify page').length).toBeGreaterThan(0))
    fireEvent.click(screen.getAllByText('Verify page')[0])
    await waitFor(() =>
      expect(calls.some(c => c.method === 'POST' && c.url.includes('/fix-focus/verify-page'))).toBe(true)
    )
  })

  it('surfaces newly_found from a verify as a Regenerate prompt (sweep #3)', async () => {
    global.fetch.mockImplementation((url) => {
      const u = String(url)
      if (u.includes('/fix-focus/verify-page')) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({
          url: 'https://x.org/about', reconciled: true,
          verified: [], still_present: [], newly_found: ['CANONICAL_MISSING'],
        }) })
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(SNAPSHOT) })
    })
    renderWithProviders(<FixFocusPanel jobId="job1" />)
    await waitFor(() => expect(screen.getAllByText('Verify page').length).toBeGreaterThan(0))
    fireEvent.click(screen.getAllByText('Verify page')[0])
    await waitFor(() => expect(screen.getByText(/new issue\(s\) found/)).toBeInTheDocument())
    expect(screen.getByText(/Regenerate to include them/)).toBeInTheDocument()
  })

  it('shows an error when a checklist toggle fails (sweep #4)', async () => {
    global.fetch.mockImplementation((url) => {
      const u = String(url)
      if (u.includes('/fix-focus/check')) {
        return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({ error: { message: 'ITEM_NOT_FOUND' } }) })
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(SNAPSHOT) })
    })
    renderWithProviders(<FixFocusPanel jobId="job1" />)
    await waitFor(() => expect(screen.getByText('Missing title')).toBeInTheDocument())
    fireEvent.click(screen.getByLabelText('Mark TITLE_MISSING fixed'))
    await waitFor(() => expect(screen.getByText(/ITEM_NOT_FOUND|Could not update|HTTP 404/)).toBeInTheDocument())
  })

  it('shows an error state when the request fails', async () => {
    global.fetch.mockImplementation(() =>
      Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({ error: { message: 'boom' } }) })
    )
    renderWithProviders(<FixFocusPanel jobId="job1" />)
    await waitFor(() => expect(screen.getByText(/Failed to load|boom|HTTP 500/)).toBeInTheDocument())
  })
})

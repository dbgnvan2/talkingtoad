import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent, within } from '@testing-library/react'
import Home from '../Home.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

/**
 * Rescan button on the home page's Recent crawls list.
 *
 * Spec: docs/pending/2026-09-01_rescan-from-home.md#R3
 *
 * Re-running a scan used to mean re-typing the URL and re-selecting every
 * setting from memory, which also made the re-run not comparable to the scan it
 * was meant to be compared against.
 */

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => ({
  ...(await vi.importActual('react-router-dom')),
  useNavigate: () => mockNavigate,
}))

vi.mock('../hooks/useCrawl.js', () => ({
  useCrawl: () => ({ start: vi.fn(), loading: false, error: null }),
}))

const FINISHED = {
  job_id: 'job-done', target_url: 'https://livingsystems.ca', status: 'complete',
  pages_crawled: 48, started_at: '2026-09-01T15:02:29Z', completed_at: '2026-09-01T15:09:00Z',
}
const RUNNING = {
  job_id: 'job-running', target_url: 'https://example.org', status: 'running',
  pages_crawled: 3, started_at: '2026-09-01T15:20:00Z', completed_at: null,
}

/** Route fetches by URL so a test never depends on call ORDER. */
function mockApi({ recent = [FINISHED], rescan = { ok: true, body: {} } } = {}) {
  global.fetch.mockImplementation((url) => {
    if (String(url).includes('/rescan')) {
      return mockFetchResponse(rescan.body, rescan.ok ? 200 : (rescan.status || 500))
    }
    if (String(url).includes('/api/crawl/recent')) return mockFetchResponse(recent)
    return mockFetchResponse({})
  })
}

const rowFor = (text) => screen.getByText(text).closest('li')

describe('Home — Rescan button', () => {
  beforeEach(() => {
    global.fetch.mockReset()
    mockNavigate.mockReset()
    localStorage.clear()
  })

  it('renders Rescan next to View Results on a finished scan', async () => {
    mockApi()
    renderWithProviders(<Home />)
    const row = await waitFor(() => rowFor('livingsystems.ca'))
    expect(within(row).getByRole('button', { name: /rescan/i })).toBeInTheDocument()
    expect(within(row).getByRole('button', { name: /view results/i })).toBeInTheDocument()
  })

  it('offers no Rescan on a running scan — there is nothing to re-run yet', async () => {
    mockApi({ recent: [RUNNING] })
    renderWithProviders(<Home />)
    const row = await waitFor(() => rowFor('example.org'))
    expect(within(row).getByRole('button', { name: /view progress/i })).toBeInTheDocument()
    expect(within(row).queryByRole('button', { name: /rescan/i })).not.toBeInTheDocument()
  })

  it('posts to the rescan endpoint for THAT job and goes to progress', async () => {
    mockApi({ rescan: { ok: true, body: { job_id: 'new-job', mode: 'crawl', status: 'queued' } } })
    renderWithProviders(<Home />)
    const row = await waitFor(() => rowFor('livingsystems.ca'))

    fireEvent.click(within(row).getByRole('button', { name: /rescan/i }))

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/progress/new-job'))
    const call = global.fetch.mock.calls.find(([u]) => String(u).includes('/rescan'))
    expect(call[0]).toContain('/api/crawl/job-done/rescan')
    expect(call[1].method).toBe('POST')
  })

  it('a single-page rescan is already finished, so it goes to results', async () => {
    mockApi({
      recent: [{ ...FINISHED, pages_crawled: 1 }],
      rescan: { ok: true, body: { job_id: 'new-page', mode: 'single_page', status: 'complete' } },
    })
    renderWithProviders(<Home />)
    const row = await waitFor(() => rowFor('livingsystems.ca'))

    fireEvent.click(within(row).getByRole('button', { name: /rescan/i }))

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/results/new-page'))
  })

  it('shows an inline error and does NOT navigate when the rescan fails', async () => {
    mockApi({
      rescan: { ok: false, status: 409, body: { error: { message: 'This scan is still running.' } } },
    })
    renderWithProviders(<Home />)
    const row = await waitFor(() => rowFor('livingsystems.ca'))

    fireEvent.click(within(row).getByRole('button', { name: /rescan/i }))

    expect(await screen.findByText(/still running/i)).toBeInTheDocument()
    expect(mockNavigate).not.toHaveBeenCalled()
    // A failed rescan must not look like it consumed the scan it came from.
    expect(rowFor('livingsystems.ca')).toBeInTheDocument()
  })

  it('re-enables the button after a failure so the user can retry', async () => {
    mockApi({ rescan: { ok: false, status: 500, body: {} } })
    renderWithProviders(<Home />)
    const row = await waitFor(() => rowFor('livingsystems.ca'))

    fireEvent.click(within(row).getByRole('button', { name: /rescan/i }))

    await waitFor(() =>
      expect(within(row).getByRole('button', { name: /rescan/i })).not.toBeDisabled())
  })

  it('an in-flight rescan disables only its OWN row', async () => {
    const other = { ...FINISHED, job_id: 'job-two', target_url: 'https://other.org' }
    // Never resolves: the click stays in flight for the assertion.
    global.fetch.mockImplementation((url) => {
      if (String(url).includes('/rescan')) return new Promise(() => {})
      if (String(url).includes('/api/crawl/recent')) return mockFetchResponse([FINISHED, other])
      return mockFetchResponse({})
    })
    renderWithProviders(<Home />)
    const first = await waitFor(() => rowFor('livingsystems.ca'))
    const second = rowFor('other.org')

    fireEvent.click(within(first).getByRole('button', { name: /rescan/i }))

    await waitFor(() =>
      expect(within(first).getByRole('button', { name: /starting/i })).toBeDisabled())
    expect(within(second).getByRole('button', { name: /rescan/i })).not.toBeDisabled()
  })
})

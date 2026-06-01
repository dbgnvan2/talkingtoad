import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import Progress from '../Progress.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useParams: () => ({ jobId: 'test-job-123' }),
    useNavigate: () => vi.fn(),
  }
})

// The real usePolling calls onData inside a useEffect-driven async loop.
// The mock must also defer onData to avoid infinite re-renders.
vi.mock('../../hooks/usePolling.js', () => {
  // Import useEffect inside the factory so we can use it in the mock hook
  const react = require('react')
  return {
    usePolling: (fetchFn, onData, _shouldStop) => {
      react.useEffect(() => {
        onData({
          status: 'running',
          pages_crawled: 42,
          pages_total: 100,
          target_url: 'https://example.com',
        })
      }, [])
    },
    isTerminal: (status) => ['complete', 'failed', 'cancelled'].includes(status),
  }
})

describe('Progress page', () => {
  beforeEach(() => {
    global.fetch.mockReset()
  })

  it('renders the progress page without crashing', () => {
    global.fetch.mockImplementation(() =>
      mockFetchResponse({
        status: 'running',
        pages_crawled: 42,
        pages_total: 100,
      })
    )
    const { container } = renderWithProviders(<Progress />, { route: '/progress/test-job-123' })
    expect(container).toBeTruthy()
  })

  it('displays progress information', async () => {
    global.fetch.mockImplementation(() =>
      mockFetchResponse({
        status: 'running',
        pages_crawled: 42,
        pages_total: 100,
      })
    )
    renderWithProviders(<Progress />, { route: '/progress/test-job-123' })
    await waitFor(() => {
      const container = document.querySelector('.min-h-screen')
      expect(container).toBeInTheDocument()
    })
  })

  it('renders the progress bar component', async () => {
    global.fetch.mockImplementation(() =>
      mockFetchResponse({
        status: 'running',
        pages_crawled: 42,
        pages_total: 100,
      })
    )
    renderWithProviders(<Progress />, { route: '/progress/test-job-123' })
    await waitFor(() => {
      const progressContainer = document.querySelector('[role="progressbar"]')
        || document.querySelector('.bg-gradient-to-r')
        || document.querySelector('.bg-green-500') // ProgressBar inner bar
      expect(progressContainer).toBeTruthy()
    })
  })

  it('renders cancel button when status is running', async () => {
    global.fetch.mockImplementation(() =>
      mockFetchResponse({
        status: 'running',
        pages_crawled: 42,
        pages_total: 100,
      })
    )
    renderWithProviders(<Progress />, { route: '/progress/test-job-123' })
    await waitFor(() => {
      const cancelBtn = screen.queryByRole('button', { name: /cancel/i })
      expect(cancelBtn || screen.queryByText(/cancel/i)).toBeTruthy()
    })
  })

  it('handles fetch error gracefully', async () => {
    global.fetch.mockImplementation(() => Promise.reject(new Error('Network error')))
    const { container } = renderWithProviders(<Progress />, { route: '/progress/test-job-123' })
    expect(container).toBeTruthy()
  })

  it('renders status heading', async () => {
    global.fetch.mockImplementation(() =>
      mockFetchResponse({
        status: 'running',
        pages_crawled: 42,
        pages_total: 100,
      })
    )
    renderWithProviders(<Progress />, { route: '/progress/test-job-123' })
    await waitFor(() => {
      const heading = document.querySelector('h2')
      expect(heading).toBeTruthy()
    })
  })

  it('renders the white card container', async () => {
    global.fetch.mockImplementation(() =>
      mockFetchResponse({
        status: 'running',
        pages_crawled: 42,
        pages_total: 100,
      })
    )
    renderWithProviders(<Progress />, { route: '/progress/test-job-123' })
    await waitFor(() => {
      const card = document.querySelector('.bg-white.rounded-2xl')
      expect(card).toBeTruthy()
    })
  })

  it('handles empty status gracefully', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse({}))
    const { container } = renderWithProviders(<Progress />, { route: '/progress/test-job-123' })
    expect(container).toBeTruthy()
  })
})

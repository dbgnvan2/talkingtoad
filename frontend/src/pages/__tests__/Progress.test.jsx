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

vi.mock('../../hooks/usePolling.js', () => ({
  usePolling: (fetch, onData, isTerminal) => {
    const mockStatus = {
      status: 'crawling',
      pages_crawled: 42,
      total_pages: 100,
    }
    onData(mockStatus)
  },
  isTerminal: (status) => ['complete', 'cancelled', 'error'].includes(status),
}))

describe('Progress page', () => {
  beforeEach(() => {
    global.fetch.mockReset()
  })

  it('renders the progress page without crashing', () => {
    global.fetch.mockImplementation(() =>
      mockFetchResponse({
        status: 'crawling',
        pages_crawled: 42,
        total_pages: 100,
      })
    )
    const { container } = renderWithProviders(<Progress />, { route: '/progress/test-job-123' })
    expect(container).toBeTruthy()
  })

  it('displays progress information', async () => {
    global.fetch.mockImplementation(() =>
      mockFetchResponse({
        status: 'crawling',
        pages_crawled: 42,
        total_pages: 100,
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
        status: 'crawling',
        pages_crawled: 42,
        total_pages: 100,
      })
    )
    renderWithProviders(<Progress />, { route: '/progress/test-job-123' })
    await waitFor(() => {
      const progressContainer = document.querySelector('[role="progressbar"]')
        || document.querySelector('.bg-gradient-to-r')
      expect(progressContainer).toBeTruthy()
    })
  })

  it('renders cancel button when crawling', async () => {
    global.fetch.mockImplementation(() =>
      mockFetchResponse({
        status: 'crawling',
        pages_crawled: 42,
        total_pages: 100,
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
        status: 'crawling',
        pages_crawled: 42,
        total_pages: 100,
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
        status: 'crawling',
        pages_crawled: 42,
        total_pages: 100,
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

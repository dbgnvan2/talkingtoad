import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import Results from '../Results.jsx'
import { renderWithProviders, mockSummary } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

// Mock useParams to return a job ID
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useParams: () => ({ jobId: 'test-job-123' }),
    useNavigate: () => vi.fn(),
  }
})

describe('Results page', () => {
  beforeEach(() => {
    global.fetch.mockReset()
  })

  function mockAllFetches() {
    global.fetch.mockImplementation((url) => {
      if (url.includes('/results/crawlability')) {
        return mockFetchResponse({
          issues: [{ issue_code: 'ORPHAN_PAGE', page_url: 'https://example.com/orphan', extra: {} }],
          summary: mockSummary,
          pagination: { page: 1, total_pages: 1, total_issues: 1 }
        })
      }
      if (url.includes('/results')) {
        return mockFetchResponse({ summary: mockSummary })
      }
      return mockFetchResponse({})
    })
  }

  it('renders the summary tab with health score', async () => {
    mockAllFetches()
    renderWithProviders(<Results />, { route: '/results/test-job-123' })
    await waitFor(() => {
      expect(screen.getByText('Audit Results')).toBeInTheDocument()
      expect(screen.getByText('87')).toBeInTheDocument()
    })
  })

  it('renders category tabs in the tab bar', async () => {
    mockAllFetches()
    renderWithProviders(<Results />, { route: '/results/test-job-123' })
    await waitFor(() => {
      expect(screen.getByText('Summary')).toBeInTheDocument()
    })
    // Check tab bar has category labels
    const tabBar = screen.getByText('Summary').closest('.border-b')
    expect(within(tabBar).getByText('Broken Links')).toBeInTheDocument()
    expect(within(tabBar).getByText('Metadata')).toBeInTheDocument()
    expect(within(tabBar).getByText('Headings')).toBeInTheDocument()
    expect(within(tabBar).getByText('Images')).toBeInTheDocument()
    expect(within(tabBar).getByText('Security')).toBeInTheDocument()
  })

  it('renders orphaned content tabs in the tab bar', async () => {
    mockAllFetches()
    renderWithProviders(<Results />, { route: '/results/test-job-123' })
    await waitFor(() => {
      expect(screen.getByText('Summary')).toBeInTheDocument()
    })
    const tabBar = screen.getByText('Summary').closest('.border-b')
    expect(within(tabBar).getByText('Orphaned Images')).toBeInTheDocument()
    expect(within(tabBar).getByText('Orphaned Pages')).toBeInTheDocument()
  })

  it('renders severity stat cards', async () => {
    mockAllFetches()
    renderWithProviders(<Results />, { route: '/results/test-job-123' })
    await waitFor(() => {
      expect(screen.getByText('Critical Issues')).toBeInTheDocument()
      expect(screen.getByText('Warnings')).toBeInTheDocument()
      expect(screen.getByText('Info Notices')).toBeInTheDocument()
    })
  })

  it('renders category drill-down boxes', async () => {
    mockAllFetches()
    renderWithProviders(<Results />, { route: '/results/test-job-123' })
    await waitFor(() => {
      expect(screen.getByText('Issues by Category')).toBeInTheDocument()
    })
  })

  it('renders export buttons', async () => {
    mockAllFetches()
    renderWithProviders(<Results />, { route: '/results/test-job-123' })
    await waitFor(() => {
      expect(screen.getByText('CSV')).toBeInTheDocument()
      expect(screen.getByText('Excel')).toBeInTheDocument()
      expect(screen.getByText('PDF Report')).toBeInTheDocument()
    })
  })

  it('renders orphaned content summary section', async () => {
    mockAllFetches()
    renderWithProviders(<Results />, { route: '/results/test-job-123' })
    await waitFor(() => {
      expect(screen.getByText('Orphaned Content')).toBeInTheDocument()
    })
  })

  it('handles empty summary gracefully without crashing', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse({}))
    const { container } = renderWithProviders(<Results />, { route: '/results/test-job-123' })
    expect(container).toBeTruthy()
  })

  it('handles fetch error gracefully without crashing', async () => {
    global.fetch.mockImplementation(() => Promise.reject(new Error('Network error')))
    const { container } = renderWithProviders(<Results />, { route: '/results/test-job-123' })
    expect(container).toBeTruthy()
  })
})

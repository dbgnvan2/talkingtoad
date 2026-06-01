import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import AIReadinessPanel from '../AIReadinessPanel.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

describe('AIReadinessPanel', () => {
  const defaultProps = {
    jobId: 'test-job',
    domain: 'example.com',
    onPageClick: vi.fn(),
    onShowHelp: vi.fn(),
  }

  beforeEach(() => {
    global.fetch.mockReset()
    // Mock both the category results fetch and GEOReportPanel's getGeoAiModel call
    global.fetch.mockImplementation((url) => {
      if (typeof url === 'string' && url.includes('/results/ai_readiness')) {
        return mockFetchResponse({
          issues: [
            {
              issue_code: 'STATISTICS_COUNT_LOW',
              category: 'ai_readiness',
              severity: 'warning',
              page_url: 'https://example.com/page1',
              extra: {},
            },
          ],
        })
      }
      // GEOReportPanel calls getGeoAiModel on mount
      if (typeof url === 'string' && url.includes('/api/geo/ai-model')) {
        return mockFetchResponse({ selected: 'gemini', available: [] })
      }
      return mockFetchResponse({})
    })
  })

  it('renders heading with domain name', async () => {
    renderWithProviders(<AIReadinessPanel {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('AI Readiness - example.com')).toBeInTheDocument()
    })
  })

  it('renders the Help button', async () => {
    renderWithProviders(<AIReadinessPanel {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText(/Help/)).toBeInTheDocument()
    })
  })

  it('shows group cards with issue counts after data loads', async () => {
    renderWithProviders(<AIReadinessPanel {...defaultProps} />)

    // STATISTICS_COUNT_LOW belongs to the "Aggarwal GEO Signals" group
    await waitFor(() => {
      expect(screen.getByText('Aggarwal GEO Signals')).toBeInTheDocument()
      expect(screen.getByText('1 issue')).toBeInTheDocument()
    })
  })

  it('displays confidence label from issueHelp data when group is expanded', async () => {
    renderWithProviders(<AIReadinessPanel {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('Aggarwal GEO Signals')).toBeInTheDocument()
    })

    // Expand the group to see confidence badge
    const groupButton = screen.getByText('Aggarwal GEO Signals').closest('button')
    groupButton.click()

    await waitFor(() => {
      // STATISTICS_COUNT_LOW has confidence: "Empirical" in issueHelp.js
      expect(screen.getByText('Empirical')).toBeInTheDocument()
    })
  })

  it('shows empty state when no issues found', async () => {
    global.fetch.mockImplementation((url) => {
      if (typeof url === 'string' && url.includes('/results/ai_readiness')) {
        return mockFetchResponse({ issues: [] })
      }
      if (typeof url === 'string' && url.includes('/api/geo/ai-model')) {
        return mockFetchResponse({ selected: 'gemini', available: [] })
      }
      return mockFetchResponse({})
    })

    renderWithProviders(<AIReadinessPanel {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText(/All AI Readiness checks passed/)).toBeInTheDocument()
    })
  })
})

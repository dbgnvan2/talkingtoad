import { describe, it, expect, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import GEOReportPanel from '../GEOReportPanel.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

describe('GEOReportPanel', () => {
  const defaultProps = {
    jobId: 'test-job',
    domain: 'example.com',
  }

  beforeEach(() => {
    global.fetch.mockReset()
    global.fetch.mockImplementation((url) => {
      if (typeof url === 'string' && url.includes('/api/geo/ai-model')) {
        return mockFetchResponse({
          selected: 'gemini-2.0-flash',
          available: [
            { id: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash' },
          ],
        })
      }
      return mockFetchResponse({})
    })
  })

  it('renders without crashing and shows the heading', async () => {
    renderWithProviders(<GEOReportPanel {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('GEO Analysis Report')).toBeInTheDocument()
    })
  })

  it('shows Run GEO Analysis buttons in pre-run state', async () => {
    renderWithProviders(<GEOReportPanel {...defaultProps} />)

    await waitFor(() => {
      // Header button + pre-run CTA both show this text
      const buttons = screen.getAllByText('▶ Run GEO Analysis')
      expect(buttons.length).toBeGreaterThanOrEqual(1)
    })
  })

  it('shows pre-run empty state with description', async () => {
    renderWithProviders(<GEOReportPanel {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('GEO Analysis not yet run')).toBeInTheDocument()
    })
  })

  it('displays the domain below the heading', async () => {
    renderWithProviders(<GEOReportPanel {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('example.com')).toBeInTheDocument()
    })
  })

  it('renders FAQ Schema Generator and Entity Schema Factory cards', async () => {
    renderWithProviders(<GEOReportPanel {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('FAQ Schema Generator')).toBeInTheDocument()
      expect(screen.getByText('Entity Schema Factory')).toBeInTheDocument()
    })
  })
})

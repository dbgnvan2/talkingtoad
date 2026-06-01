import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import GSCInsightsPanel from '../GSCInsightsPanel.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

describe('GSCInsightsPanel', () => {
  beforeEach(() => {
    global.fetch.mockReset()
  })

  it('renders "not configured" empty state when gscStatus returns 503', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse(
      { connected: false, properties: [], configured: false },
      503
    ))

    // The component handles 503 internally (returns { connected: false, configured: false })
    // We need to mock the raw response since gscStatus() intercepts 503
    global.fetch.mockImplementation(() =>
      Promise.resolve({
        ok: false,
        status: 503,
        json: () => Promise.resolve({}),
        headers: new Headers(),
      })
    )

    renderWithProviders(<GSCInsightsPanel jobId="test-job" />)

    await waitFor(() => {
      expect(screen.getByText('GSC not configured')).toBeInTheDocument()
    })
  })

  it('renders Connect button when connected:false', async () => {
    global.fetch.mockImplementation(() =>
      mockFetchResponse({ connected: false, properties: [], configured: true })
    )

    renderWithProviders(<GSCInsightsPanel jobId="test-job" />)

    await waitFor(() => {
      expect(screen.getByText('Connect Google Search Console')).toBeInTheDocument()
    })
  })

  it('renders properties and Ingest when connected:true', async () => {
    const mockProperties = [
      { siteUrl: 'https://example.com', permissionLevel: 'siteOwner' },
      { siteUrl: 'https://sub.example.com', permissionLevel: 'siteFullUser' },
    ]
    global.fetch.mockImplementation(() =>
      mockFetchResponse({ connected: true, properties: mockProperties, configured: true })
    )

    renderWithProviders(<GSCInsightsPanel jobId="test-job" />)

    await waitFor(() => {
      expect(screen.getByText('Ingest Performance Data')).toBeInTheDocument()
      expect(screen.getByText('Disconnect')).toBeInTheDocument()
    })

    // The siteOwner property should be highlighted in the select
    const select = screen.getByRole('combobox')
    expect(select.value).toBe('https://example.com')
  })

  it('renders Learn more explainer toggle', async () => {
    global.fetch.mockImplementation(() =>
      mockFetchResponse({
        connected: true,
        properties: [{ siteUrl: 'https://example.com', permissionLevel: 'siteOwner' }],
        configured: true,
      })
    )

    renderWithProviders(<GSCInsightsPanel jobId="test-job" />)

    await waitFor(() => {
      expect(screen.getByText(/Learn more/)).toBeInTheDocument()
    })

    // Click to show explainer
    const user = userEvent.setup()
    await user.click(screen.getByText(/Learn more/))

    expect(screen.getByText(/What it is:/)).toBeInTheDocument()
    expect(screen.getByText(/Why it's useful:/)).toBeInTheDocument()
    expect(screen.getByText(/Good vs bad:/)).toBeInTheDocument()
    expect(screen.getByText(/How it can mislead:/)).toBeInTheDocument()
    expect(screen.getByText(/How to use:/)).toBeInTheDocument()
  })

  it('renders without crashing with mocked api', () => {
    global.fetch.mockImplementation(() =>
      mockFetchResponse({ connected: false, properties: [], configured: false })
    )

    const { container } = renderWithProviders(<GSCInsightsPanel jobId="test-job" />)
    expect(container).toBeTruthy()
  })

  it('shows error state and retry button on fetch failure', async () => {
    global.fetch.mockImplementation(() =>
      Promise.reject(new Error('Network error'))
    )

    renderWithProviders(<GSCInsightsPanel jobId="test-job" />)

    await waitFor(() => {
      expect(screen.getByText(/Network error/)).toBeInTheDocument()
      expect(screen.getByText('Retry')).toBeInTheDocument()
    })
  })
})

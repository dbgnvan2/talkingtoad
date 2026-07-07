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
    // Backend list_properties() returns snake_case (site_url / permission_level) —
    // the real API contract. The panel must read these exact keys.
    const mockProperties = [
      { site_url: 'https://example.com', permission_level: 'siteOwner' },
      { site_url: 'https://sub.example.com', permission_level: 'siteFullUser' },
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

  it('Ingest sends the real site_url, never "undefined" (snake_case contract regression)', async () => {
    // Regression for the GSC ingest bug: backend returns snake_case site_url,
    // the panel read camelCase siteUrl → undefined → sites/undefined/... 400.
    const mockProperties = [
      { site_url: 'https://example.com/', permission_level: 'siteOwner' },
    ]
    global.fetch.mockImplementation((url) =>
      String(url).includes('/api/gsc/ingest')
        ? mockFetchResponse({ ingested: 1, period: '30d' })
        : mockFetchResponse({ connected: true, properties: mockProperties, configured: true })
    )

    renderWithProviders(<GSCInsightsPanel jobId="test-job" />)
    await waitFor(() =>
      expect(screen.getByText('Ingest Performance Data')).toBeInTheDocument()
    )

    const user = userEvent.setup()
    await user.click(screen.getByText('Ingest Performance Data'))

    await waitFor(() => {
      const ingestCall = global.fetch.mock.calls.find(([u]) =>
        String(u).includes('/api/gsc/ingest')
      )
      expect(ingestCall).toBeTruthy()
      const calledUrl = String(ingestCall[0])
      expect(calledUrl).not.toContain('undefined')
      expect(calledUrl).toContain('example.com')
    })
  })

  it('dropdown options show permission-level labels', async () => {
    const mockProperties = [
      { site_url: 'https://example.com', permission_level: 'siteOwner' },
      { site_url: 'https://full.example.com', permission_level: 'siteFullUser' },
      { site_url: 'https://res.example.com', permission_level: 'siteRestrictedUser' },
      { site_url: 'sc-domain:example.com', permission_level: 'siteUnverifiedUser' },
    ]
    global.fetch.mockImplementation(() =>
      mockFetchResponse({ connected: true, properties: mockProperties, configured: true })
    )

    renderWithProviders(<GSCInsightsPanel jobId="test-job" />)

    await waitFor(() =>
      expect(screen.getByText('Ingest Performance Data')).toBeInTheDocument()
    )

    const options = screen.getAllByRole('option')
    const texts = options.map(o => o.textContent)
    expect(texts).toContain('https://example.com — Owner')
    expect(texts).toContain('https://full.example.com — Full')
    expect(texts).toContain('https://res.example.com — Restricted')
    expect(texts).toContain('sc-domain:example.com — Unverified')
  })

  it('auto-selects the best-permission property (Full over an unverified first)', async () => {
    // Unverified property comes FIRST — the old default (properties[0]) would
    // have picked it, causing 403s. Smart default must pick the Full one.
    const mockProperties = [
      { site_url: 'sc-domain:example.com', permission_level: 'siteUnverifiedUser' },
      { site_url: 'https://example.com/', permission_level: 'siteFullUser' },
    ]
    global.fetch.mockImplementation(() =>
      mockFetchResponse({ connected: true, properties: mockProperties, configured: true })
    )

    renderWithProviders(<GSCInsightsPanel jobId="test-job" />)

    await waitFor(() =>
      expect(screen.getByText('Ingest Performance Data')).toBeInTheDocument()
    )

    const select = screen.getByRole('combobox')
    expect(select.value).toBe('https://example.com/')
  })

  it('shows limited-access hint when the selected property is unverified', async () => {
    const mockProperties = [
      { site_url: 'sc-domain:example.com', permission_level: 'siteUnverifiedUser' },
    ]
    global.fetch.mockImplementation(() =>
      mockFetchResponse({ connected: true, properties: mockProperties, configured: true })
    )

    renderWithProviders(<GSCInsightsPanel jobId="test-job" />)

    await waitFor(() =>
      expect(screen.getByText(/limited access to this property/i)).toBeInTheDocument()
    )
  })

  it('shows "Connected as {email}" when account_email is present', async () => {
    global.fetch.mockImplementation(() =>
      mockFetchResponse({
        connected: true,
        properties: [{ site_url: 'https://example.com', permission_level: 'siteOwner' }],
        configured: true,
        account_email: 'owner@example.org',
      })
    )

    renderWithProviders(<GSCInsightsPanel jobId="test-job" />)

    await waitFor(() =>
      expect(screen.getByText('Connected as owner@example.org')).toBeInTheDocument()
    )
  })

  it('shows "account not identified" hint when account_email is null', async () => {
    global.fetch.mockImplementation(() =>
      mockFetchResponse({
        connected: true,
        properties: [{ site_url: 'https://example.com', permission_level: 'siteOwner' }],
        configured: true,
        account_email: null,
      })
    )

    renderWithProviders(<GSCInsightsPanel jobId="test-job" />)

    await waitFor(() =>
      expect(screen.getByText(/account not identified/i)).toBeInTheDocument()
    )
  })

  it('renders Learn more explainer toggle', async () => {
    global.fetch.mockImplementation(() =>
      mockFetchResponse({
        connected: true,
        properties: [{ site_url: 'https://example.com', permission_level: 'siteOwner' }],
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

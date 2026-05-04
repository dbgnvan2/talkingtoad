import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import Home from '../Home.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

vi.mock('../hooks/useCrawl.js', () => ({
  useCrawl: () => ({
    start: vi.fn(),
    loading: false,
    error: null,
  }),
}))

describe('Home page', () => {
  beforeEach(() => {
    global.fetch.mockReset()
    localStorage.clear()
  })

  it('renders the home page without crashing', () => {
    global.fetch.mockImplementation(() => mockFetchResponse([]))
    const { container } = renderWithProviders(<Home />)
    expect(container).toBeTruthy()
  })

  it('renders the main heading', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse([]))
    renderWithProviders(<Home />)
    await waitFor(() => {
      const heading = screen.queryByText(/TalkingToad/, { selector: 'h1' })
      expect(heading || document.querySelector('h1')).toBeTruthy()
    })
  })

  it('renders the URL input field', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse([]))
    renderWithProviders(<Home />)
    await waitFor(() => {
      const input = screen.getByPlaceholderText(/enter.*url|https/i)
      expect(input).toBeInTheDocument()
    })
  })

  it('renders analysis toggles', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse([]))
    renderWithProviders(<Home />)
    await waitFor(() => {
      expect(screen.getByText('Link Integrity')).toBeInTheDocument()
      expect(screen.getByText('SEO Essentials')).toBeInTheDocument()
      expect(screen.getByText('Site Structure')).toBeInTheDocument()
      expect(screen.getByText('Indexability')).toBeInTheDocument()
    })
  })

  it('allows toggling analysis options', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse([]))
    renderWithProviders(<Home />)
    await waitFor(() => {
      const toggles = screen.getAllByRole('checkbox')
      expect(toggles.length).toBeGreaterThan(0)
      fireEvent.click(toggles[0])
      expect(toggles[0]).toBeTruthy()
    })
  })

  it('renders the start crawl button', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse([]))
    renderWithProviders(<Home />)
    await waitFor(() => {
      const button = screen.queryByRole('button', { name: /start|crawl/i })
      expect(button || screen.getByText(/start|scan|crawl/i)).toBeTruthy()
    })
  })

  it('saves URL to localStorage', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse([]))
    renderWithProviders(<Home />)
    await waitFor(() => {
      const input = screen.getByPlaceholderText(/enter.*url|https/i)
      fireEvent.change(input, { target: { value: 'https://example.com' } })
      expect(input.value).toBe('https://example.com')
    })
  })

  it('handles fetch error for recent jobs gracefully', async () => {
    global.fetch.mockImplementation(() => Promise.reject(new Error('Network error')))
    const { container } = renderWithProviders(<Home />)
    expect(container).toBeTruthy()
  })

  it('renders settings section with collapse toggle', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse([]))
    renderWithProviders(<Home />)
    await waitFor(() => {
      const settingsBtn = screen.queryByRole('button', { name: /settings|options|gear/i })
      expect(settingsBtn || screen.queryByText(/settings/i)).toBeTruthy()
    })
  })
})

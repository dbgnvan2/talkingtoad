/**
 * Info detail (2026-09-01 spec §7.1) — the scan setting on the home page.
 *
 * The select sends `settings.info_detail` only when it is not the default,
 * so a scan started without touching it produces the byte-identical request
 * (and score) it always did.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import { renderWithProviders } from '../../test/test-utils.jsx'
import Home from '../Home.jsx'

function jsonResponse(data, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300, status,
    json: () => Promise.resolve(data), headers: new Headers(),
  })
}

function installFetch(startCalls) {
  global.fetch.mockImplementation((url, opts) => {
    const u = typeof url === 'string' ? url : url.url
    if (u.includes('/api/crawl/recent')) return jsonResponse([])
    if (u.includes('/api/crawl/discover-scope')) return jsonResponse({ is_wordpress: false, discovery_tier: 'none', types: [], categories: [] })
    if (u.includes('/api/crawl/start')) {
      startCalls.push(JSON.parse(opts.body))
      return jsonResponse({ job_id: 'job-1' })
    }
    return jsonResponse([])
  })
}

function openSettings() {
  fireEvent.click(screen.getByRole('button', { name: /advanced settings/i }))
}

describe('Home — info detail setting', () => {
  beforeEach(() => { global.fetch.mockReset(); localStorage.clear() })

  it('offers the four levels, defaulting to all', () => {
    installFetch([])
    renderWithProviders(<Home />)
    openSettings()
    const select = screen.getByLabelText(/info detail/i)
    expect(select.value).toBe('all')
    expect([...select.options].map(o => o.value)).toEqual(['all', 'notable', 'key', 'none'])
    expect(screen.getByText(/what counts toward the health score/i)).toBeInTheDocument()
  })

  it('does not send info_detail when left at the default', async () => {
    const calls = []
    installFetch(calls)
    renderWithProviders(<Home />)
    fireEvent.change(screen.getByPlaceholderText('example.org'), { target: { value: 'https://example.org' } })
    fireEvent.click(screen.getByRole('button', { name: /start crawl/i }))
    await waitFor(() => expect(calls.length).toBe(1))
    expect(calls[0].settings?.info_detail).toBeUndefined()
  })

  it('sends the chosen level with the scan', async () => {
    const calls = []
    installFetch(calls)
    renderWithProviders(<Home />)
    openSettings()
    fireEvent.change(screen.getByLabelText(/info detail/i), { target: { value: 'notable' } })
    fireEvent.change(screen.getByPlaceholderText('example.org'), { target: { value: 'https://example.org' } })
    fireEvent.click(screen.getByRole('button', { name: /start crawl/i }))
    await waitFor(() => expect(calls.length).toBe(1))
    expect(calls[0].settings.info_detail).toBe('notable')
  })
})

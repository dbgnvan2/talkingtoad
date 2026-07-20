import { describe, it, expect, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import Home from '../Home.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'

// NOTE: this file deliberately does NOT mock useCrawl, so submitting exercises
// the real startCrawl → fetch path and we can assert the content_scope payload.

const REST_DISCOVERY = {
  is_wordpress: true,
  discovery_tier: 'rest',
  types: [
    { key: 'page', label: 'Pages', rest_base: 'pages', count: 14 },
    { key: 'post', label: 'Posts', rest_base: 'posts', count: 212 },
    { key: 'event', label: 'Events', rest_base: 'events', count: 30 },
  ],
  categories: [{ id: 7, name: 'Programs', count: 41 }],
  category_scope_supported: true,
  notes: '',
}

const SITEMAP_DISCOVERY = {
  is_wordpress: true,
  discovery_tier: 'sitemap',
  types: [
    { key: 'page', label: 'Pages', rest_base: null, count: 8 },
    { key: 'post', label: 'Posts', rest_base: null, count: 40 },
  ],
  categories: [],
  category_scope_supported: false,
  notes: 'Content types were read from the site\'s sitemap.',
}

const NONE_DISCOVERY = {
  is_wordpress: false,
  discovery_tier: 'none',
  types: [],
  categories: [],
  category_scope_supported: false,
  notes: 'This site does not expose a WordPress REST API or a typed sitemap.',
}

function jsonResponse(data, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    headers: new Headers(),
  })
}

function installFetch(discovery, startCalls) {
  global.fetch.mockImplementation((url, opts) => {
    const u = typeof url === 'string' ? url : url.url
    if (u.includes('/api/crawl/recent')) return jsonResponse([])
    if (u.includes('/api/crawl/discover-scope')) return jsonResponse(discovery)
    if (u.includes('/api/crawl/start')) {
      startCalls.push(JSON.parse(opts.body))
      return jsonResponse({ job_id: 'job-1' })
    }
    return jsonResponse([])
  })
}

function setUrl(value) {
  const input = screen.getByPlaceholderText('example.org')
  fireEvent.change(input, { target: { value } })
}

async function switchToPartial() {
  fireEvent.click(screen.getByRole('radio', { name: /choose content types/i }))
}

describe('Home — scan scope (partial scan)', () => {
  beforeEach(() => {
    global.fetch.mockReset()
    localStorage.clear()
  })

  it('discovering a WP site renders content-type checkboxes with counts', async () => {
    installFetch(REST_DISCOVERY, [])
    renderWithProviders(<Home />)
    setUrl('example.com')
    await switchToPartial()

    await waitFor(() => expect(screen.getByText('Pages')).toBeInTheDocument())
    expect(screen.getByText('Posts')).toBeInTheDocument()
    expect(screen.getByText('Events')).toBeInTheDocument()
    expect(screen.getByText('14 items')).toBeInTheDocument()
    // Category multi-select appears when supported
    expect(screen.getByText(/posts by category/i)).toBeInTheDocument()
    expect(screen.getByText('Programs')).toBeInTheDocument()
  })

  it('hides the category multi-select when not supported (sitemap tier)', async () => {
    installFetch(SITEMAP_DISCOVERY, [])
    renderWithProviders(<Home />)
    setUrl('example.com')
    await switchToPartial()

    await waitFor(() => expect(screen.getByText('Pages')).toBeInTheDocument())
    expect(screen.queryByText(/posts by category/i)).not.toBeInTheDocument()
  })

  it('shows an explanatory note when no content types are found (tier none)', async () => {
    installFetch(NONE_DISCOVERY, [])
    renderWithProviders(<Home />)
    setUrl('example.com')
    await switchToPartial()

    await waitFor(() =>
      expect(screen.getByText(/does not expose a WordPress REST API/i)).toBeInTheDocument()
    )
  })

  it('includes the selected content_scope in the start payload', async () => {
    const startCalls = []
    installFetch(REST_DISCOVERY, startCalls)
    renderWithProviders(<Home />)
    setUrl('example.com')
    await switchToPartial()

    await waitFor(() => expect(screen.getByText('Pages')).toBeInTheDocument())
    fireEvent.click(screen.getByText('Pages'))       // select the Pages type
    fireEvent.click(screen.getByText('Programs'))    // and a category

    fireEvent.click(screen.getByRole('button', { name: /start crawl/i }))

    await waitFor(() => expect(startCalls.length).toBe(1))
    expect(startCalls[0].settings.content_scope).toEqual({
      mode: 'types',
      type_keys: ['page'],
      category_ids: [7],
    })
  })

  it('a full-site scan sends no content_scope', async () => {
    const startCalls = []
    installFetch(REST_DISCOVERY, startCalls)
    renderWithProviders(<Home />)
    setUrl('example.com')
    // Leave scanMode at the default 'full'.
    fireEvent.click(screen.getByRole('button', { name: /start crawl/i }))

    await waitFor(() => expect(startCalls.length).toBe(1))
    expect(startCalls[0].settings?.content_scope).toBeUndefined()
  })
})

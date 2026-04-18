import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import FixInlinePanel from '../FixInlinePanel.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

describe('FixInlinePanel', () => {
  beforeEach(() => {
    global.fetch.mockReset()
  })

  it('renders loading state while fetching WP value', () => {
    global.fetch.mockImplementation(() => new Promise(() => {})) // never resolves
    renderWithProviders(
      <FixInlinePanel jobId="j1" pageUrl="https://example.com" issueCode="TITLE_TOO_SHORT" onClose={() => {}} />
    )
    expect(screen.getByText(/Loading current WordPress value/)).toBeInTheDocument()
  })

  it('shows fetch error when WP value fetch fails', async () => {
    global.fetch.mockImplementation(() =>
      Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({ error: { message: 'Server error' } }) })
    )
    renderWithProviders(
      <FixInlinePanel jobId="j1" pageUrl="https://example.com" issueCode="TITLE_TOO_SHORT" onClose={() => {}} />
    )
    await waitFor(() => {
      expect(screen.getByText(/Error.*Server error/)).toBeInTheDocument()
    })
  })

  it('shows edit form on successful fetch', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse({ current_value: 'Old Title' }))
    renderWithProviders(
      <FixInlinePanel jobId="j1" pageUrl="https://example.com" issueCode="TITLE_TOO_SHORT" onClose={() => {}} />
    )
    await waitFor(() => {
      // "Old Title" appears in both the current value display and the textarea
      expect(screen.getAllByText('Old Title').length).toBeGreaterThanOrEqual(1)
      expect(screen.getByPlaceholderText(/Enter new/)).toBeInTheDocument()
    })
  })

  it('renders predefined fix with one-click apply', () => {
    renderWithProviders(
      <FixInlinePanel jobId="j1" pageUrl="https://example.com" issueCode="NOT_IN_SITEMAP" predefinedValue="include" onClose={() => {}} />
    )
    expect(screen.getByText(/Apply to WordPress/)).toBeInTheDocument()
  })

  it('renders mismatch dual editor for TITLE_H1_MISMATCH', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse({ current_value: 'SEO Title' }))
    renderWithProviders(
      <FixInlinePanel
        jobId="j1"
        pageUrl="https://example.com"
        issueCode="TITLE_H1_MISMATCH"
        issueExtra={{ title: 'SEO Title', h1: 'Different Heading' }}
        onClose={() => {}}
      />
    )
    await waitFor(() => {
      expect(screen.getByText(/Content H1 Heading/)).toBeInTheDocument()
    })
  })

  it('calls onClose after successful apply', async () => {
    const onClose = vi.fn()
    global.fetch
      .mockImplementationOnce(() => mockFetchResponse({ current_value: 'Old' }))
      .mockImplementationOnce(() => mockFetchResponse({ success: true }))

    renderWithProviders(
      <FixInlinePanel jobId="j1" pageUrl="https://example.com" issueCode="TITLE_TOO_SHORT" onClose={onClose} />
    )

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Enter new/)).toBeInTheDocument()
    })

    await userEvent.click(screen.getByText(/Apply to WordPress/))

    await waitFor(() => {
      expect(screen.getByText(/Applied to WordPress/)).toBeInTheDocument()
    })
  })

  it('maps META_DESC_MISSING to Meta Description label', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse({ current_value: '' }))
    renderWithProviders(
      <FixInlinePanel jobId="j1" pageUrl="https://example.com" issueCode="META_DESC_MISSING" onClose={() => {}} />
    )
    await waitFor(() => {
      expect(screen.getByText(/Meta Description/)).toBeInTheDocument()
    })
  })
})

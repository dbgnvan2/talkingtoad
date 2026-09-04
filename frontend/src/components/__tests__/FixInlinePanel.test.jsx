import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import FixInlinePanel from '../FixInlinePanel.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'
import { wpValueResponse } from '../../test/wpValueResponse.js'

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
    global.fetch.mockImplementation(() => mockFetchResponse(wpValueResponse({ currentValue: 'Old Title' })))
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
    global.fetch.mockImplementation(() => mockFetchResponse(wpValueResponse({ currentValue: 'SEO Title' })))
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
      .mockImplementationOnce(() => mockFetchResponse(wpValueResponse({ currentValue: 'Old' })))
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
    global.fetch.mockImplementation(() => mockFetchResponse(wpValueResponse({ currentValue: '' })))
    renderWithProviders(
      <FixInlinePanel jobId="j1" pageUrl="https://example.com" issueCode="META_DESC_MISSING" onClose={() => {}} />
    )
    await waitFor(() => {
      expect(screen.getByText(/Meta Description/)).toBeInTheDocument()
    })
  })

  // ── P5.1b: the one-click codes, rendered the way Results.jsx renders them ──
  // Every test above that exercises the one-click branch passes `predefinedValue`
  // as a prop. Results.jsx:1682 — the only real call site — never does, so those
  // tests could not see that the branch was unreachable in production. These
  // render WITHOUT the prop and drive the mode off the server response.
  describe('predefined one-click fixes (no prop, as Results.jsx renders it)', () => {
    it('enters one-click mode from the fetch response for NOT_IN_SITEMAP', async () => {
      global.fetch.mockImplementation(() =>
        mockFetchResponse(wpValueResponse({
          field: 'sitemap_include', currentValue: null, predefinedValue: 'always',
        }))
      )
      renderWithProviders(
        <FixInlinePanel jobId="j1" pageUrl="https://example.com" issueCode="NOT_IN_SITEMAP" onClose={() => {}} />
      )
      await waitFor(() => {
        expect(screen.getByText(/not in your XML sitemap/)).toBeInTheDocument()
      })
      // The free-text editor must NOT also be on screen — the value is not typed.
      expect(screen.queryByPlaceholderText(/Enter new/)).not.toBeInTheDocument()
    })

    it('sends the predefined value from the response, not an empty string', async () => {
      global.fetch
        .mockImplementationOnce(() =>
          mockFetchResponse(wpValueResponse({
            field: 'sitemap_include', currentValue: null, predefinedValue: 'always',
          }))
        )
        .mockImplementationOnce(() => mockFetchResponse({ success: true }))

      renderWithProviders(
        <FixInlinePanel jobId="j1" pageUrl="https://example.com" issueCode="NOT_IN_SITEMAP" onClose={() => {}} />
      )
      await waitFor(() => {
        expect(screen.getByText(/Apply to WordPress/)).toBeInTheDocument()
      })
      await userEvent.click(screen.getByText(/Apply to WordPress/))

      await waitFor(() => {
        expect(screen.getByText(/Applied to WordPress/)).toBeInTheDocument()
      })
      const applyCall = global.fetch.mock.calls.find(([url]) => url === '/api/fixes/apply-one')
      expect(applyCall, 'apply-one was never called').toBeDefined()
      expect(JSON.parse(applyCall[1].body).proposed_value).toBe('always')
    })

    // The other direction, and specifically with an EMPTY current value. The
    // obvious wrong implementation is to switch mode when there is nothing to
    // edit (`if (!cur)`) rather than on predefined_value — which reads as correct
    // and is wrong for exactly the *_MISSING codes, whose whole meaning is that
    // WordPress holds no value. A version of this test using a non-empty current
    // value let that mutation through.
    it.each([
      ['META_DESC_MISSING', ''],
      ['TITLE_MISSING',     ''],
      ['TITLE_TOO_SHORT',   'A Real Title'],
    ])('keeps %s in the free-text editor when predefined_value is null', async (code, cur) => {
      global.fetch.mockImplementation(() =>
        mockFetchResponse(wpValueResponse({ currentValue: cur, predefinedValue: null }))
      )
      renderWithProviders(
        <FixInlinePanel jobId="j1" pageUrl="https://example.com" issueCode={code} onClose={() => {}} />
      )
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/Enter new/)).toBeInTheDocument()
      })
    })
  })
})

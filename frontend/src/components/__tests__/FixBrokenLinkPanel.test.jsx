import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import FixBrokenLinkPanel from '../FixBrokenLinkPanel.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

describe('FixBrokenLinkPanel', () => {
  const defaultProps = {
    jobId: 'test-job',
    brokenUrl: 'https://example.com/broken-page',
    onClose: vi.fn(),
  }

  beforeEach(() => {
    global.fetch.mockReset()
    defaultProps.onClose.mockReset()
  })

  it('shows loading state then renders source page data', async () => {
    global.fetch.mockImplementation((url) => {
      if (typeof url === 'string' && url.includes('/api/fixes/link-sources')) {
        return mockFetchResponse([
          { source_url: 'https://example.com/page-a', link_text: 'click here' },
        ])
      }
      return mockFetchResponse({})
    })

    renderWithProviders(<FixBrokenLinkPanel {...defaultProps} />)

    // Loading state
    expect(screen.getByText(/Looking up which pages link here/)).toBeInTheDocument()

    // After fetch resolves
    await waitFor(() => {
      expect(screen.queryByText(/Looking up which pages link here/)).not.toBeInTheDocument()
    })

    // Broken URL is displayed
    expect(screen.getByText(defaultProps.brokenUrl)).toBeInTheDocument()

    // Source page is shown (shortenUrl strips scheme)
    expect(screen.getByText(/example\.com\/page-a/)).toBeInTheDocument()
  })

  it('shows the broken URL in the panel', async () => {
    global.fetch.mockImplementation(() =>
      mockFetchResponse([
        { source_url: 'https://example.com/page-a', link_text: '' },
      ])
    )

    renderWithProviders(<FixBrokenLinkPanel {...defaultProps} />)
    expect(screen.getByText(defaultProps.brokenUrl)).toBeInTheDocument()
    expect(screen.getByText('Broken Link')).toBeInTheDocument()
  })

  it('calls replace-link endpoint when apply is clicked', async () => {
    global.fetch.mockImplementation((url) => {
      if (typeof url === 'string' && url.includes('/api/fixes/link-sources')) {
        return mockFetchResponse([
          { source_url: 'https://example.com/page-a', link_text: '' },
        ])
      }
      if (typeof url === 'string' && url.includes('/api/fixes/replace-link')) {
        return mockFetchResponse({ success: true })
      }
      return mockFetchResponse({})
    })

    renderWithProviders(<FixBrokenLinkPanel {...defaultProps} />)

    // Wait for sources to load
    await waitFor(() => {
      expect(screen.getByText(/Replace in WordPress/)).toBeInTheDocument()
    })

    // Enter replacement URL
    const input = screen.getByPlaceholderText('https://example.com/new-page')
    fireEvent.change(input, { target: { value: 'https://example.com/fixed-page' } })

    // Click apply
    fireEvent.click(screen.getByText('Replace in WordPress'))

    await waitFor(() => {
      // Verify the replace-link endpoint was called
      const replaceCalls = global.fetch.mock.calls.filter(
        ([url]) => typeof url === 'string' && url.includes('/api/fixes/replace-link')
      )
      expect(replaceCalls).toHaveLength(1)

      // Verify the request body
      const body = JSON.parse(replaceCalls[0][1].body)
      expect(body.job_id).toBe('test-job')
      expect(body.old_url).toBe('https://example.com/broken-page')
      expect(body.new_url).toBe('https://example.com/fixed-page')
    })
  })

  it('shows fetch error when link-sources request fails', async () => {
    global.fetch.mockImplementation(() =>
      mockFetchResponse({ error: { message: 'Not found' } }, 404)
    )

    renderWithProviders(<FixBrokenLinkPanel {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText(/Error: Not found/)).toBeInTheDocument()
    })
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import FixManager from '../FixManager.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

describe('FixManager', () => {
  const mockJobId = 'test-job-123'

  // The component's initial load (GET /api/fixes/{jobId}) expects an array of fix objects.
  // Each fix has: id, issue_code, page_url, field, current_value, proposed_value, status, label.
  const mockFixesArray = [
    {
      id: 'fix1',
      issue_code: 'TITLE_MISSING',
      page_url: 'https://example.com/page1',
      field: 'seo_title',
      label: 'Missing page title',
      current_value: '',
      proposed_value: 'My Page Title',
      status: 'pending',
    },
    {
      id: 'fix2',
      issue_code: 'META_DESC_MISSING',
      page_url: 'https://example.com/page1',
      field: 'meta_description',
      label: 'Missing meta description',
      current_value: '',
      proposed_value: 'This is a description',
      status: 'pending',
    },
  ]

  beforeEach(() => {
    global.fetch.mockReset()
    // FixManager uses its own apiFetch that prepends http://localhost:8000
    global.fetch.mockImplementation((url) => {
      // PATCH /api/fixes/{fixId} — approve/skip/reset a fix
      if (typeof url === 'string' && url.includes('/api/fixes/fix') && url.includes('fix')) {
        return mockFetchResponse(mockFixesArray[0])
      }
      // DELETE /api/fixes/{jobId} — clear all fixes
      if (typeof url === 'string' && url.includes('/api/fixes/') && url.includes('DELETE')) {
        return mockFetchResponse({ success: true })
      }
      // GET /api/fixes/{jobId} — initial load returns array
      if (typeof url === 'string' && url.includes('/api/fixes/')) {
        return mockFetchResponse(mockFixesArray)
      }
      return mockFetchResponse({})
    })
  })

  it('renders fix manager heading', async () => {
    renderWithProviders(<FixManager jobId={mockJobId} />)

    await waitFor(() => {
      // The component renders "Fix Manager" or "Fix Manager - {domain}"
      expect(screen.getByText(/Fix Manager/)).toBeInTheDocument()
    })
  })

  it('displays fix issue codes after loading', async () => {
    renderWithProviders(<FixManager jobId={mockJobId} />)

    await waitFor(() => {
      expect(screen.getByText('TITLE_MISSING')).toBeInTheDocument()
      expect(screen.getByText('META_DESC_MISSING')).toBeInTheDocument()
    })
  })

  it('displays fix details including proposed values', async () => {
    renderWithProviders(<FixManager jobId={mockJobId} />)

    await waitFor(() => {
      // Proposed values appear as textarea values
      expect(screen.getByDisplayValue('My Page Title')).toBeInTheDocument()
      expect(screen.getByDisplayValue('This is a description')).toBeInTheDocument()
    })
  })

  it('shows page URL path for each fix group', async () => {
    renderWithProviders(<FixManager jobId={mockJobId} />)

    await waitFor(() => {
      // The component shows the path portion of page URL in a divider
      expect(screen.getByText('/page1')).toBeInTheDocument()
    })
  })

  it('displays approve button for pending fixes', async () => {
    renderWithProviders(<FixManager jobId={mockJobId} />)

    await waitFor(() => {
      const approveButtons = screen.getAllByRole('button', { name: /approve/i })
      expect(approveButtons.length).toBeGreaterThan(0)
    })
  })

  it('allows approving individual fixes', async () => {
    renderWithProviders(<FixManager jobId={mockJobId} />)

    await waitFor(() => {
      expect(screen.getByText('TITLE_MISSING')).toBeInTheDocument()
    })

    const approveButton = screen.getAllByRole('button', { name: /approve/i })[0]
    fireEvent.click(approveButton)

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/fixes/fix1'),
        expect.objectContaining({ method: 'PATCH' })
      )
    })
  })

  it('displays fix status badges', async () => {
    renderWithProviders(<FixManager jobId={mockJobId} />)

    await waitFor(() => {
      // Pending status badges
      const badges = screen.getAllByText('pending')
      expect(badges.length).toBeGreaterThan(0)
    })
  })

  it('shows initial state with load button when fetch hangs', async () => {
    global.fetch.mockImplementation(() => new Promise(() => {})) // Never resolves
    renderWithProviders(<FixManager jobId={mockJobId} />)

    // The component starts in "not generated" state — the button and the
    // informational text both mention loading, so check for the button specifically
    const loadButton = screen.getByRole('button', { name: /Load Fixes from WordPress/ })
    expect(loadButton).toBeInTheDocument()
  })

  it('handles fetch errors gracefully', async () => {
    global.fetch.mockImplementation(() => Promise.reject(new Error('Network error')))
    renderWithProviders(<FixManager jobId={mockJobId} />)

    await waitFor(() => {
      expect(screen.getByText(/Could not load existing fixes/)).toBeInTheDocument()
    })
  })

  it('allows clearing all fixes', async () => {
    renderWithProviders(<FixManager jobId={mockJobId} />)

    await waitFor(() => {
      expect(screen.getByText('TITLE_MISSING')).toBeInTheDocument()
    })

    // The "Clear & Regenerate" button only appears when generated=true
    const clearButton = screen.getByRole('button', { name: /Clear/i })
    fireEvent.click(clearButton)

    // Toast confirm dialog appears — click OK to confirm
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('OK'))

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/fixes/'),
        expect.objectContaining({ method: 'DELETE' })
      )
    })
  })
})

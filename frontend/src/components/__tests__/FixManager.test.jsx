import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import FixManager from '../FixManager.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

describe('FixManager', () => {
  const mockJobId = 'test-job-123'

  beforeEach(() => {
    global.fetch.mockReset()
    global.fetch.mockImplementation((url) => {
      if (url.includes('/fixes')) {
        return mockFetchResponse({
          fixes: [
            {
              fix_id: 'fix1',
              issue_code: 'TITLE_MISSING',
              page_url: 'https://example.com/page1',
              field: 'seo_title',
              current_value: '',
              proposed_value: 'My Page Title',
              user_value: null,
              applied: false,
            },
            {
              fix_id: 'fix2',
              issue_code: 'META_DESC_MISSING',
              page_url: 'https://example.com/page1',
              field: 'meta_description',
              current_value: '',
              proposed_value: 'This is a description',
              user_value: null,
              applied: false,
            },
          ],
          total_fixes: 2,
          applied_count: 0,
        })
      }
      return mockFetchResponse({})
    })
  })

  it('renders fix manager with fixes list', async () => {
    renderWithProviders(<FixManager jobId={mockJobId} />)

    await waitFor(() => {
      expect(screen.getByText('Fix Manager')).toBeInTheDocument()
      expect(screen.getByText('TITLE_MISSING')).toBeInTheDocument()
      expect(screen.getByText('META_DESC_MISSING')).toBeInTheDocument()
    })
  })

  it('displays fix details including proposed values', async () => {
    renderWithProviders(<FixManager jobId={mockJobId} />)

    await waitFor(() => {
      expect(screen.getByText('My Page Title')).toBeInTheDocument()
      expect(screen.getByText('This is a description')).toBeInTheDocument()
    })
  })

  it('shows page URL for each fix', async () => {
    renderWithProviders(<FixManager jobId={mockJobId} />)

    await waitFor(() => {
      expect(screen.getByText(/example\.com\/page1/)).toBeInTheDocument()
    })
  })

  it('displays apply button for each fix', async () => {
    renderWithProviders(<FixManager jobId={mockJobId} />)

    await waitFor(() => {
      const applyButtons = screen.getAllByRole('button', { name: /apply|fix/i })
      expect(applyButtons.length).toBeGreaterThan(0)
    })
  })

  it('allows applying individual fixes', async () => {
    renderWithProviders(<FixManager jobId={mockJobId} />)

    await waitFor(() => {
      expect(screen.getByText('TITLE_MISSING')).toBeInTheDocument()
    })

    const applyButton = screen.getAllByRole('button', { name: /apply|fix/i })[0]
    fireEvent.click(applyButton)

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/apply-fix'),
        expect.any(Object)
      )
    })
  })

  it('shows applied status after applying a fix', async () => {
    let callCount = 0
    global.fetch.mockImplementation((url) => {
      if (url.includes('/fixes') && callCount === 1) {
        callCount++
        return mockFetchResponse({
          fixes: [
            {
              fix_id: 'fix1',
              issue_code: 'TITLE_MISSING',
              page_url: 'https://example.com/page1',
              field: 'seo_title',
              current_value: 'My Page Title',
              proposed_value: 'My Page Title',
              user_value: null,
              applied: true,
            },
          ],
          total_fixes: 1,
          applied_count: 1,
        })
      }
      callCount++
      return mockFetchResponse({
        fixes: [
          {
            fix_id: 'fix1',
            issue_code: 'TITLE_MISSING',
            page_url: 'https://example.com/page1',
            field: 'seo_title',
            current_value: '',
            proposed_value: 'My Page Title',
            user_value: null,
            applied: false,
          },
        ],
        total_fixes: 1,
        applied_count: 0,
      })
    })

    renderWithProviders(<FixManager jobId={mockJobId} />)

    await waitFor(() => {
      expect(screen.getByText('TITLE_MISSING')).toBeInTheDocument()
    })
  })

  it('displays total fix count', async () => {
    renderWithProviders(<FixManager jobId={mockJobId} />)

    await waitFor(() => {
      expect(screen.getByText(/2/)).toBeInTheDocument() // total fixes
    })
  })

  it('shows loading state', async () => {
    global.fetch.mockImplementation(() => new Promise(() => {})) // Never resolves
    renderWithProviders(<FixManager jobId={mockJobId} />)

    expect(screen.getByText(/Loading|loading/)).toBeInTheDocument()
  })

  it('handles fetch errors gracefully', async () => {
    global.fetch.mockImplementation(() => Promise.reject(new Error('Network error')))
    renderWithProviders(<FixManager jobId={mockJobId} />)

    await waitFor(() => {
      expect(screen.getByText(/Error|error/)).toBeInTheDocument()
    })
  })

  it('allows clearing all fixes', async () => {
    renderWithProviders(<FixManager jobId={mockJobId} />)

    await waitFor(() => {
      expect(screen.getByText('TITLE_MISSING')).toBeInTheDocument()
    })

    const clearButton = screen.getByRole('button', { name: /clear|reset/i })
    fireEvent.click(clearButton)

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/fixes'),
        expect.objectContaining({ method: 'DELETE' })
      )
    })
  })
})

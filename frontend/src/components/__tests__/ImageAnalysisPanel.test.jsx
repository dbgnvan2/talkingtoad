import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import ImageAnalysisPanel from '../ImageAnalysisPanel.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

describe('ImageAnalysisPanel', () => {
  const mockJobId = 'test-job-123'
  const mockDomain = 'example.com'

  beforeEach(() => {
    global.fetch.mockReset()
    global.fetch.mockImplementation((url) => {
      if (url.includes('/images/summary')) {
        return mockFetchResponse({
          total_images: 5,
          images_with_issues: 2,
          health_score: 72,
          by_issue: {
            IMG_ALT_MISSING: 3,
            IMG_OVERSIZED: 1,
          },
        })
      }
      if (url.includes('/images')) {
        return mockFetchResponse({
          images: [
            {
              url: 'https://example.com/img1.jpg',
              title: 'Image 1',
              alt_text: 'Alt text',
              health_score: 85,
              issues: [],
              data_source: 'html_only',
              width: 800,
              height: 600,
            },
            {
              url: 'https://example.com/img2.jpg',
              title: 'Image 2',
              alt_text: '',
              health_score: 45,
              issues: [{ issue_code: 'IMG_ALT_MISSING' }],
              data_source: 'full_fetch',
              width: 1200,
              height: 800,
            },
          ],
          total: 2,
          page: 1,
          limit: 50,
        })
      }
      return mockFetchResponse({})
    })
  })

  it('renders image analysis panel with summary stats', async () => {
    renderWithProviders(
      <ImageAnalysisPanel
        jobId={mockJobId}
        domain={mockDomain}
        onPageClick={vi.fn()}
        onShowHelp={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('Image Analysis')).toBeInTheDocument()
      expect(screen.getByText(/Health Score/)).toBeInTheDocument()
    })
  })

  it('renders image summary statistics', async () => {
    renderWithProviders(
      <ImageAnalysisPanel
        jobId={mockJobId}
        domain={mockDomain}
        onPageClick={vi.fn()}
        onShowHelp={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('5')).toBeInTheDocument() // total_images
      expect(screen.getByText('72')).toBeInTheDocument() // health_score
    })
  })

  it('renders image list with cards', async () => {
    renderWithProviders(
      <ImageAnalysisPanel
        jobId={mockJobId}
        domain={mockDomain}
        onPageClick={vi.fn()}
        onShowHelp={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('Image 1')).toBeInTheDocument()
      expect(screen.getByText('Image 2')).toBeInTheDocument()
    })
  })

  it('displays health score badges for each image', async () => {
    renderWithProviders(
      <ImageAnalysisPanel
        jobId={mockJobId}
        domain={mockDomain}
        onPageClick={vi.fn()}
        onShowHelp={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('85')).toBeInTheDocument()
      expect(screen.getByText('45')).toBeInTheDocument()
    })
  })

  it('marks images with issues visually', async () => {
    renderWithProviders(
      <ImageAnalysisPanel
        jobId={mockJobId}
        domain={mockDomain}
        onPageClick={vi.fn()}
        onShowHelp={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('IMG_ALT_MISSING')).toBeInTheDocument()
    })
  })

  it('allows sorting images by score', async () => {
    renderWithProviders(
      <ImageAnalysisPanel
        jobId={mockJobId}
        domain={mockDomain}
        onPageClick={vi.fn()}
        onShowHelp={vi.fn()}
      />
    )

    await waitFor(() => {
      const sortSelect = screen.getByRole('combobox', { name: /sort/i })
      expect(sortSelect).toBeInTheDocument()
    })
  })

  it('shows loading state initially', async () => {
    global.fetch.mockImplementation(() => new Promise(() => {})) // Never resolves
    renderWithProviders(
      <ImageAnalysisPanel
        jobId={mockJobId}
        domain={mockDomain}
        onPageClick={vi.fn()}
        onShowHelp={vi.fn()}
      />
    )

    expect(screen.getByText(/Loading/i)).toBeInTheDocument()
  })

  it('displays error message on fetch failure', async () => {
    global.fetch.mockImplementation(() => Promise.reject(new Error('Network error')))
    renderWithProviders(
      <ImageAnalysisPanel
        jobId={mockJobId}
        domain={mockDomain}
        onPageClick={vi.fn()}
        onShowHelp={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument()
    })
  })

  it('allows expanding image to view details', async () => {
    renderWithProviders(
      <ImageAnalysisPanel
        jobId={mockJobId}
        domain={mockDomain}
        onPageClick={vi.fn()}
        onShowHelp={vi.fn()}
      />
    )

    await waitFor(() => {
      const expandButtons = screen.getAllByRole('button', { name: /expand|details/i })
      expect(expandButtons.length).toBeGreaterThan(0)
    })
  })
})

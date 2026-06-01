import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
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
          image_health_score: 72,
          total_size_kb: 2048,
          avg_load_time_ms: 350,
          images_analyzed: 3,
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
              filename: 'img1.jpg',
              alt: 'Alt text for image 1',
              overall_score: 85,
              performance_score: 90,
              accessibility_score: 80,
              technical_score: 85,
              semantic_score: 75,
              issues: [],
              data_source: 'html_only',
              width: 800,
              height: 600,
              page_url: 'https://example.com/page1',
            },
            {
              url: 'https://example.com/img2.jpg',
              filename: 'img2.jpg',
              alt: '',
              overall_score: 45,
              performance_score: 50,
              accessibility_score: 30,
              technical_score: 55,
              semantic_score: 40,
              issues: ['IMG_ALT_MISSING'],
              data_source: 'full_fetch',
              width: 1200,
              height: 800,
              page_url: 'https://example.com/page2',
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
      // Summary section renders stat cards
      expect(screen.getByText('Image Health')).toBeInTheDocument()
      expect(screen.getByText('Total Images')).toBeInTheDocument()
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
      expect(screen.getByText('72%')).toBeInTheDocument() // image_health_score
    })
  })

  it('renders image list with filenames', async () => {
    renderWithProviders(
      <ImageAnalysisPanel
        jobId={mockJobId}
        domain={mockDomain}
        onPageClick={vi.fn()}
        onShowHelp={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('img1.jpg')).toBeInTheDocument()
      expect(screen.getByText('img2.jpg')).toBeInTheDocument()
    })
  })

  it('displays overall score for each image', async () => {
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
      // Issues render as badges with IMG_ prefix stripped
      expect(screen.getByText('ALT_MISSING')).toBeInTheDocument()
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
      const sortSelect = screen.getByRole('combobox')
      expect(sortSelect).toBeInTheDocument()
      expect(sortSelect.value).toBe('score')
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
      expect(screen.getByText(/Network error/i)).toBeInTheDocument()
    })
  })

  it('renders expand/collapse buttons for images', async () => {
    renderWithProviders(
      <ImageAnalysisPanel
        jobId={mockJobId}
        domain={mockDomain}
        onPageClick={vi.fn()}
        onShowHelp={vi.fn()}
      />
    )

    await waitFor(() => {
      // Each ImageCard has an expand toggle button (▼ or ▲)
      const expandButtons = screen.getAllByText('▼')
      expect(expandButtons.length).toBeGreaterThan(0)
    })
  })
})

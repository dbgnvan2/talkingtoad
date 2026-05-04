import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import OptimizeExistingModal from '../OptimizeExistingModal.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

describe('OptimizeExistingModal', () => {
  const mockImage = {
    url: 'https://example.com/img1.jpg',
    filename: 'img1.jpg',
    alt: 'Example Image',
  }
  const mockJobId = 'test-job-123'

  beforeEach(() => {
    global.fetch.mockReset()
    global.fetch.mockImplementation((url) => {
      if (url.includes('/preview-optimization')) {
        return mockFetchResponse({
          original_size_kb: 450.5,
          estimated_size_kb: 85.2,
          savings_percent: 81,
          original_dimensions: [1200, 800],
          geo_location: 'San Francisco',
          page_urls: [
            'https://example.com/page1',
            'https://example.com/page2',
          ],
        })
      }
      if (url.includes('/optimize-existing')) {
        return mockFetchResponse({
          new_url: 'https://example.com/optimized-img1.webp',
          file_size_kb: 85.2,
          page_urls: [
            'https://example.com/page1',
            'https://example.com/page2',
          ],
          geo_metadata: {
            alt_text: 'Example Image Alt',
            caption: 'Caption text',
            description: 'Detailed description',
            entities_used: ['San Francisco', 'Example'],
          },
        })
      }
      return mockFetchResponse({})
    })
  })

  it('shows loading state while analyzing image', async () => {
    global.fetch.mockImplementation(() => new Promise(() => {}))
    renderWithProviders(
      <OptimizeExistingModal
        image={mockImage}
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    expect(screen.getByText(/Analyzing/)).toBeInTheDocument()
  })

  it('displays image preview after loading', async () => {
    renderWithProviders(
      <OptimizeExistingModal
        image={mockImage}
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('img1.jpg')).toBeInTheDocument()
    })
  })

  it('shows size comparison with original and optimized sizes', async () => {
    renderWithProviders(
      <OptimizeExistingModal
        image={mockImage}
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/Estimated Savings/)).toBeInTheDocument()
      expect(screen.getByText(/450.5/)).toBeInTheDocument()
      expect(screen.getByText(/85.2/)).toBeInTheDocument()
    })
  })

  it('displays savings percentage', async () => {
    renderWithProviders(
      <OptimizeExistingModal
        image={mockImage}
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('81%')).toBeInTheDocument()
    })
  })

  it('lists pages where image is used', async () => {
    renderWithProviders(
      <OptimizeExistingModal
        image={mockImage}
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/example\.com\/page1/)).toBeInTheDocument()
      expect(screen.getByText(/example\.com\/page2/)).toBeInTheDocument()
    })
  })

  it('allows changing target width', async () => {
    renderWithProviders(
      <OptimizeExistingModal
        image={mockImage}
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await waitFor(() => {
      const widthInput = screen.getByDisplayValue('1200')
      fireEvent.change(widthInput, { target: { value: '800' } })
      expect(widthInput.value).toBe('800')
    })
  })

  it('allows entering SEO keyword', async () => {
    renderWithProviders(
      <OptimizeExistingModal
        image={mockImage}
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await waitFor(() => {
      const keywordInput = screen.getByPlaceholderText(/therapy session/)
      fireEvent.change(keywordInput, { target: { value: 'example keyword' } })
      expect(keywordInput.value).toBe('example keyword')
    })
  })

  it('displays optimize button', async () => {
    renderWithProviders(
      <OptimizeExistingModal
        image={mockImage}
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('Optimize & Upload')).toBeInTheDocument()
    })
  })

  it('starts optimization when button clicked', async () => {
    renderWithProviders(
      <OptimizeExistingModal
        image={mockImage}
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await waitFor(() => {
      const optimizeButton = screen.getByText('Optimize & Upload')
      fireEvent.click(optimizeButton)

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/optimize-existing'),
        expect.any(Object)
      )
    })
  })

  it('shows optimizing state during process', async () => {
    renderWithProviders(
      <OptimizeExistingModal
        image={mockImage}
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await waitFor(() => {
      const optimizeButton = screen.getByText('Optimize & Upload')
      fireEvent.click(optimizeButton)
    })

    await waitFor(() => {
      expect(screen.getByText(/optimizing/i)).toBeInTheDocument()
    })
  })

  it('displays success message after optimization', async () => {
    renderWithProviders(
      <OptimizeExistingModal
        image={mockImage}
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await waitFor(() => {
      const optimizeButton = screen.getByText('Optimize & Upload')
      fireEvent.click(optimizeButton)
    })

    await waitFor(() => {
      expect(screen.getByText(/Optimization Complete/)).toBeInTheDocument()
    })
  })

  it('displays new optimized image URL', async () => {
    renderWithProviders(
      <OptimizeExistingModal
        image={mockImage}
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await waitFor(() => {
      const optimizeButton = screen.getByText('Optimize & Upload')
      fireEvent.click(optimizeButton)
    })

    await waitFor(() => {
      expect(screen.getByDisplayValue(/optimized-img1\.webp/)).toBeInTheDocument()
    })
  })

  it('shows copy button for new URL', async () => {
    renderWithProviders(
      <OptimizeExistingModal
        image={mockImage}
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await waitFor(() => {
      const optimizeButton = screen.getByText('Optimize & Upload')
      fireEvent.click(optimizeButton)
    })

    await waitFor(() => {
      expect(screen.getByText('Copy')).toBeInTheDocument()
    })
  })

  it('displays geo metadata if generated', async () => {
    renderWithProviders(
      <OptimizeExistingModal
        image={mockImage}
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await waitFor(() => {
      const optimizeButton = screen.getByText('Optimize & Upload')
      fireEvent.click(optimizeButton)
    })

    await waitFor(() => {
      expect(screen.getByText(/AI-Generated Metadata/)).toBeInTheDocument()
      expect(screen.getByText('Example Image Alt')).toBeInTheDocument()
    })
  })

  it('displays next steps instructions', async () => {
    renderWithProviders(
      <OptimizeExistingModal
        image={mockImage}
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await waitFor(() => {
      const optimizeButton = screen.getByText('Optimize & Upload')
      fireEvent.click(optimizeButton)
    })

    await waitFor(() => {
      expect(screen.getByText(/Next Steps/)).toBeInTheDocument()
      expect(screen.getByText(/replace the old image/)).toBeInTheDocument()
    })
  })

  it('calls onSuccess callback when optimization completes', async () => {
    const mockOnSuccess = vi.fn()
    renderWithProviders(
      <OptimizeExistingModal
        image={mockImage}
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={mockOnSuccess}
      />
    )

    await waitFor(() => {
      const optimizeButton = screen.getByText('Optimize & Upload')
      fireEvent.click(optimizeButton)
    })

    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalled()
    })
  })

  it('displays error message on failure', async () => {
    global.fetch.mockImplementation((url) => {
      if (url.includes('/preview-optimization')) {
        return Promise.reject(new Error('Network error'))
      }
      return mockFetchResponse({})
    })

    renderWithProviders(
      <OptimizeExistingModal
        image={mockImage}
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/Error/)).toBeInTheDocument()
    })
  })
})

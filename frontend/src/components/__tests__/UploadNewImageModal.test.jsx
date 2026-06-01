import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import UploadNewImageModal from '../UploadNewImageModal.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

describe('UploadNewImageModal', () => {
  const mockJobId = 'test-job-123'

  beforeEach(() => {
    global.fetch.mockReset()
    // Mock URL.createObjectURL for file preview
    if (!global.URL.createObjectURL) {
      global.URL.createObjectURL = vi.fn(() => 'blob:mock-url')
    }
    if (!global.URL.revokeObjectURL) {
      global.URL.revokeObjectURL = vi.fn()
    }

    global.fetch.mockImplementation((url) => {
      if (typeof url === 'string' && url.includes('/optimize-upload-preview')) {
        return mockFetchResponse({
          original_size_kb: 500,
          estimated_size_kb: 85,
          savings_percent: 83,
          original_dimensions: [1920, 1080],
          geo_location: 'San Francisco',
          suggested_filename: 'test-image-small.webp',
        })
      }
      if (typeof url === 'string' && url.includes('/optimize-upload')) {
        return mockFetchResponse({
          new_url: 'https://example.com/uploads/optimized-img.webp',
          file_size_kb: 42.5,
          message: 'Image uploaded successfully',
        })
      }
      return mockFetchResponse({})
    })
  })

  /** Helper: simulate selecting a file, which triggers preview loading */
  async function selectFile(container) {
    const file = new File(['test-image-data'], 'test.jpg', { type: 'image/jpeg' })
    Object.defineProperty(file, 'size', { value: 1024 * 100 }) // 100KB

    const fileInput = container.querySelector('input[type="file"]')
    fireEvent.change(fileInput, { target: { files: [file] } })

    // Wait for preview to load
    await waitFor(() => {
      expect(screen.getByText('Optimize & Upload')).toBeInTheDocument()
    })
  }

  it('renders upload modal with title', () => {
    renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    expect(screen.getByText(/Upload/)).toBeInTheDocument()
  })

  it('displays file input area for selecting image', () => {
    const { container } = renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    // The component has a "Browse Files" button and a hidden file input
    expect(screen.getByText('Browse Files')).toBeInTheDocument()
    expect(container.querySelector('input[type="file"]')).toBeInTheDocument()
  })

  it('displays format requirements', () => {
    renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    expect(screen.getByText(/JPEG|PNG|WebP|GIF/i)).toBeInTheDocument()
  })

  it('displays file size requirements', () => {
    renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    expect(screen.getByText(/max|20MB/i)).toBeInTheDocument()
  })

  it('allows setting target width after file selection', async () => {
    const { container } = renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await selectFile(container)

    const widthInput = screen.getByDisplayValue('1200')
    fireEvent.change(widthInput, { target: { value: '800' } })
    expect(widthInput.value).toBe('800')
  })

  it('allows toggling GPS injection after file selection', async () => {
    const { container } = renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await selectFile(container)

    // GPS checkbox is labeled "Inject GPS coordinates (...)"
    const gpsCheckbox = container.querySelector('input[type="checkbox"]#applyGps')
    expect(gpsCheckbox).toBeInTheDocument()
    expect(gpsCheckbox.checked).toBe(true)
    fireEvent.click(gpsCheckbox)
    expect(gpsCheckbox.checked).toBe(false)
  })

  it('displays upload button', () => {
    renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    expect(screen.getByText(/Upload/)).toBeInTheDocument()
  })

  it('displays cancel button', () => {
    const mockOnClose = vi.fn()
    renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={mockOnClose}
        onSuccess={vi.fn()}
      />
    )

    const cancelButton = screen.getByText('Cancel')
    fireEvent.click(cancelButton)
    expect(mockOnClose).toHaveBeenCalled()
  })

  it('shows optimizing state during upload', async () => {
    const { container } = renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await selectFile(container)

    // Make the optimize-upload call hang
    global.fetch.mockImplementation(() => new Promise(() => {}))

    fireEvent.click(screen.getByText('Optimize & Upload'))

    await waitFor(() => {
      // Text appears in both header subtitle and body
      expect(screen.getAllByText(/Optimizing and uploading|uploading/).length).toBeGreaterThan(0)
    })
  })

  it('displays success message after upload', async () => {
    const { container } = renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await selectFile(container)
    fireEvent.click(screen.getByText('Optimize & Upload'))

    await waitFor(() => {
      // "Upload complete!" appears in both header and body
      expect(screen.getAllByText(/Upload Complete/i).length).toBeGreaterThan(0)
    })
  })

  it('displays new URL after successful upload', async () => {
    const { container } = renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await selectFile(container)
    fireEvent.click(screen.getByText('Optimize & Upload'))

    await waitFor(() => {
      expect(screen.getByDisplayValue(/optimized-img\.webp/)).toBeInTheDocument()
    })
  })

  it('displays file size of uploaded image', async () => {
    const { container } = renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await selectFile(container)
    fireEvent.click(screen.getByText('Optimize & Upload'))

    await waitFor(() => {
      // formatSize(42.5) = "43 KB"
      expect(screen.getByText(/43 KB/)).toBeInTheDocument()
    })
  })

  it('shows copy button for new URL', async () => {
    const { container } = renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await selectFile(container)
    fireEvent.click(screen.getByText('Optimize & Upload'))

    await waitFor(() => {
      expect(screen.getByText('Copy')).toBeInTheDocument()
    })
  })

  it('calls onSuccess callback after upload completes', async () => {
    const mockOnSuccess = vi.fn()
    const { container } = renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={mockOnSuccess}
      />
    )

    await selectFile(container)
    fireEvent.click(screen.getByText('Optimize & Upload'))

    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalled()
    })
  })

  it('displays error message on upload failure', async () => {
    const { container } = renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await selectFile(container)

    // Make the optimize-upload call fail
    global.fetch.mockImplementation(() =>
      mockFetchResponse({ error: { message: 'File size exceeds maximum' } }, 400)
    )

    fireEvent.click(screen.getByText('Optimize & Upload'))

    await waitFor(() => {
      // "Error" appears in both header subtitle and error body
      expect(screen.getAllByText(/Error/).length).toBeGreaterThan(0)
    })
  })

  it('allows retry after error', async () => {
    const { container } = renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await selectFile(container)

    // First call fails
    global.fetch.mockImplementationOnce(() =>
      mockFetchResponse({ error: { message: 'Server error' } }, 500)
    )

    fireEvent.click(screen.getByText('Optimize & Upload'))

    await waitFor(() => {
      expect(screen.getAllByText(/Error/).length).toBeGreaterThan(0)
    })

    // "Try again with different file" resets to select step
    const retryButton = screen.getByText(/Try again/i)
    fireEvent.click(retryButton)

    await waitFor(() => {
      // Back at select step
      expect(screen.getByText('Browse Files')).toBeInTheDocument()
    })
  })
})

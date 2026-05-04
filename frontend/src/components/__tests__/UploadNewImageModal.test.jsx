import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import UploadNewImageModal from '../UploadNewImageModal.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

describe('UploadNewImageModal', () => {
  const mockJobId = 'test-job-123'

  beforeEach(() => {
    global.fetch.mockReset()
    global.fetch.mockImplementation((url) => {
      if (url.includes('/upload-image')) {
        return mockFetchResponse({
          success: true,
          new_url: 'https://example.com/uploads/optimized-img.webp',
          file_size_kb: 42.5,
          message: 'Image uploaded successfully',
        })
      }
      if (url.includes('/validate-upload')) {
        return mockFetchResponse({
          valid: true,
          error: null,
          file_size_kb: 500,
        })
      }
      return mockFetchResponse({})
    })
  })

  it('renders upload modal with title', () => {
    renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    expect(screen.getByText(/Upload|upload/)).toBeInTheDocument()
  })

  it('displays file input for selecting image', () => {
    renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    const fileInput = screen.getByRole('button', { name: /choose|select|upload/i })
    expect(fileInput).toBeInTheDocument()
  })

  it('displays format requirements', () => {
    renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    expect(screen.getByText(/JPG|JPEG|PNG|WebP/i)).toBeInTheDocument()
  })

  it('displays file size requirements', () => {
    renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    expect(screen.getByText(/max|maximum|size|MB/i)).toBeInTheDocument()
  })

  it('allows setting target width', () => {
    renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    const widthInput = screen.getByDisplayValue('1200')
    fireEvent.change(widthInput, { target: { value: '800' } })
    expect(widthInput.value).toBe('800')
  })

  it('allows toggling GPS injection', () => {
    renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    const gpsCheckbox = screen.getByRole('checkbox', { name: /GPS|coordinates/i })
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

    expect(screen.getByText(/Upload|upload/)).toBeInTheDocument()
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

  it('shows uploading state during upload', async () => {
    renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    global.fetch.mockImplementation(() => new Promise(() => {}))

    const uploadButton = screen.getAllByText(/Upload/)[0]
    fireEvent.click(uploadButton)

    await waitFor(() => {
      expect(screen.getByText(/Uploading|uploading|processing/)).toBeInTheDocument()
    })
  })

  it('displays success message after upload', async () => {
    renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    const uploadButton = screen.getAllByText(/Upload/)[0]
    fireEvent.click(uploadButton)

    await waitFor(() => {
      expect(screen.getByText(/success|successful|complete/i)).toBeInTheDocument()
    })
  })

  it('displays new URL after successful upload', async () => {
    renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    const uploadButton = screen.getAllByText(/Upload/)[0]
    fireEvent.click(uploadButton)

    await waitFor(() => {
      expect(screen.getByDisplayValue(/optimized-img\.webp/)).toBeInTheDocument()
    })
  })

  it('displays file size of uploaded image', async () => {
    renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    const uploadButton = screen.getAllByText(/Upload/)[0]
    fireEvent.click(uploadButton)

    await waitFor(() => {
      expect(screen.getByText(/42.5/)).toBeInTheDocument()
    })
  })

  it('shows copy button for new URL', async () => {
    renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    const uploadButton = screen.getAllByText(/Upload/)[0]
    fireEvent.click(uploadButton)

    await waitFor(() => {
      expect(screen.getByText('Copy')).toBeInTheDocument()
    })
  })

  it('calls onSuccess callback after upload completes', async () => {
    const mockOnSuccess = vi.fn()
    renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={mockOnSuccess}
      />
    )

    const uploadButton = screen.getAllByText(/Upload/)[0]
    fireEvent.click(uploadButton)

    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalled()
    })
  })

  it('displays error message on upload failure', async () => {
    global.fetch.mockImplementation((url) => {
      if (url.includes('/upload-image')) {
        return mockFetchResponse({
          success: false,
          error: 'File size exceeds maximum',
        }, { status: 400 })
      }
      return mockFetchResponse({})
    })

    renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    const uploadButton = screen.getAllByText(/Upload/)[0]
    fireEvent.click(uploadButton)

    await waitFor(() => {
      expect(screen.getByText(/error|Error/)).toBeInTheDocument()
    })
  })

  it('allows retry after error', async () => {
    let callCount = 0
    global.fetch.mockImplementation((url) => {
      if (url.includes('/upload-image')) {
        if (callCount === 0) {
          callCount++
          return mockFetchResponse({
            success: false,
            error: 'Network error',
          }, { status: 500 })
        }
        return mockFetchResponse({
          success: true,
          new_url: 'https://example.com/uploads/optimized-img.webp',
          file_size_kb: 42.5,
        })
      }
      return mockFetchResponse({})
    })

    renderWithProviders(
      <UploadNewImageModal
        jobId={mockJobId}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    const uploadButton = screen.getAllByText(/Upload/)[0]
    fireEvent.click(uploadButton)

    await waitFor(() => {
      expect(screen.getByText(/error|Error/)).toBeInTheDocument()
    })

    const retryButton = screen.getByText(/Try again|Retry/i)
    fireEvent.click(retryButton)

    await waitFor(() => {
      expect(screen.getByText(/success|successful/i)).toBeInTheDocument()
    })
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import BatchOptimizePanel from '../BatchOptimizePanel.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

describe('BatchOptimizePanel', () => {
  const mockJobId = 'test-job-123'
  const mockImages = [
    { url: 'https://example.com/img1.jpg', filename: 'img1.jpg' },
    { url: 'https://example.com/img2.jpg', filename: 'img2.jpg' },
    { url: 'https://example.com/img3.jpg', filename: 'img3.jpg' },
  ]

  beforeEach(() => {
    global.fetch.mockReset()
    global.fetch.mockImplementation((url) => {
      if (url.includes('/batch-optimize')) {
        return mockFetchResponse({ batch_id: 'batch-123' })
      }
      if (url.includes('/batch-status')) {
        return mockFetchResponse({
          status: 'running',
          total: 3,
          completed: 1,
          failed: 0,
          progress_percent: 33,
          results: [
            {
              image_url: 'https://example.com/img1.jpg',
              success: true,
              file_size_kb: 45.2,
            },
          ],
        })
      }
      return mockFetchResponse({})
    })
  })

  it('renders batch optimize panel header', () => {
    renderWithProviders(
      <BatchOptimizePanel
        jobId={mockJobId}
        selectedImages={mockImages}
        onClose={vi.fn()}
        onComplete={vi.fn()}
      />
    )

    expect(screen.getByText('Batch Optimize')).toBeInTheDocument()
    expect(screen.getByText(/3 images selected/)).toBeInTheDocument()
  })

  it('displays optimization options before starting', () => {
    renderWithProviders(
      <BatchOptimizePanel
        jobId={mockJobId}
        selectedImages={mockImages}
        onClose={vi.fn()}
        onComplete={vi.fn()}
      />
    )

    expect(screen.getByText(/Target Width/)).toBeInTheDocument()
    expect(screen.getByText(/Parallel Limit/)).toBeInTheDocument()
    expect(screen.getByText(/Inject GPS/)).toBeInTheDocument()
  })

  it('allows setting target width', () => {
    renderWithProviders(
      <BatchOptimizePanel
        jobId={mockJobId}
        selectedImages={mockImages}
        onClose={vi.fn()}
        onComplete={vi.fn()}
      />
    )

    const widthInput = screen.getByDisplayValue('1200')
    fireEvent.change(widthInput, { target: { value: '800' } })
    expect(widthInput.value).toBe('800')
  })

  it('allows selecting parallel limit', () => {
    renderWithProviders(
      <BatchOptimizePanel
        jobId={mockJobId}
        selectedImages={mockImages}
        onClose={vi.fn()}
        onComplete={vi.fn()}
      />
    )

    const parallelSelect = screen.getByDisplayValue('3')
    fireEvent.change(parallelSelect, { target: { value: '5' } })
    expect(parallelSelect.value).toBe('5')
  })

  it('allows toggling GPS injection', () => {
    renderWithProviders(
      <BatchOptimizePanel
        jobId={mockJobId}
        selectedImages={mockImages}
        onClose={vi.fn()}
        onComplete={vi.fn()}
      />
    )

    const gpsCheckbox = screen.getByRole('checkbox', { name: /GPS/i })
    fireEvent.click(gpsCheckbox)
    expect(gpsCheckbox.checked).toBe(false)
  })

  it('displays start batch button', () => {
    renderWithProviders(
      <BatchOptimizePanel
        jobId={mockJobId}
        selectedImages={mockImages}
        onClose={vi.fn()}
        onComplete={vi.fn()}
      />
    )

    expect(screen.getByText('Start Batch')).toBeInTheDocument()
  })

  it('starts batch optimization when button clicked', async () => {
    renderWithProviders(
      <BatchOptimizePanel
        jobId={mockJobId}
        selectedImages={mockImages}
        onClose={vi.fn()}
        onComplete={vi.fn()}
      />
    )

    const startButton = screen.getByText('Start Batch')
    fireEvent.click(startButton)

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/batch-optimize'),
        expect.any(Object)
      )
    })
  })

  it('displays progress bar during optimization', async () => {
    renderWithProviders(
      <BatchOptimizePanel
        jobId={mockJobId}
        selectedImages={mockImages}
        onClose={vi.fn()}
        onComplete={vi.fn()}
      />
    )

    const startButton = screen.getByText('Start Batch')
    fireEvent.click(startButton)

    await waitFor(() => {
      expect(screen.getByText(/Processing.../)).toBeInTheDocument()
    })
  })

  it('displays progress percentage', async () => {
    renderWithProviders(
      <BatchOptimizePanel
        jobId={mockJobId}
        selectedImages={mockImages}
        onClose={vi.fn()}
        onComplete={vi.fn()}
      />
    )

    const startButton = screen.getByText('Start Batch')
    fireEvent.click(startButton)

    await waitFor(() => {
      expect(screen.getByText(/33%/)).toBeInTheDocument()
    })
  })

  it('displays pause button during optimization', async () => {
    renderWithProviders(
      <BatchOptimizePanel
        jobId={mockJobId}
        selectedImages={mockImages}
        onClose={vi.fn()}
        onComplete={vi.fn()}
      />
    )

    const startButton = screen.getByText('Start Batch')
    fireEvent.click(startButton)

    await waitFor(() => {
      expect(screen.getByText('Pause')).toBeInTheDocument()
    })
  })

  it('displays results table after optimization', async () => {
    renderWithProviders(
      <BatchOptimizePanel
        jobId={mockJobId}
        selectedImages={mockImages}
        onClose={vi.fn()}
        onComplete={vi.fn()}
      />
    )

    const startButton = screen.getByText('Start Batch')
    fireEvent.click(startButton)

    await waitFor(() => {
      expect(screen.getByText(/Image/)).toBeInTheDocument()
      expect(screen.getByText(/Status/)).toBeInTheDocument()
      expect(screen.getByText(/Size/)).toBeInTheDocument()
    })
  })

  it('displays close button', () => {
    const mockOnClose = vi.fn()
    renderWithProviders(
      <BatchOptimizePanel
        jobId={mockJobId}
        selectedImages={mockImages}
        onClose={mockOnClose}
        onComplete={vi.fn()}
      />
    )

    const cancelButton = screen.getByText('Cancel')
    fireEvent.click(cancelButton)
    expect(mockOnClose).toHaveBeenCalled()
  })
})

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react'
import React from 'react'
import { ToastProvider, useToast } from '../ToastContext.jsx'

// Helper component that exposes toast actions via buttons
function ToastConsumer() {
  const toast = useToast()
  return (
    <div>
      <button onClick={() => toast.success('Success message')}>Show Success</button>
      <button onClick={() => toast.error('Error message')}>Show Error</button>
      <button onClick={() => toast.info('Info message')}>Show Info</button>
      <button onClick={async () => {
        const result = await toast.confirm('Confirm this?')
        // Write the result somewhere testable
        document.title = result ? 'confirmed' : 'cancelled'
      }}>Show Confirm</button>
    </div>
  )
}

describe('ToastContext', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('useToast throws when used outside ToastProvider', () => {
    // Suppress error boundary output
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<ToastConsumer />)).toThrow('useToast must be used within ToastProvider')
    spy.mockRestore()
  })

  it('toast.success renders role="status" with message', () => {
    render(
      <ToastProvider>
        <ToastConsumer />
      </ToastProvider>
    )

    fireEvent.click(screen.getByText('Show Success'))

    const toast = screen.getByRole('status')
    expect(toast).toBeInTheDocument()
    expect(toast).toHaveTextContent('Success message')
  })

  it('toast.error renders role="status" with message and persists (dismiss button present)', () => {
    render(
      <ToastProvider>
        <ToastConsumer />
      </ToastProvider>
    )

    fireEvent.click(screen.getByText('Show Error'))

    const toast = screen.getByRole('status')
    expect(toast).toBeInTheDocument()
    expect(toast).toHaveTextContent('Error message')

    // Error toasts persist — dismiss button should be present
    const dismissButton = screen.getByLabelText('Dismiss')
    expect(dismissButton).toBeInTheDocument()
  })

  it('toast.info renders role="status" with message', () => {
    render(
      <ToastProvider>
        <ToastConsumer />
      </ToastProvider>
    )

    fireEvent.click(screen.getByText('Show Info'))

    const toast = screen.getByRole('status')
    expect(toast).toBeInTheDocument()
    expect(toast).toHaveTextContent('Info message')
  })

  it('success toast auto-dismisses after 4 seconds', () => {
    render(
      <ToastProvider>
        <ToastConsumer />
      </ToastProvider>
    )

    fireEvent.click(screen.getByText('Show Success'))
    expect(screen.getByRole('status')).toBeInTheDocument()

    // Advance past the 4s timeout
    act(() => {
      vi.advanceTimersByTime(4100)
    })

    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('error toast does NOT auto-dismiss', () => {
    render(
      <ToastProvider>
        <ToastConsumer />
      </ToastProvider>
    )

    fireEvent.click(screen.getByText('Show Error'))
    expect(screen.getByRole('status')).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(10000)
    })

    // Still present
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('error toast can be dismissed via dismiss button', () => {
    render(
      <ToastProvider>
        <ToastConsumer />
      </ToastProvider>
    )

    fireEvent.click(screen.getByText('Show Error'))
    expect(screen.getByRole('status')).toBeInTheDocument()

    fireEvent.click(screen.getByLabelText('Dismiss'))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('toast.confirm renders dialog with role="dialog" and aria-modal="true"', () => {
    render(
      <ToastProvider>
        <ToastConsumer />
      </ToastProvider>
    )

    fireEvent.click(screen.getByText('Show Confirm'))

    const dialog = screen.getByRole('dialog')
    expect(dialog).toBeInTheDocument()
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(screen.getByText('Confirm this?')).toBeInTheDocument()
  })

  it('toast.confirm resolves true on OK click', async () => {
    vi.useRealTimers() // need real timers for promise resolution

    render(
      <ToastProvider>
        <ToastConsumer />
      </ToastProvider>
    )

    fireEvent.click(screen.getByText('Show Confirm'))

    const okButton = screen.getByText('OK')
    fireEvent.click(okButton)

    await waitFor(() => {
      expect(document.title).toBe('confirmed')
    })

    // Dialog should be dismissed
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('toast.confirm resolves false on Cancel click', async () => {
    vi.useRealTimers()

    render(
      <ToastProvider>
        <ToastConsumer />
      </ToastProvider>
    )

    fireEvent.click(screen.getByText('Show Confirm'))

    const cancelButton = screen.getByText('Cancel')
    fireEvent.click(cancelButton)

    await waitFor(() => {
      expect(document.title).toBe('cancelled')
    })

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('toast.confirm resolves false on backdrop click', async () => {
    vi.useRealTimers()

    render(
      <ToastProvider>
        <ToastConsumer />
      </ToastProvider>
    )

    fireEvent.click(screen.getByText('Show Confirm'))

    // Click the backdrop (the dialog overlay itself)
    const dialog = screen.getByRole('dialog')
    fireEvent.click(dialog)

    await waitFor(() => {
      expect(document.title).toBe('cancelled')
    })

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

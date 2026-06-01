import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import ErrorBoundary from '../ErrorBoundary.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'

// Suppress console.error for the expected boundary logging
const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

afterEach(() => {
  consoleSpy.mockClear()
})

function ThrowingChild() {
  throw new Error('Test crash')
}

describe('ErrorBoundary', () => {
  it('renders children normally when no error is thrown', () => {
    renderWithProviders(
      <ErrorBoundary>
        <p>All good</p>
      </ErrorBoundary>
    )
    expect(screen.getByText('All good')).toBeInTheDocument()
    expect(screen.queryByText('Something Went Wrong')).not.toBeInTheDocument()
  })

  it('catches a thrown error and shows fallback UI', () => {
    renderWithProviders(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>
    )
    expect(screen.getByText('Something Went Wrong')).toBeInTheDocument()
    expect(screen.getByText(/unexpected error/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /refresh page/i })).toBeInTheDocument()
    expect(screen.queryByText('All good')).not.toBeInTheDocument()
  })

  it('displays the error message in the details section', () => {
    renderWithProviders(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>
    )
    expect(screen.getByText('Error details')).toBeInTheDocument()
    expect(screen.getByText('Test crash')).toBeInTheDocument()
  })
})

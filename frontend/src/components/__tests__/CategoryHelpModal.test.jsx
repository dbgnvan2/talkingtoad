import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CategoryHelpModal from '../CategoryHelpModal.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'

describe('CategoryHelpModal', () => {
  it('renders null when no categoryKey is provided', () => {
    renderWithProviders(
      <CategoryHelpModal categoryKey={null} onClose={() => {}} />
    )
    // Component should not render any modal content
    expect(screen.queryByRole('button', { name: /close category help/i })).not.toBeInTheDocument()
  })

  it('renders null for unknown category', () => {
    renderWithProviders(
      <CategoryHelpModal categoryKey="nonexistent" onClose={() => {}} />
    )
    // Component should not render any modal content
    expect(screen.queryByRole('button', { name: /close category help/i })).not.toBeInTheDocument()
  })

  it('renders modal content for metadata category', () => {
    renderWithProviders(
      <CategoryHelpModal categoryKey="metadata" onClose={() => {}} />
    )
    // Modal should render (not null)
    expect(screen.getByRole('button', { name: /close category help/i })).toBeInTheDocument()
  })

  it('calls onClose when backdrop is clicked', async () => {
    const onClose = vi.fn()
    const { container } = renderWithProviders(
      <CategoryHelpModal categoryKey="metadata" onClose={onClose} />
    )
    // Click the backdrop (the outer fixed div)
    const backdrop = container.querySelector('.fixed')
    await userEvent.click(backdrop)
    expect(onClose).toHaveBeenCalled()
  })
})

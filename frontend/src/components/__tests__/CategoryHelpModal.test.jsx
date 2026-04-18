import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CategoryHelpModal from '../CategoryHelpModal.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'

describe('CategoryHelpModal', () => {
  it('renders null when no categoryKey is provided', () => {
    const { container } = renderWithProviders(
      <CategoryHelpModal categoryKey={null} onClose={() => {}} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders null for unknown category', () => {
    const { container } = renderWithProviders(
      <CategoryHelpModal categoryKey="nonexistent" onClose={() => {}} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders modal content for metadata category', () => {
    renderWithProviders(
      <CategoryHelpModal categoryKey="metadata" onClose={() => {}} />
    )
    // Modal should render (not null)
    expect(screen.getByRole('button', { name: /×/ })).toBeInTheDocument()
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

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import SeverityBadge from '../SeverityBadge.jsx'

describe('SeverityBadge', () => {
  it('renders critical severity with red styling', () => {
    render(<SeverityBadge severity="critical" />)
    const badge = screen.getByText('critical')
    expect(badge).toBeInTheDocument()
    expect(badge.className).toContain('bg-red-100')
  })

  it('renders warning severity with amber styling', () => {
    render(<SeverityBadge severity="warning" />)
    const badge = screen.getByText('warning')
    expect(badge).toBeInTheDocument()
    expect(badge.className).toContain('bg-amber-100')
  })

  it('renders info severity with blue styling', () => {
    render(<SeverityBadge severity="info" />)
    const badge = screen.getByText('info')
    expect(badge).toBeInTheDocument()
    expect(badge.className).toContain('bg-blue-100')
  })

  it('falls back to gray for unknown severity', () => {
    render(<SeverityBadge severity="unknown" />)
    const badge = screen.getByText('unknown')
    expect(badge.className).toContain('bg-gray-100')
  })
})

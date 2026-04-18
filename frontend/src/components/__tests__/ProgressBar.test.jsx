import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import ProgressBar from '../ProgressBar.jsx'

describe('ProgressBar', () => {
  it('renders indeterminate state when pct is null', () => {
    const { container } = render(<ProgressBar pct={null} />)
    const bar = container.querySelector('.animate-pulse')
    expect(bar).toBeInTheDocument()
  })

  it('renders indeterminate state when pct is undefined', () => {
    const { container } = render(<ProgressBar />)
    const bar = container.querySelector('.animate-pulse')
    expect(bar).toBeInTheDocument()
  })

  it('renders 0% width for pct=0', () => {
    const { container } = render(<ProgressBar pct={0} />)
    const bar = container.querySelector('[style]')
    expect(bar.style.width).toBe('0%')
  })

  it('renders 50% width for pct=50', () => {
    const { container } = render(<ProgressBar pct={50} />)
    const bar = container.querySelector('[style]')
    expect(bar.style.width).toBe('50%')
  })

  it('renders 100% width for pct=100', () => {
    const { container } = render(<ProgressBar pct={100} />)
    const bar = container.querySelector('[style]')
    expect(bar.style.width).toBe('100%')
  })

  it('clamps values above 100', () => {
    const { container } = render(<ProgressBar pct={150} />)
    const bar = container.querySelector('[style]')
    expect(bar.style.width).toBe('100%')
  })

  it('clamps negative values to 0', () => {
    const { container } = render(<ProgressBar pct={-10} />)
    const bar = container.querySelector('[style]')
    expect(bar.style.width).toBe('0%')
  })
})

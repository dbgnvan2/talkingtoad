import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import { renderWithProviders } from '../../test/test-utils.jsx'
import PagePriorityPanel from '../PagePriorityPanel.jsx'

describe('PagePriorityPanel', () => {
  beforeEach(() => {
    global.fetch.mockReset()
  })

  it('renders the rank button initially (opt-in)', () => {
    renderWithProviders(<PagePriorityPanel jobId="job1" />)
    expect(screen.getByText(/Rank pages/)).toBeInTheDocument()
  })

  it('shows the V4 explainer when help is toggled', () => {
    renderWithProviders(<PagePriorityPanel jobId="job1" />)
    fireEvent.click(screen.getByLabelText(/Learn more about the page priority/))
    expect(screen.getByText(/What it is:/)).toBeInTheDocument()
    expect(screen.getByText(/How it can mislead:/)).toBeInTheDocument()
  })

  it('loads and renders ranked pages with bucket badges', async () => {
    global.fetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          pages: [
            { url: 'https://x/a', health_score: 40, gsc: { clicks: 5, impressions: 200 }, review_flag: { flagged: true, reasons: ['Vulnerable Star'] }, priority_rank: 1, bucket: 'Vulnerable Star' },
            { url: 'https://x/b', health_score: 90, gsc: null, review_flag: { flagged: false, reasons: [] }, priority_rank: 2, bucket: 'OK' },
          ],
          total: 2,
        }),
      })
    )
    renderWithProviders(<PagePriorityPanel jobId="job1" />)
    fireEvent.click(screen.getByText(/Rank pages/))
    await waitFor(() => expect(screen.getByText('Vulnerable Star')).toBeInTheDocument())
    expect(screen.getByText('https://x/a')).toBeInTheDocument()
    // page b has no GSC -> dash
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })

  it('shows a Hide control after ranking that collapses the table', async () => {
    global.fetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          pages: [
            { url: 'https://x/a', health_score: 40, gsc: { clicks: 5, impressions: 200 }, review_flag: { flagged: true, reasons: [] }, priority_rank: 1, bucket: 'Vulnerable Star' },
          ],
          total: 1,
        }),
      })
    )
    renderWithProviders(<PagePriorityPanel jobId="job1" />)
    fireEvent.click(screen.getByText(/Rank pages/))
    await waitFor(() => expect(screen.getByText('https://x/a')).toBeInTheDocument())

    // No misleading "Refresh"; a Hide control is offered instead.
    expect(screen.queryByText(/Refresh/)).not.toBeInTheDocument()
    const hide = screen.getByText('Hide')
    expect(hide).toBeInTheDocument()

    // Clicking Hide collapses the table and restores the Rank pages button.
    fireEvent.click(hide)
    expect(screen.queryByText('https://x/a')).not.toBeInTheDocument()
    expect(screen.getByText(/Rank pages/)).toBeInTheDocument()
  })

  it('shows an error state when the request fails', async () => {
    global.fetch.mockImplementation(() => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({ error: { message: 'boom' } }) }))
    renderWithProviders(<PagePriorityPanel jobId="job1" />)
    fireEvent.click(screen.getByText(/Rank pages/))
    await waitFor(() => expect(screen.getByText(/Failed to load|boom|HTTP 500/)).toBeInTheDocument())
  })
})

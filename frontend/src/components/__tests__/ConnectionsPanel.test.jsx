import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ConnectionsPanel from '../ConnectionsPanel.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'

// Mock the api helpers so no real network calls happen.
vi.mock('../../api', () => ({
  testLlmConnection: vi.fn(),
  gscStatus: vi.fn(),
}))

import { testLlmConnection, gscStatus } from '../../api'

describe('ConnectionsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('LLM test renders success state', async () => {
    testLlmConnection.mockResolvedValue({
      success: true,
      message: 'AI connection successful!',
      sample: 'A snappier title',
    })

    const user = userEvent.setup()
    renderWithProviders(<ConnectionsPanel onClose={() => {}} />)

    // The LLM row's Test connection button is the first one.
    const buttons = screen.getAllByRole('button', { name: 'Test connection' })
    await user.click(buttons[0])

    await waitFor(() => {
      expect(screen.getByText(/AI connection successful!/)).toBeInTheDocument()
    })
    expect(screen.getByText(/A snappier title/)).toBeInTheDocument()
    expect(testLlmConnection).toHaveBeenCalledTimes(1)
  })

  it('LLM test renders failure state', async () => {
    testLlmConnection.mockResolvedValue({
      success: false,
      message: 'Error calling AI: provider unreachable',
    })

    const user = userEvent.setup()
    renderWithProviders(<ConnectionsPanel onClose={() => {}} />)

    const buttons = screen.getAllByRole('button', { name: 'Test connection' })
    await user.click(buttons[0])

    await waitFor(() => {
      expect(screen.getByText(/Error calling AI: provider unreachable/)).toBeInTheDocument()
    })
  })

  it('GSC test renders connected state', async () => {
    gscStatus.mockResolvedValue({
      connected: true,
      configured: true,
      properties: [
        { site_url: 'https://example.com/', permission_level: 'siteOwner' },
        { site_url: 'https://b.example.com/', permission_level: 'siteFullUser' },
      ],
    })

    const user = userEvent.setup()
    renderWithProviders(<ConnectionsPanel onClose={() => {}} />)

    // The GSC row's Test connection button is the second one.
    const buttons = screen.getAllByRole('button', { name: 'Test connection' })
    await user.click(buttons[1])

    await waitFor(() => {
      expect(screen.getByText(/Connected/)).toBeInTheDocument()
    })
    expect(screen.getByText(/2 properties available/)).toBeInTheDocument()
    expect(gscStatus).toHaveBeenCalledTimes(1)
  })

  it('GSC test renders not-connected state', async () => {
    gscStatus.mockResolvedValue({
      connected: false,
      configured: true,
      properties: [],
    })

    const user = userEvent.setup()
    renderWithProviders(<ConnectionsPanel onClose={() => {}} />)

    const buttons = screen.getAllByRole('button', { name: 'Test connection' })
    await user.click(buttons[1])

    await waitFor(() => {
      expect(screen.getByText(/Configured but not connected/)).toBeInTheDocument()
    })
  })

  it('GSC test renders not-configured state (503)', async () => {
    // gscStatus() maps a 503 to { connected:false, properties:[], configured:false }.
    gscStatus.mockResolvedValue({
      connected: false,
      configured: false,
      properties: [],
    })

    const user = userEvent.setup()
    renderWithProviders(<ConnectionsPanel onClose={() => {}} />)

    const buttons = screen.getAllByRole('button', { name: 'Test connection' })
    await user.click(buttons[1])

    await waitFor(() => {
      expect(screen.getByText(/GSC not configured/)).toBeInTheDocument()
    })
  })
})

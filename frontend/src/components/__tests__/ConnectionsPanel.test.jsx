import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ConnectionsPanel from '../ConnectionsPanel.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'

// Mock the api helpers so no real network calls happen.
vi.mock('../../api', () => ({
  testLlmConnection: vi.fn(),
  gscStatus: vi.fn(),
  wpConnection: vi.fn(),
}))

import { testLlmConnection, gscStatus, wpConnection } from '../../api'

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


// ── WA5 (2026-09-02) — the WordPress row ────────────────────────────────────
// The panel tested the AI provider and GSC. Nothing tested WordPress, so when
// livingsystems.ca moved its login page every WordPress feature broke at once
// and the app could not say why.
// Spec: docs/functional-specification.md §7.8a (WA5)
describe('ConnectionsPanel — WordPress row', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  async function clickWordPress() {
    const user = userEvent.setup()
    renderWithProviders(<ConnectionsPanel onClose={() => {}} />)
    const buttons = screen.getAllByRole('button', { name: 'Test connection' })
    await user.click(buttons[2])
    return user
  }

  it('a working connection reports the site and the account', async () => {
    wpConnection.mockResolvedValue({
      configured: true, authenticated: true, site_url: 'https://example.com',
      user_id: 11, roles: ['administrator'],
      capabilities: { edit_posts: true, edit_pages: true, upload_files: true, manage_options: true },
      can_run_fixes: true, can_run_wp_audit: true,
      message: 'Connected. This account can run the fixes and the configuration audit.',
    })
    await clickWordPress()
    await waitFor(() => {
      expect(screen.getByText(/Connected/)).toBeInTheDocument()
    })
    expect(screen.getByText(/administrator/)).toBeInTheDocument()
    expect(wpConnection).toHaveBeenCalledTimes(1)
  })

  it('an unconfigured integration is not shown as a failure', async () => {
    wpConnection.mockResolvedValue({
      configured: false, authenticated: false, site_url: null, roles: [],
      capabilities: {}, can_run_fixes: false, can_run_wp_audit: false,
      message: 'No WordPress credentials are stored.',
    })
    await clickWordPress()
    await waitFor(() => {
      expect(screen.getByText(/No WordPress credentials are stored/)).toBeInTheDocument()
    })
    // "not set up" and "set up but broken" must not read the same.
    expect(screen.queryByText(/✗/)).not.toBeInTheDocument()
  })

  it('a rejected login shows the diagnosis the server sent, not a generic failure', async () => {
    wpConnection.mockResolvedValue({
      configured: true, authenticated: false, site_url: 'https://example.com',
      roles: [], capabilities: {}, can_run_fixes: false, can_run_wp_audit: false,
      message: 'Login failed at https://example.com/wp-login.php — the request was redirected.',
    })
    await clickWordPress()
    await waitFor(() => {
      expect(screen.getByText(/was redirected/)).toBeInTheDocument()
    })
  })

  it('an editor account is connected but cannot run the audit', async () => {
    wpConnection.mockResolvedValue({
      configured: true, authenticated: true, site_url: 'https://example.com',
      user_id: 4, roles: ['editor'],
      capabilities: { edit_posts: true, edit_pages: true, upload_files: true, manage_options: false },
      can_run_fixes: true, can_run_wp_audit: false,
      message: 'Connected. This account can run the fixes, but not the configuration audit.',
    })
    await clickWordPress()
    await waitFor(() => {
      expect(screen.getByText(/not the configuration audit/)).toBeInTheDocument()
    })
  })

  it('a thrown error is caught and rendered', async () => {
    wpConnection.mockRejectedValue(new Error('Network down'))
    await clickWordPress()
    await waitFor(() => {
      expect(screen.getByText(/Network down/)).toBeInTheDocument()
    })
  })
})

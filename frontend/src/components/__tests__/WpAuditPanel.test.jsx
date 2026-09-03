import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import WpAuditPanel from '../WpAuditPanel.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'

// AP1-AP4 (2026-09-03). `report_to_dict` has always returned `site_health`,
// `overlaps` and `inactive_themes`; the panel rendered none of them and only the
// PDF printed them. So the finding the WA1-WA4 work unblocked — a real `critical`
// Site Health row, the first this feature has produced — was invisible in the app
// (P25/P16). This file did not exist: the panel is the only consumer of the
// payload and nothing asserted it rendered any of it.
//
// Spec: docs/functional-specification.md §7.8

vi.mock('../../api.js', () => ({ runWpAudit: vi.fn() }))
import { runWpAudit } from '../../api.js'

const FULL = {
  plugins_total: 22,
  plugins_active: 22,
  plugins_inactive: 0,
  pending_updates: [],
  inactive_plugins: [],
  inactive_themes: ['Twenty Twenty-Five'],
  overlaps: [
    {
      responsibility: 'SEO metadata',
      label: 'Two plugins are writing your meta tags',
      why_one_owner: 'Whichever loads last wins, so the tag you edit may not be the tag served.',
      plugins: ['Yoast SEO', 'Rank Math'],
    },
  ],
  site_health: [
    {
      label: 'Background updates are not working as expected',
      status: 'critical',
      source: 'WordPress Site Health',
    },
    { label: 'Your site could not complete a loopback request', status: 'recommended',
      source: 'WordPress Site Health' },
  ],
  not_inspected: ['Plugin-internal state.'],
}

const EMPTY = {
  ...FULL, inactive_themes: [], overlaps: [], site_health: [], not_inspected: [],
}

async function run(report) {
  runWpAudit.mockResolvedValue(report)
  const user = userEvent.setup()
  renderWithProviders(<WpAuditPanel jobId="j" />)
  await user.click(screen.getByRole('button', { name: /Run WordPress audit/i }))
  await waitFor(() => expect(screen.getByTestId('wp-audit-report')).toBeInTheDocument())
}

describe('WpAuditPanel — the findings the PDF had and the screen did not', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders Site Health rows', async () => {
    await run(FULL)
    expect(screen.getByText(/Background updates are not working/)).toBeInTheDocument()
    expect(screen.getByText(/loopback request/)).toBeInTheDocument()
  })

  it('distinguishes a critical Site Health row from a recommended one', async () => {
    // `parse_site_health` preserves the status precisely so the two can be told
    // apart. The PDF dropped it and printed them identically; the panel must not.
    await run(FULL)
    const critical = screen.getByTestId('wp-health-critical')
    const recommended = screen.getByTestId('wp-health-recommended')
    expect(critical).toHaveTextContent(/Background updates/)
    expect(recommended).toHaveTextContent(/loopback/)
    expect(critical.className).not.toEqual(recommended.className)
  })

  it('renders plugin overlaps with the responsibility and the plugins claiming it', async () => {
    await run(FULL)
    expect(screen.getByText(/SEO metadata/)).toBeInTheDocument()
    expect(screen.getByText(/Yoast SEO/)).toBeInTheDocument()
    expect(screen.getByText(/Rank Math/)).toBeInTheDocument()
    expect(screen.getByText(/whichever loads last wins/i)).toBeInTheDocument()
  })

  it('renders inactive themes', async () => {
    await run(FULL)
    expect(screen.getByText(/Twenty Twenty-Five/)).toBeInTheDocument()
  })

  it('renders no empty headings when a section has nothing in it', async () => {
    // Adversarial (P2). A heading over an empty list reads as "checked, all
    // clear" — and Site Health in particular can simply fail to load, which is
    // why `not_inspected` exists. An absent section must stay absent.
    await run(EMPTY)
    expect(screen.queryByText(/Site Health/i)).not.toBeInTheDocument()
    // The heading is 'Two plugins doing one job' — no rendered text contains
    // 'overlap', so the original assertion passed even with a POPULATED
    // overlaps block (cold sweep, P27).
    expect(screen.queryByText(/Two plugins doing one job/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Inactive themes/i)).not.toBeInTheDocument()
  })

  it('still renders what it always did', async () => {
    await run(FULL)
    expect(screen.getByTestId('wp-audit-report')).toHaveTextContent('22')
    expect(screen.getByText(/No pending plugin updates/)).toBeInTheDocument()
    expect(screen.getByText(/Not inspected/)).toBeInTheDocument()
  })

  it('renders the error state instead of a report', async () => {
    runWpAudit.mockRejectedValue(new Error('DOMAIN_MISMATCH'))
    const user = userEvent.setup()
    renderWithProviders(<WpAuditPanel jobId="j" />)
    await user.click(screen.getByRole('button', { name: /Run WordPress audit/i }))
    await waitFor(() => expect(screen.getByTestId('wp-audit-error')).toHaveTextContent('DOMAIN_MISMATCH'))
    expect(screen.queryByTestId('wp-audit-report')).not.toBeInTheDocument()
  })
})

/**
 * Phase 4 — striking distance, compare card, WordPress audit, re-check all.
 * Spec: docs/pending/2026-09-02_phase4-user-value.md
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'
import StrikingDistancePanel from '../StrikingDistancePanel.jsx'
import ComparisonCard from '../ComparisonCard.jsx'
import WpAuditPanel from '../WpAuditPanel.jsx'
import RecheckAllButton from '../RecheckAllButton.jsx'

function route(map) {
  global.fetch.mockImplementation((url, opts) => {
    const u = String(url)
    for (const [needle, body] of Object.entries(map)) {
      if (u.includes(needle)) return typeof body === 'function' ? body(opts) : mockFetchResponse(body)
    }
    return mockFetchResponse({}, 404)
  })
}

describe('StrikingDistancePanel', () => {
  beforeEach(() => global.fetch.mockReset())

  it('lists in-band pages with the target query and offers open + copy', async () => {
    route({ 'striking-distance': {
      pages: [{ url: 'https://x.org/grief', position: 8.4, impressions: 400, clicks: 12, health_score: 91,
        target_query: 'grief counselling vancouver', rewrite_brief: 'Rewrite the title ...' }],
      basis: { pages_crawled: 40, pages_with_ledger: 30, band: { position_min: 5, position_max: 15 }, impressions_min: 50 },
    } })
    const onPageClick = vi.fn()
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue() } })
    renderWithProviders(<StrikingDistancePanel jobId="j" onPageClick={onPageClick} />)
    await screen.findByTestId('striking-row')
    expect(screen.getByText(/grief counselling vancouver/)).toBeInTheDocument()
    await userEvent.click(screen.getByText('Open page'))
    expect(onPageClick).toHaveBeenCalledWith('https://x.org/grief')
    await userEvent.click(screen.getByTestId('copy-https://x.org/grief'))
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('Rewrite the title ...')
  })

  it('says why the list is empty (no ledger vs nothing in band)', async () => {
    route({ 'striking-distance': { pages: [], basis: { pages_crawled: 12, pages_with_ledger: 0, band: { position_min: 5, position_max: 15 }, impressions_min: 50 } } })
    renderWithProviders(<StrikingDistancePanel jobId="j" />)
    expect(await screen.findByTestId('striking-empty')).toHaveTextContent(/No Search Console data/i)
  })
})

describe('ComparisonCard', () => {
  beforeEach(() => global.fetch.mockReset())
  const base = {
    comparison_available: true, comparable: true, reason: null,
    current: { health_score: 88, total_issues: 40, crawled_at: '2026-09-02T00:00:00Z' },
    previous: { health_score: 84, total_issues: 55, crawled_at: '2026-08-01T00:00:00Z' },
    delta: { health_score: 4, total_issues: -15, critical: 0, warning: -2 },
  }

  it('shows the delta when comparable', async () => {
    route({ '/comparison': base })
    renderWithProviders(<ComparisonCard jobId="j" />)
    const delta = await screen.findByTestId('health-delta')
    expect(delta).toHaveTextContent('(+4)')
    expect(delta.className).not.toContain('line-through')
    expect(screen.queryByTestId('comparison-reason')).not.toBeInTheDocument()
  })

  it('strikes the delta through and prints the reason when not comparable', async () => {
    route({ '/comparison': { ...base, comparable: false, reason: 'info_detail differs (notable vs all)' } })
    renderWithProviders(<ComparisonCard jobId="j" />)
    const delta = await screen.findByTestId('health-delta')
    expect(delta.className).toContain('line-through')
    expect(screen.getByTestId('comparison-reason')).toHaveTextContent('info_detail differs')
  })

  it('renders nothing without a previous scan', async () => {
    route({ '/comparison': { comparison_available: false } })
    const { container } = renderWithProviders(<ComparisonCard jobId="j" />)
    await waitFor(() => expect(global.fetch).toHaveBeenCalled())
    expect(container.querySelector('[data-testid="comparison-card"]')).toBeNull()
  })
})

describe('WpAuditPanel', () => {
  beforeEach(() => global.fetch.mockReset())

  it('runs the audit and renders the report', async () => {
    route({ '/wp-audit/': { plugins_total: 3, plugins_active: 2, plugins_inactive: 1,
      pending_updates: [{ slug: 'a', name: 'Akismet', version: '5.0', new_version: '5.1' }],
      inactive_plugins: [{ slug: 'b', name: 'Hello Dolly', version: '1' }], not_inspected: ['backup contents'] } })
    renderWithProviders(<WpAuditPanel jobId="j" />)
    await userEvent.click(screen.getByText('Run WordPress audit'))
    await screen.findByTestId('wp-audit-report')
    expect(screen.getByText(/Akismet/)).toBeInTheDocument()
    expect(screen.getByText(/Hello Dolly/)).toBeInTheDocument()
    expect(screen.getByText(/Not inspected: backup contents/)).toBeInTheDocument()
    const call = global.fetch.mock.calls.find(([u]) => String(u).includes('/wp-audit/'))
    expect(call[1].method).toBe('POST')
  })

  it('shows the API error message (no credentials)', async () => {
    route({ '/wp-audit/': () => mockFetchResponse({ error: { code: 'NO_CREDENTIALS', message: 'wp-credentials.json not found' } }, 400) })
    renderWithProviders(<WpAuditPanel jobId="j" />)
    await userEvent.click(screen.getByText('Run WordPress audit'))
    expect(await screen.findByTestId('wp-audit-error')).toHaveTextContent(/wp-credentials.json not found/)
  })
})

describe('RecheckAllButton', () => {
  beforeEach(() => { global.fetch.mockReset(); vi.useFakeTimers({ shouldAdvanceTime: true }) })

  it('starts, polls, shows progress, and calls onFinished when done', async () => {
    let calls = 0
    route({
      'recheck-all/status': () => { calls += 1; return mockFetchResponse(calls < 2
        ? { running: true, done: 3, total: 10 } : { running: false, done: 10, total: 10, resolved: 4 }) },
      'recheck-all': () => mockFetchResponse({ job_id: 'j', total: 10, status: 'started' }),
    })
    const onFinished = vi.fn()
    renderWithProviders(<RecheckAllButton jobId="j" onFinished={onFinished} />)
    await userEvent.click(screen.getByTestId('recheck-all'))
    await act(async () => { await vi.advanceTimersByTimeAsync(2100) })
    await waitFor(() => expect(screen.getByTestId('recheck-all')).toHaveTextContent('Re-checking 3 / 10'))
    await act(async () => { await vi.advanceTimersByTimeAsync(2100) })
    await waitFor(() => expect(onFinished).toHaveBeenCalledWith(expect.objectContaining({ done: 10 })))
    expect(screen.getByTestId('recheck-all')).toHaveTextContent('Re-check all pages')
    vi.useRealTimers()
  })

  it('shows the 409 message when a re-check is already running', async () => {
    route({ 'recheck-all': () => mockFetchResponse({ error: { code: 'RECHECK_IN_PROGRESS', message: 'A re-check of this scan is already running (2 of 9 pages).' } }, 409) })
    renderWithProviders(<RecheckAllButton jobId="j" />)
    await userEvent.click(screen.getByTestId('recheck-all'))
    expect(await screen.findByTestId('recheck-error')).toHaveTextContent('2 of 9')
    vi.useRealTimers()
  })
})

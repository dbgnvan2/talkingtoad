/**
 * Info detail (2026-09-01 spec §7) — the scan's info level on every surface.
 *
 * The score follows the level, so the number can never appear bare when the
 * level is not "all", and a list shortened by the level must say what it left
 * out (P31). Revealed rows are dimmed and never move the score.
 *
 * Spec: docs/pending/2026-09-01_info-tiers.md
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SeverityBadge from '../SeverityBadge.jsx'
import SummaryPanel from '../SummaryPanel.jsx'
import CategoryPanel from '../CategoryPanel.jsx'
import SeverityPanel from '../SeverityPanel.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

// ── SeverityBadge ─────────────────────────────────────────────────────────

describe('SeverityBadge info tier', () => {
  it('suffixes an info badge with its tier label', () => {
    render(<SeverityBadge severity="info" infoTier="high" />)
    expect(screen.getByText('info · Key')).toBeInTheDocument()
  })

  it('never suffixes a warning, whatever tier is passed', () => {
    render(<SeverityBadge severity="warning" infoTier="high" />)
    expect(screen.getByText('warning')).toBeInTheDocument()
  })

  it('dims a row the scan excluded from the score and says why', () => {
    render(<SeverityBadge severity="info" infoTier="low" scored={false} />)
    const badge = screen.getByText('info · Low')
    expect(badge.className).toContain('opacity-50')
    expect(badge.getAttribute('title')).toMatch(/not counted in the health score/i)
    expect(badge.getAttribute('data-scored')).toBe('false')
  })

  it('a scored info badge is not dimmed', () => {
    render(<SeverityBadge severity="info" infoTier="medium" />)
    expect(screen.getByText('info · Notable').className).not.toContain('opacity-50')
  })
})

// ── SummaryPanel ──────────────────────────────────────────────────────────

const base = {
  target_url: 'https://example.com', pages_crawled: 10, pages_with_errors: 0,
  total_issues: 6, health_score: 90, agent_health_score: 90,
  by_severity: { critical: 0, warning: 1, info: 5 },
  by_category: { broken_link: 0, metadata: 6, heading: 0 },
}
const props = {
  domain: 'example.com', jobId: 'j', onCategoryClick: vi.fn(),
  onSeverityClick: vi.fn(), onPageClick: vi.fn(), onShowPdfModal: vi.fn(),
}

describe('SummaryPanel info detail', () => {
  beforeEach(() => {
    global.fetch.mockReset()
    global.fetch.mockImplementation(() => mockFetchResponse({}))
  })

  it('at "all" the score has no scope label and the Info card shows the stored count', () => {
    renderWithProviders(<SummaryPanel {...props} summary={{
      ...base, info_detail: 'all', info_scored: 5, info_excluded: 0,
      info_by_tier: { high: 1, medium: 2, low: 2 },
    }} />)
    expect(screen.queryByTestId('score-info-detail')).not.toBeInTheDocument()
    expect(screen.queryByTestId('info-excluded')).not.toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('labels the score with its level and shows what the Info card left out', () => {
    renderWithProviders(<SummaryPanel {...props} summary={{
      ...base, info_detail: 'notable', info_scored: 3, info_excluded: 2,
      info_by_tier: { high: 1, medium: 2, low: 2 },
    }} />)
    const label = screen.getByTestId('score-info-detail')
    expect(label).toHaveTextContent(/scored at Notable and key only/i)
    expect(label).toHaveTextContent('2 info notices excluded')
    const excluded = screen.getByTestId('info-excluded')
    expect(excluded).toHaveTextContent('+2 excluded')
    expect(excluded).toHaveTextContent('Low 2')
    expect(excluded).not.toHaveTextContent('Notable')
  })

  it('a legacy summary without the new fields still renders the stored info count', () => {
    renderWithProviders(<SummaryPanel {...props} summary={base} />)
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.queryByTestId('score-info-detail')).not.toBeInTheDocument()
  })
})

// ── CategoryPanel / SeverityPanel — disclosure and reveal ─────────────────

const ROW = { issue_code: 'TITLE_TOO_SHORT', severity: 'info', impact: 1, info_tier: 'low',
  page_url: 'https://x.org/a', human_description: 'Title too short', category: 'metadata' }
const SCOPED = {
  issues: [{ ...ROW, issue_code: 'META_DESC_MISSING', human_description: 'Meta description missing', impact: 2, info_tier: 'medium', scored: true }],
  summary: { health_score: 91 },
  filtered: { domain: 'x.org', hidden: 0, by_rule: {} },
  info_filtered: { hidden: 1, by_tier: { low: 1 }, info_detail: 'notable' },
}
const REVEALED = {
  ...SCOPED,
  issues: [...SCOPED.issues, { ...ROW, scored: false }],
  info_filtered: { hidden: 0, by_tier: {}, info_detail: 'all' },
}

function routeByLevel() {
  global.fetch.mockImplementation((url) =>
    mockFetchResponse(String(url).includes('info_detail=all') ? REVEALED : SCOPED))
}

describe('CategoryPanel info detail disclosure', () => {
  beforeEach(() => { global.fetch.mockReset() })

  it('declares what the scan level excluded from the list and the score', async () => {
    routeByLevel()
    renderWithProviders(<CategoryPanel jobId="j1" category={{ key: 'metadata', label: 'Metadata' }} domain="x.org" />)
    const note = await screen.findByTestId('info-detail-disclosure')
    expect(note).toHaveTextContent('1 info notice excluded')
    expect(note).toHaveTextContent(/not counted in the health score/i)
    expect(note).toHaveTextContent('Low 1')
    expect(screen.queryByText('Title too short')).not.toBeInTheDocument()
  })

  it('"Show excluded info" requests the full list and dims the unscored rows', async () => {
    routeByLevel()
    renderWithProviders(<CategoryPanel jobId="j1" category={{ key: 'metadata', label: 'Metadata' }} domain="x.org" />)
    await screen.findByTestId('info-detail-disclosure')
    await userEvent.click(screen.getByTestId('info-detail-toggle'))
    await waitFor(() => expect(screen.getByText('Title too short')).toBeInTheDocument())
    const call = global.fetch.mock.calls.find(([u]) => String(u).includes('info_detail=all'))
    expect(call).toBeTruthy()
    expect(screen.getByText('info · Low').getAttribute('data-scored')).toBe('false')
    expect(screen.getByText('info · Notable').getAttribute('data-scored')).toBeNull()
    expect(screen.getByTestId('info-detail-toggle')).toHaveTextContent(/Back to scan setting/i)
  })

  it('says nothing when the level excluded nothing', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse({
      ...SCOPED, info_filtered: { hidden: 0, by_tier: {}, info_detail: 'all' } }))
    renderWithProviders(<CategoryPanel jobId="j1" category={{ key: 'metadata', label: 'Metadata' }} domain="x.org" />)
    await screen.findByText('Meta description missing')
    expect(screen.queryByTestId('info-detail-disclosure')).not.toBeInTheDocument()
  })
})

describe('SeverityPanel info detail disclosure', () => {
  beforeEach(() => { global.fetch.mockReset() })

  it('shows the disclosure on the info view and reveals on demand', async () => {
    routeByLevel()
    renderWithProviders(<SeverityPanel jobId="j1" severity="info" domain="x.org" onPageClick={vi.fn()} onBack={vi.fn()} />)
    await screen.findByTestId('info-detail-disclosure')
    await userEvent.click(screen.getByTestId('info-detail-toggle'))
    await waitFor(() => expect(screen.getByText('Title too short')).toBeInTheDocument())
  })

  it('does not show the disclosure on the warning view', async () => {
    routeByLevel()
    renderWithProviders(<SeverityPanel jobId="j1" severity="warning" domain="x.org" onPageClick={vi.fn()} onBack={vi.fn()} />)
    await screen.findByText('Meta description missing')
    expect(screen.queryByTestId('info-detail-disclosure')).not.toBeInTheDocument()
  })
})

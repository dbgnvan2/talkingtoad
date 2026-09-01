/**
 * D5 — the Page Audit panel reports what the re-check found.
 *
 * Spec: docs/functional-specification.md (D5)
 *
 * Owner report: "the page refresh on the Inspect — Page Audit panel doesn't
 * seem to re-analyze — it just reloads."
 *
 * It did re-analyse. `handleRefresh` awaited rescanUrl and discarded the whole
 * response — old_count, new_count, resolved_codes, checks_not_run and, on a
 * blocked page, the caveat explaining that nothing had been checked. A grep for
 * any of those field names across frontend/src returned zero hits. A re-check
 * that cleared the finding rendered identically to one that changed nothing,
 * and a failure rendered identically to both (console.error, no toast).
 *
 * These tests pin the outcome being visible. The last one pins the harder
 * rule: visible must not mean flattering.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PageFocusPanel, RecheckResultBanner } from '../Results.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

const JOB = 'job-1'
const URL = 'https://example.org/about'

// The shape /rescan-url actually returns, so a backend rename breaks this test
// rather than silently emptying the banner.
function rescanResponse(over = {}) {
  return {
    url: URL,
    status_code: 200,
    old_count: 3,
    new_count: 1,
    resolved: 2,
    added: 0,
    resolved_codes: [],
    still_present_codes: [],
    newly_found_codes: [],
    carried_over_codes: [],
    total_issues: 1,
    page_data: { title: 'About', h1_tags: ['About'], headings_outline: [] },
    by_category: {},
    checks_not_run: [],
    checks_not_run_reason: 'These checks only run during a full crawl.',
    ...over,
  }
}

/** Route every call the panel makes; rescan-url resolves to `rescan`. */
function mockPanelFetches(rescan, { rescanRejects = false } = {}) {
  global.fetch.mockImplementation((url) => {
    if (String(url).includes('/rescan-url')) {
      if (rescanRejects) return Promise.reject(new Error('Network request failed'))
      return mockFetchResponse(rescan)
    }
    if (String(url).includes('/page-issues')) {
      return mockFetchResponse({ by_category: {}, page_data: {} })
    }
    return mockFetchResponse({})
  })
}

async function clickRecheck() {
  const button = await screen.findByLabelText('Re-check this page')
  await userEvent.click(button)
  return button
}

function renderPanel() {
  return renderWithProviders(
    <PageFocusPanel jobId={JOB} pageUrl={URL} onClose={() => {}} onRescan={() => {}} />
  )
}

describe('D5 the re-check button reports its outcome', () => {
  beforeEach(() => { global.fetch.mockReset() })

  it('is labelled as a re-check, not a refresh', async () => {
    mockPanelFetches(rescanResponse())
    renderPanel()
    // The old label ("Refresh page data") is why the control was read as a
    // reload. Assert the promise the button now makes.
    expect(await screen.findByLabelText('Re-check this page')).toBeInTheDocument()
    expect(screen.queryByLabelText('Refresh page data')).not.toBeInTheDocument()
  })

  it('renders what the re-check resolved', async () => {
    mockPanelFetches(rescanResponse({ resolved_codes: ['META_DESC_MISSING'] }))
    renderPanel()
    await clickRecheck()
    await waitFor(() => {
      expect(screen.getByText(/No longer found/i)).toBeInTheDocument()
    })
    // Named by the label the operator sees in the issue list, not the raw code.
    expect(screen.getByText(/Meta description missing/i)).toBeInTheDocument()
  })

  it('shows the caveat when the page could not be read', async () => {
    // A 403/429 comes back as HTTP 200 with page_unreadable — the backend
    // correctly refuses to write anything, and said so to nobody.
    const caveat =
      'The page could not be read (HTTP 403), so nothing was re-checked and ' +
      'no finding was marked fixed.'
    mockPanelFetches(rescanResponse({ page_unreadable: true, status_code: 403, caveat }))
    renderPanel()
    await clickRecheck()
    await waitFor(() => {
      expect(screen.getByText(caveat)).toBeInTheDocument()
    })
    expect(screen.getByText(/could not be read — nothing was re-checked/i)).toBeInTheDocument()
  })

  it('shows an error rather than silence when the re-check fails', async () => {
    mockPanelFetches(null, { rescanRejects: true })
    renderPanel()
    await clickRecheck()
    // Both a persistent banner in the panel and a toast — the failure must not
    // be recoverable only from the console.
    await waitFor(() => {
      expect(screen.getAllByText(/Re-check failed/i).length).toBeGreaterThanOrEqual(2)
    })
    expect(screen.getByText(/findings below are from the last successful check/i))
      .toBeInTheDocument()
  })

  it('names the findings it kept without re-checking', async () => {
    const reason =
      'These checks compare a page against the rest of the site, so a ' +
      'single-page scan cannot evaluate them.'
    mockPanelFetches(rescanResponse({
      carried_over_codes: ['TITLE_DUPLICATE'],
      checks_not_run: ['TITLE_DUPLICATE'],
      checks_not_run_reason: reason,
    }))
    renderPanel()
    await clickRecheck()
    await waitFor(() => {
      expect(screen.getByText(/Not re-checked/i)).toBeInTheDocument()
    })
    expect(screen.getByText(/Duplicate page title/i)).toBeInTheDocument()
    expect(screen.getByText(reason)).toBeInTheDocument()
  })
})

describe('D5 adversarial — a re-check must not flatter itself', () => {
  beforeEach(() => { global.fetch.mockReset() })

  it('does not render as success when nothing was resolved', () => {
    // The correct-looking-but-wrong result: the operator clicks re-check, sees
    // a confident banner, and concludes the fix landed — when the findings are
    // all still there.
    renderWithProviders(
      <RecheckResultBanner
        result={{
          kind: 'checked',
          resolved_codes: [],
          still_present_codes: ['TITLE_TOO_LONG', 'H1_MISSING'],
          newly_found_codes: [],
          carried_over_codes: [],
        }}
        onDismiss={() => {}}
      />
    )
    expect(screen.getByText(/Still present/i)).toBeInTheDocument()
    expect(screen.queryByText(/No longer found/i)).not.toBeInTheDocument()
    // No word anywhere that would let this be read as a clearance.
    const banner = screen.getByRole('status')
    expect(banner.textContent).not.toMatch(/\b(fixed|resolved|success|all clear|done)\b/i)
  })

  it('does not claim a carried-over finding was checked', () => {
    // The backend bug in miniature: a code cannot be both resolved and
    // un-runnable. If the banner ever renders one under both headings, the
    // operator is being told two incompatible things at once.
    renderWithProviders(
      <RecheckResultBanner
        result={{
          kind: 'checked',
          resolved_codes: [],
          still_present_codes: [],
          newly_found_codes: [],
          carried_over_codes: ['ORPHAN_PAGE'],
          checks_not_run_reason: 'Only a full crawl can evaluate these.',
        }}
        onDismiss={() => {}}
      />
    )
    const banner = screen.getByRole('status')
    expect(banner.textContent).toMatch(/Not re-checked/i)
    expect(banner.textContent).not.toMatch(/No longer found/i)
  })
})

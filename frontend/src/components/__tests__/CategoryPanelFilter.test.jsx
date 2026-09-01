import { describe, it, expect, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/test-utils.jsx'
import CategoryPanel from '../CategoryPanel.jsx'

// F1 — the per-domain issue filter, surfaced on the Code page.
//
// The backend removes filtered findings from `issues` and reports what it
// removed in `filtered`. The panel MUST render that report: 123 of 170
// catalogue codes are `info`, so the severity rule hides ~72% of findings, and
// a list that simply came back shorter would read as a cleaner site. This
// repo has shipped that failure three times (P31/P24) and once shipped a
// disclosure that reached no surface at all, so the rendering is the part
// worth pinning.

const BASE = {
  issues: [
    { issue_code: 'TITLE_TOO_SHORT', severity: 'warning', page_url: 'https://x.org/a',
      human_description: 'Title too short', category: 'metadata' },
  ],
  summary: { health_score: 72 },
  filtered: { domain: 'x.org', hidden: 0, by_rule: {} },
}

const FILTERED = {
  ...BASE,
  filtered: { domain: 'x.org', hidden: 31, by_rule: { 'severity:info': 28, 'H1_MISSING': 3 } },
}

function mockOk(body) {
  global.fetch.mockImplementation(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) })
  )
}

const CATEGORY = { key: 'metadata', label: 'Metadata' }

describe('CategoryPanel — domain issue filter', () => {
  beforeEach(() => { global.fetch.mockReset() })

  it('says nothing when nothing is filtered', async () => {
    mockOk(BASE)
    renderWithProviders(
      <CategoryPanel jobId="j1" category={CATEGORY} domain="x.org" />)
    await waitFor(() => expect(screen.getByText(/Title too short/i)).toBeInTheDocument())
    expect(screen.queryByTestId('filter-disclosure')).not.toBeInTheDocument()
  })

  it('declares how many findings the filter hid, and by which rule', async () => {
    mockOk(FILTERED)
    renderWithProviders(
      <CategoryPanel jobId="j1" category={CATEGORY} domain="x.org" />)
    const note = await screen.findByTestId('filter-disclosure')
    expect(note).toHaveTextContent('31')
    // the rules must be named, not just counted — otherwise the reader cannot
    // tell which findings they are not seeing
    expect(note).toHaveTextContent(/info/i)
    expect(note).toHaveTextContent('H1_MISSING')
  })

  it('offers a per-code control to filter a code out', async () => {
    mockOk(BASE)
    renderWithProviders(
      <CategoryPanel jobId="j1" category={CATEGORY} domain="x.org" />)
    await waitFor(() => expect(screen.getByText(/Title too short/i)).toBeInTheDocument())
    expect(screen.getByTestId('filter-out-TITLE_TOO_SHORT')).toBeInTheDocument()
  })

  it('posts the rule for THIS domain when the control is used', async () => {
    mockOk(BASE)
    const user = userEvent.setup()
    renderWithProviders(
      <CategoryPanel jobId="j1" category={CATEGORY} domain="x.org" />)
    await waitFor(() => expect(screen.getByText(/Title too short/i)).toBeInTheDocument())

    await user.click(screen.getByTestId('filter-out-TITLE_TOO_SHORT'))

    await waitFor(() => {
      const post = global.fetch.mock.calls.find(
        ([url, opts]) => String(url).includes('/api/domain-filters') && opts?.method === 'POST')
      expect(post, 'no POST to /api/domain-filters was made').toBeTruthy()
      const body = JSON.parse(post[1].body)
      expect(body).toMatchObject({ domain: 'x.org', issue_code: 'TITLE_TOO_SHORT' })
    })
  })

  it('adversarial: a filtered panel is never indistinguishable from a clean one', async () => {
    // The failure this feature could introduce: every finding filtered out,
    // an empty list, and nothing saying why.
    mockOk({ ...BASE, issues: [],
             filtered: { domain: 'x.org', hidden: 12, by_rule: { 'severity:info': 12 } } })
    renderWithProviders(
      <CategoryPanel jobId="j1" category={CATEGORY} domain="x.org" />)
    const note = await screen.findByTestId('filter-disclosure')
    expect(note).toHaveTextContent('12')
  })
})

describe('CategoryPanel — undoing a filter rule', () => {
  beforeEach(() => { global.fetch.mockReset() })

  it('the "show again" control DELETEs the rule it names', async () => {
    // Gap found by a cold sweep: the add path was covered, the remove path
    // was not, so a broken undo button would have shipped silently.
    mockOk(FILTERED)
    const user = userEvent.setup()
    renderWithProviders(
      <CategoryPanel jobId="j1" category={CATEGORY} domain="x.org" />)

    await user.click(await screen.findByTestId('unfilter-severity:info'))

    await waitFor(() => {
      const del = global.fetch.mock.calls.find(
        ([url, opts]) => String(url).includes('/api/domain-filters') && opts?.method === 'DELETE')
      expect(del, 'no DELETE to /api/domain-filters was made').toBeTruthy()
      const url = String(del[0])
      expect(url).toContain('severity=info')
      expect(url).toContain('domain=x.org')
      // A severity rule must NOT be sent as an issue_code — CategoryPanel
      // slices the "severity:" prefix, and getting that wrong would 404.
      expect(url).not.toContain('issue_code')
    })
  })

  it('the per-code "show again" control sends issue_code, not severity', async () => {
    mockOk(FILTERED)
    const user = userEvent.setup()
    renderWithProviders(
      <CategoryPanel jobId="j1" category={CATEGORY} domain="x.org" />)

    await user.click(await screen.findByTestId('unfilter-H1_MISSING'))

    await waitFor(() => {
      const del = global.fetch.mock.calls.find(
        ([url, opts]) => String(url).includes('/api/domain-filters') && opts?.method === 'DELETE')
      expect(del).toBeTruthy()
      expect(String(del[0])).toContain('issue_code=H1_MISSING')
      expect(String(del[0])).not.toContain('severity=')
    })
  })
})

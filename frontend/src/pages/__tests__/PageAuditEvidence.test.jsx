/**
 * D6 — the Page Audit names the offending items.
 *
 * Spec: docs/functional-specification.md (D6)
 *
 * Owner report: "when I go to update a page, the code being reported e.g.
 * unsafe external links, doesn't report what links are the problem. This is
 * similar for many codes."
 *
 * The evidence has been on the payload since 2026-08-29, and CategoryPanel has
 * rendered it the whole time via IssueEvidence. IssueCard — the Page Audit
 * panel — hand-rolled ~14 per-code `extra` lookups instead, and `unsafe_links`
 * was never one of them. The component existed, was correct, and the second
 * screen was never connected to it.
 *
 * Third instance of that class in this repo (images_measured, checks_not_run,
 * this), so the last test here is the one that matters most: it fails if a
 * generic-evidence code renders nothing at all, whatever the reason.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { IssueCard } from '../Results.jsx'
import { IssueDetails } from '../../components/IssueEvidence.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

const JOB = 'job-1'
const URL = 'https://example.org/about'

// The payload shape /page-issues actually returns, so a backend rename breaks
// this test rather than silently emptying the panel.
function unsafeLinksIssue(over = {}) {
  return {
    issue_code: 'UNSAFE_CROSS_ORIGIN_LINK',
    category: 'security',
    severity: 'info',
    description: '25 external links open in a new tab without rel="noopener"',
    recommendation: 'Add rel="noopener noreferrer".',
    human_description: 'Unsafe external links',
    page_url: URL,
    impact: 1,
    effort: 1,
    extra: { unsafe_link_count: 25 },
    evidence: [
      'Unsafe links:',
      '  "External 0" -> https://ext0.example.com/x',
      '  "External 1" -> https://ext1.example.com/x',
    ],
    evidence_total: 25,
    evidence_basis: 'items',
    ...over,
  }
}

function detailsResponse(over = {}) {
  return {
    url: URL,
    status_code: 200,
    source: 'live',
    page_unreadable: false,
    capture_cap_note: 'The crawler records a limited number of examples per finding.',
    details: [{
      issue_code: 'UNSAFE_CROSS_ORIGIN_LINK',
      description: 'unsafe links',
      items: [
        'Unsafe links:',
        ...Array.from({ length: 20 }, (_, i) => `  "External ${i}" -> https://ext${i}.example.com/x`),
      ],
      items_total: 25,
      evidence_basis: 'items',
      truncated_at_capture: true,
    }],
    ...over,
  }
}

function renderCard(issue) {
  return renderWithProviders(
    <IssueCard issue={issue} jobId={JOB} pageUrl={URL} />
  )
}

async function openDetails() {
  await userEvent.click(await screen.findByRole('button', { name: 'Details' }))
}

describe('D6 the Page Audit shows which items are the problem', () => {
  beforeEach(() => { global.fetch.mockReset() })

  it('names the offending links instead of only counting them', async () => {
    renderCard(unsafeLinksIssue())
    await openDetails()
    // The owner's literal complaint: the count was there, the links were not.
    expect(await screen.findByText(/ext0\.example\.com/)).toBeInTheDocument()
    expect(screen.getByText(/ext1\.example\.com/)).toBeInTheDocument()
  })

  it('says how many of the total it is showing', async () => {
    renderCard(unsafeLinksIssue())
    await openDetails()
    // 3 rendered rows (a heading plus two links) against 25 on the page. The
    // count is split across React text nodes, so match on the container.
    await waitFor(() => {
      expect(screen.getByText(/What to look for/i).closest('div').textContent)
        .toMatch(/Showing 3 of 25/)
    })
  })

  it('offers a live read when the stored list is short of the truth', async () => {
    renderCard(unsafeLinksIssue())
    await openDetails()
    expect(await screen.findByRole('button', { name: /Get full details/i })).toBeInTheDocument()
  })

  it('replaces the capped list with the live one, labelled as live', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse(detailsResponse()))
    renderCard(unsafeLinksIssue())
    await openDetails()
    await userEvent.click(screen.getByRole('button', { name: /Get full details/i }))
    await waitFor(() => {
      expect(screen.getByText(/ext19\.example\.com/)).toBeInTheDocument()
    })
    expect(screen.getByText(/read from the page just now/i)).toBeInTheDocument()
    // Capture truncation is still disclosed — the live read lifts the render
    // cap, not the crawler's own capture cap. 21 rows (heading + 20 links).
    expect(screen.getByText(/What to look for/i).closest('div').textContent)
      .toMatch(/Showing 21 of 25/)
  })

  it('says so when the finding is about the page itself', async () => {
    renderCard(unsafeLinksIssue({
      issue_code: 'TITLE_MISSING',
      evidence: [], evidence_total: 0, evidence_basis: 'page',
      extra: null,
    }))
    await openDetails()
    expect(await screen.findByText(/about the page as a whole/i)).toBeInTheDocument()
    // A code with nothing to list must not offer a read that cannot help.
    expect(screen.queryByRole('button', { name: /Get full details/i })).not.toBeInTheDocument()
  })

  it('does not render the generic block when a hand-rolled one already lists the items', async () => {
    // LINK_EMPTY_ANCHOR has its own fix table in IssueCard. Rendering both
    // would list the same links twice under two headings.
    renderCard(unsafeLinksIssue({
      issue_code: 'LINK_EMPTY_ANCHOR',
      extra: { empty_anchor_count: 2, empty_anchor_hrefs: ['/a', '/b'] },
    }))
    expect(screen.queryByRole('button', { name: 'Details' })).not.toBeInTheDocument()
  })
})

describe('D6 adversarial — details must not mislead', () => {
  beforeEach(() => { global.fetch.mockReset() })

  it('does not present crawl-time items as live when the page could not be read', async () => {
    // Third appearance of this shape (E1.2, D5, here). The operator asks what
    // is on the page NOW, the fetch is blocked, and stale links come back —
    // so they re-fix links they already fixed.
    const caveat = 'The page could not be read (HTTP 403), so these are the items ' +
                   'recorded during the last crawl, not what is on the page now.'
    global.fetch.mockImplementation(() => mockFetchResponse(detailsResponse({
      source: 'stored', page_unreadable: true, status_code: 403, caveat,
    })))
    renderCard(unsafeLinksIssue())
    await openDetails()
    await userEvent.click(screen.getByRole('button', { name: /Get full details/i }))
    await waitFor(() => {
      expect(screen.getByText(caveat)).toBeInTheDocument()
    })
    expect(screen.getByText(/from the last crawl/i)).toBeInTheDocument()
    expect(screen.queryByText(/read from the page just now/i)).not.toBeInTheDocument()
  })

  it('reports a failed read as an error, not as an empty list', async () => {
    global.fetch.mockImplementation(() => Promise.reject(new Error('Network request failed')))
    renderCard(unsafeLinksIssue())
    await openDetails()
    await userEvent.click(screen.getByRole('button', { name: /Get full details/i }))
    await waitFor(() => {
      expect(screen.getByText(/Could not get full details/i)).toBeInTheDocument()
    })
  })

  it('says a finding is gone rather than showing an empty details box', async () => {
    // The live page no longer has the code. "No details available" would read
    // as a failure; it is actually the best possible answer.
    global.fetch.mockImplementation(() => mockFetchResponse(detailsResponse({ details: [] })))
    renderCard(unsafeLinksIssue())
    await openDetails()
    await userEvent.click(screen.getByRole('button', { name: /Get full details/i }))
    await waitFor(() => {
      expect(screen.getByText(/no longer on the page/i)).toBeInTheDocument()
    })
  })

  it('never renders an empty details box with no explanation', () => {
    // The class guard. Whatever the reason a list is empty, the panel must say
    // something — an empty box reads as "nothing wrong here".
    renderWithProviders(
      <IssueDetails
        jobId={JOB}
        pageUrl={URL}
        issue={{ issue_code: 'SOME_CODE', evidence: [], evidence_total: 0,
                 evidence_basis: 'items' }}
      />
    )
    expect(screen.getByRole('button', { name: 'Details' })).toBeInTheDocument()
  })

  it('a generic-evidence code is never silently skipped by the panel', async () => {
    // What went wrong for three years: the panel rendered nothing and no test
    // noticed, because every backend test asserted the payload and the payload
    // was correct the whole time.
    renderCard(unsafeLinksIssue())
    const details = await screen.findByRole('button', { name: 'Details' })
    expect(details).toBeInTheDocument()
    await userEvent.click(details)
    expect(await screen.findByText(/What to look for/i)).toBeInTheDocument()
  })
})

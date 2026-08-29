/**
 * E4 — clicking a systemic defect opens THAT issue, not just its category.
 *
 * Half the value of the link is landing somewhere useful. Dropping the reader at
 * the top of a category with a dozen collapsed rows is barely better than the
 * un-clickable list they reported.
 */
import { screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import CategoryPanel from '../CategoryPanel'
import { renderWithProviders } from '../../test/test-utils'
import { mockFetchResponse } from '../../test/setup'

const CATEGORY = { key: 'security', label: 'Security' }

const ISSUES = {
  issues: [
    {
      issue_code: 'MISSING_HSTS', severity: 'info', category: 'security',
      human_description: 'HSTS Header Missing', description: 'No HSTS header',
      recommendation: 'Add one.', page_url: 'https://x/a', extra: {},
    },
    {
      issue_code: 'UNSAFE_CROSS_ORIGIN_LINK', severity: 'info', category: 'security',
      human_description: 'Unsafe External Link',
      description: 'External link opens in a new tab without rel',
      recommendation: 'Add rel.', page_url: 'https://x/b',
      extra: { unsafe_links: [{ href: 'https://partner.org/a' }], unsafe_links_total: 1 },
    },
  ],
}

function renderPanel(focusIssueCode = null) {
  return renderWithProviders(
    <CategoryPanel jobId="job-1" category={CATEGORY} focusIssueCode={focusIssueCode} />
  )
}

describe('CategoryPanel — focused issue code', () => {
  beforeEach(() => {
    global.fetch.mockImplementation(() => mockFetchResponse(ISSUES))
  })

  it('renders both issues collapsed when nothing is focused', async () => {
    renderPanel(null)
    await waitFor(() => {
      expect(screen.getByText('Unsafe External Link')).toBeInTheDocument()
    })
    // Collapsed: the expanded body (the affected-page list) is not on screen.
    expect(screen.queryByText('https://x/b')).not.toBeInTheDocument()
  })

  it('expands the focused issue so the reader lands on it', async () => {
    renderPanel('UNSAFE_CROSS_ORIGIN_LINK')
    await waitFor(() => {
      expect(screen.getByText('https://x/b')).toBeInTheDocument()
    })
  })

  it('expands only the focused issue, not every issue in the category', async () => {
    renderPanel('UNSAFE_CROSS_ORIGIN_LINK')
    await waitFor(() => {
      expect(screen.getByText('https://x/b')).toBeInTheDocument()
    })
    // The other issue's affected page stays hidden.
    expect(screen.queryByText('https://x/a')).not.toBeInTheDocument()
  })

  it('gives every issue a stable anchor id so it can be scrolled to', async () => {
    const { container } = renderPanel(null)
    await waitFor(() => {
      expect(screen.getByText('Unsafe External Link')).toBeInTheDocument()
    })
    expect(container.querySelector('#issue-UNSAFE_CROSS_ORIGIN_LINK')).toBeTruthy()
    expect(container.querySelector('#issue-MISSING_HSTS')).toBeTruthy()
  })

  it('does not break when the focused code is not in this category', async () => {
    renderPanel('SOME_OTHER_CODE')
    await waitFor(() => {
      expect(screen.getByText('Unsafe External Link')).toBeInTheDocument()
    })
  })
})

// ── The gap this closes: evidence in the category panel ────────────────────
//
// Clicking a systemic defect landed the reader on a list of affected pages and
// nothing about WHAT was wrong on them. The PDF and the By-Page view had the
// detail; the category view did not.

const WITH_EVIDENCE = {
  issues: [
    {
      issue_code: 'UNSAFE_CROSS_ORIGIN_LINK', severity: 'info', category: 'security',
      human_description: 'Unsafe External Link',
      description: 'External link opens in a new tab without rel',
      recommendation: 'Add rel.', page_url: 'https://x/b',
      extra: {},
      evidence: [
        'Unsafe links:',
        '  "Partner site" -> https://partner.org/a',
        '  "Other org" -> https://other.org/b',
      ],
      evidence_total: 2,
    },
  ],
}

describe('CategoryPanel — what to look for', () => {
  beforeEach(() => {
    global.fetch.mockImplementation(() => mockFetchResponse(WITH_EVIDENCE))
  })

  it('shows the offending elements, not just the affected pages', async () => {
    renderPanel('UNSAFE_CROSS_ORIGIN_LINK')
    await waitFor(() => {
      expect(screen.getByText('What to look for')).toBeInTheDocument()
    })
    expect(screen.getByText('"Partner site" -> https://partner.org/a')).toBeInTheDocument()
    expect(screen.getByText('"Other org" -> https://other.org/b')).toBeInTheDocument()
  })

  it('still shows the affected pages alongside', async () => {
    renderPanel('UNSAFE_CROSS_ORIGIN_LINK')
    await waitFor(() => {
      expect(screen.getByText('https://x/b')).toBeInTheDocument()
    })
  })

  it('renders nothing when an issue has no evidence', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse({
      issues: [{ ...WITH_EVIDENCE.issues[0], evidence: [], evidence_total: 0 }],
    }))
    renderPanel('UNSAFE_CROSS_ORIGIN_LINK')
    await waitFor(() => {
      expect(screen.getByText('https://x/b')).toBeInTheDocument()
    })
    expect(screen.queryByText('What to look for')).not.toBeInTheDocument()
  })

  it('tolerates an older payload with no evidence field at all', async () => {
    const { evidence, evidence_total, ...withoutEvidence } = WITH_EVIDENCE.issues[0]
    global.fetch.mockImplementation(() => mockFetchResponse({ issues: [withoutEvidence] }))
    renderPanel('UNSAFE_CROSS_ORIGIN_LINK')
    await waitFor(() => {
      expect(screen.getByText('https://x/b')).toBeInTheDocument()
    })
    expect(screen.queryByText('What to look for')).not.toBeInTheDocument()
  })

  it('discloses a truncated evidence list', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse({
      issues: [{ ...WITH_EVIDENCE.issues[0], evidence_total: 120 }],
    }))
    renderPanel('UNSAFE_CROSS_ORIGIN_LINK')
    await waitFor(() => {
      expect(screen.getByText(/Showing 3 of 120/i)).toBeInTheDocument()
    })
  })
})

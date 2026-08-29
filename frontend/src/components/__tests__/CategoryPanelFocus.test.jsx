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

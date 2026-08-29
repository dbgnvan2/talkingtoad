/**
 * E2 — the broken-link source list in an issue card.
 *
 * Spec: docs/pending/2026-08-29_E2-broken-link-source-attribution.md#E2.2
 *
 * The backend now knows every page that links to a broken target. If the card
 * shows only the first one, the operator still cannot see that a single
 * reusable block is responsible — which was the whole problem (P25).
 */
import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { IssueCard } from '../Results'
import { renderWithProviders } from '../../test/test-utils'

const brokenLinkIssue = (extra) => ({
  issue_code: 'BROKEN_LINK_404',
  category: 'broken_link',
  severity: 'info',
  description: 'Link destination returns 404 Not Found',
  recommendation: 'Remove or update this link.',
  human_description: 'Dead Link',
  page_url: 'https://livingsystems.ca/dontation_form',
  impact: 2,
  effort: 2,
  extra,
})

describe('E2 broken-link source attribution in the issue card', () => {
  it('lists every page that links to the broken target', () => {
    renderWithProviders(
      <IssueCard
        issue={brokenLinkIssue({
          target_url: 'https://livingsystems.ca/dontation_form',
          occurrences: 3,
          occurrence_urls: [
            'https://livingsystems.ca/post-a',
            'https://livingsystems.ca/post-b',
            'https://livingsystems.ca/post-c',
          ],
          occurrence_urls_total: 3,
        })}
      />
    )
    expect(screen.getByText(/Linked from 3 pages/i)).toBeInTheDocument()
    expect(screen.getByText('https://livingsystems.ca/post-a')).toBeInTheDocument()
    expect(screen.getByText('https://livingsystems.ca/post-c')).toBeInTheDocument()
  })

  it('discloses the cap when the list is truncated (rule 6)', () => {
    const urls = Array.from({ length: 50 }, (_, i) => `https://livingsystems.ca/p${i}`)
    renderWithProviders(
      <IssueCard
        issue={brokenLinkIssue({
          target_url: 'https://livingsystems.ca/dontation_form',
          occurrences: 120,
          occurrence_urls: urls,
          occurrence_urls_total: 120,
        })}
      />
    )
    expect(screen.getByText(/Linked from 120 pages/i)).toBeInTheDocument()
    expect(screen.getByText(/showing 50 of 120/i)).toBeInTheDocument()
  })

  it('uses the singular for a single linking page', () => {
    renderWithProviders(
      <IssueCard
        issue={brokenLinkIssue({
          target_url: 'https://livingsystems.ca/gone',
          occurrences: 1,
          occurrence_urls: ['https://livingsystems.ca/only'],
          occurrence_urls_total: 1,
        })}
      />
    )
    expect(screen.getByText(/Linked from 1 page$/i)).toBeInTheDocument()
  })

  it('renders nothing when the issue carries no source list', () => {
    renderWithProviders(<IssueCard issue={brokenLinkIssue({ target_url: 'https://x/y' })} />)
    expect(screen.queryByText(/Linked from/i)).not.toBeInTheDocument()
  })
})

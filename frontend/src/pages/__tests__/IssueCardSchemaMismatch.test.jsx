import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import { IssueCard } from '../Results.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'

/**
 * SCHEMA_VISIBLE_MISMATCH detail renderer — the card must show each mismatched
 * schema field AND the exact schema value that isn't in the page's visible text.
 * Backend now emits extra.mismatched_fields as a list of {field, value} dicts.
 */
function makeMismatchIssue(mismatched_fields) {
  return {
    issue_code: 'SCHEMA_VISIBLE_MISMATCH',
    severity: 'warning',
    message: 'Schema not in visible text',
    extra: { mismatched_fields },
  }
}

describe('IssueCard — SCHEMA_VISIBLE_MISMATCH detail', () => {
  it('renders each mismatched field label and its schema value', () => {
    renderWithProviders(
      <IssueCard
        issue={makeMismatchIssue([
          { field: 'Article.headline', value: 'SEO Tips for Nonprofits' },
          { field: 'Person.name', value: 'Dr. Jane Doe' },
        ])}
        jobId="job-1"
        pageUrl="https://example.com/page"
        isOpen={false}
        onToggleFix={() => {}}
        onFixComplete={() => {}}
      />
    )
    // Field labels present.
    expect(screen.getByText('Article.headline')).toBeInTheDocument()
    expect(screen.getByText('Person.name')).toBeInTheDocument()
    // The actual schema values are shown to the user.
    expect(screen.getByText('"SEO Tips for Nonprofits"')).toBeInTheDocument()
    expect(screen.getByText('"Dr. Jane Doe"')).toBeInTheDocument()
  })

  it('defensively renders a legacy plain-string mismatch item', () => {
    renderWithProviders(
      <IssueCard
        issue={makeMismatchIssue(['Organization.name'])}
        jobId="job-1"
        pageUrl="https://example.com/page"
        isOpen={false}
        onToggleFix={() => {}}
        onFixComplete={() => {}}
      />
    )
    expect(screen.getByText('Organization.name')).toBeInTheDocument()
  })

  it('renders nothing extra when there are no mismatched fields', () => {
    renderWithProviders(
      <IssueCard
        issue={makeMismatchIssue([])}
        jobId="job-1"
        pageUrl="https://example.com/page"
        isOpen={false}
        onToggleFix={() => {}}
        onFixComplete={() => {}}
      />
    )
    expect(screen.queryByText(/not found in the page's visible text/)).toBeNull()
  })
})

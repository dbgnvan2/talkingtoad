/**
 * E4 — the systemic-defect surface in the Results summary.
 *
 * Spec: docs/pending/2026-08-29_E4-site-prevalence-escalation.md#E4.3
 *
 * P25: a value that exists in the API response but is never rendered is a
 * capability the user does not have. These assert the value actually reaches
 * the screen, not merely that the panel renders.
 */
import { fireEvent, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SummaryPanel from '../SummaryPanel'
import { renderWithProviders } from '../../test/test-utils'
import { mockFetchResponse } from '../../test/setup'
import CATEGORIES from '../../data/categories.generated.json'

const baseSummary = {
  health_score: 89,
  agent_health_score: 95,
  pages_crawled: 272,
  total_issues: 2137,
  by_severity: { critical: 0, warning: 173, info: 1964 },
  by_category: {},
}

const withPrevalence = {
  ...baseSummary,
  site_hygiene_score: 62,
  systemic_count: 2,
  prevalence: [
    {
      code: 'CONSENT_MODE_MISSING',
      human_description: 'Consent Mode Not Detected',
      pages_affected: 170,
      indexable_pages: 272,
      share: 0.625,
      tier: 'systemic',
    },
    {
      code: 'SEMANTIC_DENSITY_LOW',
      human_description: 'High Code-to-Text Ratio',
      pages_affected: 168,
      indexable_pages: 272,
      share: 0.6176,
      tier: 'systemic',
    },
    {
      code: 'META_DESC_MISSING',
      human_description: 'Missing Summary Snippet',
      pages_affected: 56,
      indexable_pages: 272,
      share: 0.2059,
      tier: 'widespread',
    },
  ],
}

// Reported by the owner after a re-crawl: "it says 16 systemic defects found but
// only lists five", and no row was clickable. Both are asserted below.
const SIX_SYSTEMIC = {
  ...baseSummary,
  site_hygiene_score: 34,
  systemic_count: 6,
  prevalence: [
    { code: 'CONSENT_MODE_MISSING', human_description: 'Consent Mode Not Detected',
      category: 'analytics', pages_affected: 74, indexable_pages: 74, share: 1.0,
      tier: 'systemic' },
    { code: 'IMG_ALT_MISSING', human_description: 'Images Missing Alt Text',
      category: 'image', pages_affected: 74, indexable_pages: 74, share: 1.0,
      tier: 'systemic' },
    { code: 'UNSAFE_CROSS_ORIGIN_LINK', human_description: 'Unsafe External Link',
      category: 'security', pages_affected: 74, indexable_pages: 74, share: 1.0,
      tier: 'systemic' },
    { code: 'AUTHOR_CREDENTIALS_MISSING', human_description: 'Author Credentials Missing',
      category: 'ai_readiness', pages_affected: 73, indexable_pages: 74, share: 0.986,
      tier: 'systemic' },
    { code: 'ENTITY_SAMEAS_MISSING', human_description: 'No sameAs Entity Links',
      category: 'ai_readiness', pages_affected: 73, indexable_pages: 74, share: 0.986,
      tier: 'systemic' },
    { code: 'SEMANTIC_DENSITY_LOW', human_description: 'High Code-to-Text Ratio',
      category: 'ai_readiness', pages_affected: 70, indexable_pages: 74, share: 0.946,
      tier: 'systemic' },
    { code: 'META_DESC_MISSING', human_description: 'Missing Summary Snippet',
      category: 'metadata', pages_affected: 20, indexable_pages: 74, share: 0.27,
      tier: 'widespread' },
  ],
}

const noop = () => {}

function renderPanel(summary, onCategoryClick = noop) {
  return renderWithProviders(
    <SummaryPanel summary={summary} onSeverityClick={noop} onCategoryClick={onCategoryClick} />
  )
}

describe('E4 systemic defects in the summary panel', () => {
  beforeEach(() => {
    // SummaryPanel mounts LLMSTxtGenerator, which fetches on mount. Give every
    // call a benign response so these tests exercise the panel, not the network.
    global.fetch.mockImplementation(() => mockFetchResponse({ content: '' }))
  })

  it('shows Site Hygiene alongside Health, not instead of it', () => {
    renderPanel(withPrevalence)
    expect(screen.getByText('Health Score')).toBeInTheDocument()
    expect(screen.getByText('Site Hygiene')).toBeInTheDocument()
    expect(screen.getByText('62')).toBeInTheDocument()
    expect(screen.getByText('89')).toBeInTheDocument()
  })

  it('states how many systemic defects there are', () => {
    renderPanel(withPrevalence)
    expect(screen.getByText(/2 systemic defects found/i)).toBeInTheDocument()
  })

  it('does not quote a threshold percentage it cannot guarantee', () => {
    // `always_systemic` codes bypass the share gate, so a 1%-footprint code can
    // be systemic. The heading previously hardcoded "30% or more", which the
    // classifier does not enforce — and which drifts the moment
    // api/config/prevalence.json changes (P4).
    renderPanel(withPrevalence)
    expect(screen.queryByText(/30% or more/i)).not.toBeInTheDocument()
  })

  it('names each systemic defect with its footprint', () => {
    renderPanel(withPrevalence)
    expect(screen.getByText('Consent Mode Not Detected')).toBeInTheDocument()
    expect(screen.getByText(/170 of 272 indexable pages \(63%\)/)).toBeInTheDocument()
  })

  it('lists only systemic defects, not widespread ones', () => {
    renderPanel(withPrevalence)
    expect(screen.queryByText('Missing Summary Snippet')).not.toBeInTheDocument()
  })

  it('renders nothing extra when no prevalence data was computed', () => {
    renderPanel(baseSummary)
    expect(screen.queryByText('Site Hygiene')).not.toBeInTheDocument()
    expect(screen.queryByText(/systemic defect/i)).not.toBeInTheDocument()
  })

  it('renders nothing extra when prevalence found no systemic defects', () => {
    renderPanel({
      ...baseSummary,
      site_hygiene_score: 100,
      systemic_count: 0,
      prevalence: [],
    })
    expect(screen.getByText('Site Hygiene')).toBeInTheDocument()
    expect(screen.queryByText(/systemic defect/i)).not.toBeInTheDocument()
  })
})

describe('E4 systemic defects — every defect listed and clickable', () => {
  beforeEach(() => {
    global.fetch.mockImplementation(() => mockFetchResponse({ content: '' }))
  })

  it('lists EVERY systemic defect, not just the first five', () => {
    // Reported: "it says 16 systemic defects found but only lists five".
    // A summary that names a count and shows a truncated list is a dead end.
    renderPanel(SIX_SYSTEMIC)
    for (const label of ['Consent Mode Not Detected', 'Images Missing Alt Text',
                         'Unsafe External Link', 'Author Credentials Missing',
                         'No sameAs Entity Links', 'High Code-to-Text Ratio']) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
  })

  it('still excludes widespread defects from the systemic list', () => {
    renderPanel(SIX_SYSTEMIC)
    expect(screen.queryByText('Missing Summary Snippet')).not.toBeInTheDocument()
  })

  it('makes each row a button that opens its own category and issue code', () => {
    const clicks = []
    renderPanel(SIX_SYSTEMIC, (index, code) => clicks.push([index, code]))

    fireEvent.click(screen.getByText('Unsafe External Link').closest('button'))
    expect(clicks).toHaveLength(1)
    const [index, code] = clicks[0]
    expect(code).toBe('UNSAFE_CROSS_ORIGIN_LINK')
    expect(CATEGORIES[index].key).toBe('security')
  })

  it('routes each defect to its OWN category, not a shared one', () => {
    const clicks = []
    renderPanel(SIX_SYSTEMIC, (index, code) => clicks.push([CATEGORIES[index].key, code]))

    fireEvent.click(screen.getByText('Images Missing Alt Text').closest('button'))
    fireEvent.click(screen.getByText('Consent Mode Not Detected').closest('button'))
    expect(clicks).toEqual([
      ['image', 'IMG_ALT_MISSING'],
      ['analytics', 'CONSENT_MODE_MISSING'],
    ])
  })

  it('shows the destination category on each row', () => {
    renderPanel(SIX_SYSTEMIC)
    const row = screen.getByText('Unsafe External Link').closest('button')
    expect(row.textContent).toMatch(/Security/i)
  })

  it('discloses a mismatch instead of silently showing a shorter list', () => {
    // The count and the list come from different fields. If they ever disagree,
    // the reader must be told rather than shown fewer rows without explanation.
    renderPanel({ ...SIX_SYSTEMIC, systemic_count: 16 })
    expect(screen.getByText(/Showing 6 of 16/i)).toBeInTheDocument()
  })

  it('does not disclose a mismatch when the numbers agree', () => {
    renderPanel(SIX_SYSTEMIC)
    expect(screen.queryByText(/Showing 6 of/i)).not.toBeInTheDocument()
  })

  it('does not make a row clickable when its category has no view', () => {
    renderPanel({
      ...baseSummary,
      systemic_count: 1,
      prevalence: [{ code: 'X', human_description: 'Unknown Category Finding',
                     category: 'not_a_real_category', pages_affected: 5,
                     indexable_pages: 10, share: 0.5, tier: 'systemic' }],
    })
    expect(screen.getByText('Unknown Category Finding').closest('button')).toBeDisabled()
  })
})

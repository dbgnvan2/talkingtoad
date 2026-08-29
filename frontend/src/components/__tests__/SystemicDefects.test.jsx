/**
 * E4 — the systemic-defect surface in the Results summary.
 *
 * Spec: docs/pending/2026-08-29_E4-site-prevalence-escalation.md#E4.3
 *
 * P25: a value that exists in the API response but is never rendered is a
 * capability the user does not have. These assert the value actually reaches
 * the screen, not merely that the panel renders.
 */
import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SummaryPanel from '../SummaryPanel'
import { renderWithProviders } from '../../test/test-utils'
import { mockFetchResponse } from '../../test/setup'

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

const noop = () => {}

function renderPanel(summary) {
  return renderWithProviders(
    <SummaryPanel summary={summary} onSeverityClick={noop} onCategoryClick={noop} />
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

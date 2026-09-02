/**
 * Phase 2 — the seven-part explainer renders, in order, with the caveat and tier.
 * Spec: docs/pending/2026-09-02_phase2-education-layer.md#E2.4
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('../../data/issueHelp.js', () => ({
  getIssueHelp: (code) => code === 'X_CODE' ? {
    title: 'A finding', mission_impact: 'Why a nonprofit cares.',
    definition: 'What it is.', impact: 'Why it matters.',
    good_vs_bad: { good: 'A good example.', bad: 'A bad example.' },
    how_it_can_mislead: 'Evidence tier: Heuristic. It can flag the wrong thing. Here is how.',
    fix: 'Do this.', confidence: 'Heuristic',
  } : null,
}))

import IssueHelpPanel from '../IssueHelpPanel.jsx'

describe('IssueHelpPanel', () => {
  it('renders every part of the explainer in reading order', () => {
    render(<IssueHelpPanel issueCode="X_CODE" />)
    const text = screen.getByTestId('issue-help').textContent
    const order = ['Why a nonprofit cares.', 'What it is.', 'Why it matters.', 'A good example.', 'A bad example.',
      'It can flag the wrong thing.', 'Do this.'].map(s => text.indexOf(s))
    expect(order.every(i => i >= 0)).toBe(true)
    expect(order).toEqual([...order].sort((a, b) => a - b))
  })

  it('shows the evidence tier as a badge and strips it from the caveat body', () => {
    render(<IssueHelpPanel issueCode="X_CODE" />)
    expect(screen.getByTestId('help-confidence')).toHaveTextContent('Heuristic')
    expect(screen.getByTestId('help-mislead')).not.toHaveTextContent('Evidence tier:')
    expect(screen.getByTestId('help-mislead')).toHaveTextContent('It can flag the wrong thing.')
  })

  it('renders nothing for an unknown code', () => {
    const { container } = render(<IssueHelpPanel issueCode="NOPE" />)
    expect(container.firstChild).toBeNull()
  })
})

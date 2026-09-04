/**
 * P7.1 — the four tools that change a nonprofit's site now explain themselves.
 *
 * Counted before the work: GEOReportPanel 2, GSCInsightsPanel 1, and zero on
 * FaqSchemaModal, GeoSettingsModal, ImageAnalysisPanel and BatchOptimizePanel.
 * The structural sweep then found two MORE hand-written copies the TODO had not
 * listed (PagePriorityPanel, FixFocusPanel) — five copies, and their labels had
 * already drifted ("Why it matters" vs "Why it's useful", "Good vs. bad" vs
 * "Good vs bad"). The labels live once now, in PanelExplainer.
 *
 * Completeness, substance and id validity are pinned in
 * tests/test_panel_help_completeness.py. This file asserts what a reader sees.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PanelExplainer from '../PanelExplainer.jsx'
import PANEL_HELP from '../../data/panelHelp.json'
import BatchOptimizePanel from '../BatchOptimizePanel.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

describe('PanelExplainer', () => {
  it('renders all five parts for every registered panel', () => {
    for (const id of Object.keys(PANEL_HELP)) {
      const { unmount } = render(<PanelExplainer id={id} />)
      for (const label of ['What it is:', "Why it's useful:", 'Good vs bad:',
                           'How it can mislead:', 'How to use:']) {
        expect(screen.getByText(label), `${id} missing ${label}`).toBeInTheDocument()
      }
      unmount()
    }
  })

  it('renders nothing for an unregistered id rather than crashing', () => {
    const { container } = render(<PanelExplainer id="not-a-panel" />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('BatchOptimizePanel explainer', () => {
  beforeEach(() => {
    global.fetch.mockReset()
    global.fetch.mockImplementation(() => mockFetchResponse({}))
  })

  it('is behind a toggle, not shown before the user asks', () => {
    renderWithProviders(
      <BatchOptimizePanel jobId="j" selectedImages={[]} onClose={vi.fn()} onComplete={vi.fn()} />
    )
    expect(screen.queryByTestId('panel-explainer-batch-optimise')).toBeNull()
    expect(screen.getByText('What is this?')).toBeInTheDocument()
  })

  it('says the old images keep being served until you swap them by hand', async () => {
    // The specific sentence, not "an explainer rendered". Without it an operator
    // watching a green progress bar will reasonably believe their site got
    // faster — the tool uploads NEW files and CLAUDE.md forbids rewriting the
    // image links automatically. It is the one line whose absence would let
    // someone report a change that did not happen.
    renderWithProviders(
      <BatchOptimizePanel jobId="j" selectedImages={[]} onClose={vi.fn()} onComplete={vi.fn()} />
    )
    await userEvent.click(screen.getByText('What is this?'))
    const block = screen.getByTestId('panel-explainer-batch-optimise')
    expect(block).toHaveTextContent(/uploads NEW files/i)
    expect(block).toHaveTextContent(/keep serving the old images until you replace each one by hand/i)
  })
})

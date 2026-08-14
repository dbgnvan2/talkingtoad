import { describe, it, expect, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { renderWithProviders } from '../../test/test-utils.jsx'
import FixFocusItemsHelp from '../FixFocusItemsHelp.jsx'

// FFS2 — the deduped Fix Focus item glossary. TITLE_MISSING has a real issueHelp
// entry; ZZZ_NO_HELP does not (exercises the human_description fallback).

const SNAPSHOT = {
  seo: {
    pages: [
      { url: 'https://x.org/a', items: [{ issue_code: 'TITLE_MISSING', priority_rank: 64, human_description: 'Missing title' }] },
      { url: 'https://x.org/b', items: [{ issue_code: 'TITLE_MISSING', priority_rank: 64, human_description: 'Missing title' }] },
    ],
  },
  geo: {
    pages: [
      { url: 'https://x.org/a', items: [{ issue_code: 'ZZZ_NO_HELP', priority_rank: 40, human_description: 'Disconnect page' }] },
    ],
  },
}

function mockOk(body) {
  global.fetch.mockImplementation(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) })
  )
}

describe('FixFocusItemsHelp', () => {
  beforeEach(() => { global.fetch.mockReset() })

  it('dedupes a repeated item to a single help entry', async () => {
    mockOk(SNAPSHOT)
    renderWithProviders(<FixFocusItemsHelp jobId="job1" />)
    // TITLE_MISSING appears on two SEO pages, but its help renders exactly once.
    await waitFor(() => expect(screen.getByText('Page title missing')).toBeInTheDocument())
    expect(screen.getAllByText('Page title missing')).toHaveLength(1)
  })

  it('renders the what-it-is and fix fields from issueHelp', async () => {
    mockOk(SNAPSHOT)
    renderWithProviders(<FixFocusItemsHelp jobId="job1" />)
    await waitFor(() => expect(screen.getByText('Page title missing')).toBeInTheDocument())
    expect(screen.getByText('What it is')).toBeInTheDocument()
    expect(screen.getByText('How to fix')).toBeInTheDocument()
  })

  it('falls back to human_description when there is no help entry', async () => {
    mockOk(SNAPSHOT)
    renderWithProviders(<FixFocusItemsHelp jobId="job1" />)
    await waitFor(() => expect(screen.getByText('Disconnect page')).toBeInTheDocument())
    expect(screen.getByText(/No detailed help entry/)).toBeInTheDocument()
  })

  it('shows an empty state when there are no items', async () => {
    mockOk({ seo: { pages: [] }, geo: { pages: [] } })
    renderWithProviders(<FixFocusItemsHelp jobId="job1" />)
    await waitFor(() => expect(screen.getByText(/No Fix Focus items yet/)).toBeInTheDocument())
  })

  it('shows an error state when the request fails', async () => {
    global.fetch.mockImplementation(() =>
      Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({ error: { message: 'boom' } }) })
    )
    renderWithProviders(<FixFocusItemsHelp jobId="job1" />)
    await waitFor(() => expect(screen.getByText(/Failed to load item help|boom|HTTP 500/)).toBeInTheDocument())
  })
})

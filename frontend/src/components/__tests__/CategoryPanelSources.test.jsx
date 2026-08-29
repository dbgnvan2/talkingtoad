/**
 * "Show Source Pages" on the Broken Links panel.
 *
 * The endpoint returns an envelope `{target_url, sources, count}`. The component
 * assigned the whole object to its `sources` state, so `sources.length` was
 * `undefined` and `sources.map` threw — the panel expanded onto nothing and the
 * button looked dead. Reported on livingsystems.ca/dontation_form.
 *
 * A rendered-widget test would not have caught this: the button rendered fine.
 * These assert the data actually reaches the list.
 */
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { BrokenLinkItem } from '../CategoryPanel'
import { renderWithProviders } from '../../test/test-utils'
import { mockFetchResponse } from '../../test/setup'

const BROKEN = 'https://livingsystems.ca/dontation_form'

const envelope = (sources) => ({
  target_url: BROKEN,
  sources,
  count: sources.length,
})

const source = (n) => ({
  source_url: `https://livingsystems.ca/post-${n}`,
  target_url: BROKEN,
  link_text: 'Donate',
  link_type: 'internal',
})

describe('BrokenLinkItem — Show Source Pages', () => {
  beforeEach(() => {
    global.fetch.mockReset()
  })

  it('lists the source pages from the response envelope', async () => {
    global.fetch.mockImplementation(() =>
      mockFetchResponse(envelope([source(1), source(2), source(3)]))
    )
    renderWithProviders(<BrokenLinkItem jobId="job-1" brokenUrl={BROKEN} />)

    await userEvent.click(screen.getByRole('button', { name: /show source pages/i }))

    await waitFor(() => {
      expect(screen.getByText(/found on 3 pages/i)).toBeInTheDocument()
    })
    expect(screen.getByText('https://livingsystems.ca/post-1')).toBeInTheDocument()
    expect(screen.getByText('https://livingsystems.ca/post-3')).toBeInTheDocument()
  })

  it('uses the singular for one source page', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse(envelope([source(1)])))
    renderWithProviders(<BrokenLinkItem jobId="job-1" brokenUrl={BROKEN} />)

    await userEvent.click(screen.getByRole('button', { name: /show source pages/i }))
    await waitFor(() => {
      expect(screen.getByText(/found on 1 page:/i)).toBeInTheDocument()
    })
  })

  it('handles an empty source list without throwing', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse(envelope([])))
    renderWithProviders(<BrokenLinkItem jobId="job-1" brokenUrl={BROKEN} />)

    await userEvent.click(screen.getByRole('button', { name: /show source pages/i }))
    await waitFor(() => {
      expect(screen.getByText(/found on 0 pages/i)).toBeInTheDocument()
    })
  })

  it('tolerates a bare array, in case the contract is ever simplified', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse([source(1), source(2)]))
    renderWithProviders(<BrokenLinkItem jobId="job-1" brokenUrl={BROKEN} />)

    await userEvent.click(screen.getByRole('button', { name: /show source pages/i }))
    await waitFor(() => {
      expect(screen.getByText(/found on 2 pages/i)).toBeInTheDocument()
    })
  })

  it('surfaces an error instead of silently doing nothing', async () => {
    global.fetch.mockImplementation(() =>
      mockFetchResponse({ error: { message: 'No job with id job-1' } }, 404)
    )
    renderWithProviders(<BrokenLinkItem jobId="job-1" brokenUrl={BROKEN} />)

    await userEvent.click(screen.getByRole('button', { name: /show source pages/i }))
    await waitFor(() => {
      expect(screen.getByText(/No job with id job-1/)).toBeInTheDocument()
    })
  })
})

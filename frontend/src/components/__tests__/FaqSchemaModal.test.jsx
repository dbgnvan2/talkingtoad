import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import FaqSchemaModal from '../FaqSchemaModal.jsx'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { mockFetchResponse } from '../../test/setup.js'

const props = { jobId: 'job1', pageUrl: 'https://example.com/counselling/', onClose: vi.fn() }

const SCHEMA = JSON.stringify({
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: [{ '@type': 'Question', name: 'Who is it for?', acceptedAnswer: { '@type': 'Answer', text: 'Anyone.' } }],
}, null, 2)

describe('FaqSchemaModal', () => {
  beforeEach(() => { global.fetch.mockReset() })

  it('renders the generated schema with copy + download actions', async () => {
    global.fetch.mockImplementation(() =>
      mockFetchResponse({ jsonld: SCHEMA, question_count: 2, refused: false, reason: null }))
    renderWithProviders(<FaqSchemaModal {...props} />)
    await waitFor(() => expect(screen.getByText('Copy snippet')).toBeInTheDocument())
    expect(screen.getByText('Download .html')).toBeInTheDocument()
    expect(screen.getByText('Download .json')).toBeInTheDocument()
    // the script-wrapped snippet is shown
    expect(screen.getByText(/application\/ld\+json/)).toBeInTheDocument()
  })

  it('shows the refusal reason instead of a schema box', async () => {
    global.fetch.mockImplementation(() =>
      mockFetchResponse({ jsonld: null, question_count: 1, refused: true, reason: 'Answers appear only after a JavaScript click.' }))
    renderWithProviders(<FaqSchemaModal {...props} />)
    await waitFor(() => expect(screen.getByText(/JavaScript click/)).toBeInTheDocument())
    expect(screen.queryByText('Copy snippet')).not.toBeInTheDocument()
  })

  it('shows an error when the request fails', async () => {
    global.fetch.mockImplementation(() => mockFetchResponse({ error: 'Page not found' }))
    renderWithProviders(<FaqSchemaModal {...props} />)
    await waitFor(() => expect(screen.getByText('Page not found')).toBeInTheDocument())
  })
})

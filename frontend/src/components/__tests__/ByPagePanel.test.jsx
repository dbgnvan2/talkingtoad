import { describe, it, expect, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { renderWithProviders } from '../../test/test-utils.jsx'
import ByPagePanel from '../ByPagePanel.jsx'

describe('ByPagePanel', () => {
  beforeEach(() => global.fetch.mockReset())

  it('renders a Citability column with the per-page grade (E5)', async () => {
    global.fetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          pages: [
            { url: 'https://x/a', status_code: 200, citability_grade: 72, issue_counts: { total: 1, critical: 0, warning: 1, info: 0 } },
            { url: 'https://x/b', status_code: 200, citability_grade: 30, issue_counts: { total: 0, critical: 0, warning: 0, info: 0 } },
          ],
        }),
      })
    )
    renderWithProviders(<ByPagePanel jobId="job1" domain="x" onPageClick={() => {}} />)
    await waitFor(() => expect(screen.getByText('https://x/a')).toBeInTheDocument())
    expect(screen.getByText('Citability')).toBeInTheDocument()
    expect(screen.getByText('72')).toBeInTheDocument()
    expect(screen.getByText('30')).toBeInTheDocument()
  })

  it('shows a dash when citability_grade is absent (old crawls, P8)', async () => {
    global.fetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          pages: [
            { url: 'https://x/a', status_code: 200, issue_counts: { total: 0, critical: 0, warning: 0, info: 0 } },
          ],
        }),
      })
    )
    renderWithProviders(<ByPagePanel jobId="job1" domain="x" onPageClick={() => {}} />)
    await waitFor(() => expect(screen.getByText('https://x/a')).toBeInTheDocument())
    expect(screen.getByText('—')).toBeInTheDocument()
  })
})

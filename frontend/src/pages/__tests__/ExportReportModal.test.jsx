/**
 * Phase 3 — PDF export options persist per browser.
 * Spec: docs/pending/2026-09-02_phase3-happy-path.md#R3.6
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { renderWithProviders } from '../../test/test-utils.jsx'
import { ExportReportModal, loadPdfOpts, PDF_OPTS_KEY } from '../Results.jsx'

describe('ExportReportModal persistence', () => {
  beforeEach(() => localStorage.clear())

  it('starts from the defaults when nothing is stored or the value is corrupt', () => {
    expect(loadPdfOpts()).toEqual({ includeHelp: true, includePages: true, summaryOnly: false })
    localStorage.setItem(PDF_OPTS_KEY, '{not json')
    expect(loadPdfOpts()).toEqual({ includeHelp: true, includePages: true, summaryOnly: false })
    localStorage.setItem(PDF_OPTS_KEY, JSON.stringify({ includeHelp: 'yes', bogus: true }))
    expect(loadPdfOpts().includeHelp).toBe(true)
  })

  it('reads a stored choice and writes a changed one', () => {
    localStorage.setItem(PDF_OPTS_KEY, JSON.stringify({ includeHelp: false }))
    const onDownload = vi.fn()
    renderWithProviders(<ExportReportModal onClose={() => {}} onDownload={onDownload} />)
    const help = screen.getByLabelText(/help text/i)
    expect(help.checked).toBe(false)
    fireEvent.click(help)
    expect(JSON.parse(localStorage.getItem(PDF_OPTS_KEY)).includeHelp).toBe(true)
    fireEvent.click(screen.getByText('Generate PDF'))
    expect(onDownload).toHaveBeenCalledWith(expect.objectContaining({ includeHelp: true, includePages: true }))
  })
})

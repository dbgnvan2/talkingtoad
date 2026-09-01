import React, { useState } from 'react'
import { getPageDetails } from '../api.js'

/**
 * D6 — "What to look for": the offending elements for one issue.
 *
 * The lines are rendered SERVER-side (api/services/issue_evidence.py) and shipped
 * on every issue as `evidence`. Deliberately not re-implemented here: a second
 * copy of a 15-shape renderer in another language is a drift waiting to happen
 * (P19), and this way the panel, the PDF and the Excel export cannot disagree.
 *
 * Lived in CategoryPanel.jsx until 2026-09-01, which is exactly why the Page
 * Audit panel showed no evidence at all: the component existed, was correct,
 * and the second screen was never connected to it.
 *
 * Spec: docs/functional-specification.md (D6)
 */
export function IssueEvidence({ evidence, evidenceTotal, source, capNote }) {
  if (!Array.isArray(evidence) || evidence.length === 0) return null
  return (
    <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-xl">
      <h4 className="text-[10px] font-black text-amber-800 uppercase tracking-widest mb-2">
        What to look for
        {source === 'live' && <span className="ml-2 normal-case font-bold text-green-700">· read from the page just now</span>}
        {source === 'stored' && <span className="ml-2 normal-case font-bold text-gray-500">· from the last crawl</span>}
      </h4>
      <ul className="space-y-1">
        {evidence.map((line, idx) => {
          const indented = line.startsWith('  ')
          const text = line.trim()
          const isHeading = !indented && text.endsWith(':')
          return (
            <li
              key={`${text}-${idx}`}
              className={
                isHeading
                  ? 'text-xs font-bold text-amber-900 mt-2 first:mt-0'
                  : `text-xs text-gray-800 break-all ${indented ? 'pl-4 font-mono' : ''}`
              }
            >
              {text}
            </li>
          )
        })}
      </ul>
      {evidenceTotal > evidence.length && (
        <p className="text-[11px] text-amber-800 mt-2">
          Showing {evidence.length} of {evidenceTotal}.{' '}
          {capNote || 'The full list is in the spreadsheet export.'}
        </p>
      )}
    </div>
  )
}

/**
 * D6 — the finding has no sub-elements to point at.
 *
 * Thirty codes are like this (PAGE_IS_THE_EVIDENCE): the page URL IS the
 * finding. Rendering nothing for them would read as "nothing wrong here",
 * which is the opposite of the truth — so say it in words. The backend tells
 * us which via `evidence_basis`; a copy of that 30-code list here would be the
 * hand-mirrored enumeration the shared renderer exists to avoid.
 */
export function NoItemsToList({ basis }) {
  return (
    <div className="mb-6 p-4 bg-gray-50 border border-gray-200 rounded-xl">
      <p className="text-xs text-gray-600">
        {basis === 'page'
          ? 'This finding is about the page as a whole — there is no list of items to point at. The fix is on this page.'
          : 'No specific items were recorded for this finding during the crawl. Use “Get full details” to read the page now.'}
      </p>
    </div>
  )
}

/**
 * D6 — the per-issue details block for the Page Audit panel.
 *
 * Renders what the payload already carries (free, no request), and offers a
 * live read when the crawl-time list was capped or empty. The live read stores
 * nothing — that was the owner's explicit framing, "show this, but not bother
 * to store it".
 */
export function IssueDetails({ jobId, pageUrl, issue }) {
  const [open, setOpen] = useState(false)
  const [live, setLive] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const basis = issue.evidence_basis || 'items'
  const stored = Array.isArray(issue.evidence) ? issue.evidence : []
  const storedTotal = issue.evidence_total || 0
  // Offer the live read when the stored list is short of the truth, or when
  // nothing was captured for a code that names items. `jobId`/`pageUrl` are
  // required: IssueCard is also rendered standalone (tests, the category view)
  // where there is no page to re-read, and a button that cannot work should
  // not appear.
  const canFetchMore =
    Boolean(jobId && pageUrl) &&
    basis !== 'page' &&
    (storedTotal > stored.length || stored.length === 0)

  async function fetchDetails() {
    setLoading(true)
    setError(null)
    try {
      const res = await getPageDetails(jobId, pageUrl, issue.issue_code)
      const entry = (res.details || []).find(d => d.issue_code === issue.issue_code)
      if (!entry) {
        // The code is gone from the live page. That is a real answer, not an
        // error, and it must not be reported as "no details available".
        setLive({ gone: true, source: res.source, caveat: res.caveat })
      } else {
        setLive({ ...entry, source: res.source, caveat: res.caveat,
                  capNote: res.capture_cap_note })
      }
    } catch (err) {
      setError(err.message || 'Could not read the page.')
    } finally {
      setLoading(false)
    }
  }

  const shown = live && !live.gone ? live.items : stored
  const shownTotal = live && !live.gone ? live.items_total : storedTotal

  return (
    <div className="mt-3">
      <button
        onClick={() => setOpen(o => !o)}
        className="text-xs font-bold text-amber-800 hover:text-amber-900 underline"
        aria-expanded={open}
      >
        {open ? 'Hide details' : 'Details'}
      </button>

      {open && (
        <div className="mt-2">
          {live?.caveat && (
            <p className="mb-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900">
              {live.caveat}
            </p>
          )}
          {error && (
            <p className="mb-2 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-800">
              Could not get full details: {error}
            </p>
          )}
          {live?.gone && (
            <p className="mb-2 p-3 bg-green-50 border border-green-200 rounded-lg text-xs text-green-800">
              This finding is no longer on the page as it is now.
            </p>
          )}

          {shown.length > 0 ? (
            <IssueEvidence
              evidence={shown}
              evidenceTotal={shownTotal}
              source={live ? live.source : undefined}
              capNote={live?.capNote}
            />
          ) : (
            !live?.gone && <NoItemsToList basis={basis} />
          )}

          {canFetchMore && !live && (
            <button
              onClick={fetchDetails}
              disabled={loading}
              className="px-3 py-1.5 bg-amber-600 text-white rounded-lg text-xs font-bold hover:bg-amber-700 disabled:opacity-50"
            >
              {loading ? 'Reading the page…' : 'Get full details'}
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export default IssueEvidence

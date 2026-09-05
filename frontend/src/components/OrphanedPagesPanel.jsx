import { useState, useEffect } from 'react'
import { getOrphanedPages } from '../api.js'
import Spinner from './Spinner.jsx'

// O2 — orphan detection is an absence-proof: it can only conclude "nothing
// links here" after seeing the whole site. When the crawl was narrowed, the
// check is skipped and the result is zero — which the green all-clear below
// would otherwise report as "no orphans found" (P31).
// Spec: docs/functional-specification.md §4.4 (ORPHAN_PAGE)
const SKIP_REASONS = {
  skipped_partial_scan:
    'this was a partial scan, so pages outside the selected content types were never fetched',
  skipped_truncated:
    'the crawl stopped at its page limit, so the rest of the site was never fetched',
  skipped_cancelled:
    'the crawl was cancelled before it finished, so part of the site was never fetched',
  skipped_single_page:
    'this was a single-page scan, which never looks at the rest of the site',
  skipped_failed:
    'the crawl failed before the site-wide checks ran',
  not_run:
    'coverage was not recorded for this crawl',
  skipped_error:
    'the results could not be loaded, so nothing about this check is known',
}

// Any status that is not 'complete' means the check did not run. An unknown
// value must therefore fall back to the generic explanation and NEVER to
// silence — returning null here would render a heading with no count, no
// explanation, and no rows, which reads as "nothing to report".
const GENERIC_SKIP_REASON = 'this scan did not cover the whole site'

function SkippedNotice({ detection }) {
  const reason = SKIP_REASONS[detection.status] || GENERIC_SKIP_REASON
  const analysed = detection.pages_analysed ?? 0
  const outOfScope = detection.pages_out_of_scope ?? 0
  return (
    <div className="py-8 px-6 bg-white rounded-2xl border border-blue-200">
      <p className="text-blue-700 font-medium">Orphan detection was not run for this scan.</p>
      <p className="text-sm text-gray-600 mt-2">
        {`This check reports pages that nothing links to, which is only knowable after crawling the
        whole site. Here ${reason} — ${analysed} ${analysed === 1 ? 'page was' : 'pages were'} analysed`}
        {outOfScope > 0 ? ` and ${outOfScope} were not fetched` : ''}
        {`. A page linked only from an unfetched page cannot be told apart from an orphan, so no
        result is shown rather than a misleading one.`}
      </p>
      <p className="text-sm text-gray-600 mt-2">Run a full scan to check for orphaned pages.</p>
    </div>
  )
}

// A crawl that DID cover the whole site still skipped WordPress archive pages
// before reading their outbound links, so "complete" is not "saw every anchor".
function CompletenessFootnote({ detection }) {
  const parts = []
  if (detection.archives_skipped) {
    parts.push('WordPress archive pages (author, category, tag, date, paginated) were skipped')
  }
  const unread = detection.pages_links_unread ?? 0
  if (unread > 0) {
    parts.push(`${unread} page${unread === 1 ? '' : 's'} could not be read (timeout, login wall or parse error)`)
  }
  if (parts.length === 0) return null
  return (
    <p className="text-xs text-gray-400 mt-3">
      {`${parts.join('; ')} — a page linked only from one of those may still be listed here.`}
    </p>
  )
}

export default function OrphanedPagesPanel({ jobId, domain, onPageClick }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getOrphanedPages(jobId)
      .then(setData)
      // A failed request tells us nothing about orphans. Returning a bare
      // {count: 0} here would render the green all-clear — the exact
      // fabricated pass this panel exists to prevent (P31).
      .catch(() => setData({ count: 0, pages: [], detection: { status: 'skipped_error' } }))
      .finally(() => setLoading(false))
  }, [jobId])

  if (loading) return <div className="py-20"><Spinner /></div>

  const skipped = data.detection && data.detection.status !== 'complete'

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-800">{domain ? `Orphaned Pages - ${domain}` : 'Orphaned Pages'}</h2>
        <p className="text-sm text-gray-500 mt-1">Pages discovered during the crawl that have no internal links pointing to them. Search engines may not find these pages.</p>
      </div>

      {!skipped && (
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-white p-4 rounded-xl border border-amber-200 text-center">
            <p className="text-2xl font-bold text-amber-600">{data.count}</p>
            <p className="text-xs text-amber-500 uppercase font-bold">Orphaned Pages</p>
          </div>
          <div className="bg-white p-4 rounded-xl border border-gray-200 text-center">
            <p className="text-xs text-gray-500 mt-2">These pages are reachable only via the sitemap or direct URL — no other page on your site links to them.</p>
          </div>
        </div>
      )}

      {skipped ? (
        <SkippedNotice detection={data.detection} />
      ) : data.count === 0 ? (
        <div className="py-12 bg-white rounded-2xl border border-green-200 text-center">
          <p className="text-green-600 text-2xl mb-2">✓</p>
          <p className="text-green-700 font-medium">All crawled pages have at least one internal link pointing to them.</p>
          {data.detection && <CompletenessFootnote detection={data.detection} />}
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 bg-gray-50">
            <p className="text-sm font-bold text-gray-700">{data.count} orphaned page{data.count !== 1 ? 's' : ''}</p>
          </div>
          <div className="divide-y divide-gray-100 max-h-[600px] overflow-y-auto">
            {data.pages.map((issue, idx) => (
              <div key={issue.page_url} className="flex items-center gap-4 px-6 py-3 hover:bg-gray-50">
                <span className="text-amber-500 font-bold text-sm w-8 text-center flex-shrink-0">{idx + 1}</span>
                <div className="flex-1 min-w-0">
                  <button
                    onClick={() => onPageClick?.(issue.page_url)}
                    className="text-sm font-mono text-blue-600 hover:underline truncate block text-left w-full"
                  >
                    {issue.page_url}
                  </button>
                  {issue.extra?.title && (
                    <p className="text-xs text-gray-400 truncate">{issue.extra.title}</p>
                  )}
                </div>
                <a
                  href={issue.page_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-3 py-1.5 text-xs font-bold bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 flex-shrink-0"
                >
                  Visit
                </a>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

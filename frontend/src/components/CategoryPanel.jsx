import React, { useState, useEffect, useMemo } from 'react'
import { getResultsByCategory, verifyBrokenLinks, markBrokenLinkFixed, getOrphanedMedia, authHeaders } from '../api.js'
import { FIXABLE_LINK_CODES } from './FixBrokenLinkPanel.jsx'
import SeverityBadge from './SeverityBadge.jsx'
import IssueHelpPanel from './IssueHelpPanel.jsx'
import Spinner from './Spinner.jsx'

export default function CategoryPanel({ jobId, category, domain, onPageClick, onShowHelp, onSummaryRefresh }) {
  const [data, setData] = useState(null)
  const [expandedCode, setExpandedCode] = useState(null)
  const [verifying, setVerifying] = useState(false)
  const [verifyResult, setVerifyResult] = useState(null)
  const [markingFixed, setMarkingFixed] = useState(false)
  const [markedFixed, setMarkedFixed] = useState(new Set())
  const [orphanedMedia, setOrphanedMedia] = useState(null)
  const [loadingOrphans, setLoadingOrphans] = useState(false)

  useEffect(() => {
    setData(null)
    setVerifyResult(null)
    setMarkedFixed(new Set())
    getResultsByCategory(jobId, category.key).then(setData).catch(() => setData({ issues: [] }))
  }, [jobId, category.key])

  async function handleVerifyBrokenLinks() {
    setVerifying(true)
    setVerifyResult(null)
    setMarkedFixed(new Set())
    try {
      const result = await verifyBrokenLinks(jobId)
      setVerifyResult(result)
    } catch (err) {
      setVerifyResult({ error: err.message })
    } finally {
      setVerifying(false)
    }
  }

  async function handleMarkAllFixed() {
    if (!verifyResult || verifyResult.fixed === 0) return
    setMarkingFixed(true)
    const fixedUrls = verifyResult.results.filter(r => r.is_fixed).map(r => r.url)
    const newMarked = new Set(markedFixed)

    for (const url of fixedUrls) {
      try {
        await markBrokenLinkFixed(jobId, url)
        newMarked.add(url)
      } catch (err) {
        console.error('Failed to mark as fixed:', url, err)
      }
    }

    setMarkedFixed(newMarked)
    setMarkingFixed(false)

    getResultsByCategory(jobId, category.key).then(setData).catch(() => {})
    onSummaryRefresh?.()
  }

  async function handleMarkOneFixed(url) {
    try {
      await markBrokenLinkFixed(jobId, url)
      setMarkedFixed(prev => new Set([...prev, url]))
      getResultsByCategory(jobId, category.key).then(setData).catch(() => {})
      onSummaryRefresh?.()
    } catch (err) {
      alert('Failed to mark as fixed: ' + err.message)
    }
  }

  const groups = useMemo(() => {
    if (!data?.issues) return {}
    return data.issues.reduce((acc, iss) => {
      if (!acc[iss.issue_code]) acc[iss.issue_code] = { ...iss, count: 0, pages: [] }
      acc[iss.issue_code].count++
      acc[iss.issue_code].pages.push(iss.page_url)
      return acc
    }, {})
  }, [data])

  if (!data) return <div className="py-20"><Spinner /></div>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-800">{category.label}{domain ? ` - ${domain}` : ''}</h2>
        <div className="flex items-center gap-3">
          {category.key === 'broken_link' && (
            <button
              onClick={handleVerifyBrokenLinks}
              disabled={verifying}
              className="px-4 py-2 bg-blue-600 text-white text-sm font-bold rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
              title="Quick check if broken links are still broken without a full crawl"
            >
              {verifying ? (
                <>
                  <span className="animate-spin">⟳</span>
                  Checking...
                </>
              ) : (
                <>🔍 Verify All</>
              )}
            </button>
          )}
          {category.key === 'image' && (
            <button
              onClick={async () => {
                setLoadingOrphans(true)
                try {
                  const result = await getOrphanedMedia(jobId)
                  setOrphanedMedia(result)
                } catch (err) {
                  setOrphanedMedia({ error: err.message })
                } finally {
                  setLoadingOrphans(false)
                }
              }}
              disabled={loadingOrphans}
              className="px-4 py-2 bg-purple-600 text-white text-sm font-bold rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center gap-2"
              title="Find images in WordPress Media Library not used on any crawled page"
            >
              {loadingOrphans ? (
                <>
                  <span className="animate-spin">⟳</span>
                  Scanning WP...
                </>
              ) : (
                <>Find Orphaned Images</>
              )}
            </button>
          )}
          <button
            onClick={onShowHelp}
            className="w-8 h-8 flex items-center justify-center rounded-full bg-indigo-100 text-indigo-600 hover:bg-indigo-200 transition-all font-bold"
            title={`Learn about ${category.label}`}
          >
            ?
          </button>
        </div>
      </div>

      {verifyResult && (
        <div className={`p-4 rounded-xl border ${verifyResult.error ? 'bg-red-50 border-red-200' : 'bg-blue-50 border-blue-200'}`}>
          {verifyResult.error ? (
            <p className="text-red-700 font-medium">Error: {verifyResult.error}</p>
          ) : (
            <>
              <div className="flex items-center gap-4 mb-3">
                <span className="text-lg font-bold text-gray-800">Verification Results</span>
                <button
                  onClick={() => setVerifyResult(null)}
                  className="text-gray-400 hover:text-gray-600 text-xl ml-auto"
                >×</button>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <div className="bg-white p-3 rounded-lg border border-gray-200 text-center">
                  <p className="text-2xl font-bold text-gray-800">{verifyResult.total}</p>
                  <p className="text-xs text-gray-500 uppercase font-bold">Total</p>
                </div>
                <div className="bg-white p-3 rounded-lg border border-green-200 text-center">
                  <p className="text-2xl font-bold text-green-600">{verifyResult.fixed}</p>
                  <p className="text-xs text-green-600 uppercase font-bold">Fixed</p>
                </div>
                <div className="bg-white p-3 rounded-lg border border-red-200 text-center">
                  <p className="text-2xl font-bold text-red-600">{verifyResult.still_broken}</p>
                  <p className="text-xs text-red-600 uppercase font-bold">Still Broken</p>
                </div>
                <div className="bg-white p-3 rounded-lg border border-yellow-200 text-center">
                  <p className="text-2xl font-bold text-yellow-600">{verifyResult.errors}</p>
                  <p className="text-xs text-yellow-600 uppercase font-bold">Errors</p>
                </div>
              </div>
              {verifyResult.fixed > 0 && (
                <div className="bg-green-100 border border-green-300 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-bold text-green-800">✓ Fixed Links (now returning 2xx):</p>
                    <button
                      onClick={handleMarkAllFixed}
                      disabled={markingFixed || verifyResult.results.filter(r => r.is_fixed).every(r => markedFixed.has(r.url))}
                      className="px-3 py-1.5 bg-green-600 text-white text-xs font-bold rounded-lg hover:bg-green-700 disabled:opacity-50"
                    >
                      {markingFixed ? 'Marking...' : markedFixed.size === verifyResult.fixed ? '✓ All Marked' : 'Mark All as Fixed'}
                    </button>
                  </div>
                  <ul className="space-y-2">
                    {verifyResult.results.filter(r => r.is_fixed).map(r => (
                      <li key={r.url} className="text-xs text-green-700 font-mono flex items-center gap-2 bg-white p-2 rounded-lg border border-green-200">
                        <span className="text-green-500 text-lg">{markedFixed.has(r.url) ? '✅' : '✓'}</span>
                        <span className="truncate flex-1" title={r.url}>{r.url}</span>
                        <span className="text-green-600 text-[10px] flex-shrink-0">({r.previous_status} → {r.current_status})</span>
                        {!markedFixed.has(r.url) && (
                          <button
                            onClick={() => handleMarkOneFixed(r.url)}
                            className="px-2 py-1 bg-green-500 text-white text-[10px] font-bold rounded hover:bg-green-600 flex-shrink-0"
                          >
                            Mark Fixed
                          </button>
                        )}
                        {markedFixed.has(r.url) && (
                          <span className="text-[10px] font-bold text-green-600 flex-shrink-0">Marked ✓</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      )}
      {orphanedMedia && (
        <div className={`p-4 rounded-xl border ${orphanedMedia.error ? 'bg-red-50 border-red-200' : 'bg-purple-50 border-purple-200'}`}>
          {orphanedMedia.error ? (
            <div className="flex items-center justify-between">
              <p className="text-red-700 font-medium">Error: {orphanedMedia.error}</p>
              <button onClick={() => setOrphanedMedia(null)} className="text-gray-400 hover:text-gray-600 text-xl">×</button>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between mb-3">
                <span className="text-lg font-bold text-gray-800">
                  Orphaned Media: {orphanedMedia.count} image{orphanedMedia.count !== 1 ? 's' : ''} not used on any page
                </span>
                <button onClick={() => setOrphanedMedia(null)} className="text-gray-400 hover:text-gray-600 text-xl">×</button>
              </div>
              {orphanedMedia.count === 0 ? (
                <p className="text-sm text-green-700 font-medium">All WordPress media images are referenced on at least one crawled page.</p>
              ) : (
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {orphanedMedia.orphaned_media.map(item => (
                    <div key={item.id} className="flex items-center gap-3 p-3 bg-white rounded-lg border border-purple-100">
                      <img
                        src={item.url}
                        alt={item.alt_text || ''}
                        className="w-12 h-12 object-cover rounded border border-gray-200 flex-shrink-0"
                        onError={e => { e.target.style.display = 'none' }}
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-bold text-gray-800 truncate">{item.title}</p>
                        <p className="text-xs font-mono text-gray-500 truncate">{item.url.split('/').pop()}</p>
                        <div className="flex items-center gap-3 mt-0.5">
                          <span className="text-xs text-gray-400">{item.mime_type}</span>
                          {item.file_size_kb && <span className="text-xs text-gray-400">{item.file_size_kb} KB</span>}
                          {item.dimensions && <span className="text-xs text-gray-400">{item.dimensions}</span>}
                          {item.post_parent === 0 && <span className="text-xs text-red-500 font-bold">Unattached</span>}
                        </div>
                      </div>
                      <a
                        href={item.admin_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="px-3 py-1.5 text-xs font-bold bg-purple-100 text-purple-700 rounded-lg hover:bg-purple-200 flex-shrink-0"
                      >
                        Edit in WP
                      </a>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {category.key === 'sitemap' && data.summary?.sitemap && (
        <div className="p-4 bg-white rounded-2xl border border-gray-200 mb-4">
          <h3 className="text-sm font-bold text-gray-700 mb-3">Sitemap</h3>
          {data.summary.sitemap.found ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-green-500 text-lg">✓</span>
                <span className="text-sm text-gray-700">Sitemap found</span>
              </div>
              {data.summary.sitemap.url && (
                <p className="text-xs text-gray-500 ml-7">
                  URL: <a href={data.summary.sitemap.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline font-mono">{data.summary.sitemap.url}</a>
                </p>
              )}
              <p className="text-xs text-gray-500 ml-7">
                {data.summary.sitemap.url_count} URLs in sitemap
              </p>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-red-500 text-lg">✗</span>
              <span className="text-sm text-gray-700">No sitemap found</span>
            </div>
          )}
        </div>
      )}

      {category.key === 'crawlability' && data.summary?.robots_txt && (
        <div className="p-4 bg-white rounded-2xl border border-gray-200 mb-4">
          <h3 className="text-sm font-bold text-gray-700 mb-3">robots.txt</h3>
          {data.summary.robots_txt.found ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-green-500 text-lg">✓</span>
                <span className="text-sm text-gray-700">robots.txt found</span>
              </div>
              {data.summary.robots_txt.rules?.length > 0 && (
                <details className="ml-7">
                  <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">
                    {data.summary.robots_txt.rules.length} rules
                  </summary>
                  <pre className="mt-2 p-3 bg-gray-50 rounded-lg text-xs text-gray-600 font-mono overflow-x-auto max-h-48 overflow-y-auto">
                    {data.summary.robots_txt.rules.join('\n')}
                  </pre>
                </details>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-yellow-500 text-lg">!</span>
              <span className="text-sm text-gray-700">No robots.txt found</span>
            </div>
          )}
        </div>
      )}

      {Object.values(groups).length === 0 ? (
        <div className="py-12 bg-white rounded-2xl border border-gray-100 text-center text-gray-400 font-medium font-serif italic">No issues found in this category.</div>
      ) : (
        Object.values(groups).map(group => (
          <div key={group.issue_code} className="bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-sm hover:border-gray-300 transition-colors">
            <button
              onClick={() => setExpandedCode(expandedCode === group.issue_code ? null : group.issue_code)}
              className="w-full flex items-center justify-between px-6 py-5"
            >
              <div className="flex items-center gap-4">
                <SeverityBadge severity={group.severity} />
                <div className="text-left">
                  <p className="font-bold text-gray-800 leading-none text-base">{group.human_description || group.issue_code}</p>
                  <p className="text-sm font-bold text-gray-400 mt-1 uppercase tracking-widest">{group.count} Affected Pages</p>
                </div>
              </div>
              <span className="text-gray-600 text-xl font-black">{expandedCode === group.issue_code ? '▲' : '▼'}</span>
            </button>

            {expandedCode === group.issue_code && (
              <div className="px-6 pb-6 border-t border-gray-50 pt-6 space-y-8">
                <IssueHelpPanel issueCode={group.issue_code} />
                <div>
                  {FIXABLE_LINK_CODES.has(group.issue_code) ? (
                    <>
                      <h4 className="text-sm font-bold text-gray-700 mb-4">Broken URLs — click "Show Source Pages" to see where these links are</h4>
                      <div className="space-y-3">
                        {group.pages.map(brokenUrl => (
                          <BrokenLinkItem
                            key={brokenUrl}
                            jobId={jobId}
                            brokenUrl={brokenUrl}
                            onMarkedFixed={() => {
                              getResultsByCategory(jobId, category.key).then(setData).catch(() => {})
                              onSummaryRefresh?.()
                            }}
                          />
                        ))}
                      </div>
                    </>
                  ) : (
                    <>
                      <h4 className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-4">Affected Pages</h4>
                      <div className="grid grid-cols-1 gap-2">
                        {group.pages.map(url => (
                          <button key={url} onClick={() => onPageClick(url)} className="text-left p-3 rounded-xl border border-gray-100 hover:bg-green-50 hover:border-green-200 transition-all font-mono text-xs text-blue-600 truncate flex justify-between items-center group">
                            <span>{url}</span>
                            <span className="text-sm font-black text-green-600 uppercase">Inspect →</span>
                          </button>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        ))
      )}
    </div>
  )
}

function BrokenLinkItem({ jobId, brokenUrl, onMarkedFixed }) {
  const [expanded, setExpanded] = useState(false)
  const [loading, setLoading] = useState(false)
  const [sources, setSources] = useState(null)
  const [error, setError] = useState(null)
  const [rescanning, setRescanning] = useState(null)
  const [rescanned, setRescanned] = useState(new Set())
  const [manualUrl, setManualUrl] = useState('')
  const [markingFixed, setMarkingFixed] = useState(false)
  const [isMarkedFixed, setIsMarkedFixed] = useState(false)

  async function handleMarkFixed() {
    setMarkingFixed(true)
    try {
      await markBrokenLinkFixed(jobId, brokenUrl)
      setIsMarkedFixed(true)
      if (onMarkedFixed) onMarkedFixed(brokenUrl)
    } catch (err) {
      alert('Failed to mark as fixed: ' + err.message)
    } finally {
      setMarkingFixed(false)
    }
  }

  async function loadSources() {
    if (sources) {
      setExpanded(!expanded)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({ job_id: jobId, target_url: brokenUrl })
      const res = await fetch(`/api/fixes/link-sources?${params}`, { headers: authHeaders() })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error?.message || 'Failed to load sources')
      setSources(data)
      setExpanded(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleRescan(sourceUrl) {
    setRescanning(sourceUrl)
    try {
      const params = new URLSearchParams({ url: sourceUrl })
      const res = await fetch(`/api/crawl/${jobId}/rescan-url?${params}`, {
        method: 'POST',
        headers: authHeaders(),
      })
      if (!res.ok) throw new Error('Rescan failed')
      setRescanned(prev => new Set([...prev, sourceUrl]))
    } catch (err) {
      alert('Rescan failed: ' + err.message)
    } finally {
      setRescanning(null)
    }
  }

  if (isMarkedFixed) {
    return (
      <div className="border border-green-200 rounded-xl overflow-hidden bg-green-50 px-4 py-3 flex items-center gap-3">
        <span className="text-green-500 text-xl">✓</span>
        <span className="font-mono text-sm text-green-700 truncate flex-1 line-through">{brokenUrl}</span>
        <span className="text-sm font-bold text-green-600">Marked as Fixed</span>
      </div>
    )
  }

  return (
    <div className="border border-red-200 rounded-xl overflow-hidden bg-white">
      <div className="flex items-center gap-3 px-4 py-3 bg-red-50">
        <span className="text-red-500 text-xl">🔗</span>
        <span className="font-mono text-sm text-red-800 truncate flex-1">{brokenUrl}</span>
        <a
          href={brokenUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-blue-600 hover:text-blue-800 underline px-2"
        >
          Test ↗
        </a>
        <button
          onClick={handleMarkFixed}
          disabled={markingFixed}
          className="px-3 py-2 bg-green-500 text-white text-sm font-bold rounded-lg hover:bg-green-600 disabled:opacity-50"
          title="Mark this broken link as fixed (removes from issue list)"
        >
          {markingFixed ? '...' : '✓ Fixed'}
        </button>
        <button
          onClick={loadSources}
          disabled={loading}
          className="px-4 py-2 bg-orange-500 text-white text-sm font-bold rounded-lg hover:bg-orange-600 disabled:opacity-50"
        >
          {loading ? 'Loading...' : expanded ? 'Hide Sources' : 'Show Source Pages'}
        </button>
      </div>

      {error && (
        <div className="px-4 py-3 bg-red-100 text-red-700 text-sm">{error}</div>
      )}

      {expanded && sources && (
        <div className="px-4 py-4 bg-gray-50 border-t border-red-100">
          <p className="text-sm font-bold text-gray-700 mb-3">
            This broken link is found on {sources.length} page{sources.length !== 1 ? 's' : ''}:
          </p>
          <div className="space-y-2">
            {sources.map(s => (
              <div key={s.source_url} className="flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200">
                <span className="font-mono text-sm text-gray-800 truncate flex-1" title={s.source_url}>
                  {s.source_url}
                </span>
                <a
                  href={s.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-blue-600 hover:text-blue-800 font-medium px-2"
                >
                  Open ↗
                </a>
                <button
                  onClick={() => handleRescan(s.source_url)}
                  disabled={rescanning === s.source_url}
                  className={`text-sm px-3 py-1.5 rounded-lg font-bold ${
                    rescanned.has(s.source_url)
                      ? 'bg-green-500 text-white'
                      : 'bg-blue-500 text-white hover:bg-blue-600'
                  } disabled:opacity-50`}
                >
                  {rescanning === s.source_url ? 'Rescanning...' : rescanned.has(s.source_url) ? '✓ Rescanned' : 'Rescan Page'}
                </button>
              </div>
            ))}
          </div>
          {sources.length === 0 && (
            <div className="space-y-3">
              <p className="text-sm text-gray-600">
                No source pages found — the link may have been removed or fixed.
              </p>
              <div className="bg-white border border-gray-200 rounded-lg p-3">
                <p className="text-sm font-medium text-gray-700 mb-2">Enter the page URL to rescan:</p>
                <div className="flex gap-2">
                  <input
                    type="url"
                    value={manualUrl}
                    onChange={e => setManualUrl(e.target.value)}
                    placeholder="https://yoursite.com/page-to-rescan"
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button
                    onClick={() => manualUrl && handleRescan(manualUrl)}
                    disabled={!manualUrl || rescanning === manualUrl}
                    className={`px-4 py-2 rounded-lg text-sm font-bold ${
                      rescanned.has(manualUrl)
                        ? 'bg-green-500 text-white'
                        : 'bg-blue-500 text-white hover:bg-blue-600'
                    } disabled:opacity-50`}
                  >
                    {rescanning === manualUrl ? 'Rescanning...' : rescanned.has(manualUrl) ? '✓ Rescanned' : 'Rescan'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

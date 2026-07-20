import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCrawl } from '../hooks/useCrawl.js'
import { getRecentJobs, scanPage, discoverScope } from '../api.js'

const ANALYSIS_TOGGLES = [
  { key: 'link_integrity', label: 'Link Integrity',  desc: 'Broken links, redirects, and status codes' },
  { key: 'seo_essentials', label: 'SEO Essentials',  desc: 'Title tags, meta descriptions, canonicals' },
  { key: 'site_structure', label: 'Site Structure',  desc: 'Heading hierarchy (H1–H6)' },
  { key: 'indexability',   label: 'Indexability',    desc: 'robots.txt, XML sitemaps, noindex tags' },
]

const SAVED_URL_KEY = 'talkingtoad_last_url'

function normaliseUrl(raw) {
  const trimmed = raw.trim()
  if (!trimmed) return trimmed
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  return 'https://' + trimmed
}

export default function Home() {
  const navigate = useNavigate()
  const [url, setUrl] = useState(() => localStorage.getItem(SAVED_URL_KEY) || '')
  const [showSettings, setShowSettings] = useState(false)
  const [maxPages, setMaxPages] = useState('')
  const [crawlDelay, setCrawlDelay] = useState('')
  const [imgSizeLimit, setImgSizeLimit] = useState('')
  const [suppressH1Input, setSuppressH1Input] = useState('')
  const [suppressBannerH1, setSuppressBannerH1] = useState(true)
  const [singlePageMode, setSinglePageMode] = useState(false)
  // All analyses enabled by default (null = all on)
  const [analyses, setAnalyses] = useState(() =>
    Object.fromEntries(ANALYSIS_TOGGLES.map(t => [t.key, true]))
  )
  // Scan scope (partial-scan feature): 'full' = whole site, 'partial' = a
  // user-selected subset of content types.
  const [scanMode, setScanMode] = useState('full')
  const [scopeLoading, setScopeLoading] = useState(false)
  const [scopeError, setScopeError] = useState(null)
  const [scopeData, setScopeData] = useState(null)   // discovery payload
  const [selectedTypes, setSelectedTypes] = useState({})  // { typeKey: true }
  const [selectedCats, setSelectedCats] = useState({})    // { categoryId: true }
  const [recentJobs, setRecentJobs] = useState([])
  const [singleUrl, setSingleUrl] = useState('')
  const [singleLoading, setSingleLoading] = useState(false)
  const [singleError, setSingleError] = useState(null)
  const { start, loading, error } = useCrawl()

  useEffect(() => {
    getRecentJobs(5)
      .then(jobs => setRecentJobs(jobs))
      .catch(() => {})
  }, [])

  function toggleAnalysis(key) {
    setAnalyses(prev => ({ ...prev, [key]: !prev[key] }))
  }

  const selectedTypeKeys = Object.keys(selectedTypes).filter(k => selectedTypes[k])
  const selectedCatIds = Object.keys(selectedCats).filter(k => selectedCats[k])
  const partialInvalid = scanMode === 'partial'
    && selectedTypeKeys.length === 0 && selectedCatIds.length === 0

  async function runDiscovery() {
    const finalUrl = normaliseUrl(url)
    if (!finalUrl) { setScopeError('Enter a website URL first'); return }
    setScopeLoading(true)
    setScopeError(null)
    try {
      const data = await discoverScope(finalUrl)
      setScopeData(data)
      setSelectedTypes({})
      setSelectedCats({})
    } catch (err) {
      setScopeError(err.message || 'Could not read the site')
      setScopeData(null)
    } finally {
      setScopeLoading(false)
    }
  }

  function handleModeChange(mode) {
    setScanMode(mode)
    if (mode === 'partial' && !scopeData && url.trim() && !scopeLoading) {
      runDiscovery()
    }
  }

  function toggleType(key) {
    setSelectedTypes(prev => ({ ...prev, [key]: !prev[key] }))
  }

  function toggleCat(id) {
    setSelectedCats(prev => ({ ...prev, [id]: !prev[id] }))
  }

  function handleSubmit(e) {
    e.preventDefault()
    if (partialInvalid) return
    const finalUrl = normaliseUrl(url)
    // Persist for next visit
    localStorage.setItem(SAVED_URL_KEY, finalUrl)
    if (finalUrl !== url) setUrl(finalUrl)

    const settings = {}
    if (maxPages) settings.max_pages = parseInt(maxPages, 10)
    if (crawlDelay) settings.crawl_delay_ms = parseInt(crawlDelay, 10)
    if (imgSizeLimit) settings.img_size_limit_kb = parseInt(imgSizeLimit, 10)
    const suppressH1s = suppressH1Input.split('\n').map(s => s.trim()).filter(Boolean)
    if (suppressH1s.length) settings.suppress_h1_strings = suppressH1s
    if (suppressBannerH1) settings.suppress_banner_h1 = true
    if (singlePageMode) settings.single_page = true
    const enabled = ANALYSIS_TOGGLES.filter(t => analyses[t.key]).map(t => t.key)
    // Only send if not all selected (null means all)
    if (enabled.length < ANALYSIS_TOGGLES.length) {
      settings.enabled_analyses = enabled
    }
    // Partial scan: send the content-type selection. Full scan sends nothing
    // (default mode="full" reproduces the whole-site crawl).
    if (scanMode === 'partial') {
      settings.content_scope = {
        mode: 'types',
        type_keys: selectedTypeKeys,
        category_ids: selectedCatIds.map(Number),
      }
    }

    start(finalUrl, settings)
  }

  async function handleScanPage(e) {
    e.preventDefault()
    const finalUrl = normaliseUrl(singleUrl.trim())
    if (!finalUrl) return
    setSingleLoading(true)
    setSingleError(null)
    try {
      const result = await scanPage(finalUrl)
      navigate(`/results/${result.job_id}`)
    } catch (err) {
      setSingleError(err.message || 'Scan failed')
      setSingleLoading(false)
    }
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-xl">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-800">TalkingToad</h1>
          <p className="mt-2 text-gray-500">Free SEO crawler for nonprofits</p>
        </div>

        {/* Recent crawls */}
        {recentJobs.length > 0 && (
          <div className="mb-4 bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide px-4 py-2 border-b border-gray-100 bg-gray-50">
              Recent crawls
            </p>
            <ul className="divide-y divide-gray-100">
              {recentJobs.map(job => {
                const isRunning = job.status === 'running' || job.status === 'pending'
                const statusColor = job.status === 'complete' ? 'text-green-600'
                  : job.status === 'failed' ? 'text-red-500'
                  : job.status === 'cancelled' ? 'text-gray-400'
                  : 'text-amber-500'
                return (
                  <li key={job.job_id} className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-800 truncate font-mono" title={job.target_url}>
                        {job.target_url.replace(/^https?:\/\//, '')}
                      </p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className={`text-xs font-medium capitalize ${statusColor}`}>{job.status}</span>
                        <span className="text-xs text-gray-400">·</span>
                        <span className="text-xs text-gray-400">{job.pages_crawled} pages</span>
                        {job.started_at && (
                          <>
                            <span className="text-xs text-gray-400">·</span>
                            <span className="text-xs text-gray-400">{new Date(job.started_at).toLocaleString()}</span>
                          </>
                        )}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => navigate(isRunning ? `/progress/${job.job_id}` : `/results/${job.job_id}`)}
                      className="flex-shrink-0 text-xs font-medium px-3 py-1.5 rounded-lg bg-green-600 text-white hover:bg-green-700 transition-colors"
                    >
                      {isRunning ? 'View Progress' : 'View Results'}
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Website URL <span className="text-red-500">*</span>
            </label>
            <div className="flex items-center border border-gray-300 rounded-lg focus-within:ring-2 focus-within:ring-green-500 focus-within:border-transparent overflow-hidden">
              <span className="px-3 py-2 text-sm text-gray-400 bg-gray-50 border-r border-gray-300 select-none whitespace-nowrap">
                https://
              </span>
              <input
                type="text"
                required
                inputMode="url"
                placeholder="example.org"
                value={url.replace(/^https?:\/\//i, '')}
                onChange={e => setUrl(e.target.value)}
                className="flex-1 px-3 py-2 text-sm focus:outline-none"
              />
            </div>
            <p className="text-xs text-gray-400 mt-1">
              https:// is added automatically — just enter the domain
            </p>
          </div>

          {/* Analysis toggles — always visible */}
          <div>
            <p className="text-xs font-medium text-gray-600 mb-2">What to check</p>
            <div className="grid grid-cols-2 gap-2">
              {ANALYSIS_TOGGLES.map(t => (
                <label
                  key={t.key}
                  className={`flex items-start gap-2 rounded-lg border px-3 py-2 cursor-pointer transition-colors ${
                    analyses[t.key]
                      ? 'border-green-400 bg-green-50'
                      : 'border-gray-200 bg-white'
                  }`}
                >
                  <input
                    type="checkbox"
                    className="mt-0.5 accent-green-600"
                    checked={analyses[t.key]}
                    onChange={() => toggleAnalysis(t.key)}
                  />
                  <span>
                    <span className="block text-xs font-medium text-gray-700">{t.label}</span>
                    <span className="block text-xs text-gray-400">{t.desc}</span>
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* Scan scope — full site vs a subset of content types */}
          <div>
            <p className="text-xs font-medium text-gray-600 mb-2">Scan scope</p>
            <div className="grid grid-cols-2 gap-2">
              <label className={`flex items-start gap-2 rounded-lg border px-3 py-2 cursor-pointer transition-colors ${
                scanMode === 'full' ? 'border-green-400 bg-green-50' : 'border-gray-200 bg-white'
              }`}>
                <input
                  type="radio"
                  name="scanMode"
                  className="mt-0.5 accent-green-600"
                  checked={scanMode === 'full'}
                  onChange={() => handleModeChange('full')}
                />
                <span>
                  <span className="block text-xs font-medium text-gray-700">Full site</span>
                  <span className="block text-xs text-gray-400">Crawl every page (default)</span>
                </span>
              </label>
              <label className={`flex items-start gap-2 rounded-lg border px-3 py-2 cursor-pointer transition-colors ${
                scanMode === 'partial' ? 'border-green-400 bg-green-50' : 'border-gray-200 bg-white'
              }`}>
                <input
                  type="radio"
                  name="scanMode"
                  className="mt-0.5 accent-green-600"
                  checked={scanMode === 'partial'}
                  onChange={() => handleModeChange('partial')}
                />
                <span>
                  <span className="block text-xs font-medium text-gray-700">Choose content types</span>
                  <span className="block text-xs text-gray-400">Pages, Posts, categories, or custom types</span>
                </span>
              </label>
            </div>

            {scanMode === 'partial' && (
              <div className="mt-3 rounded-lg border border-gray-200 bg-gray-50 p-3">
                {scopeLoading && (
                  <p className="text-xs text-gray-500">Reading the site to find content types…</p>
                )}

                {!scopeLoading && scopeError && (
                  <div className="text-xs">
                    <p className="text-red-600">{scopeError}</p>
                    <button
                      type="button"
                      onClick={runDiscovery}
                      className="mt-2 text-green-700 font-medium hover:underline"
                    >
                      Try again
                    </button>
                  </div>
                )}

                {!scopeLoading && !scopeError && scopeData && scopeData.types.length === 0 && (
                  <p className="text-xs text-gray-500">
                    {scopeData.notes || 'No content types could be detected — run a full-site scan instead.'}
                  </p>
                )}

                {!scopeLoading && !scopeError && scopeData && scopeData.types.length > 0 && (
                  <div className="space-y-3">
                    <div>
                      <div className="flex items-center justify-between mb-1.5">
                        <p className="text-xs font-medium text-gray-600">Content types</p>
                        <button
                          type="button"
                          onClick={runDiscovery}
                          className="text-xs text-gray-400 hover:text-gray-600"
                        >
                          Re-detect
                        </button>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        {scopeData.types.map(t => (
                          <label
                            key={t.key}
                            className={`flex items-center gap-2 rounded-lg border px-3 py-2 cursor-pointer transition-colors ${
                              selectedTypes[t.key] ? 'border-green-400 bg-green-50' : 'border-gray-200 bg-white'
                            }`}
                          >
                            <input
                              type="checkbox"
                              className="accent-green-600"
                              checked={!!selectedTypes[t.key]}
                              onChange={() => toggleType(t.key)}
                            />
                            <span className="min-w-0">
                              <span className="block text-xs font-medium text-gray-700 truncate">{t.label}</span>
                              {t.count != null && (
                                <span className="block text-xs text-gray-400">{t.count} item{t.count === 1 ? '' : 's'}</span>
                              )}
                            </span>
                          </label>
                        ))}
                      </div>
                    </div>

                    {scopeData.category_scope_supported && scopeData.categories.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-gray-600 mb-1.5">Posts by category (optional)</p>
                        <div className="max-h-40 overflow-y-auto grid grid-cols-2 gap-1.5 pr-1">
                          {scopeData.categories.map(c => (
                            <label
                              key={c.id}
                              className={`flex items-center gap-2 rounded-lg border px-2.5 py-1.5 cursor-pointer transition-colors ${
                                selectedCats[c.id] ? 'border-green-400 bg-green-50' : 'border-gray-200 bg-white'
                              }`}
                            >
                              <input
                                type="checkbox"
                                className="accent-green-600 flex-shrink-0"
                                checked={!!selectedCats[c.id]}
                                onChange={() => toggleCat(c.id)}
                              />
                              <span className="text-xs text-gray-700 truncate">{c.name}</span>
                              <span className="text-xs text-gray-400 ml-auto flex-shrink-0">{c.count}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    )}

                    {scopeData.notes && (
                      <p className="text-xs text-gray-400">{scopeData.notes}</p>
                    )}
                    {partialInvalid && (
                      <p className="text-xs text-amber-600">Select at least one content type or category to scan.</p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Crawl settings — collapsed by default */}
          <div>
            <button
              type="button"
              className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1"
              onClick={() => setShowSettings(v => !v)}
            >
              <span className="text-xs">{showSettings ? '▲' : '▼'}</span>
              Advanced settings (optional)
            </button>
            {showSettings && (
              <div className="mt-3 grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Max pages
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="10000"
                    placeholder="500"
                    value={maxPages}
                    onChange={e => setMaxPages(e.target.value)}
                    className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                  />
                  <p className="text-xs text-gray-400 mt-1">
                    No hard limit — larger crawls take longer.
                    At 500 ms delay, ~1,000 pages ≈ 8 min.
                  </p>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Crawl delay (ms)
                  </label>
                  <input
                    type="number"
                    min="200"
                    max="5000"
                    placeholder="500"
                    value={crawlDelay}
                    onChange={e => setCrawlDelay(e.target.value)}
                    className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Image size limit (KB)
                  </label>
                  <input
                    type="number"
                    min="10"
                    max="10000"
                    placeholder="200"
                    value={imgSizeLimit}
                    onChange={e => setImgSizeLimit(e.target.value)}
                    className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                  />
                  <p className="text-xs text-gray-400 mt-1">Images larger than this are flagged</p>
                </div>
                <div className="col-span-2">
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Suppress H1 text (one per line)
                  </label>
                  <textarea
                    rows={3}
                    placeholder={"Thinking Systems Blog\nAnother repeated heading…"}
                    value={suppressH1Input}
                    onChange={e => setSuppressH1Input(e.target.value)}
                    className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 resize-none"
                  />
                  <p className="text-xs text-gray-400 mt-1">
                    H1 headings matching these strings are ignored — use this for theme-injected
                    headings that appear on every page (e.g. a Salient page-header banner title).
                  </p>
                </div>
                <div className="col-span-2">
                  <label className={`flex items-start gap-2.5 rounded-lg border px-3 py-2.5 cursor-pointer transition-colors ${
                    suppressBannerH1 ? 'border-green-400 bg-green-50' : 'border-gray-200 bg-white'
                  }`}>
                    <input
                      type="checkbox"
                      className="mt-0.5 accent-green-600 flex-shrink-0"
                      checked={suppressBannerH1}
                      onChange={e => setSuppressBannerH1(e.target.checked)}
                    />
                    <span>
                      <span className="block text-xs font-medium text-gray-700">Ignore banner H1s automatically</span>
                      <span className="block text-xs text-gray-400 mt-0.5">
                        Skips any H1 that doesn't share words with the page title — catches theme-injected
                        parent-page banners (e.g. "Clinical Internship Programs" appearing as H1 on every
                        sub-page) without needing to list them manually above.
                      </span>
                    </span>
                  </label>
                </div>
                <div className="col-span-2">
                  <label className={`flex items-start gap-2.5 rounded-lg border px-3 py-2.5 cursor-pointer transition-colors ${
                    singlePageMode ? 'border-blue-400 bg-blue-50' : 'border-gray-200 bg-white'
                  }`}>
                    <input
                      type="checkbox"
                      className="mt-0.5 accent-blue-600 flex-shrink-0"
                      checked={singlePageMode}
                      onChange={e => setSinglePageMode(e.target.checked)}
                    />
                    <span>
                      <span className="block text-xs font-medium text-gray-700">Single-page mode</span>
                      <span className="block text-xs text-gray-400 mt-0.5">
                        Crawls only the exact URL — no sitemap seeding, no link following.
                        Useful for auditing a specific blog post or landing page with full AI Readiness checks.
                      </span>
                    </span>
                  </label>
                </div>
              </div>
            )}
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading || !url.trim() || partialInvalid}
            className="w-full bg-green-600 text-white rounded-lg py-2.5 font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Starting…' : 'Start Crawl'}
          </button>
        </form>

        {/* Single page scan */}
        <div className="mt-4">
          <p className="text-center text-xs text-gray-400 mb-2">or scan a single page</p>
          <form onSubmit={handleScanPage} className="flex gap-2">
            <input
              type="text"
              required
              inputMode="url"
              placeholder="https://example.org/specific-page"
              value={singleUrl}
              onChange={e => setSingleUrl(e.target.value)}
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            />
            <button
              type="submit"
              disabled={singleLoading || !singleUrl.trim()}
              className="flex-shrink-0 bg-gray-700 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {singleLoading ? 'Scanning…' : 'Scan Page'}
            </button>
          </form>
          {singleError && (
            <p className="mt-1 text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-1.5">
              {singleError}
            </p>
          )}
        </div>

        {/* Usage notice */}
        <p className="mt-4 text-center text-xs text-gray-400">
          This tool crawls only pages within the domain you provide. It respects
          robots.txt and introduces a delay between requests to avoid overloading
          your server.
        </p>
      </div>

    </main>
  )
}

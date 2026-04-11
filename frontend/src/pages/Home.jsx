import { useState, useEffect } from 'react'
import { useCrawl } from '../hooks/useCrawl.js'

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
  const [url, setUrl] = useState(() => localStorage.getItem(SAVED_URL_KEY) || '')
  const [showSettings, setShowSettings] = useState(false)
  const [maxPages, setMaxPages] = useState('')
  const [crawlDelay, setCrawlDelay] = useState('')
  const [imgSizeLimit, setImgSizeLimit] = useState('')
  // All analyses enabled by default (null = all on)
  const [analyses, setAnalyses] = useState(() =>
    Object.fromEntries(ANALYSIS_TOGGLES.map(t => [t.key, true]))
  )
  const { start, loading, error } = useCrawl()

  function toggleAnalysis(key) {
    setAnalyses(prev => ({ ...prev, [key]: !prev[key] }))
  }

  function handleSubmit(e) {
    e.preventDefault()
    const finalUrl = normaliseUrl(url)
    // Persist for next visit
    localStorage.setItem(SAVED_URL_KEY, finalUrl)
    if (finalUrl !== url) setUrl(finalUrl)

    const settings = {}
    if (maxPages) settings.max_pages = parseInt(maxPages, 10)
    if (crawlDelay) settings.crawl_delay_ms = parseInt(crawlDelay, 10)
    if (imgSizeLimit) settings.img_size_limit_kb = parseInt(imgSizeLimit, 10)
    const enabled = ANALYSIS_TOGGLES.filter(t => analyses[t.key]).map(t => t.key)
    // Only send if not all selected (null means all)
    if (enabled.length < ANALYSIS_TOGGLES.length) {
      settings.enabled_analyses = enabled
    }
    start(finalUrl, settings)
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-xl">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-800">TalkingToad</h1>
          <p className="mt-2 text-gray-500">Free SEO crawler for nonprofits</p>
        </div>

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
            disabled={loading || !url.trim()}
            className="w-full bg-green-600 text-white rounded-lg py-2.5 font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Starting…' : 'Start Crawl'}
          </button>
        </form>

        {/* Usage notice */}
        <p className="mt-4 text-center text-xs text-gray-400">
          This tool crawls only pages within the domain you provide. It respects
          robots.txt and introduces a delay between requests to avoid overloading
          your server.
        </p>
      </div>
    </div>
  )
}

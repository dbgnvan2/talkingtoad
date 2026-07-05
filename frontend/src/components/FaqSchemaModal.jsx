import { useState, useEffect, useCallback } from 'react'
import { getFaqSchema } from '../api.js'

/**
 * Popup modal that generates ready-to-paste FAQPage JSON-LD for one page.
 *
 * Calls POST /api/ai/faq-schema, which builds schema only from FAQ answers
 * actually present in the page HTML (never fabricated) and refuses if answers
 * are JS-only. The user can copy the snippet or download it as .html
 * (a <script type="application/ld+json"> block ready to paste) or .json
 * (the raw structured data). Copy/export only — nothing is written to WordPress.
 */
export default function FaqSchemaModal({ jobId, pageUrl, onClose }) {
  const [state, setState] = useState({ loading: true })
  const [copied, setCopied] = useState(false)

  const load = useCallback(async () => {
    setState({ loading: true })
    try {
      const data = await getFaqSchema(jobId, pageUrl)
      if (data.error) setState({ loading: false, error: data.error })
      else setState({ loading: false, ...data })
    } catch (err) {
      setState({ loading: false, error: err.message || 'Request failed' })
    }
  }, [jobId, pageUrl])

  useEffect(() => { load() }, [load])

  const scriptSnippet = state.jsonld
    ? `<script type="application/ld+json">\n${state.jsonld}\n</script>`
    : ''

  const slug = (() => {
    try { return (new URL(pageUrl).pathname.replace(/\/$/, '').split('/').pop() || 'home') }
    catch { return 'faq' }
  })()

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(scriptSnippet)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch { /* clipboard unavailable */ }
  }

  const download = (text, ext, mime) => {
    const blob = new Blob([text], { type: mime })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `faqpage-schema-${slug}.${ext}`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="FAQ schema generator"
        className="bg-white rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 p-6 rounded-t-xl flex items-start justify-between">
          <div>
            <h2 className="text-2xl font-black text-gray-800">FAQ Schema Generator</h2>
            <p className="text-sm text-gray-600 mt-1">FAQPage structured data for AI &amp; rich results</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none" aria-label="Close">×</button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-5">
          {state.loading && (
            <div className="py-12 text-center text-gray-500">
              <span className="animate-spin inline-block mr-2">&#8635;</span>
              Reading the page&rsquo;s FAQ&hellip;
            </div>
          )}

          {!state.loading && state.error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {state.error}
            </div>
          )}

          {!state.loading && state.refused && (
            <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
              <p className="font-bold mb-1">Can&rsquo;t generate schema yet</p>
              <p>{state.reason}</p>
            </div>
          )}

          {!state.loading && !state.error && !state.refused && state.jsonld && (
            <>
              <p className="text-sm text-gray-600">
                Built from <span className="font-bold">{state.question_count}</span> FAQ question{state.question_count === 1 ? '' : 's'} found in this page&rsquo;s HTML.
                Paste the snippet into a Custom HTML block, or add these Q&amp;As to your Rank&nbsp;Math / Yoast FAQ block.
              </p>

              <div className="flex flex-wrap gap-2">
                <button onClick={copy} className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-bold hover:bg-green-700 transition-all">
                  {copied ? 'Copied!' : 'Copy snippet'}
                </button>
                <button onClick={() => download(scriptSnippet, 'html', 'text/html')} className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-bold hover:bg-gray-200 transition-all">
                  Download .html
                </button>
                <button onClick={() => download(state.jsonld, 'json', 'application/ld+json')} className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-bold hover:bg-gray-200 transition-all">
                  Download .json
                </button>
              </div>

              <pre className="bg-gray-900 text-green-200 text-xs rounded-lg p-4 overflow-x-auto max-h-[45vh] whitespace-pre">
                {scriptSnippet}
              </pre>

              <p className="text-xs text-gray-500">
                Tip: after adding it, confirm with Google&rsquo;s Rich Results Test. This tool never edits your site &mdash; you paste it yourself.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

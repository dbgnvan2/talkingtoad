import React, { useState, useEffect } from 'react'
import { authHeaders } from '../api.js'

export default function LLMSTxtGenerator({ jobId }) {
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [generated, setGenerated] = useState(false)
  const [isCustom, setIsCustom] = useState(false)
  const [saveStatus, setSaveStatus] = useState(null)

  useEffect(() => {
    fetch(`/api/utility/generate-llms-txt?job_id=${jobId}`, { headers: authHeaders() })
      .then(r => r.json())
      .then(d => {
        if (d.is_custom) {
          setContent(d.content)
          setGenerated(true)
          setIsCustom(true)
        }
      })
      .catch(() => {})
  }, [jobId])

  async function handleGenerate() {
    setLoading(true)
    try {
      const r = await fetch(`/api/utility/generate-llms-txt?job_id=${jobId}`, { headers: authHeaders() })
      const d = await r.json()
      setContent(d.content)
      setGenerated(true)
      setIsCustom(d.is_custom || false)
    } catch (_e) { /* ignore */ }
    setLoading(false)
  }

  async function handleSave() {
    setSaveStatus('saving')
    try {
      await fetch('/api/utility/save-llms-txt', {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: jobId, content })
      })
      setSaveStatus('saved')
      setIsCustom(true)
      setTimeout(() => setSaveStatus(null), 2000)
    } catch (_e) { setSaveStatus('error') }
  }

  const statusLabel = isCustom ? 'llms.txt Retrieved' : generated ? 'llms.txt Recommendation' : null

  return (
    <div className="bg-white border border-indigo-100 rounded-3xl p-8 shadow-sm">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
        <div>
          <div className="flex items-center gap-3">
            <h3 className="text-lg font-bold text-gray-800">llms.txt AI Index</h3>
            {statusLabel && (
              <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${isCustom ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>
                {statusLabel}
              </span>
            )}
          </div>
          <p className="text-sm text-gray-400 mt-1">Help Gemini and ChatGPT find your most important content.</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleGenerate}
            disabled={loading}
            className="px-6 py-2.5 rounded-2xl text-sm font-black transition-all shadow-lg active:scale-95 bg-indigo-600 text-white shadow-indigo-100 hover:bg-indigo-700 disabled:opacity-50"
          >
            {loading ? 'Generating...' : generated ? 'Regenerate' : 'Generate Recommendation'}
          </button>
          {generated && (
            <button onClick={handleSave} className={`px-6 py-2.5 rounded-2xl text-sm font-black transition-all shadow-lg active:scale-95 ${saveStatus === 'saved' ? 'bg-green-600 text-white shadow-green-100' : 'bg-gray-700 text-white shadow-gray-100 hover:bg-gray-800'}`}>
              {saveStatus === 'saving' ? 'Saving...' : saveStatus === 'saved' ? 'Saved' : 'Save to Job Data'}
            </button>
          )}
        </div>
      </div>
      {generated ? (
        <textarea value={content} onChange={e => { setContent(e.target.value); setIsCustom(false) }} className="w-full h-48 bg-indigo-50/20 border border-indigo-50 rounded-2xl p-5 font-mono text-xs focus:bg-white transition-colors focus:ring-2 focus:ring-indigo-100 focus:outline-none" />
      ) : (
        <div className="py-12 text-center bg-indigo-50/20 border border-indigo-50 rounded-2xl">
          <p className="text-gray-400 text-sm">Click "Generate Recommendation" to create an llms.txt file from your crawl data.</p>
        </div>
      )}
    </div>
  )
}

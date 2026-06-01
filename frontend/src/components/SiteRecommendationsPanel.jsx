import React from 'react'

// Renders the AI site-wide recommendations. Each recommendation is an object
// { priority, category, recommendation, impact } (see api/services/ai_analyzer.py).
// Legacy/fallback: a plain string is also rendered safely.
export default function SiteRecommendationsPanel({ recommendations, onClose }) {
  const recs = Array.isArray(recommendations) ? recommendations : []

  const priorityClasses = (p) => {
    const k = (p || 'medium').toLowerCase()
    if (k === 'high') return 'bg-red-100 text-red-700'
    if (k === 'low') return 'bg-blue-100 text-blue-700'
    return 'bg-amber-100 text-amber-700'
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center" role="dialog" aria-modal="true" aria-label="Site Recommendations">
      <div className="absolute inset-0 bg-black/40" onClick={onClose}></div>
      <div className="relative bg-white rounded-2xl shadow-2xl p-8 max-w-2xl max-h-[32rem] overflow-y-auto">
        <button
          onClick={onClose}
          aria-label="Close recommendations"
          className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 rounded-full hover:bg-gray-100"
        >
          ✕
        </button>
        <h2 className="text-xl font-bold text-gray-800 mb-4">Site Recommendations</h2>
        <div className="space-y-3">
          {recs.length === 0 && (
            <p className="text-sm text-gray-400">No recommendations available.</p>
          )}
          {recs.map((rec, i) => {
            // Back-compat: a plain string recommendation.
            if (typeof rec === 'string') {
              return <p key={i} className="text-sm text-gray-700">{rec}</p>
            }
            return (
              <div key={`${rec.category || 'general'}-${i}`} className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <span className={`flex-shrink-0 text-[10px] px-2 py-1 rounded-full font-bold uppercase ${priorityClasses(rec.priority)}`}>
                    {rec.priority || 'medium'}
                  </span>
                  <div className="flex-1">
                    {rec.category && (
                      <p className="text-sm font-bold text-gray-700 mb-1">{rec.category}</p>
                    )}
                    <p className="text-sm text-gray-800">{rec.recommendation}</p>
                    {rec.impact && (
                      <p className="text-xs text-gray-600 mt-2"><strong>Impact:</strong> {rec.impact}</p>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

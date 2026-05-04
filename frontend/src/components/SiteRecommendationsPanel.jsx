import React from 'react'

export default function SiteRecommendationsPanel({ recommendations, onClose }) {
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose}></div>
      <div className="relative bg-white rounded-2xl shadow-2xl p-8 max-w-2xl max-h-96 overflow-y-auto">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 rounded-full hover:bg-gray-100"
        >
          ✕
        </button>
        <h2 className="text-xl font-bold text-gray-800 mb-4">Site Recommendations</h2>
        <div className="space-y-3">
          {recommendations && recommendations.map((rec, i) => (
            <p key={i} className="text-sm text-gray-700">{rec}</p>
          ))}
        </div>
      </div>
    </div>
  )
}

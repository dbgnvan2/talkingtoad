import React from 'react'
import { getCategoryHelp } from '../data/categoryHelp.js'

/**
 * CategoryHelpModal - Modal showing detailed help about a category
 *
 * @param {string} categoryKey - The category key (e.g., 'broken_link', 'metadata')
 * @param {function} onClose - Callback to close the modal
 */
export default function CategoryHelpModal({ categoryKey, onClose }) {
  const help = getCategoryHelp(categoryKey)

  if (!help) return null

  return (
    <div
      className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-3xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-gradient-to-r from-green-50 to-indigo-50 border-b border-gray-100 px-8 py-6 flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-black text-gray-800">{help.title}</h2>
            <p className="text-sm text-gray-500 mt-1">Category Help</p>
          </div>
          <button
            onClick={onClose}
            className="w-10 h-10 flex items-center justify-center rounded-full bg-white text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-all text-2xl font-black"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div className="px-8 py-6 space-y-6">
          {/* Description */}
          <div>
            <h3 className="text-sm font-black text-gray-400 uppercase tracking-widest mb-3">
              What This Category Covers
            </h3>
            <p className="text-base text-gray-700 leading-relaxed">
              {help.description}
            </p>
          </div>

          {/* Why It Matters */}
          <div className="bg-green-50 border border-green-100 rounded-2xl p-6">
            <h3 className="text-sm font-black text-green-700 uppercase tracking-widest mb-3 flex items-center gap-2">
              <span>💡</span> Why This Matters for Nonprofits
            </h3>
            <p className="text-base text-green-900 leading-relaxed">
              {help.why}
            </p>
          </div>

          {/* Common Issues */}
          {help.common && help.common.length > 0 && (
            <div>
              <h3 className="text-sm font-black text-gray-400 uppercase tracking-widest mb-3">
                Common Issues in This Category
              </h3>
              <ul className="space-y-2">
                {help.common.map((item, idx) => (
                  <li key={item} className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-6 h-6 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center text-xs font-bold mt-0.5">
                      {idx + 1}
                    </span>
                    <span className="text-base text-gray-700 flex-1">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* AI Scores Explanation (for Image category) */}
          {help.aiScores && (
            <div className="bg-purple-50 border border-purple-100 rounded-2xl p-6">
              <h3 className="text-sm font-black text-purple-700 uppercase tracking-widest mb-3 flex items-center gap-2">
                <span>🤖</span> {help.aiScores.title}
              </h3>
              <p className="text-base text-purple-900 mb-4">{help.aiScores.description}</p>

              <div className="space-y-3 mb-4">
                {help.aiScores.scores.map((score) => (
                  <div key={score.name} className="bg-white rounded-lg p-3">
                    <p className="text-sm font-bold text-purple-800 mb-1">{score.name}</p>
                    <p className="text-sm text-gray-700">{score.description}</p>
                  </div>
                ))}
              </div>

              {help.aiScores.howItWorks && (
                <div className="bg-purple-100 rounded-lg p-3">
                  <p className="text-xs font-bold text-purple-700 mb-1">How It Works:</p>
                  <p className="text-sm text-purple-900">{help.aiScores.howItWorks}</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-gray-50 border-t border-gray-100 px-8 py-4">
          <button
            onClick={onClose}
            className="w-full py-3 bg-green-600 text-white rounded-2xl text-base font-bold shadow-lg shadow-green-100 hover:bg-green-700 transition-all"
          >
            Got It
          </button>
        </div>
      </div>
    </div>
  )
}

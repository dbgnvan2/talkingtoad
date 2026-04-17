import { useState } from 'react'

/**
 * Modal for displaying and editing GEO AI analysis results.
 *
 * Allows users to review and modify AI-generated alt text and long descriptions
 * before applying them to the image.
 */
export default function GeoAnalysisModal({ geoResult, image, onSave, onClose }) {
  const [editedAlt, setEditedAlt] = useState(geoResult.alt_text || '')
  const [editedDescription, setEditedDescription] = useState(geoResult.long_description || '')
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave(editedAlt, editedDescription)
    } finally {
      setSaving(false)
    }
  }

  const altLength = editedAlt.length
  const altStatus = altLength < 80 ? 'short' : altLength > 125 ? 'long' : 'good'
  const descWordCount = editedDescription.trim().split(/\s+/).length
  const descStatus = descWordCount < 150 ? 'short' : descWordCount > 300 ? 'long' : 'good'

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 p-6 rounded-t-xl">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-2xl font-black text-gray-800">GEO Image Analysis</h2>
              <p className="text-sm text-gray-600 mt-1">Review and edit AI-generated metadata</p>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
            >
              ×
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Image Preview */}
          <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-lg">
            <img
              src={image.url}
              alt={image.alt || 'Image preview'}
              className="w-24 h-24 object-cover rounded border border-gray-200"
            />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-700 truncate">{image.filename}</p>
              <p className="text-xs text-gray-500 mt-1 truncate">{image.url}</p>
            </div>
          </div>

          {/* AI Analysis Metadata (Read-only) */}
          {geoResult.success && (
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
              <p className="text-sm font-bold text-purple-900 mb-3">AI Analysis Context</p>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <span className="font-semibold text-purple-800">Subject:</span>{' '}
                  <span className="text-purple-900">{geoResult.subject || 'N/A'}</span>
                </div>
                <div>
                  <span className="font-semibold text-purple-800">Theme:</span>{' '}
                  <span className="text-purple-900">{geoResult.theme || 'N/A'}</span>
                </div>
                <div>
                  <span className="font-semibold text-purple-800">Geographic Anchor:</span>{' '}
                  <span className="text-purple-900">{geoResult.geographic_anchor || 'N/A'}</span>
                </div>
                <div>
                  <span className="font-semibold text-purple-800">Entities Used:</span>{' '}
                  <span className="text-purple-900">
                    {geoResult.entities_used?.join(', ') || 'N/A'}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Editable Alt Text */}
          <div>
            <label className="block text-sm font-bold text-gray-700 mb-2">
              Alt Text (80-125 characters)
              <span
                className={`ml-2 text-xs font-normal ${
                  altStatus === 'good' ? 'text-green-600' : altStatus === 'short' ? 'text-amber-600' : 'text-red-600'
                }`}
              >
                {altLength} chars
                {altStatus === 'short' && ' (too short)'}
                {altStatus === 'long' && ' (too long)'}
                {altStatus === 'good' && ' ✓'}
              </span>
            </label>
            <textarea
              value={editedAlt}
              onChange={(e) => setEditedAlt(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              rows={2}
              placeholder="Enter alt text..."
            />
            <p className="text-xs text-gray-500 mt-1">
              Should include 1 location entity and 1 topic entity
            </p>
          </div>

          {/* Editable Long Description */}
          <div>
            <label className="block text-sm font-bold text-gray-700 mb-2">
              Long Description (150-300 words)
              <span
                className={`ml-2 text-xs font-normal ${
                  descStatus === 'good' ? 'text-green-600' : descStatus === 'short' ? 'text-amber-600' : 'text-red-600'
                }`}
              >
                {descWordCount} words
                {descStatus === 'short' && ' (too short)'}
                {descStatus === 'long' && ' (too long)'}
                {descStatus === 'good' && ' ✓'}
              </span>
            </label>
            <textarea
              value={editedDescription}
              onChange={(e) => setEditedDescription(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              rows={8}
              placeholder="Enter long description..."
            />
            <p className="text-xs text-gray-500 mt-1">
              GEO-optimized, entity-rich description for AI Overviews
            </p>
          </div>

          {/* Current vs. Generated Comparison */}
          {image.alt && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <p className="text-sm font-bold text-blue-900 mb-2">Current Alt Text (for reference)</p>
              <p className="text-sm text-blue-800 italic">&quot;{image.alt}&quot;</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-white border-t border-gray-200 p-6 rounded-b-xl flex gap-3">
          <button
            onClick={onClose}
            disabled={saving}
            className="flex-1 border border-gray-300 text-gray-700 rounded-lg py-2 text-sm hover:bg-gray-50 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !editedAlt.trim()}
            className="flex-1 bg-purple-600 text-white rounded-lg py-2 text-sm hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? 'Saving...' : 'Apply to Database'}
          </button>
        </div>
      </div>
    </div>
  )
}

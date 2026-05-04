import { useState, useEffect } from 'react'
import { previewExistingOptimization, optimizeExistingImage } from '../api'

/**
 * Modal for Workflow A: Optimize an existing WordPress image.
 *
 * Shows preview of optimization, lets user configure options,
 * then optimizes and uploads. Original stays in WP - shows
 * user which pages need to be updated manually.
 */
export default function OptimizeExistingModal({ image, jobId, onClose, onSuccess }) {
  const [step, setStep] = useState('loading') // loading, preview, optimizing, done, error
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  // Options
  const [targetWidth, setTargetWidth] = useState(1200)
  const [applyGps, setApplyGps] = useState(true)
  const [seoKeyword, setSeoKeyword] = useState('')
  const [generateGeoMetadata, setGenerateGeoMetadata] = useState(true)

  // Load preview on mount
  useEffect(() => {
    loadPreview()
  }, [])

  const loadPreview = async () => {
    setStep('loading')
    setError(null)
    try {
      const data = await previewExistingOptimization(jobId, image.url, targetWidth)
      setPreview(data)
      setStep('preview')
    } catch (err) {
      setError(err.message)
      setStep('error')
    }
  }

  const handleOptimize = async () => {
    setStep('optimizing')
    setError(null)
    try {
      const data = await optimizeExistingImage(jobId, image.url, {
        targetWidth,
        applyGps,
        seoKeyword: seoKeyword.trim() || null,
        generateGeoMetadata,
        pageH1: image.context?.h1 || '',
        surroundingText: image.context?.surrounding_text || image.surrounding_text || '',
      })
      setResult(data)
      setStep('done')
      if (onSuccess) onSuccess(data)
    } catch (err) {
      setError(err.message)
      setStep('error')
    }
  }

  const formatSize = (kb) => {
    if (kb >= 1024) return `${(kb / 1024).toFixed(1)} MB`
    return `${kb.toFixed(0)} KB`
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 p-6 rounded-t-xl">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-2xl font-black text-gray-800">Optimize Image</h2>
              <p className="text-sm text-gray-600 mt-1">
                {step === 'loading' && 'Analyzing image...'}
                {step === 'preview' && 'Review optimization settings'}
                {step === 'optimizing' && 'Optimizing and uploading...'}
                {step === 'done' && 'Optimization complete!'}
                {step === 'error' && 'Error occurred'}
              </p>
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
        <div className="p-6">
          {/* Loading State */}
          {step === 'loading' && (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              <span className="ml-3 text-gray-600">Analyzing image...</span>
            </div>
          )}

          {/* Error State */}
          {step === 'error' && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="text-red-800 font-medium">Error</p>
              <p className="text-red-700 text-sm mt-1">{error}</p>
              <button
                onClick={loadPreview}
                className="mt-3 text-sm text-red-700 underline hover:text-red-900"
              >
                Try again
              </button>
            </div>
          )}

          {/* Preview State */}
          {step === 'preview' && preview && (
            <div className="space-y-6">
              {/* Image Preview */}
              <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-lg">
                <img
                  src={image.url}
                  alt={image.alt || 'Image preview'}
                  className="w-20 h-20 object-cover rounded border border-gray-200"
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-700 truncate">{image.filename}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    {preview.original_dimensions?.[0]} × {preview.original_dimensions?.[1]} px
                  </p>
                </div>
              </div>

              {/* Size Comparison */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-sm font-bold text-blue-900 mb-3">Estimated Savings</p>
                <div className="flex items-center gap-4">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-red-600">{formatSize(preview.original_size_kb)}</p>
                    <p className="text-xs text-gray-600">Original</p>
                  </div>
                  <div className="text-2xl text-gray-400">→</div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-green-600">{formatSize(preview.estimated_size_kb)}</p>
                    <p className="text-xs text-gray-600">Optimized</p>
                  </div>
                  <div className="flex-1 text-right">
                    <p className="text-3xl font-black text-green-600">{preview.savings_percent}%</p>
                    <p className="text-xs text-gray-600">smaller</p>
                  </div>
                </div>
              </div>

              {/* Page URLs where used */}
              {preview.page_urls?.length > 0 && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                  <p className="text-sm font-bold text-amber-900 mb-2">
                    After optimization, update this image on:
                  </p>
                  <ul className="space-y-1">
                    {preview.page_urls.map((url) => (
                      <li key={url} className="text-sm">
                        <a
                          href={url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-amber-700 hover:text-amber-900 underline truncate block"
                        >
                          {url}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Options */}
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Target Width (pixels)
                  </label>
                  <input
                    type="number"
                    value={targetWidth}
                    onChange={(e) => setTargetWidth(parseInt(e.target.value) || 1200)}
                    className="w-32 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    min={200}
                    max={2000}
                    step={100}
                  />
                  <p className="text-xs text-gray-500 mt-1">Max width after resize (no upscaling)</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    SEO Keyword (optional)
                  </label>
                  <input
                    type="text"
                    value={seoKeyword}
                    onChange={(e) => setSeoKeyword(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="e.g., therapy session"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Used in filename: {seoKeyword || 'image'}-{preview.geo_location?.toLowerCase().replace(/\s+/g, '-') || 'location'}-small.webp
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="applyGps"
                    checked={applyGps}
                    onChange={(e) => setApplyGps(e.target.checked)}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <label htmlFor="applyGps" className="text-sm text-gray-700">
                    Inject GPS coordinates ({preview.geo_location || 'Not configured'})
                  </label>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="generateGeoMetadata"
                    checked={generateGeoMetadata}
                    onChange={(e) => setGenerateGeoMetadata(e.target.checked)}
                    className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                  />
                  <label htmlFor="generateGeoMetadata" className="text-sm text-gray-700">
                    🤖 Generate AI alt text, description & caption (GEO optimized)
                  </label>
                </div>
              </div>
            </div>
          )}

          {/* Optimizing State */}
          {step === 'optimizing' && (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
              <p className="mt-4 text-gray-600">Downloading, optimizing, and uploading...</p>
              <p className="text-sm text-gray-500 mt-1">This may take a moment</p>
            </div>
          )}

          {/* Done State */}
          {step === 'done' && result && (
            <div className="space-y-6">
              <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-center">
                <p className="text-2xl mb-2">✓</p>
                <p className="text-lg font-bold text-green-800">Optimization Complete!</p>
                <p className="text-sm text-green-700 mt-1">{formatSize(result.file_size_kb)} WebP uploaded</p>
              </div>

              {/* New URL */}
              <div>
                <p className="text-sm font-medium text-gray-700 mb-1">New Optimized Image URL:</p>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={result.new_url || ''}
                    readOnly
                    className="flex-1 px-3 py-2 bg-gray-100 border border-gray-300 rounded-lg text-sm"
                  />
                  <button
                    onClick={() => navigator.clipboard.writeText(result.new_url)}
                    className="px-3 py-2 bg-gray-200 hover:bg-gray-300 rounded-lg text-sm"
                  >
                    Copy
                  </button>
                </div>
              </div>

              {/* Instructions */}
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                <p className="text-sm font-bold text-amber-900 mb-2">Next Steps:</p>
                <ol className="list-decimal list-inside text-sm text-amber-800 space-y-1">
                  <li>The original image is still in WordPress</li>
                  <li>Go to the page(s) below and replace the old image with the new one</li>
                  <li>After replacing, delete the old image from Media Library</li>
                </ol>
                {result.page_urls?.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-amber-200">
                    <p className="text-sm font-medium text-amber-900">Pages to update:</p>
                    <ul className="mt-1 space-y-1">
                      {result.page_urls.map((url) => (
                        <li key={url}>
                          <a
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-amber-700 hover:text-amber-900 underline"
                          >
                            {url}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* GEO AI Metadata */}
              {result.geo_metadata && (
                <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                  <p className="text-sm font-bold text-purple-900 mb-3">🤖 AI-Generated Metadata (Applied to WordPress)</p>
                  <div className="space-y-3 text-sm">
                    <div>
                      <span className="font-medium text-purple-800">Alt Text:</span>
                      <p className="text-purple-700 mt-1 italic">"{result.geo_metadata.alt_text}"</p>
                    </div>
                    {result.geo_metadata.caption && (
                      <div>
                        <span className="font-medium text-purple-800">Caption:</span>
                        <p className="text-purple-700 mt-1">"{result.geo_metadata.caption}"</p>
                      </div>
                    )}
                    {result.geo_metadata.description && (
                      <div>
                        <span className="font-medium text-purple-800">Description:</span>
                        <p className="text-purple-700 mt-1 text-xs leading-relaxed">{result.geo_metadata.description}</p>
                      </div>
                    )}
                    {result.geo_metadata.entities_used?.length > 0 && (
                      <div className="pt-2 border-t border-purple-200">
                        <span className="font-medium text-purple-800">Entities:</span>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {result.geo_metadata.entities_used.map((entity) => (
                            <span key={entity} className="text-xs px-2 py-0.5 bg-purple-200 text-purple-800 rounded-full">
                              {entity}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-white border-t border-gray-200 p-6 rounded-b-xl flex gap-3">
          {step === 'preview' && (
            <>
              <button
                onClick={onClose}
                className="flex-1 border border-gray-300 text-gray-700 rounded-lg py-2 text-sm hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleOptimize}
                className="flex-1 bg-blue-600 text-white rounded-lg py-2 text-sm hover:bg-blue-700"
              >
                Optimize & Upload
              </button>
            </>
          )}
          {(step === 'done' || step === 'error') && (
            <button
              onClick={onClose}
              className="flex-1 bg-gray-600 text-white rounded-lg py-2 text-sm hover:bg-gray-700"
            >
              Close
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

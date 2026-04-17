import { useState, useRef } from 'react'
import { previewUploadOptimization, uploadAndOptimizeImage } from '../api'

/**
 * Modal for Workflow B: Upload and optimize a local image from hard drive.
 *
 * User selects a file via drag-drop or file picker, configures options,
 * then the image is optimized and uploaded to WordPress.
 */
export default function UploadNewImageModal({ jobId, onClose, onSuccess }) {
  const [step, setStep] = useState('select') // select, preview, optimizing, done, error
  const [selectedFile, setSelectedFile] = useState(null)
  const [filePreviewUrl, setFilePreviewUrl] = useState(null)
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [isDragging, setIsDragging] = useState(false)

  // Options
  const [targetWidth, setTargetWidth] = useState(1200)
  const [applyGps, setApplyGps] = useState(true)
  const [seoKeyword, setSeoKeyword] = useState('')
  const [generateGeoMetadata, setGenerateGeoMetadata] = useState(true)

  const fileInputRef = useRef(null)

  const handleFileSelect = async (file) => {
    if (!file) return

    // Validate file type
    const validTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
    if (!validTypes.includes(file.type)) {
      setError('Please select a valid image file (JPEG, PNG, WebP, or GIF)')
      return
    }

    // Validate file size (max 20MB)
    if (file.size > 20 * 1024 * 1024) {
      setError('File too large. Maximum size is 20MB.')
      return
    }

    setSelectedFile(file)
    setError(null)

    // Create preview URL
    const url = URL.createObjectURL(file)
    setFilePreviewUrl(url)

    // Get optimization preview
    setStep('loading')
    try {
      const data = await previewUploadOptimization(file, targetWidth)
      setPreview(data)
      setStep('preview')
    } catch (err) {
      setError(err.message)
      setStep('error')
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    handleFileSelect(file)
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleBrowseClick = () => {
    fileInputRef.current?.click()
  }

  const handleFileInputChange = (e) => {
    const file = e.target.files[0]
    handleFileSelect(file)
  }

  const handleOptimize = async () => {
    setStep('optimizing')
    setError(null)
    try {
      const data = await uploadAndOptimizeImage(selectedFile, {
        targetWidth,
        applyGps,
        seoKeyword: seoKeyword.trim() || null,
        generateGeoMetadata,
        jobId,
      })
      setResult(data)
      setStep('done')
      if (onSuccess) onSuccess(data)
    } catch (err) {
      setError(err.message)
      setStep('error')
    }
  }

  const handleReset = () => {
    setSelectedFile(null)
    setFilePreviewUrl(null)
    setPreview(null)
    setError(null)
    setStep('select')
  }

  const formatSize = (kb) => {
    if (kb >= 1024) return `${(kb / 1024).toFixed(1)} MB`
    return `${kb.toFixed(0)} KB`
  }

  const formatBytes = (bytes) => {
    if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    return `${(bytes / 1024).toFixed(0)} KB`
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 p-6 rounded-t-xl">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-2xl font-black text-gray-800">Upload & Optimize Image</h2>
              <p className="text-sm text-gray-600 mt-1">
                {step === 'select' && 'Select an image from your computer'}
                {step === 'loading' && 'Analyzing image...'}
                {step === 'preview' && 'Review optimization settings'}
                {step === 'optimizing' && 'Optimizing and uploading...'}
                {step === 'done' && 'Upload complete!'}
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
          {/* File Select State */}
          {step === 'select' && (
            <div>
              <div
                className={`border-2 border-dashed rounded-xl p-12 text-center transition-colors ${
                  isDragging
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-300 hover:border-gray-400'
                }`}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
              >
                <div className="text-5xl mb-4">📁</div>
                <p className="text-lg font-medium text-gray-700 mb-2">
                  Drag & drop an image here
                </p>
                <p className="text-sm text-gray-500 mb-4">or</p>
                <button
                  onClick={handleBrowseClick}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Browse Files
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  onChange={handleFileInputChange}
                  className="hidden"
                />
                <p className="text-xs text-gray-400 mt-4">
                  Supports: JPEG, PNG, WebP, GIF (max 20MB)
                </p>
              </div>

              {error && (
                <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-3">
                  <p className="text-sm text-red-700">{error}</p>
                </div>
              )}
            </div>
          )}

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
                onClick={handleReset}
                className="mt-3 text-sm text-red-700 underline hover:text-red-900"
              >
                Try again with different file
              </button>
            </div>
          )}

          {/* Preview State */}
          {step === 'preview' && preview && (
            <div className="space-y-6">
              {/* Image Preview */}
              <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-lg">
                {filePreviewUrl && (
                  <img
                    src={filePreviewUrl}
                    alt="Preview"
                    className="w-20 h-20 object-cover rounded border border-gray-200"
                  />
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-700 truncate">
                    {selectedFile?.name}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {preview.original_dimensions?.[0]} × {preview.original_dimensions?.[1]} px
                    {' • '}
                    {formatBytes(selectedFile?.size || 0)}
                  </p>
                </div>
                <button
                  onClick={handleReset}
                  className="text-sm text-gray-500 hover:text-gray-700 underline"
                >
                  Change
                </button>
              </div>

              {/* Size Comparison */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-sm font-bold text-blue-900 mb-3">Estimated Optimization</p>
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

              {/* New filename preview */}
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <p className="text-sm font-bold text-green-900 mb-1">New Filename</p>
                <p className="text-sm text-green-700 font-mono">
                  {preview.suggested_filename || `${seoKeyword || 'image'}-small.webp`}
                </p>
              </div>

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
                    Generate AI alt text, description & caption (GEO optimized)
                  </label>
                </div>
              </div>
            </div>
          )}

          {/* Optimizing State */}
          {step === 'optimizing' && (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
              <p className="mt-4 text-gray-600">Optimizing and uploading to WordPress...</p>
              <p className="text-sm text-gray-500 mt-1">This may take a moment</p>
            </div>
          )}

          {/* Done State */}
          {step === 'done' && result && (
            <div className="space-y-6">
              <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-center">
                <p className="text-2xl mb-2">✓</p>
                <p className="text-lg font-bold text-green-800">Upload Complete!</p>
                <p className="text-sm text-green-700 mt-1">
                  {formatSize(result.file_size_kb)} WebP uploaded to WordPress
                </p>
              </div>

              {/* New URL */}
              <div>
                <p className="text-sm font-medium text-gray-700 mb-1">WordPress Image URL:</p>
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

              {/* Next Steps */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-sm font-bold text-blue-900 mb-2">Next Steps:</p>
                <ol className="list-decimal list-inside text-sm text-blue-800 space-y-1">
                  <li>Go to WordPress and edit the page where you want to use this image</li>
                  <li>Insert the image using the Media Library or paste the URL above</li>
                </ol>
              </div>

              {/* Archive Info */}
              {result.archive_paths && (
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                  <p className="text-sm font-medium text-gray-700 mb-2">Local Archive:</p>
                  <div className="text-xs text-gray-600 space-y-1 font-mono">
                    <p>Original: {result.archive_paths.original}</p>
                    <p>Optimized: {result.archive_paths.optimized}</p>
                  </div>
                </div>
              )}

              {/* GEO AI Metadata */}
              {result.geo_metadata && (
                <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                  <p className="text-sm font-bold text-purple-900 mb-3">
                    AI-Generated Metadata (Applied to WordPress)
                  </p>
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
                        <p className="text-purple-700 mt-1 text-xs leading-relaxed">
                          {result.geo_metadata.description}
                        </p>
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
          {step === 'select' && (
            <button
              onClick={onClose}
              className="flex-1 border border-gray-300 text-gray-700 rounded-lg py-2 text-sm hover:bg-gray-50"
            >
              Cancel
            </button>
          )}
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

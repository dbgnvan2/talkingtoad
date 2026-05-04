/**
 * ImageAnalysisPanel.jsx
 *
 * v1.9image: Dedicated image analysis tab showing image health scores,
 * thumbnails, and per-image scoring breakdown with sort/filter options.
 */

import React, { useState, useEffect, useCallback } from 'react'
import { getImages, getImagesSummary, fetchImageDetails, analyzeImageWithAI, updateImageMeta, downloadAIImagePDF, analyzeImageWithGeo, applyGeoMetadata, getGeoSettings, getOrphanedMedia } from '../api.js'
import { getIssueHelp } from '../data/issueHelp.js'
import SeverityBadge from './SeverityBadge.jsx'
import GeoAnalysisModal from './GeoAnalysisModal.jsx'
import GeoSettingsModal from './GeoSettingsModal.jsx'
import OptimizeExistingModal from './OptimizeExistingModal.jsx'
import UploadNewImageModal from './UploadNewImageModal.jsx'
import BatchOptimizePanel from './BatchOptimizePanel.jsx'

export default function ImageAnalysisPanel({ jobId, domain, onPageClick, onShowHelp }) {
  const [summary, setSummary] = useState(null)
  const [images, setImages] = useState([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [sortBy, setSortBy] = useState('score')
  const [expandedImage, setExpandedImage] = useState(null)
  const [error, setError] = useState(null)
  const [fetchingAll, setFetchingAll] = useState(false)
  const [fetchProgress, setFetchProgress] = useState({ current: 0, total: 0 })
  const [selectedImages, setSelectedImages] = useState(new Set())
  const [analyzingAI, setAnalyzingAI] = useState(false)
  const [aiProgress, setAiProgress] = useState({ current: 0, total: 0 })
  const [aiResults, setAiResults] = useState(null)
  const [showWpLogin, setShowWpLogin] = useState(false)
  const [wpLoginCallback, setWpLoginCallback] = useState(null)
  const [showBatchOptimize, setShowBatchOptimize] = useState(false)
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [orphanedMedia, setOrphanedMedia] = useState(null)
  const [loadingOrphans, setLoadingOrphans] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [summaryData, imagesData] = await Promise.all([
        getImagesSummary(jobId),
        getImages(jobId, { page, limit: 50, sortBy })
      ])
      setSummary(summaryData)
      setImages(imagesData.images || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [jobId, page, sortBy])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleFetchAll = async () => {
    setFetchingAll(true)
    setFetchProgress({ current: 0, total: 0 })

    try {
      // If images are selected, only fetch those. Otherwise fetch all.
      let imagesToFetch
      if (selectedImages.size > 0) {
        // Fetch only selected images
        imagesToFetch = images.filter(img => selectedImages.has(img.url))
      } else {
        // Get all images that need fetching
        const allImagesResponse = await getImages(jobId, { page: 1, limit: 1000, sortBy: 'score' })
        const allImages = allImagesResponse.images || []
        imagesToFetch = allImages.filter(img => (img.data_source || 'html_only') !== 'full_fetch')
      }

      if (imagesToFetch.length === 0) {
        alert('All images already have full details!')
        setFetchingAll(false)
        return
      }

      setFetchProgress({ current: 0, total: imagesToFetch.length })

      // Fetch in batches of 5 at a time to avoid overwhelming the server
      const batchSize = 5
      const failedImages = []
      for (let i = 0; i < imagesToFetch.length; i += batchSize) {
        const batch = imagesToFetch.slice(i, i + batchSize)
        await Promise.all(
          batch.map(img =>
            fetchImageDetails(jobId, img.url)
              .then(() => {
                setFetchProgress(prev => ({ ...prev, current: prev.current + 1 }))
              })
              .catch(err => {
                console.error(`Failed to fetch ${img.url}:`, err)
                failedImages.push({ url: img.url, error: err.message })
                setFetchProgress(prev => ({ ...prev, current: prev.current + 1 }))
              })
          )
        )
      }

      // Show which images failed if any
      if (failedImages.length > 0) {
        console.error('Failed images:', failedImages)
      }

      // Reload data after all fetches complete
      await loadData()
      alert(`Successfully fetched details for ${imagesToFetch.length} images!`)
    } catch (err) {
      setError('Failed to fetch all images: ' + err.message)
    } finally {
      setFetchingAll(false)
      setFetchProgress({ current: 0, total: 0 })
    }
  }

  const handleAnalyzeSelected = async () => {
    if (selectedImages.size === 0) {
      alert('Please select at least one image to analyze')
      return
    }

    setAnalyzingAI(true)
    setAiProgress({ current: 0, total: selectedImages.size })

    try {
      const results = []
      const imagesToAnalyze = Array.from(selectedImages)

      // Analyze in batches of 3 at a time (AI calls are slower)
      const batchSize = 3
      for (let i = 0; i < imagesToAnalyze.length; i += batchSize) {
        const batch = imagesToAnalyze.slice(i, i + batchSize)
        const batchResults = await Promise.all(
          batch.map(imageUrl =>
            analyzeImageWithAI(jobId, imageUrl)
              .then(result => {
                setAiProgress(prev => ({ ...prev, current: prev.current + 1 }))
                return { imageUrl, ...result }
              })
              .catch(err => {
                console.error(`Failed to analyze ${imageUrl}:`, err)
                setAiProgress(prev => ({ ...prev, current: prev.current + 1 }))
                return { imageUrl, error: err.message }
              })
          )
        )
        results.push(...batchResults)
      }

      // Reload data to get updated scores
      await loadData()

      // Show results modal
      setAiResults(results)
      setSelectedImages(new Set()) // Clear selection
    } catch (err) {
      setError('Failed to analyze images: ' + err.message)
    } finally {
      setAnalyzingAI(false)
      setAiProgress({ current: 0, total: 0 })
    }
  }

  const handleToggleAll = () => {
    if (selectedImages.size === images.length) {
      setSelectedImages(new Set())
    } else {
      setSelectedImages(new Set(images.map(img => img.url)))
    }
  }


  if (loading && !summary) {
    return (
      <div className="py-20 text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600 mx-auto" />
        <p className="mt-4 text-gray-400 font-bold uppercase tracking-widest">Loading Images...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="py-12 bg-white rounded-2xl border border-red-100 text-center">
        <p className="text-red-600">{error}</p>
        <button onClick={loadData} className="mt-4 px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-bold">
          Retry
        </button>
      </div>
    )
  }

  if (!summary || summary.total_images === 0) {
    return (
      <div className="py-12 bg-white rounded-2xl border border-gray-100 text-center text-gray-400 font-medium font-serif italic">
        No images found during this crawl.
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Summary Stats */}
      <ImageSummaryStats summary={summary} />

      {/* Issue Breakdown */}
      {summary.by_issue && Object.keys(summary.by_issue).length > 0 && (
        <IssueBreakdown byIssue={summary.by_issue} />
      )}

      {/* Fetch Progress Banner */}
      {fetchingAll && (
        <div className="bg-blue-50 border border-blue-200 rounded-2xl p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-bold text-blue-800">Fetching image details...</p>
            <p className="text-sm font-bold text-blue-600">{fetchProgress.current} / {fetchProgress.total}</p>
          </div>
          <div className="w-full bg-blue-200 rounded-full h-2 overflow-hidden">
            <div
              className="bg-blue-600 h-full transition-all duration-300"
              style={{ width: `${fetchProgress.total > 0 ? (fetchProgress.current / fetchProgress.total) * 100 : 0}%` }}
            />
          </div>
        </div>
      )}

      {/* AI Analysis Progress Banner */}
      {analyzingAI && (
        <div className="bg-purple-50 border border-purple-200 rounded-2xl p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-bold text-purple-800">Analyzing images with AI...</p>
            <p className="text-sm font-bold text-purple-600">{aiProgress.current} / {aiProgress.total}</p>
          </div>
          <div className="w-full bg-purple-200 rounded-full h-2 overflow-hidden">
            <div
              className="bg-purple-600 h-full transition-all duration-300"
              style={{ width: `${aiProgress.total > 0 ? (aiProgress.current / aiProgress.total) * 100 : 0}%` }}
            />
          </div>
        </div>
      )}

      {/* Orphaned Media Results */}
      {orphanedMedia && (
        <div className={`p-4 rounded-xl border ${orphanedMedia.error ? 'bg-red-50 border-red-200' : 'bg-purple-50 border-purple-200'}`}>
          {orphanedMedia.error ? (
            <div className="flex items-center justify-between">
              <p className="text-red-700 font-medium">Error: {orphanedMedia.error}</p>
              <button onClick={() => setOrphanedMedia(null)} className="text-gray-400 hover:text-gray-600 text-xl">×</button>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between mb-3">
                <span className="text-lg font-bold text-gray-800">
                  Orphaned Media: {orphanedMedia.count} image{orphanedMedia.count !== 1 ? 's' : ''} not used on any page
                </span>
                <button onClick={() => setOrphanedMedia(null)} className="text-gray-400 hover:text-gray-600 text-xl">×</button>
              </div>
              {orphanedMedia.count === 0 ? (
                <p className="text-sm text-green-700 font-medium">All WordPress media images are referenced on at least one crawled page.</p>
              ) : (
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {orphanedMedia.orphaned_media.map(item => (
                    <div key={item.id} className="flex items-center gap-3 p-3 bg-white rounded-lg border border-purple-100">
                      <img
                        src={item.url}
                        alt={item.alt_text || ''}
                        className="w-12 h-12 object-cover rounded border border-gray-200 flex-shrink-0"
                        onError={e => { e.target.style.display = 'none' }}
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-bold text-gray-800 truncate">{item.title}</p>
                        <p className="text-xs font-mono text-gray-500 truncate">{item.url.split('/').pop()}</p>
                        <div className="flex items-center gap-3 mt-0.5">
                          <span className="text-xs text-gray-400">{item.mime_type}</span>
                          {item.file_size_kb && <span className="text-xs text-gray-400">{item.file_size_kb} KB</span>}
                          {item.dimensions && <span className="text-xs text-gray-400">{item.dimensions}</span>}
                          {item.post_parent === 0 && <span className="text-xs text-red-500 font-bold">Unattached</span>}
                        </div>
                      </div>
                      <a
                        href={item.admin_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="px-3 py-1.5 text-xs font-bold bg-purple-100 text-purple-700 rounded-lg hover:bg-purple-200 flex-shrink-0"
                      >
                        Edit in WP
                      </a>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Sort Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-bold text-gray-800">{domain ? `Images - ${domain}` : 'Images'}</h2>
          {onShowHelp && (
            <button
              onClick={onShowHelp}
              className="w-7 h-7 flex items-center justify-center rounded-full bg-indigo-100 text-indigo-600 hover:bg-indigo-200 transition-all font-bold text-sm"
              title="Learn about Image category"
            >
              ?
            </button>
          )}
          <label className="flex items-center gap-2 ml-4 cursor-pointer">
            <input
              type="checkbox"
              checked={selectedImages.size === images.length && images.length > 0}
              onChange={handleToggleAll}
              className="w-4 h-4 rounded border-gray-300 text-green-600 focus:ring-green-500"
            />
            <span className="text-sm text-gray-600 font-medium">
              {selectedImages.size > 0 ? `${selectedImages.size} selected` : 'Select All'}
            </span>
          </label>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={handleAnalyzeSelected}
            disabled={analyzingAI || loading || selectedImages.size === 0}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-bold hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            title={selectedImages.size === 0 ? "Select 'All' or specific images to analyze with AI" : "Analyze selected images with AI"}
          >
            {analyzingAI
              ? `Analyzing ${aiProgress.current}/${aiProgress.total}...`
              : '🤖 AI Analyse'
            }
          </button>
          <button
            onClick={handleFetchAll}
            disabled={fetchingAll || loading}
            className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-bold hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            title={selectedImages.size > 0 ? `Fetch WP data for ${selectedImages.size} selected images` : "Fetch WP data for all images"}
          >
            {fetchingAll
              ? `Fetching ${fetchProgress.current}/${fetchProgress.total}...`
              : selectedImages.size > 0
                ? `Fetch ${selectedImages.size} Images`
                : 'Fetch All Images'
            }
          </button>
          <button
            onClick={async () => {
              setLoadingOrphans(true)
              try {
                const result = await getOrphanedMedia(jobId)
                setOrphanedMedia(result)
              } catch (err) {
                setOrphanedMedia({ error: err.message })
              } finally {
                setLoadingOrphans(false)
              }
            }}
            disabled={loadingOrphans}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-bold hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            title="Find images in WordPress Media Library not used on any crawled page"
          >
            {loadingOrphans ? 'Scanning WP...' : 'Find Orphaned'}
          </button>
          <button
            onClick={() => setShowBatchOptimize(true)}
            disabled={selectedImages.size === 0 || loading}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-bold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            title={selectedImages.size === 0 ? "Select images to batch optimize" : `Batch optimize ${selectedImages.size} images`}
          >
            {selectedImages.size === 0
              ? '📦 Batch Optimize'
              : `📦 Optimize ${selectedImages.size}`
            }
          </button>
          <button
            onClick={() => setShowUploadModal(true)}
            className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-bold hover:bg-green-700 transition-all"
            title="Upload and optimize a new image from your computer"
          >
            📤 Upload New
          </button>
          <label className="text-sm text-gray-500 font-medium">Sort by:</label>
          <select
            value={sortBy}
            onChange={e => { setSortBy(e.target.value); setPage(1) }}
            className="px-3 py-2 border border-gray-200 rounded-lg text-sm font-medium focus:outline-none focus:ring-2 focus:ring-green-100"
          >
            <option value="score">Worst Score First</option>
            <option value="size">Largest First</option>
            <option value="load_time">Slowest First</option>
          </select>
        </div>
      </div>

      {/* Image Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {images.map((img) => (
          <ImageCard
            key={img.url}
            image={img}
            jobId={jobId}
            isExpanded={expandedImage === img.url}
            onToggle={() => setExpandedImage(expandedImage === img.url ? null : img.url)}
            onPageClick={onPageClick}
            isSelected={selectedImages.has(img.url)}
            onSelect={(url) => {
              const newSelection = new Set(selectedImages)
              if (newSelection.has(url)) {
                newSelection.delete(url)
              } else {
                newSelection.add(url)
              }
              setSelectedImages(newSelection)
            }}
            onImageUpdate={async (updated) => {
              console.log('[ImageUpdate] Updating image:', updated.url, 'with alt:', updated.alt)
              // Update the image in the list
              setImages(prev => {
                const newImages = prev.map(i => {
                  if (i.url === updated.url) {
                    console.log('[ImageUpdate] Found match, replacing:', i.url)
                    return { ...updated }
                  }
                  return i
                })
                return newImages
              })
              // Reload summary to update Total Size and other stats
              try {
                const summaryData = await getImagesSummary(jobId)
                setSummary(summaryData)
              } catch (err) {
                console.error('Failed to reload summary:', err)
              }
            }}
          />
        ))}
      </div>

      {/* AI Results Modal */}
      {aiResults && (
        <AIResultsModal
          results={aiResults}
          jobId={jobId}
          onClose={() => setAiResults(null)}
        />
      )}

      {/* Pagination */}
      {summary.total_images > 50 && (
        <div className="flex justify-center gap-2 pt-4">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-4 py-2 bg-gray-100 rounded-lg text-sm font-bold disabled:opacity-50"
          >
            Previous
          </button>
          <span className="px-4 py-2 text-sm text-gray-500">
            Page {page} of {Math.ceil(summary.total_images / 50)}
          </span>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={images.length < 50}
            className="px-4 py-2 bg-gray-100 rounded-lg text-sm font-bold disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}

      {/* WordPress Login Modal */}
      {showWpLogin && (
        <WordPressLoginModal
          onSubmit={(credentials) => {
            if (wpLoginCallback) {
              wpLoginCallback(credentials)
            }
          }}
          onClose={() => setShowWpLogin(false)}
        />
      )}

      {/* Batch Optimize Panel */}
      {showBatchOptimize && (
        <BatchOptimizePanel
          jobId={jobId}
          selectedImages={images.filter(img => selectedImages.has(img.url))}
          onClose={() => setShowBatchOptimize(false)}
          onComplete={(data) => {
            // Reload data after batch completes
            loadData()
            setSelectedImages(new Set())
          }}
        />
      )}

      {/* Upload New Image Modal */}
      {showUploadModal && (
        <UploadNewImageModal
          jobId={jobId}
          onClose={() => setShowUploadModal(false)}
          onSuccess={(data) => {
            // Optionally reload data after upload
            loadData()
          }}
        />
      )}
    </div>
  )
}

function ImageSummaryStats({ summary }) {
  const healthColor = summary.image_health_score >= 80 ? 'text-green-600' :
                      summary.image_health_score >= 60 ? 'text-amber-500' : 'text-red-600'

  const partialCount = summary.total_images - (summary.images_analyzed || 0)
  const analysisText = summary.images_analyzed
    ? `${summary.images_analyzed} fully analyzed${partialCount > 0 ? `, ${partialCount} partial` : ''}`
    : summary.images_with_metadata
    ? `${summary.images_with_metadata} with metadata`
    : 'HTML only'

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <StatCard
        label="Image Health"
        value={`${summary.image_health_score}%`}
        color={healthColor}
      />
      <StatCard
        label="Total Images"
        value={summary.total_images}
        subtext={analysisText}
      />
      <StatCard
        label="Total Size"
        value={`${summary.total_size_kb} KB`}
        subtext={summary.total_size_kb > 1024 ? `(${(summary.total_size_kb / 1024).toFixed(1)} MB)` : null}
      />
      <StatCard
        label="Avg Load Time"
        value={`${summary.avg_load_time_ms}ms`}
        color={summary.avg_load_time_ms > 500 ? 'text-amber-500' : 'text-gray-800'}
      />
    </div>
  )
}

function StatCard({ label, value, color = 'text-gray-800', subtext }) {
  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-5 text-center shadow-sm">
      <p className="text-xs font-black text-gray-400 uppercase tracking-widest mb-2">{label}</p>
      <p className={`text-2xl font-black ${color}`}>{value}</p>
      {subtext && <p className="text-xs text-gray-400 mt-1">{subtext}</p>}
    </div>
  )
}

function IssueBreakdown({ byIssue }) {
  const sortedIssues = Object.entries(byIssue)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 8)

  if (sortedIssues.length === 0) return null

  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm">
      <h3 className="text-sm font-black text-gray-400 uppercase tracking-widest mb-4">Issues Found</h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {sortedIssues.map(([code, count]) => {
          const help = getIssueHelp(code)
          const severity = help?.severity || 'info'
          return (
            <div key={code} className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
              <SeverityBadge severity={severity} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-bold text-gray-800 truncate" title={help?.title || code}>
                  {help?.title || code}
                </p>
                <p className="text-xs text-gray-500">{count} image{count !== 1 ? 's' : ''}</p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ImageCard({ image, jobId, isExpanded, onToggle, onPageClick, isSelected, onSelect, onImageUpdate }) {
  const [fetching, setFetching] = useState(false)
  const [analyzingAI, setAnalyzingAI] = useState(false)
  const [aiResult, setAiResult] = useState(null)
  const [applyingAI, setApplyingAI] = useState(false)
  const [applySuccess, setApplySuccess] = useState(false)
  const [showWpLogin, setShowWpLogin] = useState(false)
  const [geoResult, setGeoResult] = useState(null)
  const [showGeoModal, setShowGeoModal] = useState(false)
  const [showGeoSettings, setShowGeoSettings] = useState(false)
  const [geoConfigured, setGeoConfigured] = useState(false)
  const [showOptimizeModal, setShowOptimizeModal] = useState(false)

  const dataSource = image.data_source || 'html_only'
  const isPartialAnalysis = dataSource !== 'full_fetch'

  // Unified fetch handler - fetches BOTH image file + WordPress metadata
  const handleFetch = async (e) => {
    e?.stopPropagation()
    setFetching(true)
    try {
      console.log('[Fetch] Fetching image:', image.url)
      const result = await fetchImageDetails(jobId, image.url)
      console.log('[Fetch] Result:', result)

      if (result.image && onImageUpdate) {
        console.log('[Fetch] Updating image with alt:', result.image.alt)
        onImageUpdate(result.image)

        // Auto-expand to show updated details
        if (!isExpanded && onToggle) {
          onToggle()
        }
      }
    } catch (err) {
      console.error('Failed to fetch image:', err)
      alert('Failed to fetch image data: ' + err.message)
    } finally {
      setFetching(false)
    }
  }

  const handleAnalyzeAI = async (e) => {
    e.stopPropagation()

    // Extract domain from page URL
    let domain = ''
    try {
      const url = new URL(image.page_url)
      domain = url.hostname.replace('www.', '')
    } catch (err) {
      console.error('Failed to extract domain from page URL:', err)
      alert('Could not determine domain from page URL')
      return
    }

    setAnalyzingAI(true)
    try {
      // Check if GEO is configured for this domain
      const geoConfig = await getGeoSettings(domain)

      if (!geoConfig.is_configured) {
        setAnalyzingAI(false)
        const configure = confirm(
          `GEO is not configured for ${domain}.\n\n` +
          'GEO (Generative Engine Optimization) generates AI-powered metadata with geographic and topic context.\n\n' +
          'Would you like to configure it now?'
        )
        if (configure) {
          setShowGeoSettings(true)
        }
        return
      }

      // Run GEO analysis
      const result = await analyzeImageWithGeo(jobId, image.url)

      if (!result.success) {
        throw new Error(result.error || 'GEO analysis failed')
      }

      // Show modal with results
      setGeoResult(result)
      setShowGeoModal(true)
      setGeoConfigured(true)

      // Auto-expand to show analysis
      if (!isExpanded && onToggle) {
        onToggle()
      }
    } catch (err) {
      console.error('Failed to analyze image:', err)
      const errorMsg = err.message || 'Unknown error'
      if (errorMsg.includes('No GEO configuration')) {
        alert('GEO is not configured for this domain. Please configure it first.')
        setShowGeoSettings(true)
      } else {
        alert('GEO analysis failed: ' + errorMsg)
      }
    } finally {
      setAnalyzingAI(false)
    }
  }

  const handleSaveGeo = async (altText, description) => {
    try {
      // Apply GEO-optimized metadata to database
      const result = await applyGeoMetadata(jobId, image.url, altText, description)

      if (result.success) {
        // Close modal
        setShowGeoModal(false)

        // Reload image to get updated scores
        if (onImageUpdate) {
          const updatedResult = await fetchImageDetails(jobId, image.url)
          if (updatedResult.image) {
            onImageUpdate(updatedResult.image)
          }
        }

        alert(`GEO metadata applied!\n\nNew accessibility score: ${result.new_scores.accessibility_score}\nNew overall score: ${result.new_scores.overall_score}`)
      } else {
        throw new Error(result.message || 'Failed to apply GEO metadata')
      }
    } catch (err) {
      console.error('Failed to save GEO metadata:', err)
      alert('Failed to save GEO metadata: ' + err.message)
    }
  }

  const handleApplyAISuggestion = async (e, wpCredentials = null) => {
    e?.stopPropagation()
    if (!aiResult?.suggested_alt) {
      alert('No AI suggestion available')
      return
    }

    setApplyingAI(true)
    setApplySuccess(false)
    try {
      // Update WordPress
      const updateResult = await updateImageMeta(image.url, { altText: aiResult.suggested_alt, jobId, wpCredentials })
      console.log('[Apply AI] WordPress update result:', updateResult)

      // Fetch fresh data to get updated scores
      console.log('[Apply AI] Fetching fresh data to see score improvement...')
      const fetchResult = await fetchImageDetails(jobId, image.url)

      if (fetchResult.image && onImageUpdate) {
        console.log('[Apply AI] Updated image - alt:', fetchResult.image.alt, 'score:', fetchResult.image.overall_score)
        onImageUpdate(fetchResult.image)
      }

      // Re-run AI analysis to get new suggestions based on the updated alt text
      try {
        const freshAnalysis = await analyzeImageWithAI(jobId, image.url)
        setAiResult(freshAnalysis.analysis)
        console.log('[Apply AI] Fresh AI analysis:', freshAnalysis.analysis)
      } catch (aiErr) {
        console.warn('Failed to re-run AI analysis:', aiErr)
      }

      setApplySuccess(true)
      setTimeout(() => setApplySuccess(false), 3000)
    } catch (err) {
      console.error('Failed to update image:', err)
      if (err.message?.includes('DOMAIN_MISMATCH')) {
        setShowWpLogin(true)
      } else {
        alert('Failed to update WordPress image: ' + err.message)
      }
    } finally {
      setApplyingAI(false)
    }
  }

  const scoreColor = image.overall_score >= 80 ? 'bg-green-500' :
                     image.overall_score >= 60 ? 'bg-amber-500' : 'bg-red-500'

  const hasIssues = image.issues && image.issues.length > 0

  return (
    <div className={`bg-white border rounded-2xl overflow-hidden shadow-sm transition-all ${
      hasIssues ? 'border-amber-200 hover:border-amber-300' : 'border-gray-200 hover:border-gray-300'
    } ${isSelected ? 'ring-2 ring-green-400' : ''}`}>
      {/* Header with thumbnail */}
      <div className="flex gap-4 p-4">
        {/* Checkbox */}
        <div className="flex-shrink-0 flex items-start pt-1">
          <input
            type="checkbox"
            checked={isSelected}
            onChange={(e) => {
              e.stopPropagation()
              onSelect(image.url)
            }}
            className="w-4 h-4 rounded border-gray-300 text-green-600 focus:ring-green-500 cursor-pointer"
          />
        </div>

        {/* Thumbnail */}
        <div className="flex-shrink-0 w-20 h-20 bg-gray-100 rounded-lg overflow-hidden">
          <img
            src={image.url}
            alt={image.alt || ''}
            className="w-full h-full object-cover"
            loading="lazy"
            onError={(e) => { e.target.style.display = 'none' }}
          />
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-mono text-gray-600 truncate" title={image.filename}>
            {image.filename || 'Unknown'}
          </p>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <span className={`w-3 h-3 rounded-full ${scoreColor}`} />
            <span className="text-lg font-black text-gray-800">{Math.round(image.overall_score)}</span>
            {isPartialAnalysis && (
              <span className="text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded font-bold" title="Partial analysis - not all checks run">
                {dataSource === 'html_only' ? 'HTML' : 'CRAWL'}
              </span>
            )}
            <button
              onClick={handleFetch}
              disabled={fetching}
              className="px-2 py-0.5 text-[10px] bg-green-100 text-green-700 rounded font-bold hover:bg-green-200 disabled:opacity-50"
              title="Fetch live data: WordPress metadata (alt text, title) + image file (dimensions, size, load time)"
            >
              {fetching ? 'Fetching...' : '↻ Fetch WP Data'}
            </button>
            <button
              onClick={handleAnalyzeAI}
              disabled={analyzingAI}
              className="px-2 py-0.5 text-[10px] bg-purple-100 text-purple-700 rounded font-bold hover:bg-purple-200 disabled:opacity-50"
              title="GEO AI Analysis: Generate entity-rich alt text and descriptions for AI search engines"
            >
              {analyzingAI ? 'Analyzing...' : '🤖 GEO AI'}
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); setShowOptimizeModal(true) }}
              className="px-2 py-0.5 text-[10px] bg-blue-100 text-blue-700 rounded font-bold hover:bg-blue-200"
              title="Optimize: Download, resize, convert to WebP, inject GPS, upload to WordPress"
            >
              📦 Optimize
            </button>
          </div>
          <div className="flex gap-3 mt-1 text-xs text-gray-500">
            {image.file_size_kb && <span>{image.file_size_kb} KB</span>}
            {image.width && image.height && <span>{image.width}x{image.height}</span>}
            {image.format && image.format !== 'unknown' && <span className="uppercase">{image.format}</span>}
          </div>
        </div>

        {/* Expand button */}
        <button
          onClick={onToggle}
          className="flex-shrink-0 text-gray-400 hover:text-gray-600 text-xl font-black"
        >
          {isExpanded ? '▲' : '▼'}
        </button>
      </div>

      {/* Issues badges */}
      {hasIssues && (
        <div className="px-4 pb-3 flex flex-wrap gap-1">
          {image.issues.slice(0, 3).map(code => {
            const help = getIssueHelp(code)
            const sev = help?.severity || 'info'
            const colors = sev === 'critical' ? 'bg-red-100 text-red-700'
              : sev === 'warning' ? 'bg-amber-100 text-amber-700'
              : 'bg-blue-100 text-blue-600'
            return (
              <span
                key={code}
                className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${colors}`}
                title={help?.title || code}
              >
                {code.replace('IMG_', '')}
              </span>
            )
          })}
          {image.issues.length > 3 && (
            <span className="text-[10px] px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full font-bold">
              +{image.issues.length - 3} more
            </span>
          )}
        </div>
      )}

      {/* Expanded details */}
      {isExpanded && (
        <div className="border-t border-gray-100 p-4 bg-gray-50 space-y-4">
          {/* AI Analysis Result */}
          {aiResult && (
            <div className="p-4 bg-purple-50 border border-purple-200 rounded-lg">
              <p className="text-sm font-bold text-purple-800 mb-2">🤖 AI Analysis Result</p>
              <div className="space-y-3 text-sm">
                <div>
                  <span className="font-bold text-gray-700">AI Image Description:</span>
                  <p className="text-gray-800 mt-1 italic">{aiResult.description}</p>
                </div>

                {/* Current vs Suggested Alt Text */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-white p-3 rounded border border-gray-200">
                    <span className="font-bold text-gray-700 text-xs uppercase block mb-1">Current Alt Text:</span>
                    <p className="text-gray-800 text-xs">
                      {image.alt ? `"${image.alt}"` : <span className="text-red-600 italic">No alt text</span>}
                    </p>
                  </div>
                  <div className="bg-green-50 p-3 rounded border border-green-200">
                    <span className="font-bold text-green-700 text-xs uppercase block mb-1">Suggested Alt Text:</span>
                    <p className="text-green-800 text-xs font-medium">&quot;{aiResult.suggested_alt}&quot;</p>
                  </div>
                </div>

                {/* Scores */}
                <div className="grid grid-cols-2 gap-2 mt-2">
                  <div>
                    <span className="font-bold text-gray-700">Accuracy:</span> {aiResult.accuracy_score}/100
                  </div>
                  <div>
                    <span className="font-bold text-gray-700">Quality:</span> {aiResult.quality_score}/100
                  </div>
                </div>

                {aiResult.issues && aiResult.issues.length > 0 && (
                  <div>
                    <span className="font-bold text-gray-700">Issues:</span>
                    <ul className="list-disc list-inside text-gray-700 mt-1">
                      {aiResult.issues.map((issue) => (
                        <li key={issue}>{issue}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Apply to WordPress Button */}
                <div className="pt-2">
                  <button
                    onClick={handleApplyAISuggestion}
                    disabled={applyingAI || applySuccess}
                    className="w-full px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-bold hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                  >
                    {applyingAI ? 'Applying...' : applySuccess ? '✓ Applied to WordPress!' : 'Apply to WordPress'}
                  </button>
                  <p className="text-xs text-gray-500 mt-1 text-center">
                    Updates WordPress media alt text via REST API
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Partial analysis warning */}
          {isPartialAnalysis && (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
              <p className="text-xs font-bold text-amber-800 mb-1">Partial Analysis</p>
              <p className="text-xs text-amber-700">
                {dataSource === 'html_only'
                  ? 'Only HTML data available. Click "Get Details" to analyze file size, dimensions, load time, and compression.'
                  : 'Crawl metadata available (size, basic dimensions). Click "Get Details" for full analysis including load time and duplicate detection.'}
              </p>
            </div>
          )}

          {/* Score breakdown */}
          <div>
            <p className="text-xs font-black text-gray-400 uppercase tracking-widest mb-2">Score Breakdown</p>
            <div className="grid grid-cols-2 gap-2">
              <ScoreBar label="Performance" score={image.performance_score} />
              <ScoreBar label="Accessibility" score={image.accessibility_score} />
              <ScoreBar label="Technical" score={image.technical_score} />
              <ScoreBar label="Semantic" score={image.semantic_score} />
            </div>
          </div>

          {/* Details */}
          <div>
            <p className="text-sm font-black text-gray-400 uppercase tracking-widest mb-2">Details</p>
            <div className="space-y-1 text-sm">
              {/* Alt Text */}
              {image.alt && (
                <p><span className="text-gray-600 font-medium">Alt:</span> <span className="text-gray-800">{image.alt}</span></p>
              )}
              {!image.alt && (
                <p className="text-red-600 font-medium italic">Missing alt text</p>
              )}

              {/* Title */}
              {image.title && (
                <p><span className="text-gray-600 font-medium">Title:</span> <span className="text-gray-800">{image.title}</span></p>
              )}

              {/* Caption - show if fetched (even if empty) */}
              {image.data_source === 'full_fetch' && (
                <p>
                  <span className="text-gray-600 font-medium">WP Caption:</span>{' '}
                  {image.caption && image.caption.trim() ? (
                    <span className="text-gray-800">{image.caption}</span>
                  ) : (
                    <span className="text-gray-400 italic">(empty)</span>
                  )}
                </p>
              )}

              {/* Description */}
              {image.description && image.description.trim() && (
                <div>
                  <span className="text-gray-600 font-medium">
                    {image.data_source === 'geo_analyzed' ? '🤖 GEO Description:' : 'Description:'}
                  </span>{' '}
                  <span className="text-gray-800">{image.description}</span>
                </div>
              )}
              {!image.description && image.data_source === 'full_fetch' && (
                <p>
                  <span className="text-gray-600 font-medium">Description:</span>{' '}
                  <span className="text-gray-400 italic">(empty)</span>
                </p>
              )}

              {/* File Info */}
              {image.file_size_kb && (
                <p><span className="text-gray-600 font-medium">File Size:</span> <span className="text-gray-800">{image.file_size_kb} KB</span></p>
              )}

              {/* Dimensions */}
              {image.width && image.height && (
                <p><span className="text-gray-600 font-medium">Dimensions:</span> <span className="text-gray-800">{image.width} × {image.height}px</span></p>
              )}

              {/* Format */}
              {image.format && image.format !== 'unknown' && (
                <p><span className="text-gray-600 font-medium">Format:</span> <span className="text-gray-800 uppercase">{image.format}</span></p>
              )}

              {/* Load Time */}
              {image.load_time_ms && (
                <p><span className="text-gray-600 font-medium">Load Time:</span> <span className="text-gray-800">{image.load_time_ms}ms</span></p>
              )}

              {/* Overscaled Warning */}
              {image.rendered_width && image.width && image.rendered_width < image.width && (
                <p>
                  <span className="text-gray-600 font-medium">Displayed at:</span>{' '}
                  <span className="text-amber-700 font-medium">{image.rendered_width}px (intrinsic: {image.width}px) - Overscaled!</span>
                </p>
              )}

              {/* Data Source */}
              {image.data_source && (
                <p><span className="text-gray-600 font-medium">Data Source:</span> <span className="text-gray-500 text-xs uppercase">{image.data_source.replace('_', ' ')}</span></p>
              )}
            </div>
          </div>

          {/* Issues list */}
          {hasIssues && (
            <div>
              <p className="text-sm font-black text-gray-400 uppercase tracking-widest mb-2">Issues</p>
              <div className="space-y-2">
                {image.issues.map(code => {
                  const help = getIssueHelp(code)
                  return (
                    <div key={code} className="p-3 bg-white rounded-lg border border-gray-200">
                      <div className="flex items-center gap-2">
                        <SeverityBadge severity={help?.severity || 'info'} />
                        <span className="text-base font-bold text-gray-800">{help?.title || code}</span>
                      </div>
                      {help?.definition && (
                        <p className="text-sm text-gray-600 mt-1">{help.definition}</p>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Page link */}
          <button
            onClick={() => onPageClick?.(image.page_url)}
            className="w-full py-2 text-sm font-bold text-green-600 hover:text-green-700 hover:bg-green-50 rounded-lg transition-colors"
          >
            View Page: {new URL(image.page_url).pathname}
          </button>
        </div>
      )}

      {/* WordPress Login Modal */}
      {showWpLogin && (
        <WordPressLoginModal
          onSubmit={async (credentials) => {
            setShowWpLogin(false)
            await handleApplyAISuggestion(null, credentials)
          }}
          onClose={() => setShowWpLogin(false)}
        />
      )}

      {/* GEO Analysis Modal */}
      {showGeoModal && geoResult && (
        <GeoAnalysisModal
          geoResult={geoResult}
          image={image}
          onSave={handleSaveGeo}
          onClose={() => setShowGeoModal(false)}
        />
      )}

      {/* GEO Settings Modal */}
      {showGeoSettings && (
        <GeoSettingsModal
          domain={(() => {
            try {
              const url = new URL(image.page_url)
              return url.hostname.replace('www.', '')
            } catch {
              return ''
            }
          })()}
          onClose={() => setShowGeoSettings(false)}
          onSaved={() => {
            setShowGeoSettings(false)
            setGeoConfigured(true)
          }}
        />
      )}

      {/* Optimize Existing Image Modal */}
      {showOptimizeModal && (
        <OptimizeExistingModal
          image={image}
          jobId={jobId}
          onClose={() => setShowOptimizeModal(false)}
          onSuccess={(result) => {
            // Optionally refresh the image list after optimization
            console.log('Image optimized:', result)
          }}
        />
      )}
    </div>
  )
}

function ScoreBar({ label, score }) {
  const color = score >= 80 ? 'bg-green-500' : score >= 60 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-gray-500">{label}</span>
        <span className="font-bold text-gray-700">{Math.round(score)}</span>
      </div>
      <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${score}%` }} />
      </div>
    </div>
  )
}

function AIResultsModal({ results, jobId, onClose }) {
  const [exporting, setExporting] = React.useState(false)

  const handleSavePDF = async () => {
    if (exporting) return
    setExporting(true)
    try {
      // Pass the full AI results to the PDF generator
      await downloadAIImagePDF(jobId, results)
    } catch (err) {
      alert('Failed to export PDF: ' + err.message)
    } finally {
      setTimeout(() => setExporting(false), 1000)
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-3xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-gradient-to-r from-purple-50 to-indigo-50 border-b border-gray-100 px-8 py-6 flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-black text-gray-800">AI Analysis Results</h2>
            <p className="text-sm text-gray-500 mt-1">{results.length} images analyzed</p>
          </div>
          <button
            onClick={onClose}
            className="w-10 h-10 flex items-center justify-center rounded-full bg-white text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-all text-2xl font-black"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div className="px-8 py-6 space-y-4">
          {results.map((result, idx) => {
            const analysis = result.analysis
            const hasError = !!result.error

            return (
              <div key={result.imageUrl} className="p-4 bg-gray-50 rounded-2xl border border-gray-200">
                <div className="flex items-start gap-4">
                  <img
                    src={result.imageUrl}
                    alt=""
                    className="w-24 h-24 object-cover rounded-lg"
                    onError={(e) => { e.target.style.display = 'none' }}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-mono text-gray-600 truncate mb-2" title={result.imageUrl}>
                      {result.imageUrl.split('/').pop()}
                    </p>

                    {hasError ? (
                      <p className="text-sm text-red-600">Error: {result.error}</p>
                    ) : (
                      <div className="space-y-2 text-sm">
                        <div>
                          <span className="font-bold text-gray-700">Description:</span>
                          <p className="text-gray-800 mt-1">{analysis.description}</p>
                        </div>
                        <div>
                          <span className="font-bold text-gray-700">Suggested Alt:</span>
                          <p className="text-gray-800 mt-1 italic">&quot;{analysis.suggested_alt}&quot;</p>
                        </div>
                        <div className="flex gap-4 text-xs">
                          <span>Accuracy: <strong>{analysis.accuracy_score}/100</strong></span>
                          <span>Quality: <strong>{analysis.quality_score}/100</strong></span>
                          <span>Semantic Score: <strong>{analysis.semantic_score}/100</strong></span>
                        </div>
                        {analysis.issues && analysis.issues.length > 0 && (
                          <div>
                            <span className="font-bold text-gray-700">Issues:</span>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {analysis.issues.map((issue) => (
                                <span key={issue} className="text-[10px] px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full font-bold">
                                  {issue}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-gray-50 border-t border-gray-100 px-8 py-4 flex gap-3">
          <button
            onClick={handleSavePDF}
            disabled={exporting}
            className="flex-1 py-3 bg-red-600 text-white rounded-2xl text-base font-bold shadow-lg shadow-red-100 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
          >
            {exporting ? '⏳ Saving...' : '📄 Save to PDF'}
          </button>
          <button
            onClick={onClose}
            className="flex-1 py-3 bg-purple-600 text-white rounded-2xl text-base font-bold shadow-lg shadow-purple-100 hover:bg-purple-700 transition-all"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

function WordPressLoginModal({ onSubmit, onClose }) {
  const [siteUrl, setSiteUrl] = React.useState('')
  const [loginUrl, setLoginUrl] = React.useState('')
  const [username, setUsername] = React.useState('')
  const [password, setPassword] = React.useState('')
  const [saving, setSaving] = React.useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const credentials = {
        site_url: siteUrl,
        login_url: loginUrl || `${siteUrl}/wp-login.php`,
        username,
        password
      }
      await onSubmit(credentials)
    } catch (err) {
      alert('Login failed: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-3xl shadow-2xl max-w-md w-full"
        onClick={e => e.stopPropagation()}
      >
        <div className="sticky top-0 bg-gradient-to-r from-blue-50 to-indigo-50 border-b border-gray-100 px-8 py-6">
          <h2 className="text-2xl font-black text-gray-800">WordPress Login Required</h2>
          <p className="text-sm text-gray-500 mt-1">Enter credentials for the site you're crawling</p>
        </div>

        <form onSubmit={handleSubmit} className="px-8 py-6 space-y-4">
          <div>
            <label className="block text-sm font-bold text-gray-700 mb-2">Site URL</label>
            <input
              type="url"
              value={siteUrl}
              onChange={e => setSiteUrl(e.target.value)}
              placeholder="https://example.com"
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          <div>
            <label className="block text-sm font-bold text-gray-700 mb-2">
              Login URL <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <input
              type="url"
              value={loginUrl}
              onChange={e => setLoginUrl(e.target.value)}
              placeholder="https://example.com/wp-login.php"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          <div>
            <label className="block text-sm font-bold text-gray-700 mb-2">Username</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          <div>
            <label className="block text-sm font-bold text-gray-700 mb-2">Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <p className="text-xs text-blue-800">
              These credentials will be saved to <code className="bg-blue-100 px-1 rounded">wp-credentials.json</code> for future use.
            </p>
          </div>

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-3 bg-gray-100 text-gray-700 rounded-2xl text-base font-bold hover:bg-gray-200 transition-all"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 py-3 bg-blue-600 text-white rounded-2xl text-base font-bold shadow-lg shadow-blue-100 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {saving ? 'Logging in...' : 'Login & Continue'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

import React from 'react'

export default function OrphanedSummaryCards({ orphanedImages, orphanedPages, onImagesClick, onPagesClick }) {
  return (
    <div className="grid grid-cols-2 gap-4">
      {orphanedImages !== undefined && (
        <button
          onClick={onImagesClick}
          className="bg-white border border-gray-200 rounded-2xl p-6 text-center shadow-sm hover:shadow-md hover:border-blue-300 transition-all"
        >
          <p className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-2">Orphaned Images</p>
          <p className="text-4xl font-bold text-blue-600">{orphanedImages}</p>
        </button>
      )}
      {orphanedPages !== undefined && (
        <button
          onClick={onPagesClick}
          className="bg-white border border-gray-200 rounded-2xl p-6 text-center shadow-sm hover:shadow-md hover:border-blue-300 transition-all"
        >
          <p className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-2">Orphaned Pages</p>
          <p className="text-4xl font-bold text-blue-600">{orphanedPages}</p>
        </button>
      )}
    </div>
  )
}

import React from 'react'
import { useTheme } from '../contexts/ThemeContext'

export default function SettingsPanel({ onClose }) {
  const { settings, updateSetting, resetToDefaults, DEFAULT_SETTINGS } = useTheme()

  const fontCategories = [
    { key: 'headingSize', label: 'Headings & Labels', desc: 'Section titles, category names, field labels' },
    { key: 'bodySize', label: 'Body Text', desc: 'Descriptions, URLs, recommendations' },
    { key: 'badgeSize', label: 'Badges & Counts', desc: 'Numbers, severity indicators, small labels' },
  ]

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-3xl shadow-2xl max-w-md w-full p-8" onClick={e => e.stopPropagation()}>
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-xl font-black text-gray-800">Display Settings</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl">&times;</button>
        </div>

        <div className="space-y-6">
          {fontCategories.map(cat => (
            <div key={cat.key} className="space-y-2">
              <div className="flex justify-between items-center">
                <div>
                  <p className="font-bold text-gray-800">{cat.label}</p>
                  <p className="text-xs text-gray-400">{cat.desc}</p>
                </div>
                <span className="text-sm font-mono text-gray-600 bg-gray-100 px-2 py-1 rounded">
                  {settings[cat.key]}px
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-400 w-8">8px</span>
                <input
                  type="range"
                  min="8"
                  max="24"
                  value={settings[cat.key]}
                  onChange={e => updateSetting(cat.key, parseInt(e.target.value))}
                  className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-green-600"
                />
                <span className="text-xs text-gray-400 w-8">24px</span>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                <span style={{ fontSize: `${settings[cat.key]}px` }} className="text-gray-700">
                  Preview text at {settings[cat.key]}px
                </span>
              </div>
            </div>
          ))}
        </div>

        <div className="flex gap-3 mt-8 pt-6 border-t border-gray-100">
          <button
            onClick={resetToDefaults}
            className="flex-1 py-3 text-sm font-bold text-gray-500 hover:text-gray-700 border border-gray-200 rounded-xl hover:bg-gray-50 transition-colors"
          >
            Reset to Defaults
          </button>
          <button
            onClick={onClose}
            className="flex-1 py-3 bg-green-600 text-white rounded-xl text-sm font-bold shadow-lg hover:bg-green-700 transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  )
}

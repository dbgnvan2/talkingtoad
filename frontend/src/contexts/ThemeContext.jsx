import React, { createContext, useContext, useState, useEffect } from 'react'

const STORAGE_KEY = 'talkingtoad-theme-settings'

const DEFAULT_SETTINGS = {
  headingSize: 14,   // Labels, section titles, category names
  bodySize: 12,      // Descriptions, URLs, recommendations
  badgeSize: 10,     // Numbers, severity badges, counts
}

const ThemeContext = createContext(null)

export function ThemeProvider({ children }) {
  const [settings, setSettings] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      return saved ? { ...DEFAULT_SETTINGS, ...JSON.parse(saved) } : DEFAULT_SETTINGS
    } catch {
      return DEFAULT_SETTINGS
    }
  })

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  }, [settings])

  const updateSetting = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }))
  }

  const resetToDefaults = () => {
    setSettings(DEFAULT_SETTINGS)
  }

  // Generate Tailwind-like class names based on pixel sizes
  const getFontClass = (category) => {
    const size = settings[category]
    // Map pixel sizes to inline styles since Tailwind can't do dynamic values
    return { fontSize: `${size}px` }
  }

  return (
    <ThemeContext.Provider value={{
      settings,
      updateSetting,
      resetToDefaults,
      getFontClass,
      DEFAULT_SETTINGS
    }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}

import React, { memo } from 'react'
import { useTheme } from '../contexts/ThemeContext.jsx'

function StatCard({ label, value, color = 'text-gray-800' }) {
  const { getFontClass } = useTheme()

  return (
    <div className="bg-white border border-gray-200 rounded-3xl p-6 text-center shadow-sm">
      <p className={`font-black uppercase tracking-widest mb-1 ${color}`} style={getFontClass('headingSize')}>{label}</p>
      <p className={`font-black ${color}`} style={{ ...getFontClass('badgeSize'), fontSize: `${getFontClass('badgeSize').fontSize.replace('px', '') * 2.5}px` }}>{value}</p>
    </div>
  )
}

export default memo(StatCard)

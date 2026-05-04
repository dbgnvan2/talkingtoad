import { useState, memo } from 'react'

function Tooltip({ text, children }) {
  const [visible, setVisible] = useState(false)

  return (
    <span
      className="relative inline-block"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      {children}
      {visible && (
        <span className="absolute z-10 left-1/2 -translate-x-1/2 bottom-full mb-2 w-64 rounded bg-gray-800 text-white text-xs p-2 shadow-lg pointer-events-none">
          {text}
          <span className="absolute left-1/2 -translate-x-1/2 top-full border-4 border-transparent border-t-gray-800" />
        </span>
      )}
    </span>
  )
}

export default memo(Tooltip)

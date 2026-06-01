import React, { createContext, useContext, useState, useCallback, useRef } from 'react'

const ToastContext = createContext(null)

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const [confirmState, setConfirmState] = useState(null)
  const confirmResolveRef = useRef(null)
  const toastIdRef = useRef(0)

  const addToast = useCallback((message, type, persist = false) => {
    const id = ++toastIdRef.current
    setToasts(prev => [...prev, { id, message, type, persist }])
    if (!persist) {
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id))
      }, 4000)
    }
  }, [])

  const dismissToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const success = useCallback((msg) => addToast(msg, 'success'), [addToast])
  const error = useCallback((msg) => addToast(msg, 'error', true), [addToast])
  const info = useCallback((msg) => addToast(msg, 'info'), [addToast])

  const confirm = useCallback((msg) => {
    return new Promise((resolve) => {
      confirmResolveRef.current = resolve
      setConfirmState({ message: msg })
    })
  }, [])

  const handleConfirm = useCallback((value) => {
    if (confirmResolveRef.current) {
      confirmResolveRef.current(value)
      confirmResolveRef.current = null
    }
    setConfirmState(null)
  }, [])

  const value = { success, error, info, confirm }

  return (
    <ToastContext.Provider value={value}>
      {children}
      {/* Toast container */}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm"
      >
        {toasts.map(toast => (
          <div
            key={toast.id}
            role="status"
            className={`px-4 py-3 rounded-lg shadow-lg text-white text-sm flex items-center justify-between gap-2 ${
              toast.type === 'success' ? 'bg-green-600' :
              toast.type === 'error' ? 'bg-red-600' :
              'bg-blue-600'
            }`}
          >
            <span>{toast.message}</span>
            {toast.persist && (
              <button
                onClick={() => dismissToast(toast.id)}
                className="text-white/80 hover:text-white ml-2 flex-shrink-0"
                aria-label="Dismiss"
              >
                ×
              </button>
            )}
          </div>
        ))}
      </div>
      {/* Confirm modal */}
      {confirmState && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => handleConfirm(false)}
        >
          <div
            className="bg-white rounded-lg shadow-xl p-6 max-w-sm mx-4"
            onClick={e => e.stopPropagation()}
          >
            <p className="text-gray-800 mb-4">{confirmState.message}</p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => handleConfirm(false)}
                className="px-4 py-2 text-sm rounded border border-gray-300 text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={() => handleConfirm(true)}
                className="px-4 py-2 text-sm rounded bg-blue-600 text-white hover:bg-blue-700"
              >
                OK
              </button>
            </div>
          </div>
        </div>
      )}
    </ToastContext.Provider>
  )
}

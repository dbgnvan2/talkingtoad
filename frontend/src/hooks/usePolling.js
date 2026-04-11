import { useEffect, useRef, useCallback } from 'react'

const TERMINAL = new Set(['complete', 'failed', 'cancelled'])
const FAST_MS = 2000   // first 60 seconds
const SLOW_MS = 5000   // after 60 seconds

/**
 * Polls `fetchFn` every 2s for 60s, then every 5s.
 * Stops automatically when `shouldStop(data)` returns true.
 */
export function usePolling(fetchFn, onData, shouldStop) {
  const timerRef = useRef(null)
  const startedRef = useRef(null)
  const stoppedRef = useRef(false)
  const onDataRef = useRef(onData)
  const shouldStopRef = useRef(shouldStop)

  onDataRef.current = onData
  shouldStopRef.current = shouldStop

  const poll = useCallback(async () => {
    if (stoppedRef.current) return
    try {
      const data = await fetchFn()
      onDataRef.current(data)
      if (shouldStopRef.current(data)) {
        stoppedRef.current = true
        return
      }
    } catch (err) {
      // keep polling on transient errors
    }
    const elapsed = Date.now() - startedRef.current
    const delay = elapsed < 60_000 ? FAST_MS : SLOW_MS
    timerRef.current = setTimeout(poll, delay)
  }, [fetchFn])

  useEffect(() => {
    stoppedRef.current = false
    startedRef.current = Date.now()
    poll()
    return () => {
      stoppedRef.current = true
      clearTimeout(timerRef.current)
    }
  }, [poll])
}

export function isTerminal(status) {
  return TERMINAL.has(status)
}

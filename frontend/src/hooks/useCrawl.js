import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { startCrawl } from '../api.js'

/**
 * Manages the crawl start flow: POST to /api/crawl/start,
 * then navigate to the progress page.
 */
export function useCrawl() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  async function start(targetUrl, settings) {
    setLoading(true)
    setError(null)
    try {
      const data = await startCrawl(targetUrl, settings)
      localStorage.setItem('talkingtoad_last_job', JSON.stringify({
        job_id: data.job_id,
        target_url: targetUrl,
        started_at: new Date().toISOString(),
      }))
      navigate(`/progress/${data.job_id}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return { start, loading, error }
}

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mockFetchResponse } from '../test/setup.js'
import {
  getResults,
  getResultsByCategory,
  getPageIssues,
  markFixed,
  markIssueFixed,
  markBrokenLinkFixed,
  markAnchorFixed,
  getOrphanedMedia,
  getOrphanedPages,
  fixEmptyAnchor,
  changeHeadingText,
  addIgnoredImagePattern,
  removeIgnoredImagePattern,
  getIgnoredImagePatterns,
  verifyBrokenLinks,
} from '../api.js'

describe('API module', () => {
  beforeEach(() => {
    global.fetch.mockReset()
  })

  describe('getResults', () => {
    it('fetches results for a job', async () => {
      global.fetch.mockImplementation(() => mockFetchResponse({ summary: { health_score: 90 } }))
      const result = await getResults('job-1')
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/crawl/job-1/results'),
        expect.any(Object)
      )
      expect(result.summary.health_score).toBe(90)
    })
  })

  describe('getResultsByCategory', () => {
    it('fetches category results', async () => {
      global.fetch.mockImplementation(() => mockFetchResponse({ issues: [] }))
      await getResultsByCategory('job-1', 'metadata')
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('metadata'),
        expect.any(Object)
      )
    })
  })

  describe('markIssueFixed', () => {
    it('sends correct payload', async () => {
      global.fetch.mockImplementation(() => mockFetchResponse({ success: true }))
      await markIssueFixed('job-1', 'https://example.com', ['TITLE_MISSING'])
      const call = global.fetch.mock.calls[0]
      const body = JSON.parse(call[1].body)
      expect(body.job_id).toBe('job-1')
      expect(body.page_url).toBe('https://example.com')
      expect(body.issue_codes).toEqual(['TITLE_MISSING'])
    })
  })

  describe('markBrokenLinkFixed', () => {
    it('sends correct broken link codes', async () => {
      global.fetch.mockImplementation(() => mockFetchResponse({ success: true }))
      await markBrokenLinkFixed('job-1', 'https://example.com/broken')
      const call = global.fetch.mock.calls[0]
      const body = JSON.parse(call[1].body)
      expect(body.broken_url).toBe('https://example.com/broken')
      expect(body.codes).toContain('BROKEN_LINK_404')
    })
  })

  describe('markAnchorFixed', () => {
    it('sends correct anchor data', async () => {
      global.fetch.mockImplementation(() => mockFetchResponse({ success: true, remaining: 2 }))
      const result = await markAnchorFixed('job-1', 'https://example.com', 'https://example.com/link')
      expect(result.remaining).toBe(2)
    })
  })

  describe('getOrphanedMedia', () => {
    it('fetches from correct endpoint', async () => {
      global.fetch.mockImplementation(() => mockFetchResponse({ count: 5, orphaned_media: [] }))
      const result = await getOrphanedMedia('job-1')
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/fixes/orphaned-media/job-1'),
        expect.any(Object)
      )
      expect(result.count).toBe(5)
    })
  })

  describe('getOrphanedPages', () => {
    it('filters to ORPHAN_PAGE issues only', async () => {
      global.fetch.mockImplementation(() => mockFetchResponse({
        issues: [
          { issue_code: 'ORPHAN_PAGE', page_url: 'https://example.com/orphan' },
          { issue_code: 'ROBOTS_BLOCKED', page_url: 'https://example.com/blocked' },
          { issue_code: 'ORPHAN_PAGE', page_url: 'https://example.com/orphan2' },
        ]
      }))
      const result = await getOrphanedPages('job-1')
      expect(result.count).toBe(2)
      expect(result.pages).toHaveLength(2)
      expect(result.pages[0].issue_code).toBe('ORPHAN_PAGE')
    })
  })

  describe('verifyBrokenLinks', () => {
    it('posts to correct endpoint', async () => {
      global.fetch.mockImplementation(() => mockFetchResponse({ total: 3, fixed: 1 }))
      const result = await verifyBrokenLinks('job-1')
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/fixes/verify-broken-links/job-1'),
        expect.objectContaining({ method: 'POST' })
      )
    })
  })

  describe('ignored image patterns', () => {
    it('addIgnoredImagePattern sends pattern', async () => {
      global.fetch.mockImplementation(() => mockFetchResponse({ status: 'added' }))
      await addIgnoredImagePattern('/icon.svg', 'theme icon')
      const call = global.fetch.mock.calls[0]
      const body = JSON.parse(call[1].body)
      expect(body.pattern).toBe('/icon.svg')
      expect(body.note).toBe('theme icon')
    })

    it('removeIgnoredImagePattern sends pattern as query', async () => {
      global.fetch.mockImplementation(() => mockFetchResponse({ status: 'removed' }))
      await removeIgnoredImagePattern('/icon.svg')
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('pattern=%2Ficon.svg'),
        expect.objectContaining({ method: 'DELETE' })
      )
    })

    it('getIgnoredImagePatterns fetches list', async () => {
      global.fetch.mockImplementation(() => mockFetchResponse([
        { pattern: '/icon.svg', note: '', added_at: '2026-01-01' }
      ]))
      const result = await getIgnoredImagePatterns()
      expect(result).toHaveLength(1)
    })
  })

  describe('changeHeadingText', () => {
    it('sends correct query params', async () => {
      global.fetch.mockImplementation(() => mockFetchResponse({ success: true, changed: 1 }))
      await changeHeadingText('https://example.com', 'Old Heading', 'New Heading', 1)
      const url = global.fetch.mock.calls[0][0]
      expect(url).toContain('old_text=Old+Heading')
      expect(url).toContain('new_text=New+Heading')
      expect(url).toContain('level=1')
    })
  })

  describe('error handling', () => {
    it('throws on non-OK response', async () => {
      global.fetch.mockImplementation(() =>
        Promise.resolve({
          ok: false,
          status: 500,
          json: () => Promise.resolve({ error: { message: 'Server error' } }),
        })
      )
      await expect(getResults('job-1')).rejects.toThrow()
    })
  })
})

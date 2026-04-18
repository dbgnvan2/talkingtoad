import { describe, it, expect } from 'vitest'
import issueHelp, { getIssueHelp } from '../issueHelp.js'

describe('issueHelp data', () => {
  const KNOWN_CODES = [
    'TITLE_MISSING', 'TITLE_TOO_SHORT', 'TITLE_TOO_LONG',
    'META_DESC_MISSING', 'META_DESC_TOO_SHORT', 'META_DESC_TOO_LONG',
    'H1_MISSING', 'H1_MULTIPLE', 'HEADING_SKIP',
    'BROKEN_LINK_404', 'BROKEN_LINK_5XX',
    'REDIRECT_301', 'REDIRECT_302', 'REDIRECT_CHAIN',
    'CANONICAL_MISSING', 'CANONICAL_EXTERNAL',
    'OG_TITLE_MISSING', 'OG_DESC_MISSING',
    'NOINDEX_META', 'NOINDEX_HEADER',
    'IMG_ALT_MISSING', 'IMG_OVERSIZED', 'IMG_BROKEN',
    'LINK_EMPTY_ANCHOR', 'TITLE_H1_MISMATCH',
    'SEMANTIC_DENSITY_LOW', 'JSON_LD_MISSING',
    'SITEMAP_MISSING', 'NOT_IN_SITEMAP',
    'HTTP_PAGE', 'MIXED_CONTENT',
    'URL_UPPERCASE', 'URL_TOO_LONG',
    'ORPHAN_PAGE', 'THIN_CONTENT',
  ]

  it('has help content for all major issue codes', () => {
    for (const code of KNOWN_CODES) {
      const help = getIssueHelp(code)
      expect(help, `Missing help for ${code}`).toBeTruthy()
      expect(help.title, `${code} missing title`).toBeTruthy()
    }
  })

  it('every help entry has required fields', () => {
    for (const [code, help] of Object.entries(issueHelp)) {
      expect(help.title, `${code} missing title`).toBeTruthy()
      expect(help.category, `${code} missing category`).toBeTruthy()
      expect(help.severity, `${code} missing severity`).toBeTruthy()
    }
  })

  it('severity values are valid', () => {
    const validSeverities = new Set(['critical', 'warning', 'info'])
    for (const [code, help] of Object.entries(issueHelp)) {
      expect(validSeverities.has(help.severity), `${code} has invalid severity: ${help.severity}`).toBe(true)
    }
  })

  it('category values are valid', () => {
    const validCategories = new Set([
      'broken_link', 'metadata', 'heading', 'redirect',
      'crawlability', 'duplicate', 'sitemap', 'security',
      'url_structure', 'ai_readiness', 'image',
    ])
    for (const [code, help] of Object.entries(issueHelp)) {
      expect(validCategories.has(help.category), `${code} has invalid category: ${help.category}`).toBe(true)
    }
  })

  it('returns null for unknown codes', () => {
    expect(getIssueHelp('NONEXISTENT_CODE')).toBeNull()
  })
})

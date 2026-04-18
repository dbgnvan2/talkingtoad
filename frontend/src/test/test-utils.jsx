import React from 'react'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../contexts/ThemeContext.jsx'

/**
 * Custom render that wraps components in required providers.
 * Use this instead of @testing-library/react render.
 */
export function renderWithProviders(ui, { route = '/', ...options } = {}) {
  function Wrapper({ children }) {
    return (
      <MemoryRouter initialEntries={[route]}>
        <ThemeProvider>
          {children}
        </ThemeProvider>
      </MemoryRouter>
    )
  }
  return render(ui, { wrapper: Wrapper, ...options })
}

/**
 * Mock summary data for testing Results page components.
 */
export const mockSummary = {
  health_score: 87,
  pages_crawled: 385,
  total_issues: 1240,
  by_severity: { critical: 3, warning: 793, info: 444 },
  by_category: {
    broken_link: 4,
    metadata: 81,
    heading: 35,
    redirect: 5,
    crawlability: 79,
    duplicate: 9,
    sitemap: 0,
    security: 167,
    url_structure: 211,
    image: 360,
    ai_readiness: 236,
  },
  robots_txt: { found: true, rules: ['User-agent: *', 'Disallow: /wp-admin/'] },
  sitemap: { found: true, url: 'https://example.com/sitemap.xml', url_count: 385 },
}

/**
 * Mock issue data for testing.
 */
export const mockIssue = (overrides = {}) => ({
  issue_code: 'TITLE_TOO_SHORT',
  category: 'metadata',
  severity: 'warning',
  description: 'Title under 30 characters',
  recommendation: 'Write a longer title.',
  human_description: 'Short Title',
  page_url: 'https://example.com/page',
  impact: 5,
  effort: 1,
  extra: { title: 'Short', length: 5 },
  ...overrides,
})

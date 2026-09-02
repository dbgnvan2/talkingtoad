// The happy path: start a crawl, watch it finish, read the results, export the PDF.
// Spec: docs/pending/2026-09-02_phase3-happy-path.md#R3.1
import { test, expect } from '@playwright/test'

const FIXTURE = 'http://127.0.0.1:8765/'

test('start crawl → results → export PDF', async ({ page }) => {
  await page.goto('/')
  await page.getByPlaceholder('example.org', { exact: true }).fill(FIXTURE)
  await page.getByRole('button', { name: /start crawl/i }).click()

  // Progress, then Results (the progress page navigates on completion).
  await expect(page).toHaveURL(/\/(progress|results)\//, { timeout: 30_000 })
  await expect(page).toHaveURL(/\/results\//, { timeout: 150_000 })
  await expect(page.getByRole('heading', { name: /audit results/i })).toBeVisible()

  // The summary carries a health score and at least one finding.
  await expect(page.getByText(/health score/i).first()).toBeVisible()
  await expect(page.getByText(/total issues/i).first()).toBeVisible()
  const total = await page.getByText(/total issues/i).first().locator('..').innerText()
  expect(total).toMatch(/[1-9]\d*/)

  // Export the PDF and check the bytes, not just the click.
  await page.getByRole('button', { name: 'PDF Report', exact: true }).click()
  const [resp] = await Promise.all([
    page.waitForResponse(r => r.url().includes('/export/pdf') && r.request().method() === 'GET', { timeout: 120_000 }),
    page.getByRole('button', { name: 'Generate PDF', exact: true }).click(),
  ])
  expect(resp.status()).toBe(200)
  expect(resp.headers()['content-type']).toContain('application/pdf')
  // The page consumed the streamed body (Playwright then sees 0 bytes), so
  // fetch the same URL once more and check the bytes, not just the click.
  const again = await page.request.get(resp.url())
  expect(again.status()).toBe(200)
  const body = await again.body()
  expect(body.length).toBeGreaterThan(20_000)
  expect(body.subarray(0, 4).toString()).toBe('%PDF')
})

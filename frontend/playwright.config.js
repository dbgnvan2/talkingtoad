// Phase 3 (2026-09-02): the happy path, end to end, in a real browser.
// Spec: docs/pending/2026-09-02_phase3-happy-path.md#R3.1
//
// Three servers, all on loopback, all started here so `npm run e2e` is the
// whole recipe: the golden fixture site (what gets crawled), uvicorn in dev
// mode (no AUTH_TOKEN, limiter off, loopback targets allowed), and Vite.
import { defineConfig } from '@playwright/test'

const ROOT = new URL('..', import.meta.url).pathname
// The interpreter that has requirements.txt installed. CI: setup-python's
// python3. Locally the project venv usually has them and the system one does
// not (absolute path — the servers start from the repo root):
//   E2E_PYTHON=$PWD/../venv/bin/python npm run e2e
const PY = process.env.E2E_PYTHON || 'python3'
const FIXTURE_PORT = 8765
// Dedicated ports: the E2E must never attach to a developer's running backend
// (different DB, AUTH_TOKEN set, loopback targets refused) — a run that did so
// failed with 'private networks are not allowed' on the first attempt.
const API_PORT = 8011
const WEB_PORT = 5199

export default defineConfig({
  testDir: './e2e',
  timeout: 180_000,
  expect: { timeout: 20_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: `${PY} tests/golden_site/server.py --port ${FIXTURE_PORT}`,
      cwd: ROOT,
      url: `http://127.0.0.1:${FIXTURE_PORT}/`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `${PY} -m uvicorn api.main:app --port ${API_PORT}`,
      cwd: ROOT,
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        AUTH_TOKEN: '',
        RATE_LIMIT_ENABLED: 'false',
        TT_ALLOW_LOCAL_TARGETS: '1',
        // The only DB knob the store reads. The first local run of this file
        // set a variable nothing reads and wrote four fixture jobs into the
        // developer's real talkingtoad.db.
        DATABASE_URL: 'sqlite:///' + (process.env.E2E_DB_PATH || '/tmp/talkingtoad-e2e.db'),
      },
    },
    {
      command: 'npx vite --strictPort --port ' + WEB_PORT,
      cwd: new URL('.', import.meta.url).pathname,
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: false,
      env: { API_URL: `http://127.0.0.1:${API_PORT}` },
      timeout: 60_000,
    },
  ],
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
})

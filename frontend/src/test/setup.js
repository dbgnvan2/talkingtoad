import '@testing-library/jest-dom'

// Mock localStorage for jsdom
const localStorageMock = (() => {
  let store = {}
  return {
    getItem: (key) => store[key] ?? null,
    setItem: (key, value) => { store[key] = String(value) },
    removeItem: (key) => { delete store[key] },
    clear: () => { store = {} },
  }
})()
Object.defineProperty(global, 'localStorage', { value: localStorageMock })

// Mock fetch globally for all tests
global.fetch = vi.fn()

// Mock import.meta.env
vi.stubEnv('VITE_AUTH_TOKEN', 'test-token')

// Helper to create a mock fetch response
export function mockFetchResponse(data, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    headers: new Headers(),
  })
}

// Helper to mock fetch for multiple sequential calls
export function mockFetchSequence(...responses) {
  responses.forEach((resp, i) => {
    global.fetch.mockImplementationOnce(() => mockFetchResponse(resp.data, resp.status || 200))
  })
}

// Reset mocks after each test
afterEach(() => {
  vi.restoreAllMocks()
  global.fetch.mockReset()
})

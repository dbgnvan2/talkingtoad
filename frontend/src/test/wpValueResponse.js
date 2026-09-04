/**
 * The GET /api/fixes/wp-value response, as the SERVER sends it.
 *
 * Every FixInlinePanel test builds its mock from here rather than hand-writing an
 * object literal. The reason is a real defect: until 2026-09-03 the endpoint
 * returned `{"value": ...}` while the panel read `data.current_value`, so the fix
 * editor opened blank on every issue — and seven vitest cases stayed green the whole
 * time, because each one mocked `{ current_value: 'Old Title' }`. The mocks were
 * written from the component, so they agreed with the component about a key the
 * server never sent (LEARNINGS P27).
 *
 * The key set here is pinned to the live endpoint by
 * tests/test_inline_fix_contract.py::test_the_vitest_fixture_matches_the_endpoint —
 * if the server's shape changes, that pytest goes red and this file has to follow.
 * Do not add a key to a mock inline; add it here.
 */
export function wpValueResponse({
  pageUrl = 'https://example.com/about',
  field = 'seo_title',
  currentValue = null,
  predefinedValue = null,
} = {}) {
  return {
    page_url: pageUrl,
    field,
    current_value: currentValue,
    predefined_value: predefinedValue,
  }
}

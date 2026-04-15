# TalkingToad — Project TODO & Technical Debt

This file tracks infrastructure improvements, testing gaps, and future features that aren't part of the current milestone but are critical for long-term stability.

## 🔴 High Priority: Stability & QA
- [ ] **Frontend Component Testing:** Set up Vitest and React Testing Library.
    - [ ] Add "smoke tests" for `Results.jsx` to ensure it handles null/loading states without crashing.
    - [ ] Test the `ExportReportModal` and `LLMSTxtGenerator` components.
- [ ] **API Error Boundaries:** Implement a React Error Boundary around the main `Results` view to catch and report crashes rather than showing a white screen.
- [ ] **End-to-End (E2E) Testing:** Set up Playwright to test the full "Start Crawl -> View Results -> Export PDF" happy path.

## 🟡 Medium Priority: UX & Polish
- [ ] **Persistent Settings:** Save the user's preferred PDF export options (Help Text ON/OFF) in localStorage.
- [ ] **Real-time Log Streaming:** Instead of just a progress bar, show a "Live Console" during the crawl for power users.

## 🟢 Low Priority: Tech Debt
- [ ] **Type Safety:** Migrate `Results.jsx` and other large components to TypeScript.
- [ ] **CSS Refactoring:** Clean up duplicate Tailwind classes in `Results.jsx` into shared base components.

// Browser acceptance for the shared comments widget.
//
// Separate from the site configs on purpose: this suite has no server and no
// site under test. It loads a local fixture over file:// and mocks the API at
// the network layer, so it runs anywhere the repository is checked out — no
// staging host, no credentials, nothing that could touch production.
//
//   npx playwright test --config=playwright.comments.config.js
const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/browser/comments-widget',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  // Two workers at most: the layout-shift measurement is timing-sensitive, and
  // a saturated machine produces shifts the widget did not cause.
  workers: process.env.CI ? 1 : 2,
  reporter: process.env.CI
    ? [['list'], ['json', { outputFile: 'artifacts/comments-widget-e2e.json' }]]
    : 'list',
  timeout: 30_000,
  expect: { timeout: 7_000 },
  use: {
    baseURL: 'http://127.0.0.1:8787',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  // A real http origin, not file://: browsers refuse `fetch` from file://, and
  // the first run of this suite produced a green "empty state" test purely
  // because the request had failed. See static-server.js.
  webServer: {
    command: 'node tests/browser/comments-widget/static-server.js',
    url: 'http://127.0.0.1:8787/tests/browser/comments-widget/fixture.html',
    reuseExistingServer: !process.env.CI,
    timeout: 20_000,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});

// Browser acceptance for the animedia.icu pilot, against the shadow contour.
//
// No webServer here: the contour is three processes started by
// automation/host/comments_shadow_rehearsal.py --keep-up, and its base URL
// arrives as CP_PILOT_BASE. Keeping the lifecycle in one place means the API
// checks and the browser checks run against the same processes rather than
// two contours that only look alike.
//
//   npx playwright test --config=playwright.pilot.config.js
const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/browser/comments-pilot',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  // One worker: several tests write comments to one shadow database, and a
  // rate limiter is part of what is being demonstrated.
  workers: 1,
  reporter: 'list',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  use: {
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});

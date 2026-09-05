// Кросс-браузерная приёмка theme pack basis-video: Firefox и WebKit.
const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/e2e-basis-cross',
  timeout: 90_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  reporter: [['list'], ['json', {
    outputFile: 'artifacts/evidence/templates/playwright-basis-cross.json',
  }]],
  projects: [
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],
  webServer: {
    command: '.venv/bin/python tests/tools/basis_stand.py',
    url: 'http://127.0.0.1:8821/healthz',
    reuseExistingServer: true,
    timeout: 120_000,
  },
});

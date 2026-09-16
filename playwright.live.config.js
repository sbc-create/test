// Приёмка по адресам действующих витрин.
//
// Один рабочий процесс и без повторов намеренно: прогон идёт по боевому сайту
// с настоящими посетителями, и приёмка не вправе создавать нагрузку или
// повторять запросы после отказа. Адреса берутся из
// `config/live-acceptance.json`; пока они пусты, набор пропускается с
// состоянием BLOCKED_OWNER_URLS.
//
//   npx playwright test --config=playwright.live.config.js
const { defineConfig, devices } = require('@playwright/test');

const launchOptions = { args: ['--no-sandbox', '--disable-dev-shm-usage'] };

module.exports = defineConfig({
  testDir: './tests/e2e-live',
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  timeout: 120_000,
  reporter: [['list'], ['json', { outputFile: 'var/artifacts/playwright-live.json' }]],
  use: { trace: 'off', screenshot: 'only-on-failure' },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'], launchOptions } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],
});

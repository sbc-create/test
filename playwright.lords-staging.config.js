// Браузерная приёмка трёх публичных стендов Lords.
// Проверяются настоящие пакеты, распакованные и запущенные своим рантаймом, —
// то же, что поедет на сервер, а не рендерер из репозитория.
const { defineConfig, devices } = require('@playwright/test');

const CHROMIUM = process.env.FACTORY_CHROMIUM || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const launchOptions = { executablePath: CHROMIUM };

module.exports = defineConfig({
  testDir: './tests/e2e-lords-staging',
  timeout: 90_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: 'var/artifacts/playwright-lords-staging.json' }]],
  use: { launchOptions },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], launchOptions } }],
  webServer: {
    command: '.venv/bin/python tests/tools/lords_staging_stand.py',
    url: 'http://127.0.0.1:9101/readyz',
    reuseExistingServer: true,
    timeout: 120_000,
  },
});

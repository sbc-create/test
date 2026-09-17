// Браузерная проверка шаблонного контракта: обязательные блоки на трёх ширинах.
// Отдельная конфигурация от playwright.lords.config.js, потому что стенд другой:
// там четыре сайта с пакетами, здесь шаблоны без пакетов вообще.
const { defineConfig, devices } = require('@playwright/test');

const CHROMIUM = process.env.FACTORY_CHROMIUM;
const launchOptions = CHROMIUM ? { executablePath: CHROMIUM } : {};

module.exports = defineConfig({
  testDir: './tests/e2e-templates',
  globalSetup: require.resolve('./tests/e2e-templates/global-setup.js'),
  timeout: 90_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: 'var/artifacts/playwright-templates.json' }]],
  use: { launchOptions },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'], launchOptions } },
  ],
  webServer: {
    command: '.venv/bin/python tests/tools/template_stand.py',
    url: 'http://127.0.0.1:8811/healthz',
    reuseExistingServer: true,
    timeout: 120_000,
  },
});

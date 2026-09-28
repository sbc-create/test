// Браузерная проверка theme pack basis-video на собранном пилоте.
//
// Отдельная конфигурация: стенд направления Lords отдаёт профили, собранные из
// манифестов, а здесь проверяется готовая сборка пакета. Порт другой (8821),
// чтобы прогон не мог молча проверить чужие страницы.
const { defineConfig, devices } = require('@playwright/test');

const CHROMIUM = process.env.FACTORY_CHROMIUM;
const launchOptions = CHROMIUM ? { executablePath: CHROMIUM } : {};

module.exports = defineConfig({
  testDir: './tests/e2e-basis',
  timeout: 90_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: 'var/artifacts/playwright-basis.json' }]],
  use: { launchOptions },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], launchOptions } }],
  webServer: {
    command: '.venv/bin/python tests/tools/basis_stand.py',
    url: 'http://127.0.0.1:8821/healthz',
    reuseExistingServer: true,
    timeout: 120_000,
  },
});

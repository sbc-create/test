// Браузерная приёмка стенда направления Lords.
// Четыре пакета — четыре сайта на четырёх портах: разные профили обязаны
// отличаться в движке, а не только в конфигурации.
const { defineConfig, devices } = require('@playwright/test');

const CHROMIUM = process.env.FACTORY_CHROMIUM || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const launchOptions = { executablePath: CHROMIUM };

module.exports = defineConfig({
  testDir: './tests/e2e-lords',
  timeout: 90_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: 'var/artifacts/playwright-lords.json' }]],
  use: { launchOptions },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'], launchOptions } },
  ],
  webServer: {
    command: '.venv/bin/python tests/tools/lords_stand.py',
    url: 'http://127.0.0.1:8801/healthz',
    reuseExistingServer: true,
    timeout: 60_000,
  },
});

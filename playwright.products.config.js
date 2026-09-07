// Приёмка трёх продуктов в трёх движках.
//
// Стенды предпросмотра поднимаются отдельной командой и слушают только
// петлевой интерфейс. Конфигурация их не поднимает намеренно: сборка витрин
// занимает минуты, и запускать её на каждом прогоне значило бы платить за
// проверку временем сборки.
//
//   .venv/bin/python scripts/product_preview_stand.py
//   npx playwright test --config=playwright.products.config.js
const { defineConfig, devices } = require('@playwright/test');

const launchOptions = { args: ['--no-sandbox', '--disable-dev-shm-usage'] };

module.exports = defineConfig({
  testDir: './tests/e2e-products',
  fullyParallel: true,
  forbidOnly: true,
  retries: 0,
  workers: 4,
  timeout: 120_000,
  reporter: [['list'], ['json', { outputFile: 'var/artifacts/playwright-products.json' }]],
  use: { trace: 'off', screenshot: 'off' },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'], launchOptions } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],
});

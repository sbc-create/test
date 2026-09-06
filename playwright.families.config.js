// Браузерные проверки трёх семейств payload-next-multisite.
//
// Отдельная конфигурация, а не общий набор Lords: у семейств другой стенд —
// статические страницы, отрисованные настоящими компонентами приложения, без
// базы и без сервера. Сервер здесь не нужен и потому не поднимается: страница
// открывается по file://, и это честнее, чем поднимать сервер ради видимости
// сходства с боевым контуром.
const { defineConfig, devices } = require('@playwright/test');

const launchOptions = { args: ['--no-sandbox', '--disable-dev-shm-usage'] };

module.exports = defineConfig({
  testDir: './tests/e2e-families',
  fullyParallel: true,
  forbidOnly: true,
  retries: 0,
  workers: 4,
  reporter: [['list'], ['json', { outputFile: 'var/artifacts/playwright-families.json' }]],
  use: { trace: 'off', screenshot: 'off' },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'], launchOptions } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
  ],
});

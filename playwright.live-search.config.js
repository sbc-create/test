// Поиск на снимке боевого каталога.
//
// Отдельная конфигурация, потому что стенд другой: не фикстура из шестидесяти
// двух записей, а выгрузка витрины, собранной из настоящего снимка в 53 251
// запись. Указатель поиска отдаётся только на каталоге больше двухсот записей,
// и на фикстуре эта ветка не отрисовывается вовсе — проверять её там значило
// бы проверять другой код.
//
// Стенд собирается командой `scripts/build_live_search_stand.py` и живёт в
// `var/`: он выгрузка, а не исходник.
const { defineConfig, devices } = require('@playwright/test');

const launchOptions = { args: ['--no-sandbox', '--disable-dev-shm-usage'] };

module.exports = defineConfig({
  testDir: './tests/e2e-live-search',
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 2,
  timeout: 120_000,
  reporter: [['list'], ['json', { outputFile: 'var/artifacts/playwright-live-search.json' }]],
  use: { baseURL: 'http://127.0.0.1:8811', trace: 'off', screenshot: 'off' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], launchOptions } }],
  webServer: {
    command: '.venv/bin/python -m http.server 8811 --bind 127.0.0.1 --directory var/live-search-stand',
    url: 'http://127.0.0.1:8811/search/',
    reuseExistingServer: true,
    timeout: 60_000,
  },
});

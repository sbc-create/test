// Браузерная приёмка стенда направления Lords.
// Четыре пакета — четыре сайта на четырёх портах: разные профили обязаны
// отличаться в движке, а не только в конфигурации.
const { defineConfig, devices } = require('@playwright/test');

// Путь к браузеру не фиксируется в коде. Ревизия chromium привязана к версии
// @playwright/test и меняется вместе с ней, а захардкоженный путь протухает
// молча: 1.62.1 ждёт ревизию 1234 в chrome-linux64/, прежнее значение
// указывало на 1194 в chrome-linux/ — каталога с таким именем уже нет.
// Playwright сам находит браузер в PLAYWRIGHT_BROWSERS_PATH; FACTORY_CHROMIUM
// остаётся ручным переопределением для нестандартных хостов.
const CHROMIUM = process.env.FACTORY_CHROMIUM;
const launchOptions = CHROMIUM ? { executablePath: CHROMIUM } : {};

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

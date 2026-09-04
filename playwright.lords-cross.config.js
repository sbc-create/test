// Кросс-браузерная приёмка стенда Lords: только критический путь.
//
// Отдельная конфигурация от playwright.lords.config.js по двум причинам.
// Первая — состав: гонять axe, эталон раскладки и замер скорости в трёх
// движках незачем, axe и так проверяет дерево доступности одинаково, а числа
// скорости между движками несравнимы. Вторая — движки: Firefox и WebKit лежат
// в общесистемном каталоге, а не в пользовательском, и путь к ним задаётся
// переменной окружения, которую незачем навязывать основному прогону.
//
// Запуск:
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     npx playwright test --config=playwright.lords-cross.config.js
const { defineConfig, devices } = require('@playwright/test');

// Тот же приём, что и в основной конфигурации: путь к движку не зашивается,
// потому что ревизия меняется вместе с версией @playwright/test и захардкоженный
// путь протухает молча.
const CHROMIUM = process.env.FACTORY_CHROMIUM;
const launchOptions = CHROMIUM ? { executablePath: CHROMIUM } : {};

module.exports = defineConfig({
  testDir: './tests/e2e-lords-cross',
  timeout: 90_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: 'var/artifacts/playwright-lords-cross.json' }]],
  use: { launchOptions },
  projects: [
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],
  webServer: {
    command: '.venv/bin/python tests/tools/lords_stand.py',
    url: 'http://127.0.0.1:8801/healthz',
    reuseExistingServer: true,
    timeout: 60_000,
  },
});

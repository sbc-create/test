// Конфигурация браузерной приёмки.
// В этой среде доступен только Chromium из /opt/pw-browsers, поэтому проекты
// firefox/webkit объявлены, но включаются переменной FACTORY_ALL_BROWSERS=1 —
// «прогон на трёх движках» не заявляется, пока движки фактически не установлены.
const { defineConfig, devices } = require('@playwright/test');

const CHROMIUM = process.env.FACTORY_CHROMIUM || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const BASE_URL = process.env.FACTORY_BASE_URL || 'http://127.0.0.1:8082';
const AUTH = process.env.FACTORY_STAGING_AUTH || '';

// send: 'always' — иначе Playwright отдаёт учётные данные только в ответ на
// 401-вызов. Chromium повторяет запрос сам, Firefox нет: стенд закрыт
// Basic-авторизацией до любой отдачи, поэтому проверка «404 на несуществующей
// странице» получала 401, а переход на главную вис на диалоге авторизации.
// Проверку «staging закрыт» это не ослабляет — её делает test_security_smoke.py
// отдельным запросом без учётных данных.
const credentials = AUTH.includes(':')
  ? { username: AUTH.split(':')[0], password: AUTH.slice(AUTH.indexOf(':') + 1), send: 'always' }
  : undefined;

const projects = [
  {
    name: 'chromium-desktop',
    use: { ...devices['Desktop Chrome'], launchOptions: { executablePath: CHROMIUM }, httpCredentials: credentials },
  },
  {
    name: 'chromium-mobile',
    use: { ...devices['Pixel 5'], launchOptions: { executablePath: CHROMIUM }, httpCredentials: credentials },
  },
];

if (process.env.FACTORY_ALL_BROWSERS === '1') {
  projects.push(
    { name: 'firefox', use: { ...devices['Desktop Firefox'], httpCredentials: credentials } },
    { name: 'webkit', use: { ...devices['Desktop Safari'], httpCredentials: credentials } },
  );
}

module.exports = defineConfig({
  testDir: './tests/e2e',
  timeout: 45_000,
  expect: { timeout: 7_000 },
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  // Отчёт обязателен: шаг «e2e пройден» без артефакта не считается доказанным.
  reporter: [['list'], ['json', { outputFile: 'artifacts/qa/pilot-local/playwright-report.json' }]],
  use: { baseURL: BASE_URL, trace: 'off', screenshot: 'only-on-failure' },
  projects,
});

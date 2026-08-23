// Конфигурация браузерной приёмки.
// По умолчанию прогон идёт на Chromium; firefox и webkit включаются
// переменной FACTORY_ALL_BROWSERS=1. «Прогон на трёх движках» не заявляется
// сам собой: на хосте, где движки не установлены, projects остаются пустыми,
// и шаг помечается SKIPPED, а не выдаётся за пройденный.
const { defineConfig, devices } = require('@playwright/test');

const CHROMIUM = process.env.FACTORY_CHROMIUM || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const BASE_URL = process.env.FACTORY_BASE_URL || 'http://127.0.0.1:8082';
const AUTH = process.env.FACTORY_STAGING_AUTH || '';

// Учётные данные стенда отдаются заголовком, а не механизмом httpCredentials.
// Причина измерена, а не предположена: после ответа 410 Firefox перестаёт
// отправлять Basic-учётные данные этому origin, и все следующие запросы
// получают 401 — проверка честных статусов видела 401 вместо 404, а переход
// на соседнюю страницу вис на диалоге авторизации. Chromium так себя не ведёт,
// поэтому дефект и не проявлялся, пока firefox и webkit не были установлены.
// `httpCredentials.send: 'always'` здесь не помогает: этот параметр действует
// на запросы APIRequestContext, а не на навигацию страницы.
//
// Заголовок уходит только на стенд: baseURL — 127.0.0.1, других origin в этих
// тестах нет. Утверждение «staging закрыт» это не ослабляет — его проверяет
// tests/integration/test_security_smoke.py запросом без учётных данных.
const authHeader = AUTH.includes(':')
  ? { Authorization: `Basic ${Buffer.from(AUTH).toString('base64')}` }
  : undefined;

const projects = [
  {
    name: 'chromium-desktop',
    use: { ...devices['Desktop Chrome'], launchOptions: { executablePath: CHROMIUM } },
  },
  {
    name: 'chromium-mobile',
    use: { ...devices['Pixel 5'], launchOptions: { executablePath: CHROMIUM } },
  },
];

if (process.env.FACTORY_ALL_BROWSERS === '1') {
  projects.push(
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  );
}

module.exports = defineConfig({
  testDir: './tests/e2e',
  timeout: 45_000,
  expect: { timeout: 7_000 },
  fullyParallel: false,
  forbidOnly: true,
  // Повторов нет намеренно: повтор превращает настоящую нестабильность страницы
  // в зелёный статус. Вместо этого ограничивается параллелизм — на прогоне с
  // тремя движками на 4 vCPU замерен load1 до 6.0, и один тест падал по
  // таймауту от нехватки CPU, а не от дефекта: в одиночку он проходит.
  retries: 0,
  workers: process.env.FACTORY_ALL_BROWSERS === '1' ? 2 : undefined,
  // Отчёт обязателен: шаг «e2e пройден» без артефакта не считается доказанным.
  reporter: [['list'], ['json', { outputFile: 'artifacts/qa/pilot-local/playwright-report.json' }]],
  use: { baseURL: BASE_URL, trace: 'off', screenshot: 'only-on-failure',
        extraHTTPHeaders: authHeader },
  projects,
});

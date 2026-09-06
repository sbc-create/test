// Приёмка витрины на живом контуре. Стенда нет намеренно: проверяется
// работающий сайт, а не поднятая для проверки копия.
const { defineConfig, devices } = require('@playwright/test');

const CHROMIUM = process.env.FACTORY_CHROMIUM;
const launchOptions = CHROMIUM ? { executablePath: CHROMIUM } : {};

module.exports = defineConfig({
  testDir: './tests/e2e-release',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  reporter: [['list'], ['json', {
    outputFile: 'artifacts/evidence/release/playwright-live-acceptance.json',
  }]],
  use: { launchOptions },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], launchOptions } }],
});

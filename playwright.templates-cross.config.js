// Кросс-браузерная приёмка шаблонов направления: Firefox и WebKit.
// Отдельно от playwright.templates.config.js по той же причине, что и у Lords:
// состав другой (только критический путь) и движки лежат в общесистемном
// каталоге, путь к которому незачем навязывать основному прогону.
const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/e2e-templates-cross',
  globalSetup: require.resolve('./tests/e2e-templates/global-setup.js'),
  timeout: 90_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  // Отчёт — в отслеживаемые свидетельства, а не в var/: тот каталог в
  // .gitignore, и ворота в свежем клоне честно гасли бы в not_run.
  reporter: [['list'], ['json', {
    outputFile: 'artifacts/evidence/templates/playwright-templates-cross.json',
  }]],
  projects: [
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],
  webServer: {
    command: '.venv/bin/python tests/tools/template_stand.py',
    url: 'http://127.0.0.1:8811/healthz',
    reuseExistingServer: true,
    timeout: 120_000,
  },
});

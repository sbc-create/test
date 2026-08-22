// Браузерная приёмка трёх сайтов blueprint payload-next-multisite.
// Три домена обслуживает одно приложение, поэтому имена резолвятся на локальный
// стенд правилами Chromium: так проверяется настоящий заголовок Host, а не подмена.
const { defineConfig, devices } = require('@playwright/test');

const CHROMIUM = process.env.FACTORY_CHROMIUM || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const PORT = process.env.FACTORY_MULTISITE_PORT || '3000';

const hostRules = ['site-a.localhost', 'site-b.localhost', 'site-c.localhost']
  .map((host) => `MAP ${host} 127.0.0.1`)
  .join(', ');

const launchOptions = {
  executablePath: CHROMIUM,
  args: [`--host-resolver-rules=${hostRules}`],
};

module.exports = defineConfig({
  testDir: './tests/e2e-multisite',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: 'var/artifacts/playwright-multisite.json' }]],
  use: {
    baseURL: `http://site-a.localhost:${PORT}`,
    launchOptions,
  },
  projects: [
    { name: 'chromium-desktop', use: { ...devices['Desktop Chrome'], launchOptions } },
    { name: 'chromium-mobile', use: { ...devices['Pixel 5'], launchOptions } },
  ],
});

module.exports.PORT = PORT;

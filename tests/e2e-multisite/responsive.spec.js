// REQ-RESPONSIVE: ширины из задания, отсутствие горизонтальной прокрутки, снимки как доказательство.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { SITES, url } = require('./helpers');

const WIDTHS = [390, 768, 1024, 1440, 1920];
const SNAPSHOT_WIDTHS = [390, 768, 1440];
const ROUTES = [
  ['home', '/'],
  ['catalog', '/catalog/'],
  ['title', '/catalog/stand-title-1/'],
  ['episode', '/catalog/stand-title-1/season-1/episode-1/'],
  ['news', '/news/'],
];

const OUT = path.join(__dirname, '..', '..', 'var', 'artifacts', 'screenshots');
fs.mkdirSync(OUT, { recursive: true });

test.describe.configure({ mode: 'serial' });

for (const key of Object.keys(SITES)) {
  for (const [name, route] of ROUTES) {
    test(`нет горизонтальной прокрутки: [${key}] ${name}`, async ({ page }) => {
      for (const width of WIDTHS) {
        await page.setViewportSize({ width, height: width < 500 ? 844 : 900 });
        await page.goto(url(key, route));
        const overflow = await page.evaluate(() => ({
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
        }));
        expect(
          overflow.scrollWidth,
          `${key} ${route} @${width}: содержимое шире вьюпорта`,
        ).toBeLessThanOrEqual(overflow.clientWidth + 1);
      }
    });

    // Это сбор доказательств, а не визуальная проверка: baseline нет, сравнения нет.
    test(`сбор снимков экрана (без сравнения с эталоном): [${key}] ${name}`, async ({ page }, testInfo) => {
      if (testInfo.project.name !== 'chromium-desktop') {
        test.skip(true, 'снимки делаются один раз, в desktop-проекте');
      }
      for (const width of SNAPSHOT_WIDTHS) {
        await page.setViewportSize({ width, height: width < 500 ? 844 : 900 });
        await page.goto(url(key, route));
        await page.waitForTimeout(300);
        await page.screenshot({ path: path.join(OUT, `${key}-${name}-${width}.png`), fullPage: false });
      }
      expect(fs.existsSync(path.join(OUT, `${key}-${name}-390.png`))).toBe(true);
    });
  }
}

test('три темы визуально различаются токенами, а не только текстом', async ({ page }) => {
  const observed = {};
  for (const key of Object.keys(SITES)) {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(url(key, '/'));
    observed[key] = await page.evaluate(() => {
      const style = getComputedStyle(document.documentElement);
      const body = getComputedStyle(document.body);
      return {
        theme: document.documentElement.dataset.theme,
        container: style.getPropertyValue('--container').trim(),
        cardMin: style.getPropertyValue('--card-min').trim(),
        radius: style.getPropertyValue('--radius').trim(),
        background: body.backgroundColor,
        fontFamily: body.fontFamily,
        fontSize: body.fontSize,
      };
    });
  }
  const themes = new Set(Object.values(observed).map((v) => v.theme));
  const containers = new Set(Object.values(observed).map((v) => v.container));
  const backgrounds = new Set(Object.values(observed).map((v) => v.background));
  expect(themes.size, JSON.stringify(observed)).toBe(3);
  expect(containers.size, 'ширина контейнера обязана различаться').toBe(3);
  expect(backgrounds.size, 'фон обязан различаться').toBe(3);
});

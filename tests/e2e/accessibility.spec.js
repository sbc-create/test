// REQ-A11Y: клавиатура, focus, контраст, отсутствие горизонтальной прокрутки.
const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

const AXE = fs.readFileSync(path.join(__dirname, '..', '..', 'node_modules', 'axe-core', 'axe.min.js'), 'utf8');
const PAGES = ['/', '/lekcii/', '/lekcii/page/2/', '/praktikum/serial-fikstura/season-1/episode-1/',
               '/praktikum/serial-fikstura/season-1/episode-3/', '/legal/terms/', '/search/'];

test.beforeEach(async ({ context }) => {
  // CSP сайта справедливо запрещает inline-скрипты, поэтому axe внедряется init-скриптом.
  await context.addInitScript({ content: AXE });
});

for (const url of PAGES) {
  test(`axe-core без критических и серьёзных нарушений: ${url}`, async ({ page }) => {
    await page.goto(url);
    const result = await page.evaluate(async () => await window.axe.run(document, { resultTypes: ['violations'] }));
    const serious = result.violations.filter((v) => ['critical', 'serious'].includes(v.impact));
    expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(', ')}`)).toEqual([]);
  });
}

test('первый Tab попадает на skip-link и он получает видимый фокус', async ({ page }) => {
  await page.goto('/');
  await page.keyboard.press('Tab');
  const focused = await page.evaluate(() => {
    const el = document.activeElement;
    const style = getComputedStyle(el);
    return { cls: el.className, outlineWidth: style.outlineWidth, outlineStyle: style.outlineStyle };
  });
  expect(focused.cls).toContain('skip-link');
  expect(focused.outlineStyle).not.toBe('none');
});

test('skip-link переносит фокус к основному содержимому', async ({ page }) => {
  await page.goto('/');
  await page.keyboard.press('Tab');
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/#main$/);
  await expect(page.locator('#main')).toBeVisible();
});

test('навигация полностью доступна с клавиатуры', async ({ page }) => {
  await page.goto('/');
  const links = await page.locator('.primary-nav a').count();
  const reached = new Set();
  for (let i = 0; i < 15; i += 1) {
    await page.keyboard.press('Tab');
    const cls = await page.evaluate(() => document.activeElement.closest('.primary-nav') ? document.activeElement.getAttribute('href') : null);
    if (cls) reached.add(cls);
    if (reached.size >= links) break;
  }
  expect(reached.size).toBe(links);
});

for (const width of [360, 390, 768, 1024, 1440]) {
  test(`нет горизонтальной прокрутки при ширине ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/lekcii/');
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    expect(overflow).toBe(false);
  });
}

test('изображения имеют alt и заданные размеры', async ({ page }) => {
  await page.goto('/lekcii/');
  const problems = await page.evaluate(() => Array.from(document.querySelectorAll('img'))
    .filter((img) => !img.getAttribute('alt') || !img.getAttribute('width') || !img.getAttribute('height'))
    .map((img) => img.getAttribute('src')));
  expect(problems).toEqual([]);
});

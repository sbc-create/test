// REQ-A11Y: критические пользовательские сценарии трёх сайтов без серьёзных нарушений.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { SITES, url } = require('./helpers');

const AXE = fs.readFileSync(path.join(__dirname, '..', '..', 'node_modules', 'axe-core', 'axe.min.js'), 'utf8');

const ROUTES = [
  '/',
  '/catalog/',
  '/catalog/stand-title-1/',
  '/catalog/stand-title-1/season-1/',
  '/catalog/stand-title-1/season-1/episode-1/',
  '/schedule/',
  '/news/',
  '/legal/rights/',
  '/search/?q=%D0%A1%D1%82%D0%B5%D0%BD%D0%B4',
];

test.beforeEach(async ({ context }) => {
  // CSP сайта запрещает inline-скрипты, поэтому axe внедряется init-скриптом.
  await context.addInitScript({ content: AXE });
});

for (const key of Object.keys(SITES)) {
  for (const route of SITES[key].routes) {
    test(`axe-core без критических нарушений: [${key}] ${route}`, async ({ page }) => {
      await page.goto(url(key, route));
      const result = await page.evaluate(async () => window.axe.run(document, { resultTypes: ['violations'] }));
      const serious = result.violations.filter((v) => ['critical', 'serious'].includes(v.impact));
      expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(', ')}`)).toEqual([]);
    });
  }
}

test('первый Tab попадает на ссылку пропуска и она получает видимый фокус', async ({ page }) => {
  await page.goto(url('a', '/'));
  await page.keyboard.press('Tab');
  const focused = await page.evaluate(() => {
    const element = document.activeElement;
    const style = getComputedStyle(element);
    return {
      className: element.className,
      outlineStyle: style.outlineStyle,
      outlineWidth: style.outlineWidth,
      left: element.getBoundingClientRect().left,
    };
  });
  expect(focused.className).toContain('skip-link');
  expect(focused.outlineStyle).not.toBe('none');
  expect(focused.left).toBeGreaterThanOrEqual(0);
});

test('каталог проходится с клавиатуры до карточки материала', async ({ page }) => {
  await page.goto(url('a', '/catalog/'));
  const reachable = await page.evaluate(() => {
    const focusable = [...document.querySelectorAll('a[href], button, input, [tabindex]:not([tabindex="-1"])')];
    return focusable.some((element) => element.getAttribute('href')?.startsWith('/catalog/stand-title-'));
  });
  expect(reachable).toBe(true);
});

test('форма комментария доступна: у полей есть подписи', async ({ page }) => {
  await page.goto(url('a', '/catalog/stand-title-1/'));
  await expect(page.locator('#comments')).toBeVisible();
  const unlabelled = await page.evaluate(() => {
    const fields = [...document.querySelectorAll('#comments input:not([type=hidden]), #comments textarea')];
    return fields.filter((field) => {
      if (field.getAttribute('aria-label')) return false;
      if (field.id && document.querySelector(`label[for="${field.id}"]`)) return false;
      return !field.closest('label');
    }).length;
  });
  expect(unlabelled).toBe(0);
});

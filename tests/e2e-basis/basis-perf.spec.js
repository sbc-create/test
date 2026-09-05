// REQ-BASIS-PERF: сдвиг раскладки и вес документа по типам страниц basis-video.
//
// Та же оговорка, что и у направления: стенд локальный, сети нет, LCP —
// нижняя граница и записывается как наблюдение. Воротами служит CLS: сдвиг
// создаёт сам шаблон, и от сети он не зависит.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..', '..');
const PLAN = JSON.parse(
  fs.readFileSync(path.join(ROOT, 'var', 'artifacts', 'basis-stand.json'), 'utf8'));

const OUT = path.join(ROOT, 'artifacts', 'evidence', 'templates');
const CLS_BUDGET = 0.1;
const WEIGHT_BUDGET_KB = 150;
const measured = {};

const observe = () => {
  window.__cls = 0;
  new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      if (!entry.hadRecentInput) { window.__cls += entry.value; }
    }
  }).observe({ type: 'layout-shift', buffered: true });
  window.__lcp = 0;
  new PerformanceObserver((list) => {
    const last = list.getEntries().pop();
    if (last) { window.__lcp = last.startTime; }
  }).observe({ type: 'largest-contentful-paint', buffered: true });
};

test.afterAll(() => {
  fs.writeFileSync(path.join(OUT, 'basis-perf.json'),
    `${JSON.stringify({
      captured_at_utc: new Date().toISOString(), site: PLAN.site, build: PLAN.build,
      limitation: 'локальный стенд без сети: LCP — нижняя граница, не замер продукта',
      cls_budget: CLS_BUDGET, weight_budget_kb: WEIGHT_BUDGET_KB,
      measurements: measured,
    }, null, 2)}\n`);
});

test('замер сдвига умеет видеть сдвиг', async ({ page }) => {
  // Самопроверка оснастки: нуль без неё не отличим от неработающего
  // наблюдателя. Сдвиг наводится на настоящей странице — на `about:blank`
  // наблюдатель `layout-shift` молчит.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(observe);
  await page.goto(PLAN.pages[0].url, { waitUntil: 'load' });
  const before = await page.evaluate(() => window.__cls);
  await page.evaluate(() => {
    const block = document.createElement('div');
    block.style.height = '400px';
    block.style.background = '#333';
    document.body.prepend(block);
  });
  await page.waitForTimeout(800);
  const after = await page.evaluate(() => window.__cls);
  expect(after, 'наблюдатель сдвига не сработал').toBeGreaterThan(before + CLS_BUDGET);
});

for (const entry of PLAN.pages) {
  test(`${entry.page_type}: раскладка не прыгает, документ не раздут`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(observe);
    const response = await page.goto(entry.url, { waitUntil: 'load' });
    const body = await response.body();
    await page.evaluate(() => document.fonts.ready).catch(() => {});
    await page.waitForTimeout(1200);
    const vitals = await page.evaluate(() => ({ cls: window.__cls, lcp: window.__lcp }));
    const kb = Math.round(body.length / 1024);
    measured[entry.page_type] = { ...vitals, document_kb: kb, url: entry.url };
    expect(vitals.cls, `${entry.page_type}: сдвиг ${vitals.cls.toFixed(3)}`)
      .toBeLessThanOrEqual(CLS_BUDGET);
    expect(kb, `${entry.page_type}: документ ${kb} КБ`).toBeLessThanOrEqual(WEIGHT_BUDGET_KB);
  });
}

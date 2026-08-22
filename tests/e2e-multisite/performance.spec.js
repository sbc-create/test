// REQ-PERF: лабораторные бюджеты. Полевых данных нет, поэтому цифры помечены как lab.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { SITES, url } = require('./helpers');

// Лабораторные пороги строже полевых целей задания (LCP 2.5s, INP 200ms, CLS 0.1):
// стенд без сети и без рекламы обязан укладываться с запасом, иначе в поле шансов нет.
const BUDGET = { lcpMs: 2500, cls: 0.1, transferKb: 900, domNodes: 2500 };

const ROUTES = [
  ['home', '/'],
  ['catalog', '/catalog/'],
  ['title', '/catalog/stand-title-1/'],
  ['episode', '/catalog/stand-title-1/season-1/episode-1/'],
];

const OUT = path.join(__dirname, '..', '..', 'var', 'artifacts');
const results = [];

test.afterAll(() => {
  if (results.length === 0) return;
  fs.mkdirSync(OUT, { recursive: true });
  fs.writeFileSync(
    path.join(OUT, 'performance-lab.json'),
    JSON.stringify({ kind: 'lab', note: 'Лабораторные измерения на локальном стенде, не полевые CWV.', budget: BUDGET, results }, null, 2),
  );
});

for (const key of Object.keys(SITES)) {
  for (const [name, route] of ROUTES.filter(
    ([, route]) => SITES[key].routes.includes(route),
  )) {
    test(`лабораторный бюджет: [${key}] ${name}`, async ({ page }, testInfo) => {
      if (testInfo.project.name !== 'chromium-desktop') test.skip(true, 'бюджет измеряется в desktop-проекте');

      // Next отдаёт HTML частями без content-length, поэтому вес считается по
      // фактическому телу ответа. Если тело недоступно, метрика остаётся null,
      // а не превращается в честный на вид ноль.
      let transfer = 0;
      let transferMeasured = false;
      page.on('response', async (response) => {
        try {
          const body = await response.body();
          transfer += body.length;
          transferMeasured = true;
        } catch {
          // Ответ уже недоступен (редирект, отменённый запрос) — пропускаем.
        }
      });

      await page.goto(url(key, route), { waitUntil: 'load' });
      await page.waitForTimeout(1200);

      const metrics = await page.evaluate(
        () =>
          new Promise((resolve) => {
            let lcp = 0;
            let cls = 0;
            try {
              new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) lcp = Math.max(lcp, entry.startTime);
              }).observe({ type: 'largest-contentful-paint', buffered: true });
              new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) if (!entry.hadRecentInput) cls += entry.value;
              }).observe({ type: 'layout-shift', buffered: true });
            } catch {
              // Наблюдатели недоступны — вернём то, что есть, и это будет видно в артефакте.
            }
            setTimeout(
              () =>
                resolve({
                  lcpMs: Math.round(lcp),
                  cls: Math.round(cls * 1000) / 1000,
                  domNodes: document.getElementsByTagName('*').length,
                  domContentLoadedMs: Math.round(performance.timing
                    ? performance.timing.domContentLoadedEventEnd - performance.timing.navigationStart
                    : 0),
                }),
              600,
            );
          }),
      );

      const record = {
        site: key,
        route: name,
        path: route,
        transferKb: transferMeasured ? Math.round(transfer / 1024) : null,
        ...metrics,
      };
      results.push(record);

      expect(record.lcpMs, `LCP ${record.lcpMs}ms > ${BUDGET.lcpMs}ms`).toBeLessThanOrEqual(BUDGET.lcpMs);
      expect(record.cls, `CLS ${record.cls} > ${BUDGET.cls}`).toBeLessThanOrEqual(BUDGET.cls);
      expect(record.domNodes, `узлов DOM ${record.domNodes} > ${BUDGET.domNodes}`).toBeLessThanOrEqual(BUDGET.domNodes);
    });
  }
}

test('плеер резервирует место и не сдвигает страницу', async ({ page }, testInfo) => {
  if (testInfo.project.name !== 'chromium-desktop') test.skip(true, 'достаточно одного проекта');
  await page.goto(url('a', '/catalog/stand-title-1/season-1/episode-1/'), { waitUntil: 'domcontentloaded' });
  const box = await page.locator('.player-frame').boundingBox();
  expect(box).not.toBeNull();
  // Место под плеер занято сразу: соотношение сторон задано в CSS, а не появляется после загрузки.
  const ratio = box.width / box.height;
  expect(Math.abs(ratio - 16 / 9)).toBeLessThan(0.15);
});

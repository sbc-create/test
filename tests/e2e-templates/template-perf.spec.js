// REQ-TEMPLATE-PERF: сдвиг раскладки и вес документа по всем шаблонам.
//
// Про числа честно: стенд локальный, сеть отсутствует, и LCP здесь — нижняя
// граница, а не обещание боевой скорости. Выдавать её за замер продукта
// нельзя. Зато CLS от сети не зависит вовсе: сдвиг раскладки создаёт сам
// шаблон — картинкой без размеров, шрифтом без резерва, блоком, который
// появляется после первого кадра. Это и проверяется как ворота; LCP пишется
// в свидетельство как наблюдение.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..', '..');
const PLAN = JSON.parse(
  fs.readFileSync(path.join(ROOT, 'var', 'artifacts', 'template-stand.json'), 'utf8'));

const OUT = path.join(ROOT, 'artifacts', 'evidence', 'templates');
const CLS_BUDGET = 0.1;      // «хорошо» по Core Web Vitals
const WEIGHT_BUDGET_KB = 150;

const measured = {};

test.afterAll(() => {
  fs.writeFileSync(path.join(OUT, 'templates-perf.json'),
    `${JSON.stringify({
      captured_at_utc: new Date().toISOString(),
      limitation: 'локальный стенд без сети: LCP — нижняя граница, не замер продукта',
      cls_budget: CLS_BUDGET, weight_budget_kb: WEIGHT_BUDGET_KB,
      measurements: measured,
    }, null, 2)}\n`);
});

test('замер сдвига умеет видеть сдвиг', async ({ page }) => {
  // Самопроверка оснастки. CLS 0.000 одинаково выглядит и у страницы, которая
  // не прыгает, и у наблюдателя, который не подключился.
  //
  // Сдвиг наводится на настоящей странице стенда, а не на `setContent`:
  // тот открывает `about:blank`, а наблюдатель `layout-shift` на нём не
  // сообщает ничего — первая редакция этой самопроверки именно так и
  // «доказала» работу наблюдателя, который молчал.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => {
    window.__cls = 0;
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (!entry.hadRecentInput) { window.__cls += entry.value; }
      }
    }).observe({ type: 'layout-shift', buffered: true });
  });
  await page.goto(PLAN.templates[0].url, { waitUntil: 'load' });
  const before = await page.evaluate(() => window.__cls);
  // Высокий блок в начало документа: всё, что ниже, уезжает вниз — ровно тот
  // сдвиг, который ворота обязаны ловить.
  await page.evaluate(() => {
    const block = document.createElement('div');
    block.style.height = '400px';
    block.style.background = '#333';
    document.body.prepend(block);
  });
  // Ждём само событие, а не фиксированный срок. Обратный вызов наблюдателя
  // приходит асинхронно, и в загруженном прогоне 800 мс не хватало: проверка
  // падала на исправной оснастке. Ожидание по условию снимает эту зависимость
  // от загруженности машины и при этом не прощает неработающий наблюдатель —
  // тогда оно истекает по таймауту и проверка падает.
  await page.waitForFunction(() => window.__cls > 0, null, { timeout: 10_000 });
  const after = await page.evaluate(() => window.__cls);
  expect(after, 'наблюдатель сдвига не сработал — нули остальных проверок ничего не значат')
    .toBeGreaterThan(before + CLS_BUDGET);
});

for (const entry of PLAN.templates) {
  test(`${entry.profile}: раскладка не прыгает, документ не раздут`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(() => {
      window.__cls = 0;
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          // Сдвиги, вызванные действием пользователя, в CLS не входят.
          if (!entry.hadRecentInput) { window.__cls += entry.value; }
        }
      }).observe({ type: 'layout-shift', buffered: true });
      window.__lcp = 0;
      new PerformanceObserver((list) => {
        const last = list.getEntries().pop();
        if (last) { window.__lcp = last.startTime; }
      }).observe({ type: 'largest-contentful-paint', buffered: true });
    });
    const response = await page.goto(entry.url, { waitUntil: 'load' });
    const body = await response.body();
    await page.evaluate(() => document.fonts.ready).catch(() => {});
    await page.waitForLoadState('networkidle').catch(() => {});
    // Сдвиг случается после первого кадра: изображение без размеров и шрифт
    // без резерва двигают раскладку тогда, когда загрузка уже считается
    // завершённой. Замер сразу после load показал бы ноль на любой странице.
    await page.waitForTimeout(1200);
    const vitals = await page.evaluate(() => ({ cls: window.__cls, lcp: window.__lcp }));
    const kb = Math.round(body.length / 1024);
    measured[entry.profile] = { ...vitals, document_kb: kb, url: entry.url };

    expect(vitals.cls, `${entry.profile}: сдвиг раскладки ${vitals.cls.toFixed(3)}`)
      .toBeLessThanOrEqual(CLS_BUDGET);
    expect(kb, `${entry.profile}: документ ${kb} КБ`).toBeLessThanOrEqual(WEIGHT_BUDGET_KB);
  });
}

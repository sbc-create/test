// REQ-LORDS-PERFORMANCE: скорость и устойчивость раскладки измеряются, а не оцениваются.
//
// Критерий скорости в рубрике шаблона считает вес документа и число запросов —
// это дёшево и ловит грубое, но временем отрисовки не является. Здесь берутся
// две метрики, которые видит зритель: LCP (когда появилось главное) и CLS
// (насколько содержимое прыгало под курсором).
//
// Числа снимаются на локальном стенде, и это существенное ограничение: сети тут
// нет, поэтому LCP здесь — нижняя граница, а не обещание боевого значения. Для
// CLS ограничение слабее: смещения задаёт вёрстка, а не канал, и стенд ловит
// именно её. Поэтому бюджет CLS строгий, а бюджет LCP — заведомо щедрый и
// работает как сторож против обвала, а не как замер производительности.
//
// Измерения сохраняются в artifacts/templates/performance.json как
// свидетельство прогона: отчёт обязан ссылаться на числа, а не на впечатление.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { SITES, url, VIEWPORTS } = require('./helpers');

const OUT = path.join(__dirname, '..', '..', 'artifacts', 'templates');

// Бюджет смещения — тот же, что у Core Web Vitals: 0.1. Он не выдуман под
// текущий результат, иначе сторож охранял бы то, что уже есть.
const CLS_BUDGET = 0.1;

// Заведомо щедрый потолок: на локальном стенде всё, что медленнее секунды,
// означает не «медленную сеть», а поломку разметки или скрипта.
const LCP_BUDGET_MS = 1000;

const ROUTES = [['home', '/'], ['catalog', '/catalog/']];
const MEASURED = VIEWPORTS.filter((v) => v.width === 1440 || v.width === 390);

const collected = {};

// Метрики снимаются штатным PerformanceObserver, а не самодельным таймером:
// LCP и CLS определены браузером, и своё определение здесь было бы другой
// величиной под тем же именем.
const collect = () => new Promise((resolve) => {
  let lcp = 0;
  let cls = 0;
  new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) { lcp = Math.max(lcp, entry.startTime); }
  }).observe({ type: 'largest-contentful-paint', buffered: true });
  new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      // Смещения, вызванные действием пользователя, в CLS не входят по
      // определению метрики.
      if (!entry.hadRecentInput) { cls += entry.value; }
    }
  }).observe({ type: 'layout-shift', buffered: true });

  // Полсекунды тишины после загрузки: сдвиг от позднего шрифта или картинки
  // случается уже после `load`, и замер сразу по нему их не увидел бы.
  setTimeout(() => resolve({ lcp: Math.round(lcp), cls: Math.round(cls * 10000) / 10000 }), 500);
});

test.describe('скорость и устойчивость раскладки', () => {
  for (const id of Object.keys(SITES)) {
    for (const view of MEASURED) {
      for (const [routeName, route] of ROUTES) {
        const key = `${id}/${routeName}/${view.width}`;
        test(`${key}`, async ({ page }) => {
          await page.setViewportSize({ width: view.width, height: view.height });
          await page.goto(url(id, route), { waitUntil: 'load' });
          const metrics = await page.evaluate(collect);
          collected[key] = metrics;

          expect(metrics.cls, `${key}: смещение раскладки ${metrics.cls}`)
            .toBeLessThanOrEqual(CLS_BUDGET);
          expect(metrics.lcp, `${key}: LCP ${metrics.lcp} мс`)
            .toBeLessThanOrEqual(LCP_BUDGET_MS);
        });
      }
    }
  }

  test.afterAll(() => {
    fs.mkdirSync(OUT, { recursive: true });
    fs.writeFileSync(path.join(OUT, 'performance.json'), `${JSON.stringify({
      note: 'Замер на локальном стенде. LCP — нижняя граница, сети нет. CLS отражает вёрстку.',
      cls_budget: CLS_BUDGET,
      lcp_budget_ms: LCP_BUDGET_MS,
      measurements: Object.fromEntries(Object.entries(collected).sort()),
    }, null, 2)}\n`);
  });
});

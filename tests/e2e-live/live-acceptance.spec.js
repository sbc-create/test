// Приёмка продуктов на действующих сайтах.
//
// Порядок приёмки задан владельцем прямо: локальные сборки и витрины на
// выдуманных данных приёмкой продукта не являются. Поэтому набор работает
// только по адресам из `config/live-acceptance.json`, а пустой адрес — не
// провал: продукт помечается BLOCKED_OWNER_URLS, то есть ожиданием входа.
//
// Три свойства этого набора важнее его проверок.
//
// Только чтение. Каждый изменяющий запрос обрывается на уровне браузера, а не
// «не пишется по договорённости»: страница может отправить что угодно, и
// доверять её содержимому нельзя. Обрыв — это гарантия, которую видно.
//
// Отказ доступа не считается дефектом продукта. 401, 403 и 429 означают
// защиту провайдера или ограничение частоты; прогон останавливается и
// записывает причину, а витрина не объявляется сломанной.
//
// Нагрузки не создаётся. Один рабочий процесс и обход без повторов: приёмка
// идёт по действующему сайту с настоящими посетителями.

const { test, expect } = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');

const h = require('./harness');

// axe вставляется файлом, а не подтягивается с проверяемого сайта: приёмка не
// вправе ни запрашивать что-либо у боевого хоста сверх самих страниц, ни
// зависеть от его доступности для собственной оснастки.
const AXE = createRequire(__filename).resolve('axe-core/axe.min.js');
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

const CONFIG = path.join(__dirname, '..', '..', 'config', 'live-acceptance.json');
const EVIDENCE = path.join(__dirname, '..', '..', 'artifacts', 'evidence', 'products',
                           'live-acceptance.json');

const WIDTHS = h.ШИРИНЫ;

const products = h.loadConfig(CONFIG);

for (const [product, config] of Object.entries(products)) {
  test.describe(product, () => {
    const base = config.base_url;

    test.skip(!base,
      `${product}: BLOCKED_OWNER_URLS — адрес действующей витрины не передан. ` +
      'Ожидание входа owner.live_urls, а не провал продукта (docs/INPUT_REQUEST.md).');

    for (const route of config.routes) {
      for (const width of WIDTHS) {
        test(`${route} на ${width}`, async ({ page }, testInfo) => {
          const attempts = [];
          await h.readOnly(page, attempts);
          await page.setViewportSize({ width, height: 900 });

          const errors = [];
          page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });

          const url = new URL(route, base).toString();
          const response = await page.goto(url, { waitUntil: 'domcontentloaded' });
          const status = response ? response.status() : 0;

          if (h.classify(status) === 'BLOCKED_ACCESS') {
            h.record(EVIDENCE, product, `${route}@${width}`,
                   { status, verdict: 'BLOCKED_ACCESS', note: 'защита провайдера или ограничение частоты' });
            test.skip(true, `${product}${route}: ответ ${status} — доступ закрыт, ` +
                            'это не дефект витрины; прогон остановлен');
          }

          expect(status, `${url} ответил ${status}`).toBe(200);

          // Горизонтальной прокрутки нет ни на одной ширине.
          const overflow = await h.overflowPx(page);
          expect(overflow, 'горизонтальная прокрутка').toBeLessThanOrEqual(0);

          await page.addScriptTag({ path: AXE });
          const axe = await page.evaluate(
            async (tags) => window.axe.run(document, { runOnly: { type: 'tag', values: tags } }),
            TAGS);

          h.record(EVIDENCE, product, `${route}@${width}`, {
            status,
            engine: testInfo.project.name,
            overflowPx: overflow,
            axeViolations: axe.violations.map((v) => ({ id: v.id, impact: v.impact,
                                                        nodes: v.nodes.length })),
            consoleErrors: errors.length,
            mutatingRequestsBlocked: attempts.length,
          });

          expect(axe.violations, 'нарушения WCAG 2.2 AA').toEqual([]);
          expect(errors, 'ошибки консоли').toEqual([]);
          // Набор обязан быть безвредным для действующего сайта.
          expect(attempts, 'изменяющие запросы обрываются, а не отправляются').toEqual([]);
        });
      }
    }
  });
}

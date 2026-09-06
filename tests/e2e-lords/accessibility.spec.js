// REQ-LORDS-A11Y: доступность проверяется прогоном axe, а не чтением разметки.
//
// До этого доступность в рубрике шаблона проверялась по разметке — ориентиры,
// имена полей, управляемое меню. Это ловит грубое и не ловит контраст,
// дублирующиеся ориентиры, порядок заголовков и полсотни других правил. Отчёт
// честно называл это ограничением: критерий стоял со статусом «по разметке», а
// не «axe пройден».
//
// Здесь запускается настоящий axe-core 4.13.0 с наборами правил WCAG 2.0/2.1/2.2
// уровней A и AA. Результат каждого прогона сохраняется целиком — и нарушения, и
// пройденные правила, — с адресом, шириной и временем в UTC: отчёт обязан
// ссылаться на файл, а не на память.
//
// Прогон:
//   npx playwright test --config=playwright.lords.config.js accessibility
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { SITES, url } = require('./helpers');

const AXE = require.resolve('axe-core/axe.min.js');
// Свидетельства кладутся в отслеживаемый git'ом набор: `artifacts/*`
// закрыт целиком, и отчёт, ссылающийся на файл вне репозитория,
// ссылается в пустоту для всякого, кто получит только клон.
const OUT = path.join(__dirname, '..', '..', 'artifacts', 'evidence', 'templates', 'a11y');

// WCAG 2.2 AA включает в себя 2.1 и 2.0 того же уровня: критерии предыдущих
// версий не отменяются новой, а наследуются. Поэтому наборы перечислены все —
// один тег `wcag22aa` покрыл бы только новые критерии 2.2.
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

const VIEWPORTS = [
  { name: 'mobile', width: 390, height: 844 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1440, height: 900 },
];

// Ключевые состояния, включая те, о которых обычно забывают: пустой результат и
// ненайденный адрес. Страница отказа — такая же страница продукта: на ней тоже
// есть шапка, меню и фокус, и сломанной она бывает чаще прочих, потому что её
// реже открывают глазами.
const PAGES = [
  { name: 'home', route: '/' },
  { name: 'catalog', route: '/catalog/' },
  { name: 'search', route: '/search/' },
  { name: 'search-empty', route: '/search/?q=zzzzzzzzzz' },
  { name: 'not-found', route: '/nonexistent-address/' },
];

fs.mkdirSync(OUT, { recursive: true });

/** Первый адрес произведения — берётся из каталога, а не зашивается в тест. */
async function firstTitleRoute(page, id) {
  await page.goto(url(id, '/movies/'));
  const href = await page.locator('.card__title').first().getAttribute('href');
  return href;
}

async function runAxe(page, { site, pageName, viewport, route }) {
  await page.addScriptTag({ path: AXE });
  const result = await page.evaluate(async (tags) => {
    // eslint-disable-next-line no-undef
    return axe.run(document, {
      runOnly: { type: 'tag', values: tags },
    });
  }, TAGS);

  const record = {
    site,
    page: pageName,
    route,
    url: page.url(),
    viewport,
    // Время в UTC и в ISO: отчёт сверяется между машинами, а локальное время
    // сверять нечем.
    captured_at_utc: new Date().toISOString(),
    axe_version: result.testEngine && result.testEngine.version,
    tags: TAGS,
    // Счётчики покрытия сохраняются вместе с нарушениями. Ноль нарушений сам по
    // себе ничего не доказывает: так же выглядит прогон, в котором не
    // выполнилось ни одного правила. Число пройденных правил отличает одно от
    // другого прямо в файле свидетельства.
    rules_passed: result.passes.length,
    rules_inapplicable: result.inapplicable.length,
    violations: result.violations.map((v) => ({
      id: v.id,
      impact: v.impact,
      help: v.help,
      helpUrl: v.helpUrl,
      tags: v.tags,
      nodes: v.nodes.map((n) => ({
        target: n.target,
        html: n.html,
        failureSummary: n.failureSummary,
      })),
    })),
    // «Неполные» — правила, которые axe не смог решить сам. Они не нарушения и
    // не успех; прятать их значило бы округлять отчёт в свою пользу.
    incomplete: result.incomplete.map((v) => ({ id: v.id, nodes: v.nodes.length })),
  };

  const file = path.join(OUT, `axe-${site}-${pageName}-${viewport.width}.json`);
  fs.writeFileSync(file, `${JSON.stringify(record, null, 2)}\n`);
  return record;
}

function describeViolations(record) {
  return record.violations
    .map((v) => `${v.id} (${v.impact}, ${v.nodes.length} узл.): ${v.help}\n    ${
      v.nodes.map((n) => n.target.join(' ')).join('\n    ')}`)
    .join('\n  ');
}

// Самопроверка инструмента. Ноль нарушений — утверждение о странице только
// тогда, когда доказано, что инструмент вообще способен вернуть нарушение.
// Одинаково выглядит и чистая страница, и axe, который молча не выполнился.
//
// Проверка временно подсаживает два заведомых дефекта, убеждается, что axe их
// назвал, и снимает их обратно. Она живёт в наборе постоянно, а не разово в
// чужом черновике: инструмент ломается тихо и именно тогда, когда его давно
// никто не оспаривал.
test('axe способен вернуть нарушение — самопроверка инструмента', async ({ page }) => {
  await page.goto(url('lords-01', '/'));
  await page.addScriptTag({ path: AXE });

  const clean = await page.evaluate(async (tags) => axe.run(document, {
    runOnly: { type: 'tag', values: tags } }), TAGS);
  expect(clean.violations, 'страница-основание должна быть чистой').toEqual([]);
  expect(clean.passes.length, 'axe не выполнил ни одного правила').toBeGreaterThan(10);

  await page.evaluate(() => {
    const img = document.createElement('img');
    img.id = 'axe-selfcheck-img';
    img.src = '/assets/posters/selfcheck.svg';
    const button = document.createElement('button');
    button.id = 'axe-selfcheck-button';
    document.querySelector('main').append(img, button);
  });

  const dirty = await page.evaluate(async (tags) => axe.run(document, {
    runOnly: { type: 'tag', values: tags } }), TAGS);
  const found = dirty.violations.map((v) => v.id);
  expect(found, 'axe не заметил картинку без alt').toContain('image-alt');
  expect(found, 'axe не заметил кнопку без имени').toContain('button-name');

  // Подсадка снимается: следующий тест обязан видеть страницу, а не следы этого.
  await page.evaluate(() => {
    document.getElementById('axe-selfcheck-img')?.remove();
    document.getElementById('axe-selfcheck-button')?.remove();
  });
  const restored = await page.evaluate(async (tags) => axe.run(document, {
    runOnly: { type: 'tag', values: tags } }), TAGS);
  expect(restored.violations, 'подсадка не снята').toEqual([]);
});

test.describe('axe WCAG 2.2 AA', () => {
  for (const site of Object.keys(SITES)) {
    for (const viewport of VIEWPORTS) {
      for (const target of PAGES) {
        test(`${site}/${target.name}/${viewport.width}`, async ({ page }) => {
          await page.setViewportSize({ width: viewport.width, height: viewport.height });
          await page.goto(url(site, target.route));
          const record = await runAxe(page, {
            site, pageName: target.name, viewport, route: target.route,
          });
          expect(
            record.violations,
            `${site}/${target.name}/${viewport.width}:\n  ${describeViolations(record)}`,
          ).toEqual([]);
        });
      }

      test(`${site}/title/${viewport.width}`, async ({ page }) => {
        await page.setViewportSize({ width: viewport.width, height: viewport.height });
        const route = await firstTitleRoute(page, site);
        await page.goto(url(site, route));
        const record = await runAxe(page, {
          site, pageName: 'title', viewport, route,
        });
        expect(
          record.violations,
          `${site}/title/${viewport.width}:\n  ${describeViolations(record)}`,
        ).toEqual([]);
      });
    }
  }
});

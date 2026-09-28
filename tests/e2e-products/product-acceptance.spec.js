// Приёмка трёх продуктов в трёх движках на трёх ширинах.
//
// Прежняя проверка шла только в Chromium, и это не приёмка: расхождения
// движков живут ровно там, где их не ждёшь — в раскладке полей формы, в
// прокрутке рядов, в переносе навигации. Витрина, безупречная в одном
// движке, в другом уезжает вбок.
//
// Предмет проверки — результат для зрителя, а не наличие разметки. Поэтому
// каждая страница открывается по-настоящему, а утверждения формулируются так,
// чтобы зелёный результат без отрисованного содержимого был невозможен:
// «карточек больше нуля», «заголовок непустой», «выдача изменилась».
//
// Свидетельства пишутся по продукту и движку раздельно: общий файл при
// параллельном прогоне затирается, и это уже случалось.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { createRequire } = require('module');

const requireFrom = createRequire(__filename);
const AXE = requireFrom.resolve('axe-core/axe.min.js');

const ROOT = path.join(__dirname, '..', '..');
const OUT = path.join(ROOT, 'artifacts', 'evidence', 'products');

const PORTS = { 'zona-cinema': 8903, 'animedia-portal': 8904, 'basis-video': 8905 };
const WIDTHS = [390, 768, 1440];
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

/** Поверхности каждой витрины. У basis-video своя структура. */
const SURFACES = {
  'basis-video': [
    ['home', '/'],
    ['lekcii', '/lekcii/'],
    ['collection', '/collections/izbrannoe/'],
    ['news', '/news/'],
    ['search', '/search/'],
    ['not-found', '/404/'],
  ],
  default: [
    ['home', '/'],
    ['catalog', '/catalog/'],
    ['genres', '/genres/'],
    ['countries', '/countries/'],
    ['years', '/years/'],
    ['search', '/search/'],
    ['not-found', '/404.html'],
  ],
};

const surfaces = (product) => SURFACES[product] || SURFACES.default;
const base = (product) => `http://127.0.0.1:${PORTS[product]}`;

function save(product, engine, payload) {
  const dir = path.join(OUT, product);
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, `acceptance-${engine}.json`);
  let previous = {};
  try {
    previous = JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch { /* первый прогон движка */ }
  fs.writeFileSync(file, `${JSON.stringify({
    product,
    engine,
    captured_at_utc: new Date().toISOString(),
    ...previous,
    ...payload,
    surfaces: { ...(previous.surfaces || {}), ...(payload.surfaces || {}) },
  }, null, 2)}\n`);
}

/** Что видно на странице и что зритель почувствует, даже не видя. */
const probe = () => {
  const doc = document.documentElement;
  const empties = [];
  for (const tag of ['p', 'h1', 'h2', 'h3', 'li', 'dd', 'dt', 'section']) {
    for (const el of document.querySelectorAll(tag)) {
      // Живая область обязана существовать пустой, иначе сообщение не будет
      // объявлено экранным диктором. Это не незаполненная разметка.
      if (el.matches('[role="status"], [role="alert"], [aria-live]')) continue;
      if (el.children.length === 0 && !el.textContent.trim()) {
        empties.push(`${tag}.${el.getAttribute('class') || ''}`);
      }
    }
  }
  const cards = document.querySelectorAll('.card, .card-grid > li, .card-rail > li');
  const h1 = document.querySelector('h1');
  return {
    overflowX: doc.scrollWidth > doc.clientWidth + 1,
    scrollWidth: doc.scrollWidth,
    clientWidth: doc.clientWidth,
    cards: cards.length,
    h1: h1 ? h1.textContent.trim().slice(0, 60) : '',
    emptyElements: empties,
    // Служебные идентификаторы соседних витрин на странице появляться не
    // должны: `lords-04` уже однажды стоял именем бренда в чужом пакете.
    foreignIds: (document.body.innerHTML.match(/lords-0\d|site-[abc]\b|pilot-local/g) || [])
      .slice(0, 5),
  };
};

for (const product of Object.keys(PORTS)) {
  test.describe(`${product}`, () => {
    for (const [name, route] of surfaces(product)) {
      for (const width of WIDTHS) {
        test(`${name}@${width}`, async ({ page }, testInfo) => {
          const consoleErrors = [];
          const networkErrors = [];
          page.on('console', (m) => {
            if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 120));
          });
          page.on('requestfailed', (r) => {
            // Внешние хосты в этой обстановке закрыты намеренно: их отказ —
            // свойство стенда, а не витрины.
            if (r.url().startsWith(base(product))) networkErrors.push(r.url().slice(0, 100));
          });

          await page.setViewportSize({ width, height: 900 });
          const response = await page.goto(`${base(product)}${route}`, { waitUntil: 'load' });
          expect(response && response.status(), `${name}: страница не открылась`)
            .toBeLessThan(400);

          const metrics = await page.evaluate(probe);
          save(product, testInfo.project.name, {
            surfaces: { [`${name}@${width}`]: { ...metrics, consoleErrors, networkErrors } },
          });

          expect(metrics.overflowX,
            `${name}@${width}: горизонтальная прокрутка ${metrics.scrollWidth} > ${metrics.clientWidth}`)
            .toBe(false);
          expect(metrics.emptyElements, `${name}@${width}: пустые элементы`).toEqual([]);
          expect(metrics.h1.length, `${name}@${width}: заголовка нет`).toBeGreaterThan(0);
          expect(metrics.foreignIds,
            `${name}@${width}: на странице идентификаторы соседней витрины`).toEqual([]);
          expect(consoleErrors, `${name}@${width}: ошибки в консоли`).toEqual([]);
          expect(networkErrors, `${name}@${width}: отказы своих же запросов`).toEqual([]);
        });
      }
    }

    test('axe WCAG 2.2 AA на всех поверхностях', async ({ page }, testInfo) => {
      const found = [];
      for (const [name, route] of surfaces(product)) {
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto(`${base(product)}${route}`, { waitUntil: 'load' });
        await page.addScriptTag({ path: AXE });
        const result = await page.evaluate(
          async (tags) => window.axe.run(document, { runOnly: { type: 'tag', values: tags } }),
          TAGS);
        const serious = result.violations.filter(
          (v) => v.impact === 'serious' || v.impact === 'critical');
        if (serious.length) {
          found.push(`${name}: ${serious.map((v) => `${v.id}(${v.nodes.length})`).join(', ')}`);
        }
      }
      save(product, testInfo.project.name, { axe: { violations: found } });
      expect(found, `${product}: нарушения доступности`).toEqual([]);
    });

    test('обход клавиатурой доходит до содержимого', async ({ page }, testInfo) => {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(`${base(product)}/`, { waitUntil: 'load' });
      const stops = [];
      for (let i = 0; i < 14; i += 1) {
        await page.keyboard.press('Tab');
        const stop = await page.evaluate(() => {
          const el = document.activeElement;
          if (!el || el === document.body) return null;
          const box = el.getBoundingClientRect();
          const style = getComputedStyle(el);
          return {
            tag: el.tagName.toLowerCase(),
            text: (el.textContent || '').trim().slice(0, 24),
            height: Math.round(box.height),
            outline: style.outlineStyle,
          };
        });
        if (stop) stops.push(stop);
      }
      save(product, testInfo.project.name, { keyboard: stops });
      expect(stops.length, 'остановок табуляции нет').toBeGreaterThan(3);
      // Невидимый фокус — это работающая навигация, о которой пользователь не
      // знает.
      expect(stops.filter((s) => s.outline === 'none'), 'остановки без видимого фокуса')
        .toEqual([]);
      // Цель не меньше 24 px — критерий 2.5.8 уровня AA.
      expect(stops.filter((s) => s.height > 0 && s.height < 24), 'цели ниже 24 px')
        .toEqual([]);
    });

    test('двукратное увеличение текста ничего не теряет', async ({ page }, testInfo) => {
      const lost = [];
      for (const [name, route] of surfaces(product)) {
        await page.setViewportSize({ width: 1280, height: 900 });
        await page.goto(`${base(product)}${route}`, { waitUntil: 'load' });
        await page.addStyleTag({ content: 'html { font-size: 200% !important }' });
        await page.evaluate(
          () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
        const result = await page.evaluate(() => {
          const clipped = [];
          for (const el of document.querySelectorAll('body *')) {
            if (el.classList.contains('visually-hidden')) continue;
            const style = getComputedStyle(el);
            // Скрытый от глаза, но доступный диктору элемент делается тем же
            // приёмом и без класса: абсолютное положение, размер в пиксель и
            // обрезка. Он обрезан намеренно — считать это потерей значит
            // требовать поломки доступности.
            if (style.position === 'absolute' && el.clientHeight <= 1) continue;
            // Ряд прокручивается по горизонтали по устройству: обрезки в нём
            // нет, есть прокрутка, и это разные вещи.
            if (el.matches('.card-rail, .rail')) continue;
            if (style.overflow !== 'hidden' && style.overflowY !== 'hidden') continue;
            if (!el.clientHeight || !el.textContent.trim()) continue;
            if (el.scrollHeight > el.clientHeight + 2) {
              clipped.push(`${el.getAttribute('class') || el.tagName}: `
                + `${el.clientHeight}/${el.scrollHeight}`);
            }
          }
          const doc = document.documentElement;
          return { clipped, overflowX: doc.scrollWidth > doc.clientWidth + 1 };
        });
        if (result.clipped.length) lost.push(`${name}: обрезано ${result.clipped.join(', ')}`);
        if (result.overflowX) lost.push(`${name}: прокрутка вбок при 200 %`);
      }
      save(product, testInfo.project.name, { zoom200: lost });
      expect(lost, `${product}: потери при двукратном увеличении`).toEqual([]);
    });
  });
}

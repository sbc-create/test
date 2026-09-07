// Поверхности витрины на боевых данных.
//
// Тот же набор требований, что и на фикстурном стенде, но на настоящем
// каталоге. Разница не формальная. Фикстура ровная: у каждой записи есть год,
// жанр, длительность и постер. Боевой каталог рваный — у 2 746 записей нет
// года, у 86 % нет описания, у 78 % нет жанров, у половины нет ни одной
// оценки. Разметка, безупречная на ровных данных, на рваных показывает пустые
// подписи, обрезанные строки и подписи без значений.
//
// Проверяется поэтому именно то, что ломается от пустоты: доступность,
// отсутствие горизонтальной прокрутки, отсутствие пустых текстовых элементов и
// подписей без значений.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { createRequire } = require('module');

const requireFrom = createRequire(__filename);
const AXE = requireFrom.resolve('axe-core/axe.min.js');

const BASE = process.env.LIVE_SEARCH_URL || 'http://127.0.0.1:8811';
const OUT = path.join(__dirname, '..', '..', 'artifacts', 'evidence', 'templates');
fs.mkdirSync(OUT, { recursive: true });

const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const WIDTHS = [390, 768, 1440];

const ROUTES = [
  ['home', '/'],
  ['catalog', '/catalog/'],
  ['catalog-page-2', '/catalog/page/2/'],
  ['genres', '/genres/'],
  ['years', '/years/'],
  ['countries', '/countries/'],
  ['search', '/search/'],
  ['not-found', '/404.html'],
];

const collected = { captured_at_utc: null, pages: [] };

function save() {
  const file = path.join(OUT, 'live-surfaces.json');
  let previous = { pages: [] };
  try {
    previous = JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch { /* первый работник */ }
  fs.writeFileSync(file, `${JSON.stringify({
    captured_at_utc: new Date().toISOString(),
    base: BASE,
    source: 'снимок боевого каталога, 53 251 запись',
    pages: [...(previous.pages || []), ...collected.pages].filter(
      (entry, index, all) => all.findIndex((other) => other.key === entry.key) === index,
    ),
  }, null, 2)}\n`);
}

/** Первая страница произведения из выборки — её адрес берётся из каталога. */
async function firstTitlePath(page) {
  await page.goto(`${BASE}/catalog/`, { waitUntil: 'load' });
  const href = await page.locator('.card__title').first().getAttribute('href');
  return href;
}

const probe = () => {
  const empties = [];
  const текстовые = ['p', 'h1', 'h2', 'h3', 'li', 'dd', 'dt', 'figcaption'];
  for (const tag of текстовые) {
    for (const el of document.querySelectorAll(tag)) {
      if (el.children.length === 0 && !el.textContent.trim()) {
        empties.push(`${tag}.${el.getAttribute('class') || ''}`);
      }
    }
  }
  // Подпись без значения: `dt` без непустого `dd` следом.
  const dangling = [];
  for (const dt of document.querySelectorAll('dt')) {
    const dd = dt.nextElementSibling;
    if (!dd || dd.tagName.toLowerCase() !== 'dd' || !dd.textContent.trim()) {
      dangling.push(dt.textContent.trim());
    }
  }
  const doc = document.documentElement;
  return {
    empties,
    dangling,
    overflowX: doc.scrollWidth > doc.clientWidth + 1,
    scrollWidth: doc.scrollWidth,
    clientWidth: doc.clientWidth,
    cards: document.querySelectorAll('.card').length,
  };
};

test.describe('боевые данные не ломают разметку', () => {
  for (const [name, route] of ROUTES) {
    for (const width of WIDTHS) {
      test(`${name}@${width}`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto(`${BASE}${route}`, { waitUntil: 'load' });
        const result = await page.evaluate(probe);
        collected.pages.push({ key: `${name}@${width}`, route, width, ...result });
        save();
        expect(result.empties, `${name}@${width}: пустые текстовые элементы`).toEqual([]);
        expect(result.dangling, `${name}@${width}: подписи без значений`).toEqual([]);
        expect(result.overflowX,
          `${name}@${width}: горизонтальная прокрутка ${result.scrollWidth} > ${result.clientWidth}`)
          .toBe(false);
      });
    }
  }
});

test.describe('страница произведения на рваных данных', () => {
  for (const width of WIDTHS) {
    test(`title@${width}`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      const href = await firstTitlePath(page);
      expect(href, 'в каталоге нет ни одной карточки со ссылкой').toBeTruthy();
      await page.goto(`${BASE}${href}`, { waitUntil: 'load' });
      const result = await page.evaluate(probe);
      collected.pages.push({ key: `title@${width}`, route: href, width, ...result });
      save();
      expect(result.empties, `страница произведения@${width}: пустые элементы`).toEqual([]);
      expect(result.dangling, `страница произведения@${width}: подписи без значений`).toEqual([]);
      expect(result.overflowX, `страница произведения@${width}: прокрутка вбок`).toBe(false);
      // Заголовок обязан быть: запись без названия не должна получать страницу.
      expect((await page.locator('h1').innerText()).trim().length).toBeGreaterThan(0);
    });
  }
});

test.describe('axe WCAG 2.2 AA на боевых данных', () => {
  for (const [name, route] of [['home', '/'], ['catalog', '/catalog/'],
    ['genres', '/genres/'], ['search', '/search/'],
    // Собственная страница витрины, а не страница веб-сервера: статический
    // сервер стенда отвечает на несуществующий адрес своей заглушкой, и
    // проверять её значило бы проверять оснастку.
    ['not-found', '/404.html']]) {
    test(`${name}`, async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(`${BASE}${route}`, { waitUntil: 'load' });
      await page.addScriptTag({ path: AXE });
      const result = await page.evaluate(
        async (tags) => window.axe.run(document, { runOnly: { type: 'tag', values: tags } }),
        TAGS,
      );
      fs.writeFileSync(
        path.join(OUT, 'a11y', `axe-live-${name}.json`),
        `${JSON.stringify({
          captured_at_utc: new Date().toISOString(),
          page: name, source: 'боевой каталог', standard: 'WCAG 2.0/2.1/2.2 A+AA',
          rules_passed: result.passes.length,
          violations: result.violations.map((v) => ({
            id: v.id, impact: v.impact, help: v.help,
            nodes: v.nodes.map((n) => ({ target: n.target, failureSummary: n.failureSummary })),
          })),
        }, null, 2)}\n`,
      );
      const serious = result.violations.filter(
        (v) => v.impact === 'serious' || v.impact === 'critical');
      const described = serious.map(
        (v) => `${v.id} (${v.impact}): ${v.help}\n    ${v.nodes.map((n) => n.target.join(' ')).join('\n    ')}`,
      ).join('\n  ');
      expect(serious, `${name}:\n  ${described}`).toEqual([]);
    });
  }
});

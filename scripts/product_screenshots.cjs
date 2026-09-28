/**
 * Снимки страниц продукта и проверка того, что на них видно.
 *
 * Снимок нужен владельцу, а числа — проверке. Одно без другого бесполезно:
 * по снимку нельзя утверждать «нет горизонтальной прокрутки», а по числам
 * нельзя увидеть, что страница выглядит незаконченной.
 *
 * Снимаются настоящие страницы собранного пакета, а не отдельная витринная
 * заготовка: демонстрационная страница показывает намерение, а не продукт.
 *
 * Запуск:
 *   node scripts/product_screenshots.cjs zona-cinema [базовый-адрес]
 */
const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const product = process.argv[2];
// Порт закреплён за продуктом: витрина живёт в корне своего порта, потому что
// её страницы ссылаются на стили и скрипты от корня.
const PORTS = { 'zona-cinema': 8903, 'animedia-portal': 8904, 'basis-video': 8905, yummy: 8906 };
const BASE = process.argv[3] || `http://127.0.0.1:${PORTS[process.argv[2]] || 8903}`;

if (!product) {
  console.error('нужно имя продукта');
  process.exit(2);
}

const OUT = path.join(ROOT, 'artifacts', 'evidence', 'products', product, 'screenshots');
fs.mkdirSync(OUT, { recursive: true });

/**
 * Страницы, которые владелец откроет первыми.
 *
 * У каждой витрины они свои: у basis-video нет ни каталога, ни жанров — это
 * витрина видеоматериалов с лекциями, подборками и новостями. Снимать у неё
 * `/catalog/` значило бы снимать страницу «не найдено» и называть её
 * поверхностью продукта.
 */
const PAGES_BY_PRODUCT = {
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
    ['search', '/search/'],
    ['genres', '/genres/'],
    ['not-found', '/404.html'],
  ],
};
const PAGES = PAGES_BY_PRODUCT[product] || PAGES_BY_PRODUCT.default;

const WIDTHS = [390, 768, 1440];

/** То, что на снимке не видно, но зритель почувствует. */
const probe = () => {
  const doc = document.documentElement;
  const empties = [];
  for (const tag of ['p', 'h1', 'h2', 'h3', 'li', 'dd', 'dt', 'section']) {
    for (const el of document.querySelectorAll(tag)) {
      // Живая область обязана существовать пустой: сообщение, вставленное в
      // элемент, которого не было в документе, экранный диктор не объявит.
      // Считать её незаполненной разметкой значит требовать поломки
      // доступности ради опрятности отчёта.
      if (el.matches('[role="status"], [role="alert"], [aria-live]')) continue;
      if (el.children.length === 0 && !el.textContent.trim()) {
        empties.push(`${tag}.${el.getAttribute('class') || ''}`);
      }
    }
  }
  const cards = [...document.querySelectorAll('.card')];
  const titles = cards.map((c) => (c.querySelector('.card__title')?.textContent || '').trim());
  return {
    overflowX: doc.scrollWidth > doc.clientWidth + 1,
    scrollWidth: doc.scrollWidth,
    clientWidth: doc.clientWidth,
    documentHeight: doc.scrollHeight,
    cards: cards.length,
    emptyTitles: titles.filter((t) => !t).length,
    longestTitle: titles.reduce((m, t) => Math.max(m, t.length), 0),
    sections: document.querySelectorAll('section').length,
    emptyElements: empties,
    canvas: getComputedStyle(document.body).backgroundColor,
    text: getComputedStyle(document.body).color,
  };
};

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const report = { product, base: BASE, captured_at_utc: new Date().toISOString(), pages: [] };
  const consoleErrors = [];
  const networkErrors = [];

  for (const [name, route] of PAGES) {
    for (const width of WIDTHS) {
      const context = await browser.newContext({ viewport: { width, height: 900 } });
      const page = await context.newPage();
      page.on('console', (m) => {
        if (m.type() === 'error') consoleErrors.push(`${name}@${width}: ${m.text().slice(0, 120)}`);
      });
      page.on('requestfailed', (r) => {
        // Внешние хосты в этой обстановке закрыты намеренно: их отказ —
        // свойство стенда, а не витрины, и в дефекты он не идёт.
        if (!r.url().startsWith(BASE)) return;
        networkErrors.push(`${name}@${width}: ${r.url().slice(0, 100)}`);
      });
      await page.goto(`${BASE}${route}`, { waitUntil: 'load' }).catch(() => {});
      await page.evaluate(
        () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
      const metrics = await page.evaluate(probe);
      const file = path.join(OUT, `${name}-${width}.png`);
      await page.screenshot({ path: file, fullPage: width === 1440 });
      report.pages.push({ page: name, route, width, screenshot: path.relative(ROOT, file), ...metrics });
      await context.close();
    }
  }

  report.consoleErrors = consoleErrors;
  report.networkErrors = networkErrors;
  fs.writeFileSync(path.join(path.dirname(OUT), 'visual-report.json'),
    `${JSON.stringify(report, null, 2)}\n`);
  await browser.close();

  const bad = report.pages.filter((p) => p.overflowX || p.emptyElements.length);
  console.log(`${product}: снимков ${report.pages.length}, `
    + `страниц с замечаниями ${bad.length}, ошибок в консоли ${consoleErrors.length}`);
  for (const p of bad.slice(0, 6)) {
    console.log(`  ${p.page}@${p.width}: прокрутка=${p.overflowX} `
      + `пустых элементов=${p.emptyElements.length} ${p.emptyElements.slice(0, 3).join(', ')}`);
  }
})();

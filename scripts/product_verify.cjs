/**
 * Проверка витрины в браузере: работает ли она и доступна ли.
 *
 * Предмет — не наличие управления, а результат. Кнопка, которая не меняет
 * выдачу, хуже отсутствующей: зритель считает её рабочей и делает вывод о
 * каталоге, а не об интерфейсе. Поэтому каждая проверка сравнивает выдачу до
 * и после действия.
 *
 * Свидетельства пишутся в каталог продукта, а не в общий файл: параллельные
 * прогоны разных витрин однажды уже затирали друг друга, и выглядело это как
 * «отчёт почему-то неполный», а не как гонка.
 *
 * Запуск:
 *   node scripts/product_verify.cjs zona-cinema
 */
const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { createRequire } = require('module');

const requireFrom = createRequire(__filename);
const AXE = requireFrom.resolve('axe-core/axe.min.js');

const ROOT = path.resolve(__dirname, '..');
const product = process.argv[2];
const PORTS = { 'zona-cinema': 8903, 'animedia-portal': 8904, 'basis-video': 8905, yummy: 8906 };
const BASE = process.argv[3] || `http://127.0.0.1:${PORTS[product]}`;

if (!product || !PORTS[product]) {
  console.error('нужно имя продукта из списка: ' + Object.keys(PORTS).join(', '));
  process.exit(2);
}

const OUT = path.join(ROOT, 'artifacts', 'evidence', 'products', product);
fs.mkdirSync(OUT, { recursive: true });

const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const WIDTHS = [390, 768, 1440];

/** Маршруты витрины. У basis-video своя структура — каталога и жанров нет. */
const ROUTES = product === 'basis-video'
  ? [['home', '/'], ['lekcii', '/lekcii/'], ['news', '/news/'],
    ['collection', '/collections/izbrannoe/'], ['search', '/search/']]
  : [['home', '/'], ['catalog', '/catalog/'], ['genres', '/genres/'],
    ['years', '/years/'], ['search', '/search/']];

const checks = [];
const runs = [];

function record(name, ok, detail) {
  checks.push({ check: name, ok, detail });
}

async function cards(page) {
  return page.locator('.card, .card-grid > li, .card-rail > li').count();
}

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  // ---- Навигация: каждая ссылка меню ведёт на существующую страницу -------
  await page.goto(`${BASE}/`, { waitUntil: 'load' });
  const navHrefs = await page.locator('header a[href^="/"]').evaluateAll(
    (nodes) => [...new Set(nodes.map((n) => n.getAttribute('href')))]);
  const broken = [];
  for (const href of navHrefs) {
    const response = await page.goto(`${BASE}${href}`, { waitUntil: 'load' });
    if (!response || response.status() >= 400) broken.push(`${href} → ${response && response.status()}`);
  }
  record('навигация ведёт на существующие страницы', broken.length === 0,
    broken.length ? `не открылись: ${broken.join(', ')}` : `${navHrefs.length} ссылок`);

  // ---- Каталог и фильтры --------------------------------------------------
  if (product !== 'basis-video') {
    await page.goto(`${BASE}/catalog/`, { waitUntil: 'load' });
    const inCatalog = await cards(page);
    const catalogTitles = await page.locator('.card__title').allInnerTexts();
    record('каталог наполнен', inCatalog > 0, `${inCatalog} карточек`);

    // Фильтр обязан менять выдачу, а не только адрес.
    await page.goto(`${BASE}/genres/`, { waitUntil: 'load' });
    const genreHref = await page.locator('main a[href^="/genres/"]:not([href$="/genres/"])')
      .first().getAttribute('href').catch(() => null);
    if (genreHref) {
      await page.goto(`${BASE}${genreHref}`, { waitUntil: 'load' });
      const inGenre = await cards(page);
      const genreTitles = await page.locator('.card__title').allInnerTexts();
      const heading = (await page.locator('h1').innerText()).trim();
      // Сравнивается состав, а не число. Обе страницы показывают полную
      // страницу выдачи, и равенство чисел ничего не доказывает: первая
      // редакция проверки на этом и ошиблась, объявив рабочий фильтр
      // сломанным.
      const same = JSON.stringify(genreTitles) === JSON.stringify(catalogTitles);
      record('фильтр по жанру меняет выдачу', inGenre > 0 && !same,
        `${genreHref}: ${inGenre} карточек, заголовок «${heading}», `
        + `состав ${same ? 'совпал с каталогом' : 'отличается от каталога'}`);
      // Состояние выбора обязано жить в адресе и переживать перезагрузку.
      const before = await page.locator('.card__title').allInnerTexts();
      await page.reload({ waitUntil: 'load' });
      const after = await page.locator('.card__title').allInnerTexts();
      record('выбор переживает перезагрузку', JSON.stringify(before) === JSON.stringify(after),
        `${before.length} записей до и ${after.length} после`);
    } else {
      record('фильтр по жанру меняет выдачу', false, 'в указателе жанров нет ссылок');
    }

    // Пагинация остаётся внутри раздела.
    await page.goto(`${BASE}/catalog/`, { waitUntil: 'load' });
    const next = page.locator('.pagination a').filter({ hasText: '2' }).first();
    if (await next.count()) {
      const href = await next.getAttribute('href');
      await page.goto(`${BASE}${href}`, { waitUntil: 'load' });
      record('вторая страница каталога открывается', (await cards(page)) > 0,
        `${href}: ${await cards(page)} карточек`);
    } else {
      record('вторая страница каталога открывается', false, 'пагинации нет');
    }
  }

  // ---- Поиск --------------------------------------------------------------
  //
  // Отметка «серверный поиск неприменим» снята: она была верной, пока поиска
  // не существовало. Теперь витрина отдаёт указатель и ищет по нему на
  // странице — во всех трёх движках, — и проверка обязана это проверять, а не
  // ссылаться на прежнее устройство.
  const serverSideSearch = false;
  await page.goto(`${BASE}/search/`, { waitUntil: 'load' });
  const field = page.locator('#search-q, #q-main, input[type="search"], input[name="q"]').first();
  if (await field.count()) {
    await field.fill(product === 'basis-video' ? 'материал' : 'матрица');
    await field.press('Enter');
    await page.waitForTimeout(2500);
    const found = await cards(page)
      + await page.locator('#search-results li').count();
    const note = (await page.locator('.count, #search-count, #search-hint').first()
      .textContent().catch(() => '')) || '';
    if (serverSideSearch) {
      const hint = (await page.locator('main .empty').first().textContent()
        .catch(() => '')) || '';
      record('страница поиска объясняет себя до запроса', hint.trim().length > 0,
        `подсказка «${hint.trim().slice(0, 60)}»`);
      checks.push({
        check: 'выдача поиска (серверная)', ok: null,
        detail: 'не применимо в статической выгрузке: движок здесь не работает',
      });
    } else {
      record('поиск отвечает на запрос', found > 0 || /найдено|ничего/i.test(note),
        `карточек ${found}, сообщение «${note.trim().slice(0, 60)}»`);
    }
  } else {
    record('поиск отвечает на запрос', false, 'поля поиска на странице нет');
  }

  // ---- Доступность и адаптивность ----------------------------------------
  for (const [name, route] of ROUTES) {
    for (const width of WIDTHS) {
      const ctx = await browser.newContext({ viewport: { width, height: 900 } });
      const p2 = await ctx.newPage();
      await p2.goto(`${BASE}${route}`, { waitUntil: 'load' });
      await p2.addScriptTag({ path: AXE });
      const result = await p2.evaluate(
        async (tags) => window.axe.run(document, { runOnly: { type: 'tag', values: tags } }), TAGS);
      const serious = result.violations.filter(
        (v) => v.impact === 'serious' || v.impact === 'critical');
      const overflow = await p2.evaluate(() => {
        const d = document.documentElement;
        return { overflowX: d.scrollWidth > d.clientWidth + 1, scrollWidth: d.scrollWidth };
      });
      runs.push({
        page: name, width, rules_passed: result.passes.length,
        violations: serious.map((v) => ({ id: v.id, impact: v.impact, help: v.help,
          nodes: v.nodes.map((n) => n.target) })),
        ...overflow,
      });
      await ctx.close();
    }
  }

  await browser.close();

  fs.writeFileSync(path.join(OUT, 'functional-report.json'),
    `${JSON.stringify({ product, base: BASE, captured_at_utc: new Date().toISOString(), checks },
      null, 2)}\n`);
  fs.writeFileSync(path.join(OUT, 'a11y-report.json'),
    `${JSON.stringify({ product, base: BASE, captured_at_utc: new Date().toISOString(),
      standard: 'WCAG 2.0/2.1/2.2 A+AA', runs }, null, 2)}\n`);

  // `ok: null` — не провал и не успех, а неприменимость: считать её провалом
  // значит требовать от предпросмотра того, чего он делать не умеет.
  const failed = checks.filter((c) => c.ok === false);
  const violations = runs.reduce((n, r) => n + r.violations.length, 0);
  const overflows = runs.filter((r) => r.overflowX);
  console.log(`${product}: проверок ${checks.length}, не прошли ${failed.length}; `
    + `прогонов axe ${runs.length}, нарушений ${violations}, прокрутка на ${overflows.length}`);
  for (const c of failed) console.log(`  ✗ ${c.check}: ${c.detail}`);
  for (const r of runs.filter((x) => x.violations.length).slice(0, 4)) {
    console.log(`  axe ${r.page}@${r.width}: ${r.violations.map((v) => v.id).join(', ')}`);
  }
})();

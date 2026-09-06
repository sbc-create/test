// Фильтры на боевом каталоге: работают ли они на самом деле.
//
// Фасеты витрины — ссылки на разделы, а не поля выбора: поле без `name` и
// `method` на статической витрине не меняет ничего, и это уже исправлялось.
// Здесь проверяется не наличие управления, а результат: сужает ли выбор
// выдачу, помнит ли адрес состояние, переживает ли оно перезагрузку,
// пагинацию и кнопку «назад», и говорит ли пустой раздел о своей пустоте.
//
// На боевом каталоге это важнее, чем на фикстуре: у 78 % записей жанров нет
// вовсе, у 85 % нет страны. Раздел, собранный из такого каталога, легко
// оказывается пустым или, наоборот, неотличимым от общего списка.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const BASE = process.env.LIVE_SEARCH_URL || 'http://127.0.0.1:8811';
const OUT = path.join(__dirname, '..', '..', 'artifacts', 'evidence', 'templates');
fs.mkdirSync(OUT, { recursive: true });

const collected = { captured_at_utc: null, filters: [] };

function save() {
  const file = path.join(OUT, 'live-filters.json');
  let previous = { filters: [] };
  try {
    previous = JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch { /* первый работник */ }
  fs.writeFileSync(file, `${JSON.stringify({
    captured_at_utc: new Date().toISOString(),
    base: BASE,
    source: 'снимок боевого каталога, 53 251 запись',
    filters: [...(previous.filters || []), ...collected.filters].filter(
      (entry, index, all) => all.findIndex((other) => other.key === entry.key) === index,
    ),
  }, null, 2)}\n`);
}

const SECTIONS = [
  ['жанры', '/genres/', '/genres/'],
  ['годы', '/years/', '/years/'],
  ['страны', '/countries/', '/countries/'],
];

async function counts(page) {
  return {
    cards: await page.locator('.card').count(),
    note: (await page.locator('.count').first().textContent().catch(() => '')) || '',
  };
}

test.describe('раздел фильтра сужает выдачу', () => {
  for (const [label, index, prefix] of SECTIONS) {
    test(`${label}: выбор ведёт в раздел и меняет выдачу`, async ({ page }) => {
      await page.goto(`${BASE}/catalog/`, { waitUntil: 'load' });
      const before = await counts(page);

      await page.goto(`${BASE}${index}`, { waitUntil: 'load' });
      // Ссылка на конкретное значение, а не на сам указатель: на странице
      // жанров есть и ссылка «/genres/» — в навигации и в крошках, — и переход
      // по ней возвращает на ту же страницу, где карточек нет вовсе.
      const link = page.locator(
        `main a[href^="${prefix}"]:not([href$="${prefix}"])`).first();
      await expect(link, `${label}: в указателе нет ни одной ссылки`).toBeVisible();
      const href = await link.getAttribute('href');
      const title = (await link.innerText()).trim();

      await page.goto(`${BASE}${href}`, { waitUntil: 'load' });
      const after = await counts(page);

      collected.filters.push({
        key: `${label}-выбор`, section: label, href, title,
        catalogCards: before.cards, sectionCards: after.cards, note: after.note.trim(),
      });
      save();

      expect(after.cards, `${label} ${href}: раздел пуст`).toBeGreaterThan(0);
      // Раздел обязан отличаться от общего каталога: иначе выбор не выбирает.
      const heading = (await page.locator('h1').innerText()).trim();
      expect(heading.toLowerCase(),
        `${label} ${href}: заголовок раздела не называет выбранное значение`)
        .not.toBe('каталог');
      // Число записей раздела названо и не совпадает с полным каталогом.
      expect(after.note, `${label} ${href}: раздел не говорит, сколько в нём записей`)
        .toMatch(/\d/);
    });
  }
});

test.describe('состояние выбора живёт в адресе', () => {
  test('перезагрузка раздела даёт ту же выдачу', async ({ page }) => {
    await page.goto(`${BASE}/genres/`, { waitUntil: 'load' });
    const href = await page.locator(
      'main a[href^="/genres/"]:not([href$="/genres/"])').first().getAttribute('href');
    await page.goto(`${BASE}${href}`, { waitUntil: 'load' });
    const first = await page.locator('.card__title').allInnerTexts();
    await page.reload({ waitUntil: 'load' });
    const second = await page.locator('.card__title').allInnerTexts();
    expect(second).toEqual(first);
  });

  test('кнопка «назад» возвращает прежний список', async ({ page }) => {
    await page.goto(`${BASE}/catalog/`, { waitUntil: 'load' });
    const catalog = await page.locator('.card__title').allInnerTexts();
    await page.goto(`${BASE}/genres/`, { waitUntil: 'load' });
    const href = await page.locator(
      'main a[href^="/genres/"]:not([href$="/genres/"])').first().getAttribute('href');
    await page.goto(`${BASE}${href}`, { waitUntil: 'load' });
    await page.goBack();
    await page.goBack();
    await expect(page).toHaveURL(/\/catalog\/$/);
    expect(await page.locator('.card__title').allInnerTexts()).toEqual(catalog);
  });

  test('вторая страница раздела остаётся в разделе', async ({ page }) => {
    await page.goto(`${BASE}/genres/`, { waitUntil: 'load' });
    const hrefs = await page.locator(
      'main a[href^="/genres/"]:not([href$="/genres/"])').evaluateAll(
      (nodes) => nodes.map((n) => n.getAttribute('href')));
    let paged = null;
    for (const href of hrefs.slice(0, 12)) {
      await page.goto(`${BASE}${href}`, { waitUntil: 'load' });
      const next = page.locator('.pagination a').filter({ hasText: '2' }).first();
      if (await next.count()) { paged = { href, next: await next.getAttribute('href') }; break; }
    }
    test.skip(paged === null, 'ни один раздел не разбит на страницы');
    // Адрес второй страницы обязан остаться внутри раздела: иначе пагинация
    // выбрасывает зрителя в общий каталог, и выбор теряется молча.
    expect(paged.next.startsWith(paged.href),
      `вторая страница уводит из раздела: ${paged.href} → ${paged.next}`).toBe(true);
    await page.goto(`${BASE}${paged.next}`, { waitUntil: 'load' });
    expect(await page.locator('.card').count()).toBeGreaterThan(0);
    collected.filters.push({ key: 'пагинация-раздела', ...paged });
    save();
  });
});

test.describe('фильтры работают без JavaScript', () => {
  test('переход в раздел и обратно при выключенном скрипте', async ({ browser }) => {
    const context = await browser.newContext({ javaScriptEnabled: false });
    const page = await context.newPage();
    await page.goto(`${BASE}/genres/`, { waitUntil: 'load' });
    const href = await page.locator(
      'main a[href^="/genres/"]:not([href$="/genres/"])').first().getAttribute('href');
    await page.goto(`${BASE}${href}`, { waitUntil: 'load' });
    expect(await page.locator('.card').count(),
      'без скрипта раздел пуст — значит выбор держался на скрипте').toBeGreaterThan(0);
    await context.close();
  });
});

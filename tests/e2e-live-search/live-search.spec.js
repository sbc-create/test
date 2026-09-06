// Поиск на боевом каталоге: проверка в браузере, а не в замерах.
//
// Замеры показывают время сопоставления. Работает ли поиск для зрителя,
// показывает только браузер: указатель нужно забрать, разобрать, отрисовать
// выдачу и не сломаться на медленной связи и на пустом ответе.
//
// Стенд собран из настоящего снимка каталога — 53 251 запись, — а не из
// фикстуры. Фикстура здесь бесполезна принципиально: указатель отдаётся
// только там, где встроенного набора нет, то есть на каталоге больше двухсот
// записей. На фикстуре из шестидесяти двух эта ветка не отрисовывается вовсе,
// и любая проверка на ней доказывала бы работу другого кода.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const OUT = path.join(__dirname, '..', '..', 'artifacts', 'evidence', 'templates');
fs.mkdirSync(OUT, { recursive: true });

const BASE = process.env.LIVE_SEARCH_URL || 'http://127.0.0.1:8811';

const collected = { captured_at_utc: null, queries: [] };

function save() {
  const file = path.join(OUT, 'live-search.json');
  let previous = { queries: [] };
  try {
    previous = JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch { /* первый работник */ }
  fs.writeFileSync(file, `${JSON.stringify({
    captured_at_utc: new Date().toISOString(),
    base: BASE,
    source: 'снимок боевого каталога, 53 251 запись',
    // Дубли убираются по запросу: работники дописывают файл каждый по разу,
    // и один и тот же запрос иначе попадает в свидетельство пять раз подряд.
    queries: [...(previous.queries || []), ...collected.queries].filter(
      (entry, index, all) => all.findIndex((other) => other.query === entry.query) === index,
    ),
  }, null, 2)}\n`);
}

async function search(page, query) {
  await page.goto(`${BASE}/search/`, { waitUntil: 'load' });
  await page.fill('#search-q', query);
  await page.press('#search-q', 'Enter');
  const started = Date.now();
  await page.waitForFunction(
    () => {
      const note = document.getElementById('search-count');
      const grid = document.getElementById('grid');
      if (!note) return false;
      const text = note.textContent || '';
      return text.includes('Найдено') || text.includes('ничего не нашлось')
        || text.includes('не загрузился') || (grid && grid.children.length > 0);
    },
    null,
    { timeout: 60_000 },
  );
  return {
    ms: Date.now() - started,
    note: (await page.locator('#search-count').textContent()).trim(),
    cards: await page.locator('#grid .card').count(),
    titles: await page.locator('#grid .card__title').allInnerTexts(),
  };
}

test.describe('поиск находит записи боевого каталога', () => {
  for (const query of ['матрица', 'ведьмак', 'война', 'дом', 'stranger']) {
    test(`запрос «${query}» даёт выдачу`, async ({ page }) => {
      const result = await search(page, query);
      collected.queries.push({ query, ...result, titles: result.titles.slice(0, 5) });
      save();
      expect(result.cards, `«${query}»: выдача пуста — ${result.note}`).toBeGreaterThan(0);
      expect(result.note, `«${query}»: страница не сказала, сколько нашла`)
        .toContain('Найдено');
      // Найденное обязано отвечать запросу, а не быть любыми записями.
      const normalized = query.toLowerCase();
      const matching = result.titles.filter((t) => t.toLowerCase().includes(normalized));
      expect(matching.length,
        `«${query}»: ни одно из названий не содержит запрос — ${result.titles.slice(0, 3)}`)
        .toBeGreaterThan(0);
    });
  }
});

test.describe('поиск честен в неудаче', () => {
  test('бессмысленный запрос даёт прямой ответ, а не пустоту', async ({ page }) => {
    const result = await search(page, 'ыыыжжжщщщфывапролдж');
    collected.queries.push({ query: 'ыыыжжжщщщфывапролдж', ...result, titles: [] });
    save();
    expect(result.cards).toBe(0);
    expect(result.note, 'страница молчит вместо ответа').toContain('ничего не нашлось');
  });

  test('однобуквенный запрос не выдаёт полкаталога', async ({ page }) => {
    await page.goto(`${BASE}/search/`, { waitUntil: 'load' });
    await page.fill('#search-q', 'я');
    await page.press('#search-q', 'Enter');
    await page.waitForTimeout(1500);
    expect(await page.locator('#grid .card').count(),
      'один символ выдал результаты — он совпадает почти с чем угодно').toBe(0);
  });
});

test.describe('страница поиска пригодна без JavaScript', () => {
  test('форма и разделы доступны при выключенном скрипте', async ({ browser }) => {
    const context = await browser.newContext({ javaScriptEnabled: false });
    const page = await context.newPage();
    await page.goto(`${BASE}/search/`, { waitUntil: 'load' });
    await expect(page.locator('form[role="search"] input#search-q')).toBeVisible();
    // Без скрипта поиск не работает, и страница обязана оставить рабочий путь.
    const links = await page.locator('#search-count a').count();
    expect(links, 'без скрипта страница не предлагает ни одного работающего раздела')
      .toBeGreaterThan(0);
    await context.close();
  });
});

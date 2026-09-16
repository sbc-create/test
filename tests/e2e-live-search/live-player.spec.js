// Состояния плеера на боевых данных.
//
// Пустая область — не состояние. На боевой витрине это уже случалось:
// `<video-player>` имел размер 0×0, скрипт провайдера был подключён, а
// запасной текст оставался скрытым — показать его было некому. Зритель видел
// большой пустой прямоугольник без единого слова о том, что произошло.
//
// Здесь проверяются четыре состояния, которые зритель может застать: ожидание
// загрузки, работающий плеер, подтверждённое отсутствие видео и отказ. Скрипт
// провайдера в проверке недоступен намеренно — внешние хосты закрыты, и это
// ровно та обстановка, в которой запасное состояние обязано сработать.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const BASE = process.env.LIVE_SEARCH_URL || 'http://127.0.0.1:8811';
const OUT = path.join(__dirname, '..', '..', 'artifacts', 'evidence', 'templates');
fs.mkdirSync(OUT, { recursive: true });

const collected = { captured_at_utc: null, players: [] };

function save() {
  const file = path.join(OUT, 'live-player.json');
  let previous = { players: [] };
  try {
    previous = JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch { /* первый работник */ }
  fs.writeFileSync(file, `${JSON.stringify({
    captured_at_utc: new Date().toISOString(),
    base: BASE,
    players: [...(previous.players || []), ...collected.players].filter(
      (entry, index, all) => all.findIndex((other) => other.key === entry.key) === index,
    ),
  }, null, 2)}\n`);
}

// Адреса берутся из самого стенда, а не из каталога. Стенд отрисовывает
// выборку страниц произведений — сорок из пятидесяти трёх тысяч, — и первая
// карточка каталога почти наверняка в неё не попала: тест уходил на
// несуществующий адрес и справедливо не находил там плеера.
const STAND_TITLES = path.join(__dirname, '..', '..', 'var', 'live-search-stand', 'title');

function renderedTitles() {
  return fs.readdirSync(STAND_TITLES)
    .filter((name) => fs.existsSync(path.join(STAND_TITLES, name, 'index.html')))
    .sort();
}

function anyTitle() {
  const titles = renderedTitles();
  if (!titles.length) { throw new Error('в стенде нет ни одной страницы произведения'); }
  return `/title/${titles[0]}/`;
}

test.describe('плеер объясняет своё состояние', () => {
  test('без скрипта провайдера зритель получает текст, а не пустоту', async ({ page }) => {
    const href = anyTitle();
    await page.goto(`${BASE}${href}`, { waitUntil: 'load' });

    const frame = page.locator('.player__frame');
    await expect(frame, 'области плеера нет вовсе').toBeVisible();

    // Скрипт провайдера недоступен, значит плеер не поднимется. Страница
    // обязана это заметить и сказать — молчание здесь неотличимо от поломки.
    await page.waitForFunction(
      () => {
        const wrap = document.querySelector('.player__frame');
        const fallback = document.querySelector('[data-player-fallback]');
        const state = wrap && wrap.getAttribute('data-player-state');
        return (fallback && !fallback.hasAttribute('hidden'))
          || (state && state !== 'loading');
      },
      null,
      { timeout: 30_000 },
    ).catch(() => {});

    const observed = await page.evaluate(() => {
      const wrap = document.querySelector('.player__frame');
      const fallback = document.querySelector('[data-player-fallback]');
      const box = wrap ? wrap.getBoundingClientRect() : null;
      return {
        state: wrap ? wrap.getAttribute('data-player-state') : null,
        fallbackVisible: !!fallback && !fallback.hasAttribute('hidden'),
        fallbackText: fallback ? fallback.textContent.trim().slice(0, 60) : null,
        height: box ? Math.round(box.height) : 0,
        width: box ? Math.round(box.width) : 0,
      };
    });
    collected.players.push({ key: 'без-скрипта-провайдера', href, ...observed });
    save();

    // Место под плеер зарезервировано: нулевая высота — это скачок раскладки
    // при появлении видео и пустота при его отсутствии.
    expect(observed.height, 'область плеера нулевой высоты').toBeGreaterThan(80);
    expect(observed.fallbackVisible || observed.state === 'unavailable'
      || observed.state === 'error',
    `плеер не поднялся и промолчал: состояние ${observed.state}, `
    + `запасной текст скрыт`).toBe(true);
  });

  test('при выключенном JavaScript объяснение видно сразу', async ({ browser }) => {
    const context = await browser.newContext({ javaScriptEnabled: false });
    const page = await context.newPage();
    const href = anyTitle();
    await page.goto(`${BASE}${href}`, { waitUntil: 'load' });
    const text = await page.locator('.player__frame').innerText();
    collected.players.push({ key: 'без-javascript', href, text: text.trim().slice(0, 80) });
    save();
    expect(text.trim().length,
      'без скрипта область плеера пуста: зритель видит прямоугольник без слов')
      .toBeGreaterThan(0);
    await context.close();
  });

  test('подтверждённое отсутствие видео названо словами', async ({ page }) => {
    // Записи, у которых источник подтвердил отсутствие потока, получают не
    // плеер, а объяснение. Проверяется, что объяснение — текст, а не пустой
    // кадр: это разные вещи для зрителя.
    const hrefs = renderedTitles().map((name) => `/title/${name}/`);
    let silent = null;
    for (const href of hrefs) {
      await page.goto(`${BASE}${href}`, { waitUntil: 'load' });
      const hasPlayer = await page.locator('video-player').count();
      if (!hasPlayer) { silent = href; break; }
    }
    test.skip(silent === null, 'среди первых записей нет ни одной без плеера');
    const text = await page.locator('.player__frame').innerText();
    collected.players.push({ key: 'подтверждённая-тишина', href: silent,
      text: text.trim().slice(0, 80) });
    save();
    expect(text.trim().length,
      'запись без плеера показывает пустой кадр вместо объяснения').toBeGreaterThan(0);
  });
});

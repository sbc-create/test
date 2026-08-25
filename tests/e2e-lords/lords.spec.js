// REQ-LORDS-TEMPLATE: стенд направления Lords в браузере.
// Проверяется поведение страницы, а не текст разметки: перенос, переполнение,
// работа фильтров и пагинации видны только в движке.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { SITES, url, VIEWPORTS } = require('./helpers');

const OUT = path.join(__dirname, '..', '..', 'var', 'artifacts', 'lords-screenshots');
fs.mkdirSync(OUT, { recursive: true });

const IDS = Object.keys(SITES);

// Маршруты, общие для всех четырёх сайтов.
const COMMON_ROUTES = [
  ['home', '/'],
  ['catalog', '/catalog/'],
  ['movies', '/movies/'],
  ['series', '/series/'],
  ['new', '/new/'],
  ['genres', '/genres/'],
  ['years', '/years/'],
  ['countries', '/countries/'],
  ['search', '/search/'],
];

// Секреты, которых не должно быть ни в разметке, ни в скриптах.
const FORBIDDEN = [
  'CDNVIDEOHUB_API_TOKEN',
  'CDNVIDEOHUB_PUBLISHER_ID',
  'NEXT_PUBLIC',
  'secret://',
];

test.describe.configure({ mode: 'serial' });

test.describe('маршруты отвечают', () => {
  for (const id of IDS) {
    for (const [name, route] of COMMON_ROUTES) {
      test(`[${id}] ${name} отдаёт HTML и не пуст`, async ({ page }) => {
        const response = await page.goto(url(id, route));
        expect(response.status(), `${id}${route}`).toBe(200);
        expect(response.headers()['x-robots-tag']).toBe('noindex, nofollow');
        await expect(page.locator('h1')).toHaveCount(1);
        await expect(page.locator('header.site-header')).toBeVisible();
        await expect(page.locator('footer.site-footer')).toBeVisible();
      });
    }
  }

  test('нормализация адреса отвечает перенаправлением', async ({ page }) => {
    const response = await page.goto(url('lords-01', '/catalog'));
    expect(response.url()).toContain('/catalog/');
    expect(response.status()).toBe(200);
  });

  test('несуществующий адрес отдаёт 404 со страницей', async ({ page }) => {
    const response = await page.goto(url('lords-01', '/no-such-address/'));
    expect(response.status()).toBe(404);
    await expect(page.locator('h1')).toContainText('не найдена');
  });

  test('выключенный тип контента отдаёт 404, а не пустой список', async ({ page }) => {
    // Аниме выключено во всех четырёх пакетах.
    for (const id of IDS) {
      const response = await page.goto(url(id, '/anime/'));
      expect(response.status(), `${id}/anime/`).toBe(404);
    }
  });
});

test.describe('раскладка на трёх ширинах', () => {
  for (const id of IDS) {
    for (const [name, route] of [['home', '/'], ['catalog', '/catalog/'], ['genres', '/genres/']]) {
      test(`[${id}] ${name}: нет горизонтальной прокрутки`, async ({ page }) => {
        for (const view of VIEWPORTS) {
          await page.setViewportSize({ width: view.width, height: view.height });
          await page.goto(url(id, route));
          const box = await page.evaluate(() => ({
            scroll: document.documentElement.scrollWidth,
            client: document.documentElement.clientWidth,
          }));
          expect(
            box.scroll,
            `${id} ${route} @${view.width}: содержимое шире вьюпорта`,
          ).toBeLessThanOrEqual(box.client + 1);
        }
      });
    }
  }

  test('сетка карточек меняет число колонок вместе с шириной', async ({ page }) => {
    const columns = {};
    for (const view of VIEWPORTS) {
      await page.setViewportSize({ width: view.width, height: view.height });
      await page.goto(url('lords-01', '/catalog/'));
      columns[view.name] = await page.evaluate(() => {
        const grid = document.getElementById('grid');
        return getComputedStyle(grid).gridTemplateColumns.split(' ').length;
      });
    }
    expect(columns.mobile).toBeLessThan(columns.tablet);
    expect(columns.tablet).toBeLessThan(columns.desktop);
  });

  test('меню на телефоне открывается кнопкой', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(url('lords-01', '/'));
    const nav = page.locator('#site-nav');
    await expect(nav).toBeHidden();
    await page.locator('.nav-toggle').click();
    await expect(nav).toBeVisible();
  });
});

test.describe('каталог: фильтры, сортировка, пагинация', () => {
  test('фильтр по жанру сокращает список', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(url('lords-01', '/catalog/'));
    const before = await page.locator('.card').count();
    const value = await page.locator('#f-genre option').nth(1).getAttribute('value');
    await page.selectOption('#f-genre', value);
    await page.waitForFunction(
      (n) => document.querySelectorAll('.card').length !== n,
      before,
    );
    const after = await page.locator('.card').count();
    expect(after).toBeGreaterThan(0);
    expect(after).not.toBe(before);
  });

  test('сортировка меняет порядок карточек', async ({ page }) => {
    await page.goto(url('lords-01', '/catalog/'));
    const first = await page.locator('.card__title').first().innerText();
    await page.selectOption('#f-sort', 'name');
    await page.waitForFunction(
      (name) => {
        const node = document.querySelector('.card__title');
        return node && node.textContent.trim() !== name;
      },
      first.trim(),
    );
    expect(await page.locator('.card__title').first().innerText()).not.toBe(first);
  });

  test('сброс возвращает полный список', async ({ page }) => {
    await page.goto(url('lords-01', '/catalog/'));
    const before = await page.locator('.card').count();
    const value = await page.locator('#f-genre option').nth(1).getAttribute('value');
    await page.selectOption('#f-genre', value);
    await page.waitForFunction((n) => document.querySelectorAll('.card').length !== n, before);
    await page.locator('.facets__reset').click();
    await page.waitForFunction((n) => document.querySelectorAll('.card').length === n, before);
    expect(await page.locator('.card').count()).toBe(before);
  });

  test('серверная пагинация ведёт на вторую страницу', async ({ page }) => {
    await page.goto(url('lords-01', '/catalog/'));
    await expect(page.locator('.pagination')).toBeVisible();
    await page.locator('.pagination a[rel="next"]').click();
    await expect(page).toHaveURL(/\/catalog\/page\/2\/$/);
    await expect(page.locator('.card').first()).toBeVisible();
  });

  test('поиск находит запись по названию', async ({ page }) => {
    await page.goto(url('lords-01', '/catalog/'));
    const name = (await page.locator('.card__title').first().innerText()).trim();
    await page.goto(url('lords-01', `/search/?q=${encodeURIComponent(name)}`));
    await expect(page.locator('#grid .card').first()).toBeVisible();
    await expect(page.locator('#search-count')).toContainText('Найдено');
  });
});

test.describe('страница произведения', () => {
  test('сериал показывает сезоны и серии', async ({ page }) => {
    await page.goto(url('lords-01', '/series/'));
    await page.locator('.card__title').first().click();
    await expect(page.locator('.seasons details.season').first()).toBeVisible();
    await expect(page.locator('.episode').first()).toBeVisible();
    await expect(page.locator('.breadcrumbs')).toBeVisible();
    await expect(page.locator('.facts')).toBeVisible();
  });

  test('фильм не показывает сезонов', async ({ page }) => {
    await page.goto(url('lords-01', '/movies/'));
    await page.locator('.card__title').first().click();
    await expect(page.locator('details.season')).toHaveCount(0);
    await expect(page.locator('.seasons')).toContainText('сезонов нет');
  });

  test('вместо плеера стоит заглушка с диагностическим статусом', async ({ page }) => {
    await page.goto(url('lords-01', '/movies/'));
    await page.locator('.card__title').first().click();
    await expect(page.locator('.player__frame')).toBeVisible();
    await expect(page.locator('.player__status'))
      .toHaveText('BLOCKED_INPUT_CDNVIDEOHUB_CREDENTIALS');
    expect(await page.locator('iframe').count()).toBe(0);
  });

  test('блок комментариев на месте и отправка выключена', async ({ page }) => {
    await page.goto(url('lords-01', '/movies/'));
    await page.locator('.card__title').first().click();
    await expect(page.locator('.comments')).toBeVisible();
    await expect(page.locator('.comments button')).toBeDisabled();
  });

  test('похожее показывается и ведёт на другую запись', async ({ page }) => {
    await page.goto(url('lords-01', '/movies/'));
    await page.locator('.card__title').first().click();
    const current = page.url();
    const related = page.locator('section.section .card__title').first();
    await expect(related).toBeVisible();
    await related.click();
    expect(page.url()).not.toBe(current);
  });
});

test.describe('четыре профиля различимы', () => {
  test('акцентный цвет и плотность отличаются у всех четырёх', async ({ page }) => {
    const seen = new Set();
    for (const id of IDS) {
      await page.goto(url(id, '/'));
      const accent = await page.evaluate(() =>
        getComputedStyle(document.documentElement).getPropertyValue('--accent').trim());
      const gap = await page.evaluate(() =>
        getComputedStyle(document.documentElement).getPropertyValue('--gap').trim());
      expect(accent, `${id}: акцент не задан`).toBeTruthy();
      seen.add(`${accent}|${gap}`);
    }
    expect(seen.size, 'профили визуально не различаются').toBe(IDS.length);
  });

  test('заголовки главных страниц не совпадают', async ({ page }) => {
    const titles = new Set();
    for (const id of IDS) {
      await page.goto(url(id, '/'));
      titles.add((await page.locator('h1').innerText()).trim());
    }
    expect(titles.size).toBe(IDS.length);
  });

  test('подборки есть только там, где тип включён', async ({ page }) => {
    // Подборки включены в lords-01 и lords-03, выключены в lords-02 и lords-04.
    for (const id of ['lords-01', 'lords-03']) {
      expect((await page.goto(url(id, '/collections/'))).status()).toBe(200);
    }
    for (const id of ['lords-02', 'lords-04']) {
      expect((await page.goto(url(id, '/collections/'))).status()).toBe(404);
    }
  });
});

test.describe('секретов нет ни в разметке, ни в скриптах', () => {
  test('HTML и JS чисты', async ({ page }) => {
    const bodies = [];
    page.on('response', async (response) => {
      const type = response.headers()['content-type'] || '';
      if (!/html|javascript|json/.test(type)) return;
      try {
        bodies.push([response.url(), await response.text()]);
      } catch (e) {
        // тело недоступно — не повод падать: проверяем то, что дошло
      }
    });
    for (const id of IDS) {
      await page.goto(url(id, '/'));
      await page.goto(url(id, '/catalog/'));
    }
    await page.goto(url('lords-01', '/movies/'));
    await page.locator('.card__title').first().click();
    expect(bodies.length).toBeGreaterThan(0);
    for (const [href, text] of bodies) {
      for (const marker of FORBIDDEN) {
        expect(text.includes(marker), `${href}: найдено «${marker}»`).toBe(false);
      }
    }
  });

  test('страницы не ходят за внешними ресурсами', async ({ page }) => {
    const external = [];
    page.on('request', (request) => {
      const target = new URL(request.url());
      if (!['127.0.0.1', 'localhost'].includes(target.hostname)) external.push(request.url());
    });
    for (const id of IDS) {
      await page.goto(url(id, '/'));
    }
    expect(external, `внешние запросы: ${external.join(', ')}`).toHaveLength(0);
  });
});

// Сбор доказательств. Эталонов нет, сравнения с ними нет — снимки сохраняются
// как свидетельство прогона и осматриваются человеком.
test.describe('снимки экрана', () => {
  for (const id of IDS) {
    test(`[${id}] снимки трёх ширин`, async ({ page }) => {
      for (const view of VIEWPORTS) {
        await page.setViewportSize({ width: view.width, height: view.height });
        for (const [name, route] of [['home', '/'], ['catalog', '/catalog/']]) {
          await page.goto(url(id, route));
          await page.screenshot({
            path: path.join(OUT, `${id}-${name}-${view.width}.png`),
            fullPage: false,
          });
        }
      }
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(url(id, '/movies/'));
      await page.locator('.card__title').first().click();
      await page.screenshot({ path: path.join(OUT, `${id}-title-1440.png`), fullPage: false });
    });
  }
});

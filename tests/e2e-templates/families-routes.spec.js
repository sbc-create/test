// REQ-FAMILIES-ROUTES: маршруты и состояния двух новых семейств.
//
// Контракт блоков проверяет главную. Витрина же состоит не из главной: каталог,
// разделы, поиск и посадочные страницы фасетов — это и есть то, чем
// пользуются. Отдельно проверяются состояния, которые обычно не проверяет
// никто, потому что их «и так видно»: пустой поиск, отсутствующая страница,
// страница без карточек.
//
// Оценка `states_ux` в матрице раньше опиралась на признак «пакет существует» —
// то есть ни на что. Этот файл делает её измеримой.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..', '..');
const PLAN = JSON.parse(
  fs.readFileSync(path.join(ROOT, 'var', 'artifacts', 'template-stand.json'), 'utf8'));

const FAMILIES = PLAN.templates.filter(
  (t) => t.profile === 'zona-cinema' || t.profile === 'animedia-portal');

// Маршруты сняты с собранного превью, а не придуманы: список в спецификации
// разошёлся бы со сборкой при первом изменении профиля.
const ROUTES = ['/catalog/', '/genres/', '/years/', '/countries/', '/new/',
                '/movies/', '/series/', '/search/'];

const OUT = path.join(ROOT, 'artifacts', 'evidence', 'templates', 'families-routes');
fs.mkdirSync(OUT, { recursive: true });

const seen = {};
test.afterAll(() => {
  fs.writeFileSync(path.join(OUT, 'routes.json'),
    `${JSON.stringify({ captured_at_utc: new Date().toISOString(), routes: seen }, null, 2)}\n`);
});

for (const family of FAMILIES) {
  test.describe(family.profile, () => {
    for (const route of ROUTES) {
      test(`${route} отдаётся и читается`, async ({ page }) => {
        const response = await page.goto(family.url.replace(/\/$/, '') + route,
          { waitUntil: 'load' });
        expect(response.status(), route).toBe(200);
        const h1 = page.locator('h1');
        await expect(h1, `${route}: нет заголовка`).toBeVisible();
        const text = (await h1.textContent()).trim();
        expect(text.length, `${route}: заголовок пуст`).toBeGreaterThan(0);

        // Заголовок вкладки и описание — часть страницы, а не украшение: без
        // них раздел неотличим от соседнего в истории и в закладках.
        const title = await page.title();
        expect(title.trim().length, `${route}: пустой title`).toBeGreaterThan(0);
        seen[`${family.profile}${route}`] = { status: 200, h1: text, title };
      });
    }

    test('пустой поиск объясняет, а не показывает пустоту', async ({ page }) => {
      await page.goto(`${family.url.replace(/\/$/, '')}/search/`, { waitUntil: 'load' });
      // Пустой поиск — состояние, а не ошибка. Страница обязана объяснить, что
      // делать: молчащая страница с одним полем читается как поломка.
      const body = (await page.locator('main, body').first().textContent()).trim();
      expect(body.length, 'страница поиска пуста').toBeGreaterThan(60);
      await expect(page.locator('form[role="search"], form input[name="q"]').first())
        .toBeVisible();
    });

    test('отсутствующая страница не притворяется существующей', async ({ page }) => {
      const response = await page.goto(
        `${family.url.replace(/\/$/, '')}/такого-раздела-нет-xyz/`,
        { waitUntil: 'load' });
      // Стенд отдаёт файлы, и код ответа задаёт он, а не шаблон. Проверяется
      // то, за что отвечает шаблон: несуществующий адрес не должен вернуть
      // страницу, выглядящую как настоящий раздел с содержимым.
      const status = response.status();
      if (status === 200) {
        const cards = await page.locator('.card').count();
        expect(cards, 'несуществующий адрес отдал витрину с карточками').toBe(0);
      } else {
        expect(status).toBeGreaterThanOrEqual(400);
      }
      seen[`${family.profile}/404`] = { status };
    });
  });
}

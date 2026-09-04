// REQ-LORDS-CROSSBROWSER: критический путь в Firefox и WebKit.
//
// Вся приёмка стенда до этого шла в одном движке. Одного движка достаточно,
// чтобы поймать логику, и недостаточно, чтобы поймать движок: `aspect-ratio`,
// `:focus-visible`, поведение `<details>`, восстановление истории и сетка с
// `auto-fill` расходятся между Chromium, Firefox и WebKit чаще всего.
//
// Здесь только критический путь, а не весь набор. Причина не в экономии:
// широкий набор в трёх движках превращается в источник шума, который перестают
// читать. Критический путь — то, потеря чего означает, что сайтом нельзя
// пользоваться, и его провал нельзя списать на особенность движка.
const { test, expect } = require('@playwright/test');
const { url } = require('../e2e-lords/helpers');

const SITE = 'lords-01';

test.describe('критический путь', () => {
  test('главная → каталог → карточка → страница произведения', async ({ page }) => {
    await page.goto(url(SITE, '/'));
    await expect(page.locator('h1')).toBeVisible();

    await page.locator('.site-footer a[href="/catalog/"]').first().click();
    await expect(page).toHaveURL(/\/catalog\/$/);
    await expect(page.locator('.card').first()).toBeVisible();

    const title = page.locator('.card__title').first();
    const href = await title.getAttribute('href');
    await title.click();
    await expect(page).toHaveURL(new RegExp(`${href.replace(/[/]/g, '\\/')}$`));
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('.player__frame')).toBeVisible();
  });

  test('кадр плеера держит пропорцию и не съезжает', async ({ page }) => {
    // `aspect-ratio` — свойство, которое движки внедряли в разное время и с
    // разными краевыми случаями. Если кадр не зарезервирован, включение
    // настоящего плеера сдвинет раскладку именно здесь.
    await page.goto(url(SITE, '/movies/'));
    await page.locator('.card__title').first().click();
    const frame = page.locator('.player__frame');
    await expect(frame).toBeVisible();
    const box = await frame.boundingBox();
    expect(box.width).toBeGreaterThan(0);
    expect(box.height).toBeGreaterThan(0);
    const ratio = box.width / box.height;
    expect(ratio, `пропорция кадра ${ratio.toFixed(3)} вместо 16/9`).toBeGreaterThan(1.5);
    expect(ratio, `пропорция кадра ${ratio.toFixed(3)} вместо 16/9`).toBeLessThan(2.0);
  });

  test('поиск находит запись и ведёт на неё', async ({ page }) => {
    await page.goto(url(SITE, '/catalog/'));
    const name = await page.locator('.card__title').first().textContent();
    await page.goto(url(SITE, '/search/'));
    await page.locator('#search-q').fill(name.trim().slice(0, 10));
    await expect(page.locator('.card').first()).toBeVisible({ timeout: 10_000 });
    await page.locator('.card__title').first().click();
    await expect(page.locator('h1')).toBeVisible();
  });

  test('пустая выдача поиска объясняет себя, а не молчит', async ({ page }) => {
    await page.goto(url(SITE, '/search/?q=zzzzzzzzzz'));
    await page.locator('#search-q').fill('zzzzzzzzzz');
    await expect(page.locator('#search-count')).toContainText(/Найдено|Введите/);
    expect(await page.locator('.card').count()).toBe(0);
  });

  test('несуществующий адрес отдаёт 404 и остаётся навигабельным', async ({ page }) => {
    const response = await page.goto(url(SITE, '/nonexistent-address/'));
    expect(response.status()).toBe(404);
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('.site-footer')).toBeVisible();
  });

  test('назад и вперёд восстанавливают страницу', async ({ page }) => {
    await page.goto(url(SITE, '/'));
    await page.goto(url(SITE, '/catalog/'));
    await page.goBack();
    await expect(page).toHaveURL(new RegExp(`${url(SITE, '/')}$`));
    await page.goForward();
    await expect(page).toHaveURL(/\/catalog\/$/);
    await expect(page.locator('.card').first()).toBeVisible();
  });

  test('фильтр каталога работает и сбрасывается', async ({ page }) => {
    await page.goto(url(SITE, '/catalog/'));
    const before = await page.locator('.card').count();
    const value = await page.locator('#f-genre option').nth(1).getAttribute('value');
    await page.selectOption('#f-genre', value);
    await page.waitForFunction((n) => document.querySelectorAll('.card').length !== n, before);
    await page.locator('.facets__reset').click();
    await page.waitForFunction((n) => document.querySelectorAll('.card').length === n, before);
    expect(await page.locator('.card').count()).toBe(before);
  });

  test('меню на телефоне открывается и закрывается', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(url(SITE, '/'));
    const toggle = page.locator('.nav-toggle');
    await expect(toggle).toBeVisible();
    await toggle.click();
    await expect(page.locator('#site-nav')).toHaveAttribute('data-open', 'true');
    await toggle.click();
    await expect(page.locator('#site-nav')).toHaveAttribute('data-open', 'false');
  });
});

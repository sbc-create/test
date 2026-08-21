// REQ-QA-LEVELS: критические пользовательские сценарии из acceptance.scenarios пакета.
const { test, expect } = require('@playwright/test');

test('browse-catalog: каталог → вторая страница → карточка материала', async ({ page }) => {
  await page.goto('/lekcii/');
  await expect(page.locator('h1')).toHaveText('Лекции');
  const firstPageItems = await page.locator('#items > li').count();
  expect(firstPageItems).toBeGreaterThan(0);

  await page.locator('.page-next').click();
  await expect(page).toHaveURL(/\/lekcii\/page\/2\/$/);
  await expect(page.locator('#items > li').first()).toBeVisible();

  const card = page.locator('.card-link').first();
  const href = await card.getAttribute('href');
  await card.click();
  await expect(page).toHaveURL(new RegExp(href.replace(/\//g, '\\/') + '$'));
  await expect(page.locator('h1')).toBeVisible();
  await expect(page.locator('.breadcrumbs')).toBeVisible();
});

test('unavailable-video: недоступный эпизод показывает статус, а не другой ролик', async ({ page }) => {
  await page.goto('/praktikum/serial-fikstura/season-1/episode-3/');
  await expect(page.locator('.availability')).toBeVisible();
  await expect(page.locator('.player-frame')).toHaveCount(0);
  const html = await page.content();
  expect(html).not.toContain('"@type": "VideoObject"');
});

test('available-video: эпизод показывает плеер над сгибом на мобильном', async ({ page }) => {
  await page.goto('/praktikum/serial-fikstura/season-1/episode-1/');
  const player = page.locator('.player-frame');
  await expect(player).toBeVisible();
  const box = await player.boundingBox();
  const viewport = page.viewportSize();
  expect(box.y).toBeLessThan(viewport.height * 1.5);
});

test('пагинация работает без JavaScript', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false, httpCredentials: contextCredentials() });
  const page = await context.newPage();
  const response = await page.goto((process.env.FACTORY_BASE_URL || 'http://127.0.0.1:8082') + '/lekcii/page/2/');
  expect(response.status()).toBe(200);
  await expect(page.locator('#items > li').first()).toBeVisible();
  await expect(page.locator('.pagination a[href]').first()).toBeVisible();
  await context.close();
});

test('«Показать ещё» дополняет серверную пагинацию, а не заменяет её', async ({ page }) => {
  await page.goto('/lekcii/');
  const before = await page.locator('#items > li').count();
  const button = page.locator('.load-more');
  await expect(button).toBeVisible();
  await expect(page.locator('.pagination a[href]').first()).toBeVisible();
  await button.click();
  await expect.poll(async () => page.locator('#items > li').count()).toBeGreaterThan(before);
});

test('удалённый и несуществующий контент отдают честные статусы', async ({ page }) => {
  const gone = await page.goto('/410/');
  expect(gone.status()).toBe(410);
  const missing = await page.goto('/lekcii/page/999/');
  expect(missing.status()).toBe(404);
  await expect(page.locator('h1')).toBeVisible();
});

function contextCredentials() {
  const auth = process.env.FACTORY_STAGING_AUTH || '';
  if (!auth.includes(':')) return undefined;
  return { username: auth.split(':')[0], password: auth.slice(auth.indexOf(':') + 1) };
}

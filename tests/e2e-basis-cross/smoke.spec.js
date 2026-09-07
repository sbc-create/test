// REQ-BASIS-CROSSBROWSER: критический путь theme pack basis-video в Firefox и WebKit.
//
// Тот же принцип, что и у направления: axe и рубрику незачем гонять в трёх
// движках, а раскладку — нужно. Здесь проходится путь, потеря которого
// означает, что витриной нельзя пользоваться: главная → раздел → материал.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..', '..');
const PLAN = JSON.parse(
  fs.readFileSync(path.join(ROOT, 'var', 'artifacts', 'basis-stand.json'), 'utf8'));

const at = (type) => (PLAN.pages.find((p) => p.page_type === type) || {}).url;

test('главная → раздел → материал', async ({ page }) => {
  await page.goto(PLAN.pages.find((p) => p.page_type === 'home').url, { waitUntil: 'load' });
  await expect(page.locator('h1')).toBeVisible();

  const card = page.locator('.card a, a.card').first();
  await expect(card).toBeVisible();
  await card.click();
  await expect(page.locator('h1')).toBeVisible();
});

test('кадр плеера держит размеры до подключения поставщика', async ({ page }) => {
  // `aspect-ratio` расходится между движками чаще прочего, а кадр плеера — то
  // самое место, где расхождение видно зрителю как прыжок раскладки.
  await page.goto(at('title'), { waitUntil: 'load' });
  const frame = page.locator('.player-frame').first();
  await expect(frame).toBeVisible();
  const box = await frame.boundingBox();
  expect(box.height, 'кадр плеера схлопнулся в ноль').toBeGreaterThan(50);
  const ratio = box.width / box.height;
  expect(ratio, `пропорция кадра ${ratio.toFixed(2)} вместо 16/9`).toBeGreaterThan(1.5);
  expect(ratio).toBeLessThan(2.1);
});

test('страница поиска отдаёт форму и не уезжает вбок на телефоне', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(at('search'), { waitUntil: 'load' });
  await expect(page.locator('form[role="search"] input[name="q"]').first()).toBeVisible();
  const box = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(box.scroll, `уезжает вбок: ${box.scroll} > ${box.client}`)
    .toBeLessThanOrEqual(box.client + 1);
});

test('состояние недоступности объяснено, а не пусто', async ({ page }) => {
  await page.goto(at('content_unavailable'), { waitUntil: 'load' });
  const notice = page.locator('.availability, [role="status"]').first();
  await expect(notice).toBeVisible();
  const text = (await notice.textContent()).trim();
  expect(text.length, 'блок состояния пуст').toBeGreaterThan(20);
});

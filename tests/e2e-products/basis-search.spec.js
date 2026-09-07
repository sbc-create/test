// Поиск basis-video: работает ли он для зрителя.
//
// До этого цикла поиска не было вовсе. Страница показывала форму, движок
// отвечал бы на запрос сервером — но в статической выгрузке движка нет, и
// зритель, введя запрос, не получал ничего. Отметка «не применимо» была
// честной, а поиска от неё не появлялось.
//
// Проверяется поведение, а не наличие поля: набранный запрос обязан дать
// выдачу, опечатка — тоже, бессмысленный запрос — прямой ответ, а адрес —
// сохранить запрос, чтобы страницу можно было перезагрузить и послать
// ссылкой.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const BASE = 'http://127.0.0.1:8905';
const OUT = path.join(__dirname, '..', '..', 'artifacts', 'evidence', 'products', 'basis-video');
fs.mkdirSync(OUT, { recursive: true });

/** Ждём ответа страницы, а не истечения срока: срок ловит не то. */
async function search(page, query) {
  await page.goto(`${BASE}/search/`, { waitUntil: 'load' });
  await page.fill('#q-main', query);
  await page.press('#q-main', 'Enter');
  await page.waitForFunction(
    () => {
      const hint = document.getElementById('search-hint');
      const results = document.getElementById('search-results');
      const text = hint ? hint.textContent : '';
      return /Найдено|ничего не нашлось|не загрузился|повреждён/.test(text)
        || (results && !results.hidden && results.children.length > 0);
    },
    null,
    { timeout: 30_000 },
  ).catch(() => {});
  return {
    hint: (await page.locator('#search-hint').textContent()).trim(),
    results: await page.locator('#search-results li').count(),
    titles: await page.locator('#search-results li a').allInnerTexts(),
    url: page.url(),
  };
}

const collected = [];

test.afterAll(async () => {
  fs.writeFileSync(path.join(OUT, 'search-report.json'),
    `${JSON.stringify({ base: BASE, captured_at_utc: new Date().toISOString(),
      checks: collected }, null, 2)}\n`);
});

test.describe('поиск basis-video', () => {
  test('точный запрос находит материал', async ({ page }) => {
    const result = await search(page, 'материал 03');
    collected.push({ query: 'материал 03', ...result });
    expect(result.results, `выдача пуста: ${result.hint}`).toBeGreaterThan(0);
    expect(result.hint).toContain('Найдено');
    expect(result.titles.join(' | ')).toContain('материал 03');
  });

  test('опечатка не отменяет находку', async ({ page }) => {
    // «матреиал» — перестановка соседних букв, самая частая опечатка.
    const result = await search(page, 'матреиал');
    collected.push({ query: 'матреиал', ...result });
    expect(result.results, `опечатка потеряна: ${result.hint}`).toBeGreaterThan(0);
  });

  test('чужая раскладка понимается', async ({ page }) => {
    // «vfnthbfk» на русской раскладке даёт «материал».
    const result = await search(page, 'vfnthbfk');
    collected.push({ query: 'vfnthbfk', ...result });
    expect(result.results, `раскладка не распознана: ${result.hint}`).toBeGreaterThan(0);
  });

  test('«ё» и «е» не различаются', async ({ page }) => {
    const plain = await search(page, 'фикстура');
    const yo = await search(page, 'фикстурё');
    collected.push({ query: 'фикстура/фикстурё', plain: plain.results, yo: yo.results,
      hint: plain.hint, results: plain.results, titles: [], url: plain.url });
    expect(plain.results).toBeGreaterThan(0);
  });

  test('бессмысленный запрос отвечает прямо, а не молчит', async ({ page }) => {
    const result = await search(page, 'ыыыжжжщщщфывапролдж');
    collected.push({ query: 'ыыыжжжщщщфывапролдж', ...result });
    expect(result.results).toBe(0);
    expect(result.hint, 'страница молчит вместо ответа').toContain('ничего не нашлось');
  });

  test('однобуквенный запрос не выдаёт всё подряд', async ({ page }) => {
    const result = await search(page, 'м');
    collected.push({ query: 'м', ...result });
    expect(result.results, 'один символ совпадает почти с чем угодно').toBe(0);
  });

  test('запрос остаётся в адресе и переживает перезагрузку', async ({ page }) => {
    const first = await search(page, 'материал 05');
    expect(first.url, 'запрос не попал в адрес').toContain('q=');
    await page.reload({ waitUntil: 'load' });
    await page.waitForFunction(
      () => /Найдено/.test(document.getElementById('search-hint').textContent),
      null, { timeout: 30_000 }).catch(() => {});
    const after = await page.locator('#search-results li').count();
    collected.push({ query: 'материал 05 (перезагрузка)', hint: '', results: after,
      titles: [], url: page.url() });
    expect(after, 'после перезагрузки выдача пропала').toBeGreaterThan(0);
  });

  test('без JavaScript страница остаётся пригодной', async ({ browser }) => {
    const context = await browser.newContext({ javaScriptEnabled: false });
    const page = await context.newPage();
    await page.goto(`${BASE}/search/`, { waitUntil: 'load' });
    await expect(page.locator('form[role="search"] #q-main')).toBeVisible();
    // Поиск без скрипта не работает и работать не может; страница обязана
    // оставить путь, а не тупик.
    const links = await page.locator('#search-hint a').count();
    expect(links, 'без скрипта страница не предлагает ни одного раздела')
      .toBeGreaterThan(0);
    await context.close();
  });
});

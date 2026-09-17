// REQ-TEMPLATE-CONTRACT: обязательные блоки шаблона на 390, 768 и 1440 px.
//
// Проверяется не «страница отвечает», а «шаблон отдал то, что объявил». Состав
// берётся из манифеста через var/artifacts/template-stand.json: спецификация не
// хранит собственного списка блоков, иначе она проверяла бы свою копию, а не
// шаблон. Ширины 390/768/1440 попадают в три разные ветки медиазапросов Lords
// (640px и 1024px, factory/lords/theme.py), поэтому одна ширина за другую здесь
// не отвечает.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..', '..');
const PLAN = JSON.parse(
  fs.readFileSync(path.join(ROOT, 'var', 'artifacts', 'template-stand.json'), 'utf8'),
);

const VIEWPORTS = [
  { name: 'mobile', width: 390, height: 844, columns: 'mobile' },
  { name: 'tablet', width: 768, height: 1024, columns: 'tablet' },
  { name: 'desktop', width: 1440, height: 900, columns: 'desktop' },
];

// Блоки, живущие внутри первого экрана: у них своя разметка, но метка та же.
const HERO_BLOCKS = new Set(['hero_search', 'hero_facets']);

// Последовательного режима здесь нет намеренно: упавшая проверка одного блока
// не должна прятать состояние остальных — harness должен показать весь список
// расхождений разом, а не первое из них.
for (const entry of PLAN.templates) {
  test.describe(`шаблон ${entry.profile}`, () => {
    for (const view of VIEWPORTS) {
      test(`${view.name} ${view.width}px: объявленные блоки на месте`, async ({ page }) => {
        await page.setViewportSize({ width: view.width, height: view.height });
        const response = await page.goto(entry.url);
        expect(response.status()).toBe(200);

        // Каркас страницы к манифесту не относится и обязан быть всегда.
        await expect(page.locator('h1')).toHaveCount(1);
        await expect(page.locator('header.site-header')).toBeVisible();
        await expect(page.locator('footer.site-footer')).toBeVisible();
        await expect(page.locator('[data-block="hero"]')).toBeVisible();

        for (const block of entry.home_blocks) {
          const marked = page.locator(`[data-block="${block}"]`);
          // Больше одного узла — законно: type_rows даёт по секции на каждый
          // включённый тип контента. Ноль — нет.
          const count = await marked.count();
          expect(count, `${entry.profile}: блок ${block} объявлен, но не выведен`)
            .toBeGreaterThan(0);
          await expect(marked.first(), `${entry.profile}: блок ${block} выведен, но не виден`)
            .toBeVisible();
          if (HERO_BLOCKS.has(block)) {
            const inside = await marked.first().evaluate(
              (el) => Boolean(el.closest('[data-block="hero"]')));
            expect(inside, `${entry.profile}: ${block} обязан быть внутри первого экрана`)
              .toBe(true);
          }
        }
      });

      test(`${view.name} ${view.width}px: нет горизонтальной прокрутки`, async ({ page }) => {
        await page.setViewportSize({ width: view.width, height: view.height });
        await page.goto(entry.url);
        const box = await page.evaluate(() => ({
          scroll: document.documentElement.scrollWidth,
          client: document.documentElement.clientWidth,
        }));
        expect(box.scroll, `${entry.profile} ${view.width}px`).toBeLessThanOrEqual(box.client + 1);
      });

      test(`${view.name} ${view.width}px: колонок столько, сколько в манифесте`, async ({ page }) => {
        await page.setViewportSize({ width: view.width, height: view.height });
        await page.goto(entry.url);
        const grid = page.locator('.grid').first();
        if (await grid.count() === 0) {
          test.skip(true, 'у шаблона нет сетки на главной');
        }
        const columns = await grid.evaluate(
          (el) => getComputedStyle(el).gridTemplateColumns.trim().split(/\s+/).length);
        expect(columns, `${entry.profile} на ${view.width}px`).toBe(entry.columns[view.columns]);
      });
    }

    test('порядок блоков совпадает с манифестом', async ({ page }) => {
      // Порядок — часть шаблона, а не украшение: манифест перечисляет блоки
      // сверху вниз, и переставленный блок означает другую витрину.
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(entry.url);
      const shown = await page.evaluate(() => Array.from(
        document.querySelectorAll('main [data-block]'), (el) => el.dataset.block));
      // Повторы схлопываются: type_rows выводит секцию на каждый тип контента,
      // и они идут подряд — это один блок манифеста, а не несколько.
      const order = shown.filter((b, i) => shown.indexOf(b) === i);
      const declared = entry.home_blocks.filter((b) => order.includes(b));
      const seen = order.filter((b) => declared.includes(b));
      expect(seen).toEqual(declared);
    });
  });
}

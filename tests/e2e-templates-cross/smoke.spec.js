// REQ-TEMPLATES-CROSSBROWSER: критический путь шаблонов направления в Firefox и WebKit.
//
// Контракт блоков и доступность проверяются в одном движке: дерево
// доступности и состав разметки от движка не зависят. Зависит раскладка —
// `aspect-ratio`, `auto-fill`, `:focus-visible`, `<details>` — и именно она
// ломается молча: страница отвечает 200, блоки на месте, а витрина уехала.
//
// Проверяется критический путь, а не весь набор: то, потеря чего означает, что
// витриной нельзя пользоваться.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..', '..');
const PLAN = JSON.parse(
  fs.readFileSync(path.join(ROOT, 'var', 'artifacts', 'template-stand.json'), 'utf8'));

for (const entry of PLAN.templates) {
  test.describe(`${entry.profile}`, () => {
    test('главная отдаётся и держит ширину', async ({ page }) => {
      const response = await page.goto(entry.url, { waitUntil: 'load' });
      expect(response.status(), `${entry.url}`).toBe(200);
      await expect(page.locator('h1')).toBeVisible();

      // Горизонтальная прокрутка — самый частый способ, которым раскладка
      // расходится между движками: сетка, посчитанная одним, не помещается
      // в другом. Проверяется на телефоне, где запас меньше всего.
      await page.setViewportSize({ width: 390, height: 844 });
      const box = await page.evaluate(() => ({
        scroll: document.documentElement.scrollWidth,
        client: document.documentElement.clientWidth,
      }));
      expect(box.scroll, `уезжает вбок: ${box.scroll} > ${box.client}`)
        .toBeLessThanOrEqual(box.client + 1);
    });

    test('карточка ведёт на страницу и та открывается', async ({ page }) => {
      await page.goto(entry.url, { waitUntil: 'load' });
      const card = page.locator('a.card, .card a, .card__title').first();
      const count = await card.count();
      test.skip(count === 0, 'на главной этого профиля нет карточек каталога');
      const href = await card.getAttribute('href');
      expect(href, 'карточка без адреса').toBeTruthy();
      await card.click();
      await expect(page.locator('h1')).toBeVisible();
    });

    test('видимость фокуса не теряется', async ({ page }) => {
      // `:focus-visible` — расхождение движков, а не украшение: без видимого
      // фокуса витрина перестаёт быть проходимой с клавиатуры, и это не видно
      // ни в одном снимке разметки.
      await page.goto(entry.url, { waitUntil: 'load' });
      await page.keyboard.press('Tab');
      const focus = await page.evaluate(() => {
        const el = document.activeElement;
        if (!el || el === document.body) { return null; }
        const style = getComputedStyle(el);
        return {
          tag: el.tagName.toLowerCase(),
          outline: style.outlineStyle,
          width: style.outlineWidth,
          shadow: style.boxShadow,
        };
      });
      expect(focus, 'первый Tab никуда не привёл').not.toBeNull();
      const visible = (focus.outline !== 'none' && focus.width !== '0px')
        || (focus.shadow && focus.shadow !== 'none');
      expect(visible, `фокус на ${focus.tag} ничем не показан`).toBeTruthy();
    });
  });
}

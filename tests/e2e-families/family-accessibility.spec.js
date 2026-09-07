// Доступность трёх семейств: axe WCAG 2.2 AA, клавиатура, двукратный текст.
//
// Предмет проверки — слой шаблонов: разметка компонентов и стили семейства.
// Это не приёмка боевой витрины и ею не притворяется: у витрин portal_light,
// pulse и editorial нет ни боевого домена, ни окружения, и до их появления
// приёмка остаётся BLOCKED. Но разметка, контраст и работа с клавиатуры от
// домена не зависят и обязаны быть верны уже сейчас.
//
// Три ширины обязательны: нарушение контраста живёт в теме и видно везде, а
// перекрытие целей и перенос — только на узкой.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { createRequire } = require('module');

const requireFrom = createRequire(__filename);
const AXE = requireFrom.resolve('axe-core/axe.min.js');

const STAND = path.join(__dirname, '..', '..', 'blueprints', 'payload-next-multisite',
  'app', 'var', 'family-stand');
const OUT = path.join(__dirname, '..', '..', 'artifacts', 'evidence', 'templates', 'a11y');
fs.mkdirSync(OUT, { recursive: true });

const FAMILIES = ['portal_light', 'pulse', 'editorial'];
const WIDTHS = [390, 768, 1440];
// Поверхности берутся из описи стенда, а не перечисляются здесь: перечень в
// двух местах расходится, и расходится молча.
const INDEX = JSON.parse(fs.readFileSync(path.join(STAND, 'index.json'), 'utf8'));
const SURFACES = INDEX.surfaces || ['catalog'];
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

const url = (family, surface = 'catalog') => `file://${path.join(
  STAND, surface === 'catalog' ? `${family}.html` : `${family}-${surface}.html`)}`;

test.describe('axe WCAG 2.2 AA', () => {
  for (const family of FAMILIES) {
    for (const surface of SURFACES) {
    for (const width of WIDTHS) {
      test(`${family}/${surface}/${width}`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto(url(family, surface), { waitUntil: 'load' });
        await page.addScriptTag({ path: AXE });
        const result = await page.evaluate(
          async (tags) => window.axe.run(document, { runOnly: { type: 'tag', values: tags } }),
          TAGS,
        );
        fs.writeFileSync(
          path.join(OUT, `axe-family-${family}-${surface}-${width}.json`),
          `${JSON.stringify({
            captured_at_utc: new Date().toISOString(),
            family, surface, width, standard: 'WCAG 2.0/2.1/2.2 A+AA',
            rules_passed: result.passes.length,
            violations: result.violations.map((v) => ({
              id: v.id, impact: v.impact, help: v.help,
              nodes: v.nodes.map((n) => ({ target: n.target, failureSummary: n.failureSummary })),
            })),
          }, null, 2)}\n`,
        );
        const serious = result.violations.filter(
          (v) => v.impact === 'serious' || v.impact === 'critical');
        const described = serious.map(
          (v) => `${v.id} (${v.impact}): ${v.help}\n    ${v.nodes.map((n) => n.target.join(' ')).join('\n    ')}`,
        ).join('\n  ');
        expect(serious, `${family}/${surface}/${width}:\n  ${described}`).toEqual([]);
      });
    }
    }
  }
});

test.describe('клавиатура', () => {
  for (const family of FAMILIES) {
    test(`${family}: обход страницы клавишей табуляции доходит до содержимого`, async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(url(family), { waitUntil: 'load' });
      const seen = [];
      for (let step = 0; step < 12; step += 1) {
        await page.keyboard.press('Tab');
        seen.push(await page.evaluate(() => {
          const el = document.activeElement;
          if (!el || el === document.body) return null;
          const box = el.getBoundingClientRect();
          const style = getComputedStyle(el);
          return {
            tag: el.tagName.toLowerCase(),
            text: (el.textContent || '').trim().slice(0, 30),
            width: Math.round(box.width),
            height: Math.round(box.height),
            outline: style.outlineStyle,
          };
        }));
      }
      const stops = seen.filter(Boolean);
      expect(stops.length, `${family}: остановок табуляции нет`).toBeGreaterThan(3);
      // Фокус обязан быть виден: невидимый фокус — это работающая навигация,
      // о которой пользователь не знает.
      const invisible = stops.filter((s) => s.outline === 'none');
      expect(invisible, `${family}: остановки без видимого фокуса: ${JSON.stringify(invisible)}`)
        .toEqual([]);
      // Цель не меньше 24 px: критерий 2.5.8 уровня AA.
      const small = stops.filter((s) => s.height > 0 && s.height < 24);
      expect(small, `${family}: цели ниже 24 px: ${JSON.stringify(small)}`).toEqual([]);
    });
  }
});

test.describe('двукратное увеличение текста', () => {
  for (const family of FAMILIES) {
    for (const surface of SURFACES) {
    test(`${family}/${surface}: при 200 % ничего не теряется и не уезжает вбок`, async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 900 });
      await page.goto(url(family, surface), { waitUntil: 'load' });
      await page.addStyleTag({ content: 'html { font-size: 200% !important }' });
      await page.evaluate(
        () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
      const result = await page.evaluate(() => {
        const clipped = [];
        for (const el of document.querySelectorAll('body *')) {
          if (el.classList.contains('visually-hidden')) continue;
          const style = getComputedStyle(el);
          if (style.overflow !== 'hidden' && style.overflowY !== 'hidden') continue;
          if (!el.clientHeight || !el.textContent.trim()) continue;
          if (el.scrollHeight > el.clientHeight + 2) {
            clipped.push({
              cls: el.getAttribute('class') || el.tagName.toLowerCase(),
              need: el.scrollHeight, have: el.clientHeight,
              text: el.textContent.trim().slice(0, 40),
            });
          }
        }
        const doc = document.documentElement;
        return { clipped, overflowX: doc.scrollWidth > doc.clientWidth + 1 };
      });
      expect(result.clipped,
        `${family}/${surface}: содержимое обрезано при 200 %`).toEqual([]);
      expect(result.overflowX,
        `${family}/${surface}: горизонтальная прокрутка при 200 %`).toBe(false);
    });
    }
  }
});

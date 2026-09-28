// REQ-BASIS-A11Y: доступность и адаптивность theme pack basis-video.
//
// Проверяется собранный пилот, а не стенд направления: у basis-video свой
// рендерер и своя карта маршрутов. Состав страниц берётся из карты сборки
// (`var/artifacts/basis-stand.json`), поэтому новый тип страницы попадает под
// проверку сам, а не после правки этого файла.
//
// Рубрика качества уже оценила эти же страницы в 10.0 из 10, но она читает
// разметку. Контраст, размер целей на реальной ширине и горизонтальная
// прокрутка в разметке не видны — их видно только в браузере.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..', '..');
const PLAN = JSON.parse(
  fs.readFileSync(path.join(ROOT, 'var', 'artifacts', 'basis-stand.json'), 'utf8'));

const { AA_MIN, INPUT_MIN_FONT, measureTargets, failingAA } = require('../lib/target-size');

const AXE = ['/home/claude/work-templates/site-factory/node_modules/axe-core/axe.min.js',
             '/home/claude/node_modules/axe-core/axe.min.js'].find(fs.existsSync);
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const VIEWPORTS = [
  { name: 'mobile', width: 390, height: 844 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1440, height: 900 },
];

const OUT = path.join(ROOT, 'artifacts', 'evidence', 'templates', 'basis-a11y');
fs.mkdirSync(OUT, { recursive: true });

test('карта стенда не пуста', () => {
  // Прогон по пустому списку страниц проходит и ничего не доказывает.
  expect(PLAN.pages.length, 'стенд не отдал ни одной страницы').toBeGreaterThanOrEqual(10);
});

for (const entry of PLAN.pages) {
  for (const viewport of VIEWPORTS) {
    test(`${entry.page_type} — ${viewport.name} ${viewport.width}px`, async ({ browser }) => {
      const context = await browser.newContext({
        viewport: { width: viewport.width, height: viewport.height },
      });
      const page = await context.newPage();
      const response = await page.goto(entry.url, { waitUntil: 'load' });
      // Страницы 404 и 410 отдаются стендом как файлы и отвечают 200: статус
      // задаёт сервер публикации, а не сборка. Проверяется содержимое.
      expect(response, `${entry.url} не ответил`).not.toBeNull();
      await page.addScriptTag({ path: AXE });
      const result = await page.evaluate(
        async (tags) => axe.run(document, { runOnly: { type: 'tag', values: tags } }), TAGS);
      const serious = result.violations.filter(
        (v) => v.impact === 'serious' || v.impact === 'critical');

      const targets = await page.evaluate(measureTargets);
      const smallAA = failingAA(targets);
      const smallInputs = viewport.width > 390 ? [] : await page.evaluate(
        (min) => [...document.querySelectorAll('input, select, textarea')]
          .filter((el) => el.type !== 'hidden')
          .map((el) => ({ name: el.name || el.id || el.tagName.toLowerCase(),
                          size: Math.round(parseFloat(getComputedStyle(el).fontSize) * 100) / 100 }))
          .filter((el) => el.size < min), INPUT_MIN_FONT);

      // Горизонтальная прокрутка — отдельный отказ адаптивности: страница может
      // не иметь ни одного нарушения axe и всё равно уезжать вбок.
      const overflow = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      }));

      fs.writeFileSync(
        path.join(OUT, `axe-${entry.page_type}-${viewport.width}.json`),
        `${JSON.stringify({
          captured_at_utc: new Date().toISOString(), site: PLAN.site, build: PLAN.build,
          page_type: entry.page_type, viewport: viewport.width, url: entry.url,
          rules_passed: result.passes.length,
          violations: result.violations.map((v) => ({ id: v.id, impact: v.impact, help: v.help,
            nodes: v.nodes.map((n) => n.target) })),
          targets_total: targets.length, failing_aa: smallAA,
          small_inputs: smallInputs, overflow,
        }, null, 2)}\n`);

      const named = (l) => l.map((t) => `${t.cls || t.tag} ${t.width}×${t.height} «${t.text}»`).join('; ');
      expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`),
        `${entry.page_type} ${viewport.width}px`).toEqual([]);
      expect(smallAA, `${entry.page_type} ${viewport.width}px, цели меньше ${AA_MIN} px: ${named(smallAA)}`).toEqual([]);
      expect(smallInputs, `поля мельче ${INPUT_MIN_FONT} px`).toEqual([]);
      expect(overflow.scrollWidth,
        `${entry.page_type} ${viewport.width}px уезжает вбок: ${overflow.scrollWidth} > ${overflow.clientWidth}`)
        .toBeLessThanOrEqual(overflow.clientWidth + 1);
      await context.close();
    });
  }
}

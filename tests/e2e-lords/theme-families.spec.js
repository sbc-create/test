// lords_dark и lords_light обязаны быть различимы, а не называться по-разному.
//
// Требование владельца названо прямо: «явное визуальное различие lords_dark и
// lords_light». До сих пор это не проверялось ничем: тема выбиралась профилем,
// проверки смотрели на доступность и раскладку, а вопрос «отличаются ли две
// витрины на глаз» не задавался.
//
// Проверяется именно светлота, а не совпадение строк темы. Две палитры могут
// называться тёмной и светлой и при этом различаться на несколько процентов
// яркости — тогда зритель не увидит разницы, как бы они ни назывались. Поэтому
// меряются относительная яркость полотна и текста и контраст между ними.
//
// Отдельно проверяется, что светлая тема действительно светлая, а тёмная —
// тёмная: перепутать их местами легче, чем кажется, и заметить это по одному
// снимку почти невозможно.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { SITES, url } = require('./helpers');

const OUT = path.join(__dirname, '..', '..', 'artifacts', 'evidence', 'templates');
fs.mkdirSync(OUT, { recursive: true });

//: Витрины и объявленная у них тема. Взято из пакетов (`tenant.theme`).
const THEMES = {
  'lords-01': 'lords_dark',
  'lords-02': 'lords_dark',
  'lords-03': 'lords_light',
  'lords-04': 'lords_light',
};

const collected = { captured_at_utc: null, palettes: {} };

function save() {
  const file = path.join(OUT, 'lords-theme-families.json');
  let previous = { palettes: {} };
  try {
    previous = JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch { /* первый работник */ }
  fs.writeFileSync(file, `${JSON.stringify({
    captured_at_utc: new Date().toISOString(),
    palettes: { ...(previous.palettes || {}), ...collected.palettes },
  }, null, 2)}\n`);
}

/** Относительная яркость по WCAG: та же величина, по которой считают контраст. */
const measure = () => {
  const channel = (value) => {
    const c = value / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  const luminance = (rgb) => {
    const [r, g, b] = rgb.match(/\d+/g).slice(0, 3).map(Number);
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
  };
  const body = getComputedStyle(document.body);
  const canvas = luminance(body.backgroundColor);
  const text = luminance(body.color);
  const contrast = (Math.max(canvas, text) + 0.05) / (Math.min(canvas, text) + 0.05);
  return {
    canvasColor: body.backgroundColor,
    textColor: body.color,
    canvasLuminance: Math.round(canvas * 1000) / 1000,
    textLuminance: Math.round(text * 1000) / 1000,
    contrast: Math.round(contrast * 100) / 100,
  };
};

test.describe('семейства тем Lords', () => {
  for (const site of Object.keys(THEMES)) {
    test(`${site} (${THEMES[site]}): палитра измерена`, async ({ page }) => {
      await page.goto(url(site, '/'), { waitUntil: 'load' });
      const palette = await page.evaluate(measure);
      collected.palettes[site] = { theme: THEMES[site], ...palette };
      save();

      // Контраст полотна и текста — требование 1.4.3 уровня AA для обычного
      // текста. Тема, не дотягивающая до него, нечитаема независимо от того,
      // светлая она или тёмная.
      expect(palette.contrast,
        `${site}: контраст полотна и текста ${palette.contrast} ниже 4.5`)
        .toBeGreaterThanOrEqual(4.5);

      // Тёмная тема обязана быть тёмной, светлая — светлой. Порог 0.18 взят
      // как середина между обычным белым полотном (1.0) и обычным тёмным
      // (около 0.01): попасть в него случайно нельзя.
      if (THEMES[site] === 'lords_dark') {
        expect(palette.canvasLuminance,
          `${site} объявлена тёмной, а полотно светлое: яркость ${palette.canvasLuminance}`)
          .toBeLessThan(0.18);
      } else {
        expect(palette.canvasLuminance,
          `${site} объявлена светлой, а полотно тёмное: яркость ${palette.canvasLuminance}`)
          .toBeGreaterThan(0.18);
      }
    });
  }
});

test.describe('тёмное и светлое семейства различимы', () => {
  test('полотна расходятся не на проценты, а в разы', async ({ page }) => {
    const palettes = {};
    for (const site of ['lords-01', 'lords-03']) {
      await page.goto(url(site, '/'), { waitUntil: 'load' });
      palettes[site] = await page.evaluate(measure);
    }
    const dark = palettes['lords-01'].canvasLuminance;
    const light = palettes['lords-03'].canvasLuminance;
    collected.palettes['различие'] = { dark, light, ratio: (light + 0.05) / (dark + 0.05) };
    save();

    // Отношение яркостей — та же величина, что и контраст: ниже четырёх
    // означает, что рядом две витрины выглядят вариантами одной, а не разными
    // семействами.
    const ratio = (light + 0.05) / (dark + 0.05);
    expect(ratio,
      `полотна lords_dark (${dark}) и lords_light (${light}) различаются в ${ratio.toFixed(1)} раза`)
      .toBeGreaterThan(4);
  });

  test('витрины одного семейства палитрой не расходятся', async ({ page }) => {
    // Внутри семейства палитра обязана совпадать: иначе «семейство» — это
    // просто слово в манифесте, а не общий облик.
    const palettes = {};
    for (const site of ['lords-01', 'lords-02']) {
      await page.goto(url(site, '/'), { waitUntil: 'load' });
      palettes[site] = await page.evaluate(measure);
    }
    expect(palettes['lords-01'].canvasColor).toBe(palettes['lords-02'].canvasColor);
  });
});

test.describe('выбор темы переживает перезагрузку', () => {
  for (const site of ['lords-01', 'lords-03']) {
    test(`${site}: выбранная тема остаётся после перезагрузки`, async ({ page }) => {
      await page.goto(url(site, '/'), { waitUntil: 'load' });
      const before = await page.evaluate(measure);

      // Выбирается тема, противоположная умолчанию витрины.
      const target = THEMES[site] === 'lords_dark' ? 'light' : 'dark';
      await page.locator(`.theme-switch button[data-theme-set="${target}"]`).click();
      await page.waitForFunction(
        (value) => document.documentElement.getAttribute('data-theme') === value, target);
      const after = await page.evaluate(measure);
      expect(after.canvasColor,
        `${site}: выбор темы не изменил полотно`).not.toBe(before.canvasColor);

      await page.reload({ waitUntil: 'load' });
      const restored = await page.evaluate(measure);
      expect(restored.canvasColor,
        `${site}: выбор темы не пережил перезагрузку`).toBe(after.canvasColor);
      // Контраст обязан держаться и в выбранной теме, а не только в стоящей
      // по умолчанию.
      expect(restored.contrast,
        `${site}/${target}: контраст ${restored.contrast} ниже 4.5`).toBeGreaterThanOrEqual(4.5);
    });
  }
});

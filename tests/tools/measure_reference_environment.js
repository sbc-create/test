/*
 * Среда замера: локаль, часовой пояс, доступные шрифты, политика анимаций,
 * версия драйвера и ревизия браузера.
 *
 * Контракт визуального сравнения требует, чтобы эти значения были объявлены
 * обеими сторонами и совпали: они меняют метрики текста и поведение переходов,
 * а инструмент замера их не задаёт. Объявить их можно только измерением — из
 * репозитория они недоказуемы.
 *
 * Страница не открывается: браузер запускается на about:blank, наружу не идёт
 * ни один запрос.
 *
 * Использование:
 *   node tests/tools/measure_reference_environment.js <файл>
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const out = process.argv[2];
const executablePath = process.env.FACTORY_CHROMIUM || undefined;

// Набор проверяемых семейств фиксирован: «какие шрифты есть в системе» браузер
// не перечисляет, и список обязан быть одинаковым у обеих сторон.
const FAMILIES = [
  'Arial', 'Helvetica', 'Times New Roman', 'Courier New', 'Georgia', 'Verdana',
  'Tahoma', 'Trebuchet MS', 'Roboto', 'Open Sans', 'Noto Sans', 'Noto Color Emoji',
  'DejaVu Sans', 'DejaVu Serif', 'DejaVu Sans Mono', 'Liberation Sans',
  'Liberation Serif', 'Liberation Mono', 'Ubuntu', 'Cantarell', 'FreeSans',
];

(async () => {
  const browser = await chromium.launch(executablePath ? { executablePath } : {});
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  await page.goto('about:blank');

  const probe = await page.evaluate((families) => ({
    locale: navigator.language,
    locales: [...navigator.languages],
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    reduced_motion: window.matchMedia('(prefers-reduced-motion: reduce)').matches
      ? 'reduce' : 'no-preference',
    forced_colors: window.matchMedia('(forced-colors: active)').matches ? 'active' : 'none',
    color_scheme: window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light',
    device_pixel_ratio: window.devicePixelRatio,
    // Наличие семейства определяется шириной текста, а не document.fonts.check:
    // check() возвращает true и для отсутствующего семейства, потому что
    // отвечает на другой вопрос — загружены ли шрифты для этой строки.
    // Сравнение с тремя базовыми семействами надёжно: если семейства нет,
    // строка рисуется базовым и ширины совпадают.
    fonts_available: (() => {
      const context = document.createElement('canvas').getContext('2d');
      const sample = 'mmmmmmmmmmlliWWWQ@#0123456789';
      const width = (font) => { context.font = font; return context.measureText(sample).width; };
      const base = { monospace: width('72px monospace'), 'sans-serif': width('72px sans-serif'),
                     serif: width('72px serif') };
      return families.filter((family) => Object.entries(base).some(
        ([generic, reference]) => width(`72px "${family}", ${generic}`) !== reference));
    })(),
  }), FAMILIES);

  const version = browser.version();
  await browser.close();

  const result = {
    tool: 'tests/tools/measure_reference_environment.js',
    measured_at_utc: new Date().toISOString(),
    renderer: {
      engine: 'chromium',
      driver: 'playwright',
      driver_version: require('playwright/package.json').version,
      browser_version: version,
      browser_build: path.basename(
        (chromium.executablePath() || '').split('/chrome-linux')[0] || 'unknown'),
      executable_from: chromium.executablePath() || null,
    },
    fonts_probed: FAMILIES,
    ...probe,
  };

  fs.writeFileSync(out, JSON.stringify(result, null, 2));
  console.log(JSON.stringify({ locale: result.locale, timezone: result.timezone,
                               fonts: result.fonts_available.length,
                               browser_build: result.renderer.browser_build }));
})();

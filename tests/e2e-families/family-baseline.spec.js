// Эталон раскладки трёх семейств.
//
// У Lords такой эталон есть давно, и он уже дважды ловил то, чего не видит ни
// axe, ни проверка переполнения: шапка, выросшая вдвое от переключателя тем, и
// доля постера в карточке, изменившаяся от длины названий. Оба раза правка
// была задумана, но следствие — нет.
//
// Здесь то же самое для семейств payload-next-multisite. Меряются величины, а
// не картинки: снимок экрана ловит любую разницу, включая незначащую, и потому
// со временем перестаёт запускаться. Числа же говорят, что именно изменилось.
//
// Эталон обновляется только осознанно — командой FAMILIES_UPDATE_BASELINE=1 —
// и вместе с объяснением, почему изменение задумано.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const STAND = path.join(__dirname, '..', '..', 'blueprints', 'payload-next-multisite',
  'app', 'var', 'family-stand');
const BASELINE = path.join(__dirname, 'family-baseline.json');

const INDEX = JSON.parse(fs.readFileSync(path.join(STAND, 'index.json'), 'utf8'));
const FAMILIES = INDEX.families;
const SURFACES = INDEX.surfaces || ['catalog'];
const WIDTHS = [390, 768, 1440];

const UPDATE = process.env.FAMILIES_UPDATE_BASELINE === '1';
//: Допуск в пикселях. Ноль недостижим: движки округляют по-разному, и эталон
//: с нулевым допуском падал бы от смены версии браузера, ничего не сообщая.
const TOLERANCE = 2;

const url = (family, surface) => `file://${path.join(
  STAND, surface === 'catalog' ? `${family}.html` : `${family}-${surface}.html`)}`;

const measure = () => {
  const px = (value) => Math.round(parseFloat(value) * 100) / 100;
  const box = (selector) => {
    const el = document.querySelector(selector);
    if (!el) return null;
    const rect = el.getBoundingClientRect();
    return { w: Math.round(rect.width), h: Math.round(rect.height) };
  };
  const grid = document.querySelector('.grid');
  const body = getComputedStyle(document.body);
  return {
    header: box('.site-header'),
    main: box('main'),
    firstCard: box('.card'),
    footer: box('.site-footer'),
    columns: grid ? getComputedStyle(grid).gridTemplateColumns.split(' ').length : 0,
    bodySize: px(body.fontSize),
    documentHeight: Math.round(document.documentElement.scrollHeight),
  };
};

function readBaseline() {
  try {
    return JSON.parse(fs.readFileSync(BASELINE, 'utf8'));
  } catch {
    return { note: 'Эталон раскладки семейств. Обновляется FAMILIES_UPDATE_BASELINE=1 '
      + 'и только осознанно.', tolerance_px: TOLERANCE, measurements: {} };
  }
}

const collected = readBaseline();

// Запись слиянием: работники Playwright — отдельные процессы, каждый со своей
// копией модуля. Прямая запись оставляла в эталоне измерения того, кто
// закончил последним: из сорока пяти сохранялось десять. Ошибка эта в наборе
// уже третья по счёту, и каждый раз она выглядит как «эталон почему-то
// неполный», а не как гонка.
function persist() {
  let previous = { measurements: {} };
  try {
    previous = JSON.parse(fs.readFileSync(BASELINE, 'utf8'));
  } catch { /* эталона ещё нет */ }
  const merged = {
    note: collected.note,
    tolerance_px: TOLERANCE,
    measurements: { ...(previous.measurements || {}), ...collected.measurements },
  };
  fs.writeFileSync(BASELINE, `${JSON.stringify(merged, null, 2)}\n`);
}

test.describe('эталон раскладки семейств', () => {
  // Эталон снят в Chromium и сверяет витрину с самой собой: он существует
  // затем, чтобы поймать наше изменение раскладки, а не разницу движков.
  //
  // Разница движков настоящая и измерена: поле поиска WebKit и Firefox
  // рисуют на три пикселя выше, и высота страницы расходится ровно на эти
  // три. Ослабить допуск ради зелёного значило бы перестать замечать
  // изменения такого же размера в самой витрине — а именно они и опасны.
  // Держать три эталона значило бы сверять браузеры друг с другом.
  //
  // Кросс-браузерность при этом не теряется: axe, увеличение текста,
  // клавиатура, облик и различие семейств идут во всех трёх движках.
  test.skip(({ browserName }) => browserName !== 'chromium',
    'эталон раскладки снят в Chromium и сверяется в нём же');

  for (const family of FAMILIES) {
    for (const surface of SURFACES) {
      for (const width of WIDTHS) {
        const key = `${family}/${surface}/${width}`;
        test(key, async ({ page }) => {
          await page.setViewportSize({ width, height: 900 });
          await page.goto(url(family, surface), { waitUntil: 'load' });
          const now = await page.evaluate(measure);

          if (UPDATE) {
            collected.measurements[key] = now;
            persist();
            test.skip(true, 'эталон обновляется');
            return;
          }

          const было = collected.measurements[key];
          expect(было, `${key}: эталона нет — снимите его осознанно`).toBeTruthy();

          const расхождения = [];
          const сверить = (имя, a, b) => {
            if (a === null || b === null) {
              if (a !== b) расхождения.push(`${имя}: было ${JSON.stringify(a)}, стало ${JSON.stringify(b)}`);
              return;
            }
            if (typeof a === 'number') {
              if (Math.abs(a - b) > TOLERANCE) расхождения.push(`${имя}: было ${a}, стало ${b}`);
              return;
            }
            for (const поле of Object.keys(a)) {
              if (Math.abs(a[поле] - b[поле]) > TOLERANCE) {
                расхождения.push(`${имя}.${поле}: было ${a[поле]}, стало ${b[поле]}`);
              }
            }
          };
          for (const поле of Object.keys(было)) сверить(поле, было[поле], now[поле]);

          expect(расхождения, `${key}:\n  ${расхождения.join('\n  ')}`).toEqual([]);
        });
      }
    }
  }
});

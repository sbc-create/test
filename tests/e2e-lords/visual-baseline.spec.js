// REQ-LORDS-VISUAL-BASELINE: раскладка сравнивается с эталоном, а не осматривается.
//
// Снимки экрана рядом (`lords.spec.js`, «снимки экрана») собираются как
// свидетельство прогона и сравнения ни с чем не ведут — это записано там прямо.
// Свидетельство отвечает на вопрос «как это выглядело», но не на вопрос «что
// изменилось», а именно второй и нужен, чтобы правка темы не уехала молча.
//
// Эталон здесь — числа, а не пиксели. Причина не в удобстве: попиксельное
// сравнение ломается от версии шрифта и сглаживания, и команда привыкает
// перезаписывать эталон не глядя. Числа переживают смену браузера, читаются в
// diff'е глазами и ломаются ровно тогда, когда раскладка действительно
// изменилась.
//
// Обновление эталона — осознанное действие:
//   LORDS_UPDATE_BASELINE=1 npx playwright test --config=playwright.lords.config.js \
//     visual-baseline
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { SITES, url, VIEWPORTS } = require('./helpers');

// Эталон лежит рядом со своим потребителем и отслеживается git'ом. В
// artifacts/ ему не место: этот каталог целиком в .gitignore, и эталон,
// не доехавший до свежего клона, превращает проверку в ошибку чтения файла.
const BASELINE = path.join(__dirname, 'visual-baseline.json');
const UPDATE = process.env.LORDS_UPDATE_BASELINE === '1';

// Допуск в один пиксель — только для длин: округление ширины контейнера пляшет
// на дробных масштабах и само по себе изменением раскладки не является.
const TOLERANCE_PX = 1;

// Пропорция карточки — отношение, а не длина: пиксельный допуск для неё
// бессмыслен.
const TOLERANCE_RATIO = 0.01;

// Поля, которые обязаны совпасть точно. Счётчик колонок сюда входит по прямой
// причине: шесть колонок вместо пяти — это смена плотности витрины, а не
// округление. Общий допуск в один пиксель такую подмену проглатывал, и первая
// же проверка эталона на испорченном значении прошла успешно — то есть эталон
// не проверял ничего.
const EXACT_FIELDS = new Set([
  'columns', 'cardsInFirstRow', 'docWidth', 'bodyFontSize', 'h1FontSize',
  'horizontalScroll',
]);

const ROUTES = [['home', '/'], ['catalog', '/catalog/']];

// Числа собираются в странице: снаружи доступны только те размеры, которые
// движок уже посчитал.
const measure = () => {
  const round = (v) => Math.round(v * 100) / 100;
  const docWidth = document.documentElement.clientWidth;

  const main = document.querySelector('main .container') || document.querySelector('main');
  const mainRect = main ? main.getBoundingClientRect() : null;

  const header = document.querySelector('.site-header');
  const headerRect = header ? header.getBoundingClientRect() : null;

  const cards = [...document.querySelectorAll('.card')];
  const first = cards.length ? cards[0].getBoundingClientRect() : null;

  // Колонки берутся из посчитанной сетки, а не из числа карточек в первом ряду.
  // Разница существенная: на первой странице каталога лежит блок 2025 года из
  // трёх записей, и подсчёт по ряду сообщал бы «три колонки» там, где сетка
  // рассчитана на шесть. Такой эталон молча пропустил бы смену плотности.
  const grid = document.querySelector('.grid');
  let columns = 0;
  if (grid) {
    const template = getComputedStyle(grid).gridTemplateColumns;
    columns = template && template !== 'none' ? template.trim().split(/\s+/).length : 0;
  }
  const cardsInFirstRow = cards.length
    ? cards.filter((c) => Math.round(c.getBoundingClientRect().top)
        === Math.round(cards[0].getBoundingClientRect().top)).length
    : 0;

  const body = getComputedStyle(document.body);
  const h1 = document.querySelector('h1');

  return {
    docWidth,
    contentWidth: mainRect ? round(mainRect.width) : 0,
    gutter: mainRect ? round((docWidth - mainRect.width) / 2) : 0,
    headerHeight: headerRect ? round(headerRect.height) : 0,
    columns,
    cardsInFirstRow,
    cardWidth: first ? round(first.width) : 0,
    cardRatio: first && first.height ? round(first.width / first.height) : 0,
    bodyFontSize: round(parseFloat(body.fontSize)),
    h1FontSize: h1 ? round(parseFloat(getComputedStyle(h1).fontSize)) : 0,
    // Горизонтальная прокрутка — отказ адаптивности, видимый без спора о вкусе.
    horizontalScroll: document.documentElement.scrollWidth > docWidth + 1,
  };
};

test.describe('визуальный эталон раскладки', () => {
  const collected = {};

  for (const id of Object.keys(SITES)) {
    for (const view of VIEWPORTS) {
      for (const [routeName, route] of ROUTES) {
        const key = `${id}/${routeName}/${view.width}`;
        test(`${key}`, async ({ page }) => {
          await page.setViewportSize({ width: view.width, height: view.height });
          await page.goto(url(id, route));
          const actual = await page.evaluate(measure);
          collected[key] = actual;

          // Отказ адаптивности проверяется всегда, эталон ему не нужен.
          expect(actual.horizontalScroll, `${key}: появилась горизонтальная прокрутка`)
            .toBe(false);

          if (UPDATE) { test.skip(true, 'режим обновления эталона'); }

          const baseline = JSON.parse(fs.readFileSync(BASELINE, 'utf8'));
          const expected = baseline.measurements[key];
          expect(expected, `${key}: строки нет в эталоне — обнови эталон осознанно`)
            .toBeTruthy();

          for (const [field, value] of Object.entries(expected)) {
            const label = `${key}.${field}: было ${value}, стало ${actual[field]}`;
            if (EXACT_FIELDS.has(field) || typeof value !== 'number') {
              expect(actual[field], label).toBe(value);
            } else if (field === 'cardRatio') {
              expect(Math.abs(actual[field] - value), label)
                .toBeLessThanOrEqual(TOLERANCE_RATIO);
            } else {
              expect(Math.abs(actual[field] - value), label)
                .toBeLessThanOrEqual(TOLERANCE_PX);
            }
          }
        });
      }
    }
  }

  test.afterAll(() => {
    if (!UPDATE) { return; }
    fs.mkdirSync(path.dirname(BASELINE), { recursive: true });
    fs.writeFileSync(BASELINE, `${JSON.stringify({
      note: 'Эталон раскладки. Обновляется командой LORDS_UPDATE_BASELINE=1 и только осознанно.',
      tolerance_px: TOLERANCE_PX,
      measurements: Object.fromEntries(Object.entries(collected).sort()),
    }, null, 2)}\n`);
  });
});

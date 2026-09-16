// Три семейства обязаны быть разными семействами, а не одной темой в трёх
// красках.
//
// Требование сформулировано владельцем прямо: portal_light, pulse и editorial
// — самостоятельные визуальные семейства, и различие доказывается структурой
// страниц, типографикой, плотностью, карточками, навигацией и композициями.
// Цвет в этот перечень не входит вовсе, и это существенно: перекрасить тему —
// работа на десять минут, которая выглядит как новое семейство и им не
// является.
//
// Поэтому проверка меряет то, что цветом подделать нельзя: размер и высоту
// строки текста, ширину колонки чтения, число колонок сетки, промежутки,
// пропорции и рамки карточек. Совпадение по всем этим величинам означает, что
// семейства одинаковы, чем бы они ни были покрашены.
//
// Стенд отрисован настоящими компонентами приложения и настоящими стилями.
// Он не заменяет приёмку боевой витрины и на неё не претендует: у витрин этих
// семейств нет ни боевого домена, ни окружения, и это внешний блокер.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const STAND = path.join(__dirname, '..', '..', 'blueprints', 'payload-next-multisite',
  'app', 'var', 'family-stand');
const OUT = path.join(__dirname, '..', '..', 'artifacts', 'evidence', 'templates');
fs.mkdirSync(OUT, { recursive: true });

const FAMILIES = ['portal_light', 'pulse', 'editorial'];
const WIDTHS = [390, 768, 1440];

const url = (family) => `file://${path.join(STAND, `${family}.html`)}`;

const collected = { captured_at_utc: null, families: {}, distinctness: [] };

// Запись слиянием, а не перезаписью. Работники Playwright — отдельные
// процессы со своей копией модуля: каждый знает только свои измерения, и
// прямая запись оставляла в файле результат того, кто закончил последним.
// Ровно эта ошибка однажды уже стёрла свидетельства целого прогона.
function save() {
  const file = path.join(OUT, 'family-identity.json');
  let previous = { families: {}, distinctness: [] };
  try {
    previous = JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch { /* файла ещё нет — это первый работник */ }
  const merged = {
    captured_at_utc: new Date().toISOString(),
    families: { ...(previous.families || {}), ...collected.families },
    distinctness: [...(previous.distinctness || []), ...collected.distinctness].filter(
      (entry, index, all) =>
        all.findIndex((other) => other.pair.join('|') === entry.pair.join('|')) === index,
    ),
  };
  fs.writeFileSync(file, `${JSON.stringify(merged, null, 2)}\n`);
}

/** Метрики семейства: всё, что нельзя изменить одной лишь краской. */
const measure = () => {
  const px = (value) => Math.round(parseFloat(value) * 100) / 100;
  const body = getComputedStyle(document.body);
  const lede = document.querySelector('.lede');
  const h1 = document.querySelector('h1');
  const grid = document.querySelector('.grid');
  const card = document.querySelector('.card');
  const poster = document.querySelector('.card__poster');
  const header = document.querySelector('.site-header');
  const nav = document.querySelectorAll('.site-header a');
  const gridStyle = grid ? getComputedStyle(grid) : null;
  const cardStyle = card ? getComputedStyle(card) : null;
  const posterBox = poster ? poster.getBoundingClientRect() : null;

  return {
    typography: {
      bodySize: px(body.fontSize),
      bodyLineHeight: px(body.lineHeight),
      headingSize: h1 ? px(getComputedStyle(h1).fontSize) : null,
      ledeSize: lede ? px(getComputedStyle(lede).fontSize) : null,
      ledeWidth: lede ? Math.round(lede.getBoundingClientRect().width) : null,
      fontFamily: body.fontFamily.split(',')[0].replace(/["']/g, ''),
    },
    density: {
      columns: gridStyle ? gridStyle.gridTemplateColumns.split(' ').length : null,
      gap: gridStyle ? px(gridStyle.gap || gridStyle.rowGap) : null,
      containerWidth: Math.round(
        (document.querySelector('.container') || document.body).getBoundingClientRect().width),
    },
    card: {
      ratio: posterBox && posterBox.height
        ? Math.round((posterBox.width / posterBox.height) * 100) / 100
        : null,
      radius: cardStyle ? px(cardStyle.borderTopLeftRadius) : null,
      borderTop: cardStyle ? px(cardStyle.borderTopWidth) : null,
      borderBottom: cardStyle ? px(cardStyle.borderBottomWidth) : null,
    },
    navigation: {
      links: nav.length,
      headerHeight: header ? Math.round(header.getBoundingClientRect().height) : null,
      direction: header ? getComputedStyle(header).display : null,
    },
  };
};

test.describe('семейства измеримы', () => {
  for (const family of FAMILIES) {
    for (const width of WIDTHS) {
      test(`${family}@${width}: страница собирается и меряется`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto(url(family), { waitUntil: 'load' });
        const metrics = await page.evaluate(measure);
        collected.families[`${family}@${width}`] = metrics;
        save();
        // Страница обязана быть страницей, а не набором стилей без содержимого.
        expect(await page.locator('.card').count(),
          `${family}: карточки не отрисованы`).toBeGreaterThan(0);
        expect(metrics.typography.bodySize,
          `${family}: размер текста не вычислен`).toBeGreaterThan(0);
        expect(await page.locator('.site-header a').count(),
          `${family}: навигации нет`).toBeGreaterThan(0);
      });
    }
  }
});

test.describe('семейства различимы не только краской', () => {
  // Величины, по которым семейства обязаны расходиться. Одного совпадения
  // мало для вывода, поэтому считается доля различающихся признаков.
  const SIGNALS = [
    ['typography.bodySize', (m) => m.typography.bodySize],
    ['typography.bodyLineHeight', (m) => m.typography.bodyLineHeight],
    ['typography.headingSize', (m) => m.typography.headingSize],
    ['typography.ledeWidth', (m) => m.typography.ledeWidth],
    ['density.columns', (m) => m.density.columns],
    ['density.gap', (m) => m.density.gap],
    ['card.ratio', (m) => m.card.ratio],
    ['card.radius', (m) => m.card.radius],
    ['card.borderBottom', (m) => m.card.borderBottom],
  ];

  for (const [a, b] of [['portal_light', 'pulse'], ['portal_light', 'editorial'],
    ['pulse', 'editorial']]) {
    test(`${a} и ${b} — разные семейства`, async ({ page }) => {
      const metrics = {};
      for (const family of [a, b]) {
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto(url(family), { waitUntil: 'load' });
        metrics[family] = await page.evaluate(measure);
      }
      const differing = [];
      const same = [];
      for (const [name, pick] of SIGNALS) {
        const left = pick(metrics[a]);
        const right = pick(metrics[b]);
        (left !== right ? differing : same).push(`${name}: ${left} / ${right}`);
      }
      collected.distinctness.push({ pair: [a, b], differing, same });
      save();
      // Порог назван и обоснован: из девяти конструктивных признаков семейства
      // обязаны расходиться минимум по четырём. Меньше — это одна тема в двух
      // красках, как бы ни отличались цвета.
      expect(differing.length,
        `${a} и ${b} совпадают по ${same.length} признакам из ${SIGNALS.length}:\n  `
        + same.join('\n  ')).toBeGreaterThanOrEqual(4);
    });
  }
});

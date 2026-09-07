/**
 * Различие продуктов: разные витрины, а не одна вёрстка в трёх красках.
 *
 * Требование владельца названо прямо, и цвет в него не входит: различие
 * доказывается композицией, навигацией, типографической шкалой, плотностью,
 * формой карточек и способом показа метаданных. Перекрасить тему — работа на
 * десять минут, которая выглядит новым продуктом и им не является.
 *
 * Поэтому меряется то, что краской подделать нельзя. Числовое сравнение при
 * этом не единственное доказательство: рядом снимаются страницы, и рубрика в
 * отчёте называет словами, чем витрины отличаются. Одно число без снимка
 * убеждает не больше, чем снимок без числа.
 *
 * Запуск:
 *   node scripts/product_distinctness.cjs
 */
const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'artifacts', 'evidence', 'products');
fs.mkdirSync(OUT, { recursive: true });

const PRODUCTS = {
  'zona-cinema': 8903,
  'animedia-portal': 8904,
  'basis-video': 8905,
};

/** Признаки, которые нельзя изменить одной лишь краской. */
const measure = () => {
  const px = (v) => Math.round(parseFloat(v) * 100) / 100;
  const body = getComputedStyle(document.body);
  const h1 = document.querySelector('h1');
  const h2 = document.querySelector('h2');
  const card = document.querySelector('.card');
  const poster = document.querySelector('.card__poster, .card-image');
  const grid = document.querySelector('.grid, .card-grid, .card-rail');
  const header = document.querySelector('header, .site-header');
  const gridStyle = grid ? getComputedStyle(grid) : null;
  const posterBox = poster ? poster.getBoundingClientRect() : null;
  const cardStyle = card ? getComputedStyle(card) : null;

  return {
    typography: {
      body: px(body.fontSize),
      lineHeight: px(body.lineHeight),
      h1: h1 ? px(getComputedStyle(h1).fontSize) : null,
      h2: h2 ? px(getComputedStyle(h2).fontSize) : null,
      scale: h1 && h2
        ? Math.round((parseFloat(getComputedStyle(h1).fontSize)
          / parseFloat(getComputedStyle(h2).fontSize)) * 100) / 100
        : null,
    },
    density: {
      container: Math.round((document.querySelector('.container, .wrap, main')
        || document.body).getBoundingClientRect().width),
      gap: gridStyle ? px(gridStyle.gap || gridStyle.columnGap || '0') : null,
      flow: gridStyle ? gridStyle.gridAutoFlow : null,
      columns: gridStyle && gridStyle.gridTemplateColumns
        ? gridStyle.gridTemplateColumns.split(' ').length : null,
    },
    card: {
      ratio: posterBox && posterBox.height
        ? Math.round((posterBox.width / posterBox.height) * 100) / 100 : null,
      radius: cardStyle ? px(cardStyle.borderTopLeftRadius) : null,
    },
    composition: {
      sections: document.querySelectorAll('section').length,
      navLinks: header ? header.querySelectorAll('a').length : 0,
      headerHeight: header ? Math.round(header.getBoundingClientRect().height) : null,
      hasHero: !!document.querySelector('.hero, .hero--catalog, [class*="hero"]'),
      hasRail: !!document.querySelector('.card-rail, .rail'),
      hasSearchInHeader: !!(header && header.querySelector('input[type="search"], #q')),
      documentHeight: Math.round(document.documentElement.scrollHeight),
    },
    canvas: body.backgroundColor,
  };
};

const SIGNALS = [
  ['typography.body', (m) => m.typography.body],
  ['typography.h1', (m) => m.typography.h1],
  ['typography.scale', (m) => m.typography.scale],
  ['density.container', (m) => m.density.container],
  ['density.gap', (m) => m.density.gap],
  ['density.flow', (m) => m.density.flow],
  ['card.ratio', (m) => m.card.ratio],
  ['card.radius', (m) => m.card.radius],
  ['composition.sections', (m) => m.composition.sections],
  ['composition.navLinks', (m) => m.composition.navLinks],
  ['composition.headerHeight', (m) => m.composition.headerHeight],
  ['composition.hasRail', (m) => m.composition.hasRail],
];

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const metrics = {};
  for (const [product, port] of Object.entries(PRODUCTS)) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: 'load' });
    metrics[product] = await page.evaluate(measure);
    await context.close();
  }
  await browser.close();

  const pairs = [];
  const names = Object.keys(PRODUCTS);
  for (let i = 0; i < names.length; i += 1) {
    for (let j = i + 1; j < names.length; j += 1) {
      const a = names[i];
      const b = names[j];
      const differing = [];
      const same = [];
      for (const [name, pick] of SIGNALS) {
        const left = pick(metrics[a]);
        const right = pick(metrics[b]);
        (String(left) !== String(right) ? differing : same).push(`${name}: ${left} / ${right}`);
      }
      pairs.push({ pair: [a, b], differing, same });
    }
  }

  fs.writeFileSync(path.join(OUT, 'distinctness.json'), `${JSON.stringify({
    captured_at_utc: new Date().toISOString(),
    note: 'Цвет в признаки не входит: перекрасить тему не значит сделать новый продукт.',
    threshold: 6,
    signals: SIGNALS.map(([n]) => n),
    metrics,
    pairs,
  }, null, 2)}\n`);

  let bad = 0;
  for (const p of pairs) {
    const ok = p.differing.length >= 6;
    if (!ok) bad += 1;
    console.log(`${p.pair.join(' и ')}: различий ${p.differing.length} из ${SIGNALS.length}`
      + `${ok ? '' : ' — НЕДОСТАТОЧНО'}`);
    if (!ok) for (const s of p.same) console.log(`    = ${s}`);
  }
  process.exit(bad ? 1 : 0);
})();

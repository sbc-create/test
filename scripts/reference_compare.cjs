#!/usr/bin/env node
/**
 * Сличение кандидата с зафиксированным пакетом эталона.
 *
 * ## Чего здесь СОЗНАТЕЛЬНО нет
 *
 * Попиксельного SSIM между эталоном и кандидатом. У них разное содержимое:
 * другие постеры, другие названия, другое число записей. Совпадение пикселей
 * в такой паре означало бы, что мы скопировали чужой контент, а расхождение не
 * означает ничего. Методика невалидна для этой пары, и подменять ею измерение
 * было бы имитацией проверки.
 *
 * ## Что здесь есть
 *
 * Геометрия и типографика — то, что эталонный пакет и измерял: ширина
 * контейнера, желоба, высота шапки и подвала, размеры и начертания шрифтов,
 * цвета, сетки, доли карточек, переполнение. Эти величины сравнимы при разном
 * содержимом, потому что описывают раскладку, а не картинку.
 *
 * Плюс снимки рядом (эталон | кандидат) для человеческого просмотра. Метрики
 * его не заменяют и заменять не должны.
 *
 * Расхождения не округляются в свою пользу: шрифт, высота плеера, блок 404,
 * H1 и отступы объявляются различающимися, если различаются.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { chromium } = require(process.env.PW_ROOT
  ? path.join(process.env.PW_ROOT, 'playwright')
  : 'playwright');

const OUT = process.env.CMP_OUT || './artifacts/reference-compare';

/** Проба — та же, что снимала эталон, слово в слово по смыслу. */
const PROBE = `(() => {
  const doc = document.documentElement;
  const roleStyle = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const s = getComputedStyle(el);
    return { fontSize: s.fontSize, lineHeight: s.lineHeight, fontWeight: s.fontWeight,
             fontFamily: s.fontFamily, color: s.color };
  };
  const всеКандидаты = [...document.querySelectorAll('body *')].filter((el) => {
    const r = el.getBoundingClientRect();
    return r.width > 40 && r.width < doc.clientWidth - 1 && r.height > 100;
  });
  const main = всеКандидаты.reduce((a, b) =>
    (a && a.getBoundingClientRect().width >= b.getBoundingClientRect().width ? a : b), null)
    || document.body;
  const mainRect = main.getBoundingClientRect();
  const header = document.querySelector('header, .header, [role="banner"], #header');
  const footer = document.querySelector('footer, .footer, #footer');
  // Селекторы карточек дополнены нашими семействами: у эталона классы свои,
  // и общий список не находит ни .c, ни .zt, ни .zr. Без этого доли карточек
  // у кандидата всегда выходили бы нулями — и это была бы ошибка пробы, а не
  // свойство вёрстки.
  const карточки = [...document.querySelectorAll(
    '.card, .th-item, .short, .movie, article, a.c, a.zt, a.zr')];
  const доли = {};
  for (const c of карточки) {
    const r = c.getBoundingClientRect();
    if (r.width > 4 && r.height > 4) {
      const k = (r.width / r.height).toFixed(2); доли[k] = (доли[k] || 0) + 1;
    }
  }
  const постеры = [...document.querySelectorAll(
    '.card img, .th-img img, .short img, .poster img, img.poster, .c__p img, .zt__p img, .zr__p img')];
  const долиП = {};
  for (const p of постеры) {
    const r = p.getBoundingClientRect();
    if (r.width > 4 && r.height > 4) {
      const k = (r.width / r.height).toFixed(2); долиП[k] = (долиП[k] || 0) + 1;
    }
  }
  const сетки = [...document.querySelectorAll('*')]
    .filter((el) => getComputedStyle(el).display === 'grid').slice(0, 12)
    .map((el) => ({ columns: getComputedStyle(el).gridTemplateColumns.split(' ').filter(Boolean).length,
                    gap: getComputedStyle(el).gap, children: el.children.length }));
  const плеер = document.querySelector('iframe, video, video-player, .player, #player, [data-player]');
  const pr = плеер ? плеер.getBoundingClientRect() : null;
  return {
    documentWidth: doc.clientWidth,
    contentWidth: Math.round(mainRect.width),
    contentMaxWidth: getComputedStyle(main).maxWidth,
    contentSelector: String(main.className || main.tagName).slice(0, 40),
    gutter: Math.round((doc.clientWidth - mainRect.width) / 2),
    scrollHeight: doc.scrollHeight,
    horizontalOverflow: doc.scrollWidth > doc.clientWidth + 1,
    header: header ? { height: Math.round(header.getBoundingClientRect().height),
                       position: getComputedStyle(header).position,
                       sticky: getComputedStyle(header).position === 'sticky' } : null,
    footer: footer ? { height: Math.round(footer.getBoundingClientRect().height) } : null,
    typography: { body: roleStyle('body'), h1: roleStyle('h1'), h2: roleStyle('h2'),
                  h3: roleStyle('h3'), a: roleStyle('a'), p: roleStyle('p'),
                  button: roleStyle('button, .btn, input[type="submit"]') },
    colors: { background: getComputedStyle(document.body).backgroundColor,
              text: getComputedStyle(document.body).color },
    cardAspectRatios: доли, posterAspectRatios: долиП, cards: карточки.length,
    grids: сетки,
    sectionCount: document.querySelectorAll('section').length,
    linkCount: document.querySelectorAll('a[href]').length,
    imageCount: document.querySelectorAll('img').length,
    player: pr ? { width: Math.round(pr.width), height: Math.round(pr.height),
                   aspectRatio: +(pr.width / Math.max(1, pr.height)).toFixed(2),
                   tag: плеер.tagName.toLowerCase() } : null,
  };
})()`;

/** Различия, которые нельзя сглаживать. Каждое — со своим допуском и причиной. */
const СВЕРКИ = [
  { имя: 'ширина контейнера', путь: m => m.contentWidth, допуск: 40, ед: 'px' },
  { имя: 'желоб', путь: m => m.gutter, допуск: 40, ед: 'px' },
  { имя: 'высота шапки', путь: m => m.header && m.header.height, допуск: 12, ед: 'px' },
  { имя: 'шапка липкая', путь: m => m.header && m.header.sticky, точное: true },
  { имя: 'высота подвала', путь: m => m.footer && m.footer.height, допуск: 60, ед: 'px' },
  { имя: 'кегль body', путь: m => m.typography.body && parseFloat(m.typography.body.fontSize), допуск: 1, ед: 'px' },
  { имя: 'кегль h1', путь: m => m.typography.h1 && parseFloat(m.typography.h1.fontSize), допуск: 4, ед: 'px' },
  { имя: 'начертание h1', путь: m => m.typography.h1 && m.typography.h1.fontWeight, точное: true },
  { имя: 'семейство шрифта body', путь: m => m.typography.body && m.typography.body.fontFamily.split(',')[0], точное: true },
  { имя: 'фон страницы', путь: m => m.colors.background, точное: true },
  { имя: 'переполнение по горизонтали', путь: m => m.horizontalOverflow, точное: true },
  { имя: 'доля плеера', путь: m => m.player && m.player.aspectRatio, допуск: 0.15 },
  { имя: 'высота плеера', путь: m => m.player && m.player.height, допуск: 80, ед: 'px' },
];

function сверить(эталон, кандидат) {
  const строки = [];
  for (const с of СВЕРКИ) {
    let a, b;
    try { a = с.путь(эталон); } catch (e) { a = null; }
    try { b = с.путь(кандидат); } catch (e) { b = null; }
    if (a === null || a === undefined || b === null || b === undefined) {
      строки.push({ признак: с.имя, эталон: a, кандидат: b, вердикт: 'НЕТ ДАННЫХ' });
      continue;
    }
    let совпало;
    if (с.точное) совпало = String(a) === String(b);
    else совпало = Math.abs(Number(a) - Number(b)) <= с.допуск;
    строки.push({ признак: с.имя, эталон: a, кандидат: b,
                  вердикт: совпало ? 'БЛИЗКО' : 'РАСХОЖДЕНИЕ',
                  допуск: с.допуск === undefined ? 'точное' : с.допуск });
  }
  return строки;
}

async function main() {
  const план = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const эталон = JSON.parse(fs.readFileSync(план.reference_measurements, 'utf8'));
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const page = await (await browser.newContext()).newPage();
  const отчёт = { reference: эталон.base, candidate: план.base, pairs: [] };

  for (const пара of план.pairs) {
    const эталонный = эталон.archetypes[пара.reference];
    if (!эталонный) { отчёт.pairs.push({ ...пара, skipped: 'нет архетипа в эталоне' }); continue; }
    for (const vp of план.viewports) {
      const измЭт = эталонный.viewports[String(vp)];
      if (!измЭт) continue;
      await page.setViewportSize({ width: vp, height: 900 });
      await page.goto(план.base + пара.candidate, { waitUntil: 'load', timeout: 60000 });
      await page.waitForTimeout(1500);
      const измКан = await page.evaluate(PROBE);
      const имя = `${пара.reference}-${vp}`;
      await page.screenshot({ path: path.join(OUT, `cand-${имя}.png`), fullPage: false });
      отчёт.pairs.push({
        reference: пара.reference, candidate: пара.candidate, viewport: vp,
        reference_screenshot: измЭт.screenshot, candidate_screenshot: `cand-${имя}.png`,
        comparison: сверить(измЭт, измКан),
        candidate_measurements: измКан,
      });
    }
  }
  await browser.close();
  fs.writeFileSync(path.join(OUT, 'reference-compare.json'), JSON.stringify(отчёт, null, 1));

  let близко = 0, расх = 0, нет = 0;
  const поПризнаку = {};
  for (const п of отчёт.pairs) {
    for (const с of п.comparison || []) {
      if (с.вердикт === 'БЛИЗКО') близко++;
      else if (с.вердикт === 'РАСХОЖДЕНИЕ') { расх++; (поПризнаку[с.признак] = поПризнаку[с.признак] || []).push(`${п.reference}@${п.viewport}: ${с.эталон} → ${с.кандидат}`); }
      else нет++;
    }
  }
  console.log(`сверок: близко=${близко} расхождений=${расх} без данных=${нет}`);
  for (const [признак, случаи] of Object.entries(поПризнаку)) {
    console.log(`  РАСХОЖДЕНИЕ ${признак} (${случаи.length}): ${случаи[0]}`);
  }
  console.log(`отчёт: ${path.join(OUT, 'reference-compare.json')}`);
}

main().catch(e => { console.error(e); process.exit(1); });

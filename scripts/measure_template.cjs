/**
 * Замеры витрины в тех же полях, что и закреплённый референс.
 *
 * Сравнивать можно только одинаково измеренное. Поля и способ их получения
 * повторяют `docs/product/LORDS-REFERENCE-MEASUREMENTS.md`: ширина контента,
 * gutter, высота шапки, типографика по ролям, пропорции карточек, сетки,
 * число секций, ссылок и изображений, геометрия плеера.
 *
 * Снимок и числа собираются в одном проходе: снимок без чисел не позволяет
 * утверждать «нет горизонтальной прокрутки», числа без снимка не показывают,
 * что страница выглядит незаконченной.
 *
 * Запуск: node measure_template.cjs <базовый-адрес> <выходной-каталог> [метка]
 */
const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const BASE = process.argv[2];
const OUT = process.argv[3];
const LABEL = process.argv[4] || 'current';
if (!BASE || !OUT) { console.error('нужны базовый адрес и выходной каталог'); process.exit(2); }

const WIDTHS = [360, 390, 768, 1024, 1366, 1440, 1920];
const PAGES = [
  ['home', '/'],
  ['catalog', '/catalog/'],
  ['genres', '/genres/'],
  ['search', '/search/'],
  ['not-found', '/404.html'],
];

const probe = () => {
  const doc = document.documentElement;
  const cs = (el) => (el ? getComputedStyle(el) : null);
  const roleStyle = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const s = getComputedStyle(el);
    return { fontSize: s.fontSize, lineHeight: s.lineHeight, fontWeight: s.fontWeight,
             fontFamily: s.fontFamily, color: s.color };
  };
  // Ширина контента — у блока, который РЕАЛЬНО ограничивает вёрстку.
  //
  // `main` тянется во всю ширину окна, и измерять его значит всегда получать
  // ширину вьюпорта: контейнер 1240 px и контейнер 1100 px выглядели бы
  // одинаково. Берём элемент с непустым max-width, самый широкий из таких.
  const кандидаты = [...document.querySelectorAll('.container, main, .layout, .page, .wrap')];
  const ограничивающие = кандидаты.filter((el) => {
    const mw = getComputedStyle(el).maxWidth;
    return mw && mw !== 'none';
  });
  const main = (ограничивающие.length ? ограничивающие : кандидаты)
    .reduce((a, b) => (a && a.getBoundingClientRect().width >= b.getBoundingClientRect().width ? a : b),
            null) || document.body;
  const mainRect = main.getBoundingClientRect();
  const mainMaxWidth = getComputedStyle(main).maxWidth;
  const mainSelector = main.className || main.tagName;
  const header = document.querySelector('header, .header, [role="banner"]');
  const cards = [...document.querySelectorAll('.card, .card-item, article.card')];
  const ratios = {};
  for (const c of cards) {
    const r = c.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) {
      const k = (r.width / r.height).toFixed(2);
      ratios[k] = (ratios[k] || 0) + 1;
    }
  }
  const posters = [...document.querySelectorAll('.card img, .card__poster, .poster')];
  const posterRatios = {};
  for (const p of posters) {
    const r = p.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) {
      const k = (r.width / r.height).toFixed(2);
      posterRatios[k] = (posterRatios[k] || 0) + 1;
    }
  }
  const grids = [...document.querySelectorAll('*')]
    .filter((el) => getComputedStyle(el).display === 'grid')
    .map((el) => ({
      selector: el.className || el.tagName,
      columns: getComputedStyle(el).gridTemplateColumns.split(' ').filter(Boolean).length,
      template: getComputedStyle(el).gridTemplateColumns,
    }));
  // Перекрытия и обрезанные управляющие элементы.
  const controls = [...document.querySelectorAll('a, button, input, select, [tabindex]')];
  let clipped = 0, offscreen = 0;
  // Элемент внутри прокручиваемого по горизонтали блока не «за экраном»: это
  // карусель, и он достижим прокруткой. Считать её содержимое недоступным
  // значило бы объявить дефектом саму карусель — измерено на главной: все
  // двенадцать «недоступных» ссылок лежали в `.rail`.
  const вПрокрутке = (el) => {
    for (let p = el.parentElement; p; p = p.parentElement) {
      if (/(auto|scroll)/.test(getComputedStyle(p).overflowX)) return true;
    }
    return false;
  };
  for (const c of controls) {
    const r = c.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if ((r.right > doc.clientWidth + 1 || r.left < -1) && !вПрокрутке(c)) offscreen++;
    const p = c.closest('[style*="overflow"], .clip');
    if (p) {
      const pr = p.getBoundingClientRect();
      if (r.bottom > pr.bottom + 1 || r.right > pr.right + 1) clipped++;
    }
  }
  return {
    documentWidth: doc.clientWidth,
    contentWidth: Math.round(mainRect.width),
    contentMaxWidth: mainMaxWidth,
    contentSelector: mainSelector,
    gutter: Math.round((doc.clientWidth - mainRect.width) / 2),
    scrollHeight: doc.scrollHeight,
    horizontalOverflow: doc.scrollWidth > doc.clientWidth + 1,
    header: header ? { height: Math.round(header.getBoundingClientRect().height),
                       position: getComputedStyle(header).position } : null,
    typography: { body: roleStyle('body'), h1: roleStyle('h1'), h2: roleStyle('h2'),
                  h3: roleStyle('h3'), a: roleStyle('a'), p: roleStyle('p'),
                  button: roleStyle('button, .button, .btn') },
    colors: { background: getComputedStyle(document.body).backgroundColor,
              text: getComputedStyle(document.body).color },
    cardAspectRatios: ratios,
    posterAspectRatios: posterRatios,
    cards: cards.length,
    grids,
    sectionCount: document.querySelectorAll('section').length,
    linkCount: document.querySelectorAll('a[href]').length,
    imageCount: document.querySelectorAll('img').length,
    paginationLinks: document.querySelectorAll('.pagination a, nav.pagination a').length,
    brokenImages: [...document.querySelectorAll('img')]
      .filter((i) => i.complete && i.naturalWidth === 0).length,
    controlsOffscreen: offscreen,
    controlsClipped: clipped,
    player: (() => {
      const el = document.querySelector('iframe, video, .player, [data-player]');
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { width: Math.round(r.width), height: Math.round(r.height),
               aspectRatio: +(r.width / Math.max(1, r.height)).toFixed(2), tag: el.tagName.toLowerCase() };
    })(),
  };
};

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const результат = { label: LABEL, base: BASE, measured_at: new Date().toISOString(), pages: {} };
  for (const [имя, путь] of PAGES) {
    результат.pages[имя] = { url: BASE + путь, viewports: {} };
    for (const w of WIDTHS) {
      const ctx = await browser.newContext({ viewport: { width: w, height: 900 },
                                             deviceScaleFactor: 1 });
      const page = await ctx.newPage();
      const ошибки = [];
      const неудачные = [];
      page.on('console', (m) => { if (m.type() === 'error') ошибки.push(m.text().slice(0, 200)); });
      page.on('requestfailed', (r) => неудачные.push(r.url().slice(0, 160)));
      let статус = null;
      try {
        const ответ = await page.goto(BASE + путь, { waitUntil: 'networkidle', timeout: 30000 });
        статус = ответ ? ответ.status() : null;
        const данные = await page.evaluate(probe);
        const снимок = path.join(OUT, `${LABEL}-${имя}-${w}.png`);
        await page.screenshot({ path: снимок, fullPage: true });
        данные.httpStatus = статус;
        данные.consoleErrors = ошибки;
        данные.failedRequests = неудачные;
        данные.screenshot = path.basename(снимок);
        данные.screenshotSha256 = crypto.createHash('sha256')
          .update(fs.readFileSync(снимок)).digest('hex');
        результат.pages[имя].viewports[w] = данные;
      } catch (e) {
        результат.pages[имя].viewports[w] = { error: String(e).slice(0, 300), httpStatus: статус };
      }
      await ctx.close();
    }
  }
  await browser.close();
  const файл = path.join(OUT, `measurements-${LABEL}.json`);
  fs.writeFileSync(файл, JSON.stringify(результат, null, 1));
  const sha = crypto.createHash('sha256').update(fs.readFileSync(файл)).digest('hex');
  console.log(`замеры: ${файл}`);
  console.log(`manifest_sha256=${sha}`);
})();

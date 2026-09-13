/**
 * Съёмка эталона: снимки и геометрия публичного референса.
 *
 * Только чтение. Ни авторизации, ни обхода защиты, ни загрузки видео. Из
 * страницы сохраняются снимок и измерения интерфейса; тексты, изображения и
 * идентификаторы референса отдельно не сохраняются — нужна структурная мера,
 * а не чужие материалы. Это записано в `inventory/reference-sources.yaml` и
 * здесь не ослабляется.
 *
 * Измеряется тот же набор полей, что и у нашей витрины
 * (`scripts/measure_template.cjs`): сравнивать можно только одинаково
 * измеренное.
 *
 * Запуск: node scripts/capture_reference.cjs <база> <выходной-каталог> <json-архетипов>
 */
const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const БАЗА = process.argv[2];
const OUT = process.argv[3];
const АРХЕТИПЫ = JSON.parse(process.argv[4]);
const БЕЗ_СНИМКОВ = process.argv[5] === '--no-screenshots';
const WIDTHS = [360, 390, 768, 1024, 1366, 1440, 1920];

if (!БАЗА || !OUT) {
  console.error('нужны база и выходной каталог');
  process.exit(2);
}

const probe = () => {
  const doc = document.documentElement;
  const roleStyle = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const s = getComputedStyle(el);
    return { fontSize: s.fontSize, lineHeight: s.lineHeight, fontWeight: s.fontWeight,
             fontFamily: s.fontFamily, color: s.color };
  };
  // Ограничивающий блок ищется по НАБЛЮДАЕМОМУ признаку, а не по списку
  // классов.
  //
  // Список классов уже дважды выбрал не тот элемент: сначала `main`, шириной
  // во всё окно, потом `main.glavnoe` — внутренний блок эталона шириной 370
  // при настоящем контейнере 380. Классы у чужого сайта свои, и угадывать их
  // бессмысленно. Признак контейнера: он уже окна, он высокий, и он самый
  // широкий из таких.
  const всеКандидаты = [...document.querySelectorAll('body *')].filter((el) => {
    const r = el.getBoundingClientRect();
    return r.width > 40 && r.width < doc.clientWidth - 1 && r.height > 100;
  });
  const main = всеКандидаты
    .reduce((a, b) => (a && a.getBoundingClientRect().width >= b.getBoundingClientRect().width ? a : b), null)
    || document.body;
  const mainRect = main.getBoundingClientRect();
  const header = document.querySelector('header, .header, [role="banner"], #header');
  const footer = document.querySelector('footer, .footer, #footer');
  const карточки = [...document.querySelectorAll('.card, .th-item, .short, .movie, article')];
  const доли = {};
  for (const c of карточки) {
    const r = c.getBoundingClientRect();
    if (r.width > 4 && r.height > 4) {
      const k = (r.width / r.height).toFixed(2);
      доли[k] = (доли[k] || 0) + 1;
    }
  }
  const постеры = [...document.querySelectorAll('.card img, .th-img img, .short img, .poster img, img.poster')];
  const долиПостеров = {};
  for (const p of постеры) {
    const r = p.getBoundingClientRect();
    if (r.width > 4 && r.height > 4) {
      const k = (r.width / r.height).toFixed(2);
      долиПостеров[k] = (долиПостеров[k] || 0) + 1;
    }
  }
  const сетки = [...document.querySelectorAll('*')]
    .filter((el) => getComputedStyle(el).display === 'grid')
    .slice(0, 12)
    .map((el) => ({ columns: getComputedStyle(el).gridTemplateColumns.split(' ').filter(Boolean).length,
                    gap: getComputedStyle(el).gap,
                    children: el.children.length }));
  const плеер = document.querySelector('iframe, video, video-player, .player, #player');
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
    cardAspectRatios: доли,
    posterAspectRatios: долиПостеров,
    cards: карточки.length,
    grids: сетки,
    sectionCount: document.querySelectorAll('section').length,
    linkCount: document.querySelectorAll('a[href]').length,
    imageCount: document.querySelectorAll('img').length,
    paginationLinks: document.querySelectorAll('.pagination a, .navigation a, .pages a').length,
    player: pr ? { width: Math.round(pr.width), height: Math.round(pr.height),
                   aspectRatio: +(pr.width / Math.max(1, pr.height)).toFixed(2),
                   tag: плеер.tagName.toLowerCase() } : null,
  };
};

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const результат = { base: БАЗА, captured_at: new Date().toISOString(), archetypes: {} };
  for (const [архетип, путь] of Object.entries(АРХЕТИПЫ)) {
    результат.archetypes[архетип] = { url: БАЗА + путь, viewports: {} };
    for (const w of WIDTHS) {
      const ctx = await browser.newContext({ viewport: { width: w, height: 900 },
                                             deviceScaleFactor: 1 });
      const page = await ctx.newPage();
      try {
        const ответ = await page.goto(БАЗА + путь, { waitUntil: 'domcontentloaded', timeout: 30000 });
        // Сеть внешнего сайта может не затихать вовсе (реклама, счётчики).
        // Ждём разумную паузу после загрузки разметки, а не тишины: иначе
        // съёмка не завершается, и эталона не будет вовсе.
        await page.waitForTimeout(1200);
        const данные = await page.evaluate(probe);
        данные.httpStatus = ответ ? ответ.status() : null;
        const имя = `ref-${архетип}-${w}.png`;
        if (!БЕЗ_СНИМКОВ) {
          await page.screenshot({ path: path.join(OUT, имя), fullPage: true });
        }
        if (fs.existsSync(path.join(OUT, имя))) {
          данные.screenshot = имя;
          данные.screenshotSha256 = crypto.createHash('sha256')
            .update(fs.readFileSync(path.join(OUT, имя))).digest('hex');
          данные.screenshotBytes = fs.statSync(path.join(OUT, имя)).size;
        }
        результат.archetypes[архетип].viewports[w] = данные;
      } catch (e) {
        результат.archetypes[архетип].viewports[w] = { error: String(e).slice(0, 200) };
      }
      await ctx.close();
    }
    // Запись после каждого архетипа: прерванный прогон не должен терять всё
    // снятое. Манифест дописывается заново — он мал.
    fs.writeFileSync(path.join(OUT, 'reference-measurements.json'),
                     JSON.stringify(результат, null, 1));
    console.log(`снят: ${архетип}`);
  }
  await browser.close();
  const файл = path.join(OUT, 'reference-measurements.json');
  fs.writeFileSync(файл, JSON.stringify(результат, null, 1));
  const sha = crypto.createHash('sha256').update(fs.readFileSync(файл)).digest('hex');
  console.log(`манифест: ${файл}`);
  console.log(`manifest_sha256=${sha}`);
})();

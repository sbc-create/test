/**
 * Браузерная матрица Yummy: маршруты × ширины, измерение фактического DOM.
 *
 * Почему не «проверка под известный breakpoint»
 * ---------------------------------------------
 *
 * Проверка, написанная под уже известное значение в CSS, доказывает, что CSS
 * не изменился, и ничего не говорит о том, что видит посетитель. Здесь
 * измеряется фактический DOM: `scrollWidth`, прямоугольники карточек, число
 * колонок сетки, реальные размеры изображений. Совпадение с ожиданием — вывод
 * из измерения, а не его условие.
 *
 * Что снимается на каждой паре «маршрут × ширина»
 * ----------------------------------------------
 *
 * * горизонтальное переполнение документа и самый широкий виновный узел;
 * * полностраничный кадр (before/after сравниваются кадрами, а не словами);
 * * заголовки: число H1 и порядок уровней;
 * * изображения: naturalWidth, соотношение сторон, растягивание, alt, lazy;
 * * обрезанный текст (`overflow: hidden` при переполнении содержимого);
 * * дубли ID, скрытые интерактивные элементы, размеры целей;
 * * ошибки консоли, необработанные исключения и неудавшиеся запросы;
 * * инвентарь ссылок — для отдельной проверки «куда они ведут».
 *
 * axe запускается отдельным флагом: дерево доступности от ширины почти не
 * зависит, и гонять его на всех шести — шум, который перестают читать.
 */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const axeSource = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');

function arg(name, fallback = null) {
  const i = process.argv.indexOf(name);
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}
const has = (name) => process.argv.includes(name);

const BASE = arg('--base');
const OUT = arg('--out');
const ROUTES_FILE = arg('--routes');
const WIDTHS = (arg('--widths', '320,390,768,1024,1440,1920')).split(',').map(Number);
const AXE_WIDTHS = (arg('--axe-widths', '390,1440')).split(',').map(Number);
const SHOTS = !has('--no-screenshots');
const EXECUTABLE = process.env.FACTORY_CHROMIUM || null;
const LABEL = arg('--label', 'run');

if (!BASE || !OUT || !ROUTES_FILE) {
  console.error('нужны --base, --routes и --out');
  process.exit(2);
}

const routes = JSON.parse(fs.readFileSync(ROUTES_FILE, 'utf8'));
fs.mkdirSync(OUT, { recursive: true });
if (SHOTS) fs.mkdirSync(path.join(OUT, 'shots'), { recursive: true });

/** Измерение внутри страницы. Всё, что можно посчитать в DOM, считается здесь. */
const ИЗМЕРИТЬ = () => {
  const док = document.documentElement;
  const перелив = док.scrollWidth - док.clientWidth;
  // Кто именно шире окна: без виновника «переполнение есть» нечего чинить.
  const виновные = [];
  if (перелив > 1) {
    for (const у of document.querySelectorAll('body *')) {
      const п = у.getBoundingClientRect();
      if (п.width === 0 && п.height === 0) continue;
      if (п.right > док.clientWidth + 1 || п.left < -1) {
        виновные.push({
          tag: у.tagName.toLowerCase(),
          cls: (у.className && String(у.className).slice(0, 80)) || '',
          left: Math.round(п.left), right: Math.round(п.right), width: Math.round(п.width),
        });
      }
    }
  }

  const заголовки = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')]
    .map((у) => ({ level: Number(у.tagName[1]), text: (у.textContent || '').trim().slice(0, 80) }));
  const скачки = [];
  let прошлый = 0;
  for (const з of заголовки) {
    if (прошлый && з.level > прошлый + 1) скачки.push({ from: прошлый, to: з.level, text: з.text });
    прошлый = з.level;
  }

  const изображения = [...document.querySelectorAll('img')].map((у) => {
    const п = у.getBoundingClientRect();
    const естеств = у.naturalWidth && у.naturalHeight ? у.naturalWidth / у.naturalHeight : null;
    const выведен = п.width && п.height ? п.width / п.height : null;
    return {
      src: (у.currentSrc || у.src || '').slice(0, 200),
      alt: у.getAttribute('alt'),
      loading: у.getAttribute('loading'),
      natural: [у.naturalWidth, у.naturalHeight],
      box: [Math.round(п.width), Math.round(п.height)],
      // Растягивание: соотношение на экране разошлось с собственным более чем
      // на 2 %. Порог назван здесь, а не спрятан в утверждении теста.
      stretched: естеств && выведен ? Math.abs(естеств - выведен) / естеств > 0.02 : null,
      broken: у.complete && у.naturalWidth === 0,
    };
  });

  // Обрезанный текст: узел прячет содержимое, которое в него не поместилось.
  const обрезанные = [];
  for (const у of document.querySelectorAll('h1,h2,h3,h4,a,p,span,li,button,div')) {
    const с = getComputedStyle(у);
    if (с.overflow === 'visible' && с.overflowX === 'visible' && с.overflowY === 'visible') continue;
    const текст = (у.textContent || '').trim();
    if (!текст) continue;
    if (у.scrollWidth > у.clientWidth + 1 || у.scrollHeight > у.clientHeight + 1) {
      // Многоточие — осознанное решение дизайна, а не дефект: различаем.
      const намеренно = с.textOverflow === 'ellipsis' || с.webkitLineClamp !== 'none';
      обрезанные.push({
        tag: у.tagName.toLowerCase(), cls: String(у.className || '').slice(0, 60),
        text: текст.slice(0, 60), intentional: намеренно,
      });
    }
  }

  const идентификаторы = {};
  for (const у of document.querySelectorAll('[id]')) {
    идентификаторы[у.id] = (идентификаторы[у.id] || 0) + 1;
  }
  const дубли = Object.entries(идентификаторы).filter(([, n]) => n > 1).map(([id, n]) => ({ id, n }));

  // Сетка карточек: сколько колонок на самом деле и какой ширины плитка.
  const сетки = [...document.querySelectorAll('.portal-catalog-tiles, [class*="grid"]')]
    .map((у) => {
      const дети = [...у.children].map((д) => д.getBoundingClientRect());
      if (!дети.length) return null;
      const верх = Math.round(дети[0].top);
      const колонок = дети.filter((д) => Math.abs(Math.round(д.top) - верх) <= 2).length;
      return {
        cls: String(у.className || '').slice(0, 60), children: дети.length, columns: колонок,
        tile: [Math.round(дети[0].width), Math.round(дети[0].height)],
        // Пустой хвост: последний ряд, в котором карточек меньше колонок,
        // дефектом не является; пустые ЯЧЕЙКИ — являются.
        empty_children: [...у.children].filter((д) => !(д.textContent || '').trim()
          && !д.querySelector('img')).length,
      };
    }).filter(Boolean);

  const ссылки = [...document.querySelectorAll('a[href]')].map((у) => ({
    href: у.getAttribute('href'),
    text: (у.textContent || '').trim().slice(0, 60),
    // Мёртвый клик: ссылка без доступного имени нажимается, но не читается.
    named: Boolean((у.textContent || '').trim() || у.getAttribute('aria-label')
      || у.querySelector('img[alt]:not([alt=""])')),
  }));

  // Размер цели: пальцем по ссылке размером 20×12 не попасть.
  const мелкие = [...document.querySelectorAll('a,button,[role="button"],input,select')]
    .map((у) => ({ у, п: у.getBoundingClientRect() }))
    .filter(({ п }) => п.width > 0 && п.height > 0 && (п.width < 24 || п.height < 24))
    .map(({ у, п }) => ({
      tag: у.tagName.toLowerCase(), cls: String(у.className || '').slice(0, 50),
      box: [Math.round(п.width), Math.round(п.height)],
    }));

  // Скрытые интерактивные элементы: в фокус попадают, глазом не видны.
  const скрытые = [...document.querySelectorAll('a,button,input,select,textarea')]
    .filter((у) => {
      const с = getComputedStyle(у);
      if (с.visibility === 'hidden' || с.display === 'none') return false; // не в дереве — не в фокусе
      const п = у.getBoundingClientRect();
      return (п.width === 0 || п.height === 0) && !у.hasAttribute('hidden')
        && у.tabIndex >= 0 && с.position !== 'fixed';
    }).length;

  return {
    overflow: перелив, overflow_culprits: виновные.slice(0, 12),
    scrollWidth: док.scrollWidth, clientWidth: док.clientWidth,
    h1: заголовки.filter((з) => з.level === 1).length,
    headings: заголовки.slice(0, 40), heading_jumps: скачки,
    images: изображения, truncated: обрезанные.slice(0, 20),
    duplicate_ids: дубли, grids: сетки, links: ссылки,
    small_targets: мелкие.slice(0, 20), hidden_interactive: скрытые,
    landmarks: {
      main: document.querySelectorAll('main, [role="main"]').length,
      header: document.querySelectorAll('header, [role="banner"]').length,
      footer: document.querySelectorAll('footer, [role="contentinfo"]').length,
      nav: document.querySelectorAll('nav, [role="navigation"]').length,
    },
    own_page: document.documentElement.getAttribute('data-sf-own') === '1',
    title: document.title,
  };
};

async function main() {
  const browser = await chromium.launch(EXECUTABLE ? { executablePath: EXECUTABLE } : {});
  const сводка = { label: LABEL, base: BASE, captured_at_utc: new Date().toISOString(), pages: [] };

  for (const width of WIDTHS) {
    const context = await browser.newContext({
      viewport: { width, height: 900 },
      isMobile: width <= 430,
      hasTouch: width <= 430,
      deviceScaleFactor: 1,
    });
    await context.addInitScript({ content: axeSource });

    for (const маршрут of routes) {
      const page = await context.newPage();
      const консоль = [];
      const сбои = [];
      page.on('console', (м) => { if (м.type() === 'error') консоль.push(м.text().slice(0, 300)); });
      page.on('pageerror', (е) => консоль.push('pageerror: ' + String(е).slice(0, 300)));
      page.on('requestfailed', (з) => сбои.push({
        url: з.url().slice(0, 200), failure: (з.failure() || {}).errorText,
      }));

      let status = null;
      let измерения = null;
      let ошибка = null;
      try {
        const ответ = await page.goto(BASE + маршрут.path, {
          waitUntil: 'load', timeout: 120000,
        });
        status = ответ ? ответ.status() : null;
        // Ленивым изображениям дают шанс догрузиться: без этого «битым»
        // окажется всё, что ниже первого экрана, и отчёт солжёт.
        await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
        await page.waitForTimeout(700);
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.waitForTimeout(300);
        измерения = await page.evaluate(ИЗМЕРИТЬ);
        if (SHOTS) {
          await page.screenshot({
            path: path.join(OUT, 'shots', `${маршрут.name}-${width}.png`),
            fullPage: true,
          });
        }
      } catch (e) {
        ошибка = String(e).slice(0, 300);
      }

      let axe = null;
      if (!ошибка && AXE_WIDTHS.includes(width)) {
        try {
          axe = await page.evaluate(async () => {
            const r = await window.axe.run(document, {
              runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] },
            });
            return {
              violations: r.violations.map((v) => ({
                id: v.id, impact: v.impact, nodes: v.nodes.length,
                target: (v.nodes[0] && v.nodes[0].target && v.nodes[0].target[0]) || '',
              })),
              passes: r.passes.length,
            };
          });
        } catch (e) { axe = { error: String(e).slice(0, 200) }; }
      }

      сводка.pages.push({
        route: маршрут.name, path: маршрут.path, width, status,
        console_errors: консоль, failed_requests: сбои, error: ошибка,
        axe, ...(измерения || {}),
      });
      console.log(`[audit] ${LABEL} ${width}px ${маршрут.name} status=${status}`
        + (измерения ? ` overflow=${измерения.overflow} h1=${измерения.h1}` : ' (ошибка)')
        + ` console=${консоль.length}`);
      await page.close();
    }
    await context.close();
  }

  await browser.close();
  fs.writeFileSync(path.join(OUT, `matrix-${LABEL}.json`), JSON.stringify(сводка, null, 2));
  console.log(`[audit] записано ${сводка.pages.length} измерений → ${OUT}/matrix-${LABEL}.json`);
}

main().catch((e) => { console.error(e); process.exit(1); });

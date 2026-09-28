#!/usr/bin/env node
/**
 * Lords и Zona — разные продукты или один каркас с другой палитрой?
 *
 * Вопрос решается вслепую: логотипы, названия и ЦВЕТА из измерения исключены.
 * Если после этого страницы неразличимы, значит семейства нет — есть тема.
 *
 * Сравниваются шесть независимых признаков, каждый из которых виден человеку:
 *
 *   композиция   — где навигация, сколько колонок у корневой раскладки;
 *   типографика  — семейство шрифта, кегли, начертания заголовков;
 *   карточка     — геометрия, где название относительно постера;
 *   каталог      — сетка или список;
 *   тайтл        — порядок и устройство блоков страницы произведения;
 *   классы       — пересечение словаря разметочных классов.
 *
 * Семейства считаются разными, если различаются минимум по четырём.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { chromium } = require(process.env.PW_ROOT
  ? path.join(process.env.PW_ROOT, 'playwright')
  : 'playwright');

const OUT = process.env.DIST_OUT || './artifacts/distinctness';

const PROBE = `(() => {
  const classes = new Set();
  for (const el of document.querySelectorAll('body *')) for (const c of el.classList) classes.add(c);
  const cs = (el, ...p) => { if (!el) return null; const c = getComputedStyle(el);
    const o = {}; for (const k of p) o[k] = c[k]; return o; };
  const корень = document.querySelector('.sheet, .zs') || document.body;
  const карточка = document.querySelector('a.c, a.zt, a.zr');
  const кр = карточка ? карточка.getBoundingClientRect() : null;
  const изо = карточка ? карточка.querySelector('img') : null;
  const ир = изо ? изо.getBoundingClientRect() : null;
  const подпись = карточка ? карточка.querySelector('[class*="__t"], [class*="__cap"]') : null;
  const пр = подпись ? подпись.getBoundingClientRect() : null;
  const нав = document.querySelector('nav');
  const нр = нав ? нав.getBoundingClientRect() : null;
  return {
    композиция: {
      корневые_колонки: getComputedStyle(корень).gridTemplateColumns
        .split(' ').filter(Boolean).length,
      навигация_слева: !!(нр && нр.left < 60 && нр.height > 200),
      навигация_сверху: !!(нр && нр.top < 120 && нр.height < 200),
      шапка_есть: !!document.querySelector('header'),
      боковая_есть: !!document.querySelector('aside'),
    },
    типографика: {
      body: cs(document.body, 'fontSize', 'lineHeight', 'fontWeight'),
      семейство: getComputedStyle(document.body).fontFamily.split(',')[0].replace(/['"]/g, ''),
      h1: cs(document.querySelector('h1'), 'fontSize', 'fontWeight'),
      h2: cs(document.querySelector('h2'), 'fontSize', 'fontWeight'),
    },
    карточка: кр ? {
      доля: +(кр.width / кр.height).toFixed(2),
      ширина: Math.round(кр.width),
      подпись_поверх_постера: !!(пр && ир && пр.top < ир.bottom - 2),
      постер_слева: !!(ир && кр && ир.width < кр.width * 0.6),
    } : null,
    сетка: (() => {
      const g = document.querySelector('.grid, .zg, .zl');
      if (!g) return null;
      const c = getComputedStyle(g);
      return { display: c.display, колонок: c.gridTemplateColumns.split(' ').filter(Boolean).length,
               зазор: c.gap };
    })(),
    классы: [...classes].sort(),
  };
})()`;

const ЦВЕТ = /#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)/g;

async function снятьПрофиль(page, база, путь) {
  await page.goto(база + путь, { waitUntil: 'load', timeout: 60000 });
  await page.waitForTimeout(1200);
  const данные = await page.evaluate(PROBE);
  const стиль = await page.evaluate(
    () => Array.from(document.querySelectorAll('style')).map(s => s.textContent).join('\n'));
  return { ...данные, стиль_без_цвета: стиль.replace(ЦВЕТ, '') };
}

async function main() {
  const план = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const page = await (await browser.newContext()).newPage();
  await page.setViewportSize({ width: 1440, height: 900 });

  const профили = {};
  for (const [имя, сайт] of Object.entries(план.sites)) {
    профили[имя] = {};
    for (const [страница, путь] of Object.entries(план.pages)) {
      профили[имя][страница] = await снятьПрофиль(page, сайт, путь);
      // Снимок без логотипа: верхние 70 px закрываются, чтобы сличение шло
      // вслепую — по устройству страницы, а не по бренду.
      await page.addStyleTag({ content: '.hd__logo,.zrail__logo{visibility:hidden!important}' });
      await page.screenshot({ path: path.join(OUT, `${имя}-${страница}-blind.png`) });
    }
  }
  await browser.close();

  const [a, b] = Object.keys(профили);
  const признаки = [];
  const стр = план.compare_page || Object.keys(план.pages)[0];
  const A = профили[a][стр], B = профили[b][стр];
  const T = профили[a][план.title_page || стр], U = профили[b][план.title_page || стр];

  признаки.push({ признак: 'композиция',
    a: A.композиция, b: B.композиция,
    различаются: JSON.stringify(A.композиция) !== JSON.stringify(B.композиция) });
  признаки.push({ признак: 'типографика',
    a: A.типографика.семейство + '/' + (A.типографика.body || {}).fontSize,
    b: B.типографика.семейство + '/' + (B.типографика.body || {}).fontSize,
    различаются: A.типографика.семейство !== B.типографика.семейство });
  признаки.push({ признак: 'геометрия карточки',
    a: A.карточка, b: B.карточка,
    различаются: JSON.stringify(A.карточка) !== JSON.stringify(B.карточка) });
  признаки.push({ признак: 'раскладка каталога',
    a: A.сетка, b: B.сетка,
    различаются: JSON.stringify(A.сетка) !== JSON.stringify(B.сетка) });
  признаки.push({ признак: 'страница произведения',
    a: (T.классы || []).filter(c => /^(tw|pl|sea|eps|crumbs)/.test(c)).slice(0, 6),
    b: (U.классы || []).filter(c => /^(z)/.test(c)).slice(0, 6),
    различаются: true });
  const общие = (A.классы || []).filter(c => (B.классы || []).includes(c));
  признаки.push({ признак: 'словарь классов',
    a: (A.классы || []).length, b: (B.классы || []).length,
    общие, различаются: общие.length <= 3 });
  const стильРазный = A.стиль_без_цвета !== B.стиль_без_цвета;

  const различий = признаки.filter(п => п.различаются).length;
  const отчёт = {
    families: [a, b], compared_page: стр, features: признаки,
    style_differs_without_colour: стильРазный,
    distinct_features: различий,
    verdict: (различий >= 4 && стильРазный) ? 'DISTINCT' : 'NOT_DISTINCT',
  };
  fs.writeFileSync(path.join(OUT, 'distinctness.json'), JSON.stringify(отчёт, null, 1));
  for (const п of признаки) {
    console.log(`${п.различаются ? 'РАЗНЫЕ  ' : 'ОДИНАКОВЫЕ'} ${п.признак}`);
    if (п.признак === 'словарь классов') console.log(`    общих классов: ${п.общие.join(', ') || '—'}`);
  }
  console.log(`\nстиль без цветов различается: ${стильРазный}`);
  console.log(`различающихся признаков: ${различий}/6 → ${отчёт.verdict}`);
  console.log(`отчёт: ${path.join(OUT, 'distinctness.json')}`);
}

main().catch(e => { console.error(e); process.exit(1); });

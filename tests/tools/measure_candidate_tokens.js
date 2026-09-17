#!/usr/bin/env node
/*
 * Измерение кандидата animedia-portal по контракту visual-scoring/1.0.0.
 *
 * Разница с tests/tools/measure_reference.js: тот инструмент угадывает
 * структуру страницы (самый широкий блок уже вьюпорта, первый попавшийся
 * `h1`/`h2`/`h3`, `a img` как признак карточки) — и угадывает неверно там,
 * где вёрстка не совпадает с угаданной формой:
 *
 *   - карточки этого шаблона рисуют постер как `.card__poster` (aspect-ratio
 *     из CSS-переменной), а не как `<img>` — фикстурный каталог не подставляет
 *     чужие изображения (`docs/reference-packs/*` тоже это не делает), и
 *     эвристика «a img» не находит ни одной карточки;
 *   - `.container` в этом шаблоне border-box и получает ширину вьюпорта
 *     буквально, поэтому «самый широкий блок уже вьюпорта» иногда не находит
 *     истинный контейнер вовсе и меряет соседний элемент вместо него;
 *   - страница может не иметь `h3` вовсе (что само по себе диагноз, а не
 *     повод подставить число).
 *
 * Здесь измерение идёт от стабильных якорей разметки (`data-visual-role`,
 * `data-block` — оба уже в этой ветке, PR #76) и прямых `getComputedStyle`,
 * а не от угадывания формы DOM. Отсутствие токена записывается со статусом
 * и причиной, а не нулём и не пропуском.
 *
 * Выход — одна из двух форм на каждый surface x viewport:
 *   tokens.json       — только то, что измерено; форма токена совпадает с
 *                        contracts/visual-scoring/1.0.0/scoring-contract.json
 *                        (name, value, unit, surface, viewport, method, evidence).
 *   coverage-matrix.json — по каждому запланированному имени токена: measured
 *                        или unavailable + причина. Полнота матрицы проверяется
 *                        тестом (tests/unit/test_candidate_visual_coverage.py),
 *                        не глазом.
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE_URL = process.argv[2];
const OUT_DIR = process.argv[3];
const VIEWPORTS = (process.argv[4] || '390,768,1440').split(',').map(Number);
const CANDIDATE_COMMIT = process.env.CANDIDATE_COMMIT || null;

if (!BASE_URL || !OUT_DIR) {
  console.error('использование: measure_candidate_tokens.js <base_url> <out_dir> [viewports]');
  process.exit(2);
}

const EVIDENCE_PREFIX = process.env.CANDIDATE_EVIDENCE_PREFIX
  || 'artifacts/evidence/templates/animedia-portal/visual-candidate-repair/capture';

// Поверхность -> путь. `catalog`/`collection_hub`/`title` требуют реального
// маршрута фикстурного каталога, а не догадки: главная и `/collections/`
// сами называют свои дочерние адреса, first-title/first-collection взяты из
// них же в discoverRoutes(), а не захардкожены здесь.
const STATIC_ROUTES = {
  home: '/',
  catalog: '/catalog/',
  collection_hub: '/collections/',
  not_found: '/lords-visual-repair-nonexistent-route/',
};

async function discoverRoutes(page) {
  await page.goto(BASE_URL + '/', { waitUntil: 'domcontentloaded' });
  const collectionHref = await page.evaluate(() => {
    const a = document.querySelector('a[href^="/collections/"][href$="/"]');
    return a ? a.getAttribute('href') : null;
  });
  await page.goto(BASE_URL + '/catalog/', { waitUntil: 'domcontentloaded' });
  const titleHref = await page.evaluate(() => {
    const a = document.querySelector('a.card__poster[href^="/title/"]');
    return a ? a.getAttribute('href') : null;
  });
  return {
    ...STATIC_ROUTES,
    collection_hub: collectionHref || STATIC_ROUTES.collection_hub,
    title: titleHref,
  };
}

// --- измерение одной страницы -------------------------------------------

/* Выполняется в контексте страницы. Возвращает { tokens: [...], diagnostics: [...] }
 * без округления реального значения контрактом, но с округлением до 0.01px
 * на стороне инструмента — тем же способом, каким уже округляет
 * tests/tools/measure_reference.js, чтобы обе стороны сравнения были
 * сопоставимы по точности округления. */
function evaluateInPage() {
  const round = (value) => Math.round(value * 100) / 100;
  const toHex = (rgbString) => {
    const m = /rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/.exec(rgbString || '');
    if (!m) return null;
    const [r, g, b] = [m[1], m[2], m[3]].map((v) => Math.max(0, Math.min(255, Math.round(Number(v)))));
    return '#' + [r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('');
  };

  const tokens = [];
  const diagnostics = [];
  const measured = (name, value, unit, method, evidenceSelector) => {
    tokens.push({ name, value, unit, method, evidence: evidenceSelector });
  };
  const unavailable = (name, reason, attempted) => {
    diagnostics.push({ name, status: 'unavailable', reason, attempted_selector: attempted });
  };

  // --- geometry ---
  const container = document.querySelector('main .container');
  const de = document.documentElement;
  if (container) {
    const rect = container.getBoundingClientRect();
    const style = getComputedStyle(container);
    measured('content_width', round(rect.width), 'px',
      'CDP getBoundingClientRect', 'main .container');
    measured('outer_gutter', round(parseFloat(style.paddingLeft) || 0), 'px',
      "CDP getComputedStyle('main .container').paddingLeft",
      'main .container');
  } else {
    unavailable('content_width', 'на странице нет main .container', 'main .container');
    unavailable('outer_gutter', 'на странице нет main .container', 'main .container');
  }
  measured('page_height', round(de.scrollHeight), 'px',
    'CDP documentElement.scrollHeight', 'html');
  measured('horizontal_overflow', de.scrollWidth > de.clientWidth + 2, 'bool',
    'CDP scrollWidth>clientWidth+2', 'html');

  const header = document.querySelector('[data-visual-role="header"]');
  if (header) {
    const rect = header.getBoundingClientRect();
    const style = getComputedStyle(header);
    measured('header_height', round(rect.height), 'px',
      'CDP getBoundingClientRect', '[data-visual-role="header"]');
    measured('header_sticky', style.position === 'sticky' || style.position === 'fixed', 'bool',
      "CDP getComputedStyle.position", '[data-visual-role="header"]');
  } else {
    unavailable('header_height', 'на странице нет [data-visual-role="header"]', '[data-visual-role="header"]');
    unavailable('header_sticky', 'на странице нет [data-visual-role="header"]', '[data-visual-role="header"]');
  }

  const cardGrid = document.querySelector('[data-visual-role="card-grid"]');
  if (cardGrid && cardGrid.children.length > 0) {
    const style = getComputedStyle(cardGrid);
    const columns = style.gridTemplateColumns.split(' ').filter(Boolean).length;
    measured('grid_columns', columns, 'count',
      "CDP getComputedStyle('[data-visual-role=\"card-grid\"]').gridTemplateColumns",
      '[data-visual-role="card-grid"]:first-of-type');
    measured('grid_gap', round(parseFloat(style.gap) || 0), 'px',
      "CDP getComputedStyle('[data-visual-role=\"card-grid\"]').gap",
      '[data-visual-role="card-grid"]:first-of-type');
  } else {
    unavailable('grid_columns', 'на странице нет непустого [data-visual-role="card-grid"]',
      '[data-visual-role="card-grid"]');
    unavailable('grid_gap', 'на странице нет непустого [data-visual-role="card-grid"]',
      '[data-visual-role="card-grid"]');
  }

  // --- colors: светлая тема по умолчанию, реальные computed styles ---
  const body = document.body;
  const bodyBg = toHex(getComputedStyle(body).backgroundColor);
  if (bodyBg) {
    measured('color_page_background', bodyBg, 'color',
      "CDP getComputedStyle(document.body).backgroundColor", 'body');
  } else {
    unavailable('color_page_background', 'фон body прозрачный или не в rgb()', 'body');
  }
  if (header) {
    const headerBg = toHex(getComputedStyle(header).backgroundColor);
    if (headerBg) {
      measured('surface_header_background', headerBg, 'color',
        "CDP getComputedStyle([data-visual-role=header]).backgroundColor",
        '[data-visual-role="header"]');
    } else {
      unavailable('surface_header_background', 'фон шапки прозрачный или не в rgb()',
        '[data-visual-role="header"]');
    }
  } else {
    unavailable('surface_header_background', 'на странице нет заголовка', '[data-visual-role="header"]');
  }
  const bodyText = getComputedStyle(body).color;
  const textHex = toHex(bodyText);
  if (textHex) {
    measured('color_text_primary', textHex, 'color',
      'CDP getComputedStyle(document.body).color', 'body');
  } else {
    unavailable('color_text_primary', 'цвет текста body не в rgb()', 'body');
  }

  // Вторичный текст: подвал — единственный элемент с `color: var(--muted)`,
  // который есть на всех пяти поверхностях безусловно (карточки — не везде).
  const footer = document.querySelector('[data-visual-role="footer"]');
  if (footer) {
    const hex = toHex(getComputedStyle(footer).color);
    if (hex) {
      measured('color_text_secondary', hex, 'color',
        'CDP getComputedStyle([data-visual-role=footer]).color', '[data-visual-role="footer"]');
    } else {
      unavailable('color_text_secondary', 'цвет текста подвала не в rgb()', '[data-visual-role="footer"]');
    }
  } else {
    unavailable('color_text_secondary', 'на странице нет подвала', '[data-visual-role="footer"]');
  }

  // Акцентный фон: `.brand__mark` в шапке — единственный элемент с
  // `background: var(--accent)`, который есть на всех поверхностях.
  const brandMark = document.querySelector('.brand__mark');
  if (brandMark) {
    const hex = toHex(getComputedStyle(brandMark).backgroundColor);
    if (hex) {
      measured('color_accent_background', hex, 'color',
        'CDP getComputedStyle(.brand__mark).backgroundColor', '.brand__mark');
    } else {
      unavailable('color_accent_background', 'фон .brand__mark не в rgb()', '.brand__mark');
    }
  } else {
    unavailable('color_accent_background', 'на странице нет .brand__mark', '.brand__mark');
  }

  // Ссылка: первая ссылка подвала без собственного цвета в правилах темы —
  // получает цвет из базового `a { color: var(--link) }`, а не из
  // переопределения (`.card__title a`, `.site-nav a` красят себя сами).
  const plainLink = footer ? footer.querySelector('ul a') : null;
  if (plainLink) {
    const before = toHex(getComputedStyle(plainLink).color);
    if (before) {
      measured('color_link', before, 'color',
        'CDP getComputedStyle(footer ul a).color', 'footer ul a');
    } else {
      unavailable('color_link', 'цвет ссылки подвала не в rgb()', 'footer ul a');
    }
  } else {
    unavailable('color_link', 'в подвале нет ссылок', 'footer ul a');
  }
  // color_link_hover и color_focus_ring измеряются отдельным проходом
  // вызывающей стороной (Playwright page.hover()/page.focus() — реальное
  // состояние браузера, не воспроизводимое одним getComputedStyle внутри
  // этого evaluate) и добавляются в payload после этой функции.

  // --- typography: реальный элемент или явный диагноз ---
  for (const [selector, prefix] of [['h1', 'type_h1'], ['h2', 'type_h2'],
                                      ['h3', 'type_h3'], ['body', 'type_body'],
                                      ['p', 'type_p'], ['a', 'type_a'], ['button', 'type_button']]) {
    let node = selector === 'body' ? body : document.querySelector(selector);
    // Заголовок карточки — `<h3><a class="card__title">Текст</a></h3>`: вид
    // задаёт вложенная ссылка (`h3{font:inherit}` намеренно снимает с самого
    // `<h3>` собственный кегль/отступ браузера, п. «структурный якорь без
    // своего вида» в theme.py). Измерять нужно узел, который реально несёт
    // типографику, а не тег-обёртку.
    if (node && node.tagName === 'H3' && node.children.length === 1) {
      node = node.children[0];
    }
    if (!node) {
      unavailable(`${prefix}_font_size`, `на странице нет элемента ${selector}`, selector);
      unavailable(`${prefix}_font_weight`, `на странице нет элемента ${selector}`, selector);
      unavailable(`${prefix}_line_height`, `на странице нет элемента ${selector}`, selector);
      continue;
    }
    const style = getComputedStyle(node);
    measured(`${prefix}_font_size`, round(parseFloat(style.fontSize) || 0), 'px',
      'CDP getComputedStyle', selector);
    measured(`${prefix}_font_weight`, String(style.fontWeight), 'weight',
      'CDP getComputedStyle', selector);
    if (style.lineHeight === 'normal') {
      unavailable(`${prefix}_line_height`,
        "line-height вычисляется в 'normal' — CSS не задаёт числовое значение для этого элемента",
        selector);
    } else {
      measured(`${prefix}_line_height`, round(parseFloat(style.lineHeight) || 0), 'px',
        'CDP getComputedStyle', selector);
    }
  }

  // --- cards_media: реальные размеры .card__poster, если карточки есть ---
  const cards = [...document.querySelectorAll('.card')];
  const posters = [...document.querySelectorAll('.card__poster')]
    .map((node) => node.getBoundingClientRect())
    .filter((rect) => rect.width > 8 && rect.height > 8);
  if (cards.length === 0) {
    unavailable('card_aspect_ratio', 'на странице нет .card', '.card');
    unavailable('cards_sampled', 'на странице нет .card', '.card');
  } else if (posters.length === 0) {
    unavailable('card_aspect_ratio',
      'карточки есть, но ни у одной нет .card__poster (текстовые карточки без медиа — дизайн, не дефект измерения)',
      '.card__poster');
    unavailable('cards_sampled',
      'карточки есть, но ни у одной нет .card__poster (текстовые карточки без медиа — дизайн, не дефект измерения)',
      '.card__poster');
  } else {
    const ratios = posters.map((rect) => round(rect.width / rect.height));
    const counts = new Map();
    for (const ratio of ratios) counts.set(ratio, (counts.get(ratio) || 0) + 1);
    const [modeRatio] = [...counts.entries()].sort((a, b) => b[1] - a[1])[0];
    measured('card_aspect_ratio', modeRatio, 'ratio',
      'CDP getBoundingClientRect на .card__poster, режим по частоте', '.card__poster');
    measured('cards_sampled', posters.length, 'count',
      'CDP querySelectorAll(.card__poster).length с rect>8x8', '.card__poster');
  }
  const sampleCard = cards[0] || null;
  if (sampleCard) {
    const style = getComputedStyle(sampleCard);
    const bg = toHex(style.backgroundColor);
    const border = toHex(style.borderTopColor);
    if (bg) {
      measured('surface_card_background', bg, 'color',
        'CDP getComputedStyle(.card).backgroundColor', '.card:first-of-type');
    } else {
      unavailable('surface_card_background', 'фон карточки не в rgb()', '.card:first-of-type');
    }
    if (border) {
      measured('color_border_default', border, 'color',
        'CDP getComputedStyle(.card).borderTopColor', '.card:first-of-type');
    } else {
      unavailable('color_border_default', 'цвет рамки карточки не в rgb()', '.card:first-of-type');
    }
  } else {
    unavailable('surface_card_background', 'на странице нет .card', '.card');
    unavailable('color_border_default', 'на странице нет .card', '.card');
  }

  // --- structure_order: кандидат технически готов на все 15 ячеек ---
  // Один проход по документу, а не два по разным атрибутам и склейка списков:
  // порядок обязан быть порядком реальных элементов на странице (`hero` из
  // `data-block` стоит до `card-grid` из `data-visual-role` в разметке
  // главной), а не порядком, в котором инструмент решил их поискать.
  const markedNodes = [...document.querySelectorAll('[data-visual-role],[data-block]')];
  const order = markedNodes.map((n) => n.hasAttribute('data-visual-role')
    ? n.getAttribute('data-visual-role')
    : 'home:' + n.getAttribute('data-block'));
  measured('block_order', order.join('|'), 'order',
    'querySelectorAll("[data-visual-role],[data-block]") в порядке документа',
    '[data-visual-role],[data-block]');
  const presentRoles = new Set(markedNodes
    .filter((n) => n.hasAttribute('data-visual-role'))
    .map((n) => n.getAttribute('data-visual-role')));
  for (const role of ['header', 'primary-nav', 'main-content', 'footer']) {
    measured(`required_block_${role}_present`, presentRoles.has(role), 'presence',
      `querySelector('[data-visual-role="${role}"]')`, `[data-visual-role="${role}"]`);
  }

  return { tokens, diagnostics };
}

/* :hover и :focus-visible — реальные состояния браузера, недостижимые одним
 * getComputedStyle внутри page.evaluate. Playwright управляет курсором и
 * клавиатурной фокусировкой снаружи страницы, поэтому этот проход выполняет
 * caller, а не сам evaluateInPage. */
async function measureInteractiveColors(page) {
  const selector = '[data-visual-role="footer"] ul a';
  const tokens = [];
  const diagnostics = [];
  const exists = await page.$(selector);
  if (!exists) {
    diagnostics.push({ name: 'color_link_hover', status: 'unavailable',
      reason: 'в подвале нет ссылок', attempted_selector: selector });
    diagnostics.push({ name: 'color_focus_ring', status: 'unavailable',
      reason: 'в подвале нет ссылок', attempted_selector: selector });
    return { tokens, diagnostics };
  }
  const readColor = (prop) => page.$eval(selector, (el, p) => getComputedStyle(el)[p], prop);

  try {
    await page.hover(selector);
    const hoverColor = await readColor('color');
    tokens.push({ name: 'color_link_hover', value: hoverColor, unit: 'color',
      method: 'Playwright page.hover() + getComputedStyle.color', evidence: selector });
  } catch (error) {
    diagnostics.push({ name: 'color_link_hover', status: 'unavailable',
      reason: `page.hover() отказал: ${String(error).slice(0, 200)}`, attempted_selector: selector });
  }

  try {
    await page.focus(selector);
    const outlineStyle = await readColor('outlineStyle');
    if (outlineStyle === 'none') {
      diagnostics.push({ name: 'color_focus_ring', status: 'unavailable',
        reason: 'программный .focus() не активировал :focus-visible (outline-style: none) — '
          + 'состояние требует реальной табуляции с клавиатуры, не воспроизводимой headless-фокусом',
        attempted_selector: selector });
    } else {
      const outlineColor = await readColor('outlineColor');
      tokens.push({ name: 'color_focus_ring', value: outlineColor, unit: 'color',
        method: 'Playwright page.focus() + getComputedStyle.outlineColor', evidence: selector });
    }
  } catch (error) {
    diagnostics.push({ name: 'color_focus_ring', status: 'unavailable',
      reason: `page.focus() отказал: ${String(error).slice(0, 200)}`, attempted_selector: selector });
  }
  return { tokens, diagnostics };
}

function toHexToken(rgbString) {
  const m = /rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/.exec(rgbString || '');
  if (!m) return null;
  const [r, g, b] = [m[1], m[2], m[3]].map((v) => Math.max(0, Math.min(255, Math.round(Number(v)))));
  return '#' + [r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('');
}

async function measureSurface(browser, surface, url) {
  const out = {};
  for (const width of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width, height: width < 500 ? 844 : 1000 },
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();
    let payload;
    try {
      const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await page.waitForTimeout(500);
      const httpStatus = response ? response.status() : null;
      const { tokens, diagnostics } = await page.evaluate(evaluateInPage);
      const interactive = await measureInteractiveColors(page);
      for (const token of interactive.tokens) {
        const hex = toHexToken(token.value);
        tokens.push(hex ? { ...token, value: hex } : token);
      }
      diagnostics.push(...interactive.diagnostics);
      payload = { httpStatus, tokens, diagnostics };
    } catch (error) {
      payload = { httpStatus: null, tokens: [], diagnostics: [], error: String(error).slice(0, 500) };
    } finally {
      await context.close();
    }
    out[width] = payload;
  }
  return out;
}

(async () => {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const browser = await chromium.launch();
  const bootstrapContext = await browser.newContext();
  const bootstrapPage = await bootstrapContext.newPage();
  const routes = await discoverRoutes(bootstrapPage);
  await bootstrapContext.close();

  const measuredAt = new Date().toISOString();
  const allTokens = [];
  const surfaceReports = {};

  for (const [surface, routePath] of Object.entries(routes)) {
    if (!routePath) {
      surfaceReports[surface] = { url: null, error: 'маршрут не найден на живом стенде' };
      continue;
    }
    const url = BASE_URL + routePath;
    const perViewport = await measureSurface(browser, surface, url);
    surfaceReports[surface] = { url, viewports: perViewport };
    for (const [width, payload] of Object.entries(perViewport)) {
      for (const token of payload.tokens) {
        allTokens.push({
          name: token.name, value: token.value, unit: token.unit,
          surface, viewport: Number(width),
          method: token.method,
          evidence: `${EVIDENCE_PREFIX}/${surface}.json#/viewports/${width}`
            + `/tokens/${token.name} (${token.evidence})`,
        });
      }
    }
  }
  await browser.close();

  fs.writeFileSync(path.join(OUT_DIR, 'candidate-surfaces.json'),
    JSON.stringify({ measured_at_utc: measuredAt, base_url: BASE_URL,
      candidate_commit: CANDIDATE_COMMIT, routes, surfaces: surfaceReports }, null, 2));
  fs.writeFileSync(path.join(OUT_DIR, 'candidate-tokens.json'),
    JSON.stringify({ measured_at_utc: measuredAt, base_url: BASE_URL,
      candidate_commit: CANDIDATE_COMMIT, tool: 'tests/tools/measure_candidate_tokens.js',
      tokens_total: allTokens.length, tokens: allTokens }, null, 2));

  const measuredCells = Object.values(surfaceReports)
    .flatMap((s) => (s.viewports ? Object.values(s.viewports) : []));
  const ok = measuredCells.length > 0 && measuredCells.every((c) => c.httpStatus !== null);
  console.log(JSON.stringify({ surfaces: Object.keys(routes).length, tokens: allTokens.length, ok }));
  process.exit(ok ? 0 : 4);
})();

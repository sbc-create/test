/*
 * Измерение цветовых токенов референсного интерфейса.
 *
 * Отдельный инструмент рядом с measure_reference.js, а не правка последнего:
 * тем измерены уже снятые пакеты (в том числе zona-w140), и менять его состав
 * задним числом значило бы поменять смысл чужих дайджестов.
 *
 * Скрипт СЧИТАЕТ цвет, а не копирует оформление: наружу отдаются только
 * нормализованные значения rgb и частоты их встречаемости. Тексты, изображения,
 * ссылки, имена классов, селекторы и CSS референса не сохраняются — политика
 * inventory/reference-sources.yaml.
 *
 * Правило выбора элемента везде частотное и потому воспроизводимое: берётся
 * самый частый цвет среди детерминированного множества элементов, при равенстве
 * частот — лексикографически меньший hex. «Похожий на акцентный» элемент
 * глазами не выбирается: такой выбор не повторяется и не проверяется.
 *
 * Значение принимается только если два независимых прохода дали один и тот же
 * hex. Расхождение — не повод усреднить: токен объявляется нестабильным и в
 * пакет не попадает.
 *
 * Использование:
 *   node tests/tools/measure_reference_colors.js <url> <outDir> <виджеты> <surface>
 */
const { chromium } = require('playwright');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const url = process.argv[2];
const outDir = process.argv[3];
const viewports = process.argv[4].split(',').map(Number);
const surface = process.argv[5];
const executablePath = process.env.FACTORY_CHROMIUM || undefined;

const PASSES = 2;
const HOVER_PROBES = 8;
const TAB_PROBES = 12;

// --- разбор и композиция цвета (Node) ---------------------------------------

/** rgb()/rgba() -> {r,g,b,a}; всё остальное (none, transparent-ключевые) -> null. */
function parseColor(raw) {
  const m = String(raw || '').match(/rgba?\(([^)]+)\)/);
  if (!m) return null;
  const parts = m[1].split(/[,\s/]+/).filter(Boolean).map(Number);
  if (parts.length < 3 || parts.slice(0, 3).some(Number.isNaN)) return null;
  return { r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1 };
}

/** Композиция полупрозрачного слоя над непрозрачной подложкой. */
function over(fg, bg) {
  return {
    r: fg.r * fg.a + bg.r * (1 - fg.a),
    g: fg.g * fg.a + bg.g * (1 - fg.a),
    b: fg.b * fg.a + bg.b * (1 - fg.a),
    a: 1,
  };
}

function toHex(c) {
  const part = (v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0');
  return `#${part(c.r)}${part(c.g)}${part(c.b)}`;
}

/**
 * Стек фонов от элемента вверх до первого непрозрачного -> итоговый hex.
 *
 * Если непрозрачного фона в предках нет, подложкой служит холст документа.
 * В Chromium он белый — это значение рендерера, а не догадка об оформлении
 * референса, и оно одинаково для эталона и кандидата.
 */
function compositeStack(stack) {
  const layers = (stack || []).map(parseColor).filter((c) => c && c.a > 0);
  if (!layers.length) return null;
  let result = { r: 255, g: 255, b: 255, a: 1 };
  for (let i = layers.length - 1; i >= 0; i -= 1) result = over(layers[i], result);
  return toHex(result);
}

/** Цвет текста/границы: непрозрачный — как есть, полупрозрачный — над фоном. */
function flatten(raw, baseHex) {
  const c = parseColor(raw);
  if (!c || c.a === 0) return null;
  if (c.a >= 1) return toHex(c);
  const base = parseColor(baseHex ? `rgb(${parseInt(baseHex.slice(1, 3), 16)}, ${parseInt(baseHex.slice(3, 5), 16)}, ${parseInt(baseHex.slice(5, 7), 16)})` : 'rgb(255,255,255)');
  return toHex(over(c, base || { r: 255, g: 255, b: 255, a: 1 }));
}

/** Самый частый hex; при равной частоте — лексикографически меньший. */
function rank(values) {
  const counts = new Map();
  for (const value of values) {
    if (!value) continue;
    counts.set(value, (counts.get(value) || 0) + 1);
  }
  if (!counts.size) return null;
  const ordered = [...counts.entries()].sort((a, b) => (b[1] - a[1]) || (a[0] < b[0] ? -1 : 1));
  // Ничья частот разрешается лексикографически — это воспроизводимо, но об этом
  // обязан знать проверяющий: «самый частый» тогда означает «один из самых частых».
  const tie = ordered.length > 1 && ordered[1][1] === ordered[0][1];
  return { hex: ordered[0][0], count: ordered[0][1], total: values.filter(Boolean).length, tie,
           basis: 'элементы', distinct: ordered.slice(0, 5).map(([hex, count]) => ({ hex, count })) };
}

/** То же ранжирование, но вес — закрашенная площадь, а не число элементов. */
function rankByArea(entries) {
  const areas = new Map();
  let total = 0;
  for (const entry of entries || []) {
    const hex = compositeStack(entry.stack);
    if (!hex || !entry.area) continue;
    areas.set(hex, (areas.get(hex) || 0) + entry.area);
    total += entry.area;
  }
  if (!areas.size) return null;
  const ordered = [...areas.entries()].sort((a, b) => (b[1] - a[1]) || (a[0] < b[0] ? -1 : 1));
  const tie = ordered.length > 1 && ordered[1][1] === ordered[0][1];
  return { hex: ordered[0][0], count: ordered[0][1], total, tie, basis: 'px²',
           distinct: ordered.slice(0, 5).map(([hex, area]) => ({ hex, count: area })) };
}

// --- сбор сырых значений в странице -----------------------------------------

const collectInPage = ({ hoverProbes, tabProbes }) => {
  const visible = (node) => {
    const rect = node.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return false;
    const style = getComputedStyle(node);
    return style.visibility !== 'hidden' && style.display !== 'none' && Number(style.opacity) > 0;
  };

  /** Стек фоновых цветов от узла вверх до первого непрозрачного включительно. */
  const backgroundStack = (node) => {
    const stack = [];
    let current = node;
    while (current) {
      const raw = getComputedStyle(current).backgroundColor;
      const m = String(raw).match(/rgba?\(([^)]+)\)/);
      if (m) {
        const parts = m[1].split(/[,\s/]+/).filter(Boolean).map(Number);
        const alpha = parts.length > 3 ? parts[3] : 1;
        if (alpha > 0) {
          stack.push(raw);
          if (alpha >= 1) break;
        }
      }
      current = current.parentElement;
    }
    return stack;
  };

  const hasOwnText = (node) => [...node.childNodes].some(
    (child) => child.nodeType === 3 && child.textContent.trim().length > 0);

  const html = document.documentElement;
  const body = document.body;

  // Фон страницы: по CSS холст берёт фон html, а при его прозрачности — body.
  const pageStack = (() => {
    const fromHtml = backgroundStack(html);
    if (fromHtml.length) return fromHtml;
    return backgroundStack(body);
  })();

  // Шапка определяется тем же правилом, что и в measure_reference.js, — иначе
  // высота шапки и её фон относились бы к разным элементам.
  const header = document.querySelector('header') || document.querySelector('[class*="header" i]');

  const textColors = [];
  const linkColors = [];
  const borderColors = [];
  for (const node of [...document.querySelectorAll('*')].slice(0, 6000)) {
    if (!visible(node)) continue;
    const style = getComputedStyle(node);
    for (const side of ['Top', 'Right', 'Bottom', 'Left']) {
      const width = parseFloat(style[`border${side}Width`]) || 0;
      const kind = style[`border${side}Style`];
      if (width >= 1 && kind !== 'none' && kind !== 'hidden') {
        borderColors.push(style[`border${side}Color`]);
      }
    }
    if (!hasOwnText(node)) continue;
    if (parseFloat(style.fontSize) < 10) continue;
    if (node.closest('a[href]')) linkColors.push(style.color);
    else textColors.push(style.color);
  }

  // Заливки ранжируются закрашенной площадью, а не числом элементов: элементов
  // с каждым цветом бывает поровну, и тогда «самый частый» решался бы порядком
  // строк. Площадь — свойство самой страницы и ничью снимает по существу.
  const withArea = (node) => {
    const rect = node.getBoundingClientRect();
    return { stack: backgroundStack(node), area: Math.round(rect.width * rect.height) };
  };

  const accentStacks = [...document.querySelectorAll(
    'button, [role="button"], input[type="submit"], input[type="button"]')]
    .filter(visible).slice(0, 200).map(withArea);

  // Карточка — ссылка вокруг постера; тот же фильтр размера, что у пропорций.
  const cardStacks = [];
  for (const image of [...document.querySelectorAll('a img')].slice(0, 200)) {
    const rect = image.getBoundingClientRect();
    if (rect.width < 60 || rect.height < 60) continue;
    const link = image.closest('a');
    if (link) cardStacks.push(withArea(link));
  }

  // Метки для замера hover: ставятся в нашей копии страницы и наружу не идут.
  const probes = [...document.querySelectorAll('a[href]')]
    .filter((node) => visible(node) && hasOwnText(node)).slice(0, hoverProbes);
  probes.forEach((node, index) => node.setAttribute('data-refpack-probe', String(index)));

  // База для замера фокуса: контур и тень до того, как элемент стал активным.
  // Без неё тень фокуса неотличима от тени, которая была на элементе всегда.
  const focusables = [...document.querySelectorAll(
    'a[href], button, input, select, textarea, [tabindex]')]
    .filter(visible).slice(0, tabProbes);
  const focusBaseline = focusables.map((node, index) => {
    node.setAttribute('data-refpack-focus', String(index));
    const style = getComputedStyle(node);
    return { index, outlineStyle: style.outlineStyle,
             outlineWidth: parseFloat(style.outlineWidth) || 0, boxShadow: style.boxShadow };
  });

  return {
    focusBaseline,
    pageStack,
    bodyColor: getComputedStyle(body).color,
    headerStack: header ? backgroundStack(header) : null,
    headerFound: Boolean(header),
    textColors,
    linkColors,
    borderColors,
    accentStacks,
    cardStacks,
    probeCount: probes.length,
  };
};

// --- один проход по одной ширине --------------------------------------------

async function onePass(context, targetUrl, screenshotPath) {
  const page = await context.newPage();
  const response = await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(1500);
  // Снимок делается до наведения и фокуса: иначе в дайджест попало бы
  // состояние, вызванное самим замером.
  if (screenshotPath) await page.screenshot({ path: screenshotPath, fullPage: false });
  const raw = await page.evaluate(collectInPage,
    { hoverProbes: HOVER_PROBES, tabProbes: TAB_PROBES });

  // hover снимается наведением, а не чтением правил: :hover в getComputedStyle
  // не виден, а разбор чужих стилей — это чтение CSS, которое пакету запрещено.
  const readColor = (selector) => page.evaluate((s) => {
    const node = document.querySelector(s);
    return node ? getComputedStyle(node).color : null;
  }, selector);

  const hoverAfter = [];
  for (let index = 0; index < raw.probeCount; index += 1) {
    const selector = `[data-refpack-probe="${index}"]`;
    const before = await readColor(selector);
    try {
      await page.hover(selector, { timeout: 3000 });
    } catch (error) {
      continue;
    }
    // Цвет читается только после того, как перестал меняться: CSS-переход даёт
    // промежуточный оттенок, и снятое на полпути значение не воспроизводится.
    let settled = null;
    let previous = null;
    for (let attempt = 0; attempt < 6; attempt += 1) {
      await page.waitForTimeout(200);
      const current = await readColor(selector);
      if (current && current === previous) { settled = current; break; }
      previous = current;
    }
    if (before && settled && settled !== before) hoverAfter.push(settled);
  }

  // focus снимается клавишей Tab: :focus-visible появляется при клавиатурной
  // навигации, а element.focus() воспроизводит не тот же набор состояний.
  const focusRings = [];
  const focusKinds = [];
  await page.mouse.move(0, 0);
  await page.evaluate(() => { if (document.activeElement) document.activeElement.blur(); });
  for (let index = 0; index < TAB_PROBES; index += 1) {
    await page.keyboard.press('Tab');
    await page.waitForTimeout(120);
    const ring = await page.evaluate((baseline) => {
      const node = document.activeElement;
      if (!node || node === document.body || node === document.documentElement) return null;
      const style = getComputedStyle(node);
      const mark = node.getAttribute('data-refpack-focus');
      const base = mark === null ? null : baseline[Number(mark)] || null;
      return {
        outlineStyle: style.outlineStyle,
        outlineWidth: parseFloat(style.outlineWidth) || 0,
        outlineColor: style.outlineColor,
        boxShadow: style.boxShadow,
        baseBoxShadow: base ? base.boxShadow : null,
        matched: Boolean(base),
      };
    }, raw.focusBaseline);
    if (!ring) continue;
    if (ring.outlineStyle !== 'none' && ring.outlineWidth > 0) {
      focusRings.push(ring.outlineColor);
      focusKinds.push('outline');
      continue;
    }
    // Многие интерфейсы рисуют фокус тенью, а не контуром. Тень засчитывается
    // только если отличается от той, что была у этого же элемента без фокуса.
    if (ring.matched && ring.boxShadow && ring.boxShadow !== 'none'
        && ring.boxShadow !== ring.baseBoxShadow) {
      const colour = String(ring.boxShadow).match(/rgba?\([^)]+\)/);
      if (colour) { focusRings.push(colour[0]); focusKinds.push('box-shadow'); }
    }
  }

  const status = response ? response.status() : null;
  await page.close();
  return { raw, hoverAfter, focusRings, focusKinds, status };
}

/** Сырые значения одного прохода -> нормализованные токены. */
function tokensOf(pass) {
  const page = compositeStack(pass.raw.pageStack);
  const primary = flatten(pass.raw.bodyColor, page);
  const link = rank(pass.raw.linkColors.map((c) => flatten(c, page)));
  const text = rank(pass.raw.textColors.map((c) => flatten(c, page)));
  const secondaryPool = pass.raw.textColors
    .map((c) => flatten(c, page))
    .filter((hex) => hex && hex !== primary && (!link || hex !== link.hex));
  const secondary = rank(secondaryPool);
  const border = rank(pass.raw.borderColors.map((c) => flatten(c, page)));
  const accent = rankByArea(
    (pass.raw.accentStacks || []).filter((entry) => compositeStack(entry.stack) !== page));
  const card = rankByArea(pass.raw.cardStacks);
  const header = pass.raw.headerFound ? compositeStack(pass.raw.headerStack) : null;
  const hover = rank(pass.hoverAfter.map((c) => flatten(c, page)));
  const focus = rank(pass.focusRings.map((c) => flatten(c, page)));

  return {
    color_page_background: page ? { value: page } : null,
    surface_header_background: header ? { value: header } : null,
    surface_card_background: card ? { value: card.hex, samples: card } : null,
    color_text_primary: primary ? { value: primary } : null,
    color_text_secondary: secondary ? { value: secondary.hex, samples: secondary } : null,
    color_accent_background: accent ? { value: accent.hex, samples: accent } : null,
    color_link: link ? { value: link.hex, samples: link } : null,
    color_link_hover: hover ? { value: hover.hex, samples: hover } : null,
    color_border_default: border ? { value: border.hex, samples: border } : null,
    color_focus_ring: focus ? { value: focus.hex, samples: focus } : null,
    _all_text: text ? { value: text.hex, samples: text } : null,
  };
}

const ABSENT_REASON = {
  surface_header_background: 'шапка не найдена ни по тегу header, ни по признаку класса',
  surface_card_background: 'карточек с постером ≥60×60 на поверхности нет',
  color_text_secondary: 'весь видимый текст вне ссылок окрашен одним цветом: второго цвета текста у эталона нет',
  color_accent_background: 'интерактивных элементов с фоном, отличным от фона страницы, на поверхности нет',
  color_link: 'видимых ссылок с собственным текстом на поверхности нет',
  color_link_hover: 'ни одна из проверенных ссылок не меняет цвет при наведении',
  color_border_default: 'элементов с ненулевой видимой границей на поверхности нет',
  color_focus_ring: 'клавиатурная навигация не даёт видимого контура фокуса',
};

(async () => {
  const result = {
    url,
    surface,
    tool: 'tests/tools/measure_reference_colors.js',
    method: 'Playwright/Chromium CDP getComputedStyle, частотное ранжирование, два независимых прохода',
    passes: PASSES,
    measured_at_utc: new Date().toISOString(),
    viewports: {},
    errors: [],
  };

  let browser;
  try {
    browser = await chromium.launch(executablePath ? { executablePath } : {});
  } catch (error) {
    result.errors.push({ stage: 'launch', message: String(error).slice(0, 400) });
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(path.join(outDir, 'colors.json'), JSON.stringify(result, null, 2));
    process.exit(3);
  }

  fs.mkdirSync(outDir, { recursive: true });

  for (const width of viewports) {
    const height = width < 500 ? 844 : 1000;
    try {
      const startedAt = new Date().toISOString();
      const passes = [];
      for (let index = 0; index < PASSES; index += 1) {
        const context = await browser.newContext({
          viewport: { width, height },
          deviceScaleFactor: 1,
        });
        passes.push(await onePass(
          context, url, index === 0 ? path.join(outDir, `colors-${width}.png`) : null));
        await context.close();
      }

      const first = tokensOf(passes[0]);
      const second = tokensOf(passes[1]);
      const tokens = {};
      const unstable = [];
      const absent = [];
      for (const name of Object.keys(first)) {
        if (name.startsWith('_')) continue;
        const a = first[name];
        const b = second[name];
        if (!a || !b) {
          absent.push({ name, reason: ABSENT_REASON[name] || 'значение не получено ни одним проходом',
                        pass_a: a ? a.value : null, pass_b: b ? b.value : null });
          continue;
        }
        if (a.value !== b.value) {
          unstable.push({ name, pass_a: a.value, pass_b: b.value });
          continue;
        }
        tokens[name] = {
          value: a.value,
          stable: `${PASSES}/${PASSES} проходов дали одно значение`,
          samples: a.samples || null,
        };
      }

      const shot = path.join(outDir, `colors-${width}.png`);
      const digest = fs.existsSync(shot)
        ? crypto.createHash('sha256').update(fs.readFileSync(shot)).digest('hex')
        : null;

      result.viewports[width] = {
        viewport: { width, height, deviceScaleFactor: 1 },
        // Метки времени именно этой ширины: одна метка на весь прогон не
        // позволила бы сказать, когда снято конкретное значение.
        measured_from_utc: startedAt,
        measured_to_utc: new Date().toISOString(),
        http_status: passes[0].status,
        screenshot: { file: path.basename(shot), sha256: digest },
        probe_links: passes[0].raw.probeCount,
        focus_stops: passes[0].raw.focusBaseline.length,
        focus_kinds: passes[0].focusKinds,
        tokens,
        unstable,
        absent,
      };
    } catch (error) {
      result.errors.push({ stage: `viewport-${width}`, message: String(error).slice(0, 400) });
    }
  }

  await browser.close();
  fs.writeFileSync(path.join(outDir, 'colors.json'), JSON.stringify(result, null, 2));
  const measured = Object.keys(result.viewports).length;
  console.log(JSON.stringify({ surface, measured, errors: result.errors.length }));
  process.exit(measured > 0 ? 0 : 4);
})();

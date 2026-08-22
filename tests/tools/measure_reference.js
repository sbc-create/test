/*
 * Измерение референсного интерфейса. Скрипт СЧИТАЕТ, а не копирует: наружу
 * отдаются только числа (ширины, отступы, размеры шрифтов, пропорции, счётчики),
 * порядок секций по тегам и признаки поведения. Тексты, изображения, ссылки,
 * идентификаторы рекламы и каталог не сохраняются.
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const url = process.argv[2];
const outDir = process.argv[3];
const viewports = process.argv[4].split(',').map(Number);
const executablePath = process.env.FACTORY_CHROMIUM || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';

const measureInPage = () => {
  const round = (value) => Math.round(value * 100) / 100;
  const px = (value) => round(parseFloat(value) || 0);

  const body = document.body;
  const docWidth = document.documentElement.clientWidth;

  // Основной контейнер: самый широкий блок, который уже вьюпорта и содержит текст.
  const candidates = [...document.querySelectorAll('div, main, section, header, footer')]
    .map((node) => {
      const rect = node.getBoundingClientRect();
      return { node, width: round(rect.width), left: round(rect.left) };
    })
    .filter((item) => item.width > docWidth * 0.5 && item.width <= docWidth);
  const contentWidth = candidates.length
    ? Math.max(...candidates.filter((item) => item.width < docWidth).map((item) => item.width), 0)
    : 0;
  const gutter = contentWidth ? round((docWidth - contentWidth) / 2) : 0;

  const header = document.querySelector('header') || document.querySelector('[class*="header" i]');
  const headerRect = header ? header.getBoundingClientRect() : null;
  const headerStyle = header ? getComputedStyle(header) : null;

  const typography = {};
  for (const selector of ['body', 'h1', 'h2', 'h3', 'a', 'p', 'button']) {
    const node = document.querySelector(selector);
    if (!node) continue;
    const style = getComputedStyle(node);
    typography[selector] = {
      fontSize: px(style.fontSize),
      lineHeight: style.lineHeight === 'normal' ? 'normal' : px(style.lineHeight),
      fontWeight: style.fontWeight,
    };
  }

  // Пропорции карточек: изображения внутри ссылок — типичная карточка каталога.
  const ratios = {};
  for (const image of [...document.querySelectorAll('a img')].slice(0, 200)) {
    const rect = image.getBoundingClientRect();
    if (rect.width < 60 || rect.height < 60) continue;
    const ratio = round(rect.width / rect.height);
    const key = String(ratio);
    ratios[key] = (ratios[key] || 0) + 1;
  }

  // Порядок секций верхнего уровня: только теги, классы и высоты, без текста.
  const sections = [...(document.querySelector('main')?.children || body.children)]
    .slice(0, 40)
    .map((node, index) => {
      const rect = node.getBoundingClientRect();
      return {
        index,
        tag: node.tagName.toLowerCase(),
        height: round(rect.height),
        childCount: node.children.length,
      };
    })
    .filter((item) => item.height > 0);

  const player = document.querySelector('video-player, iframe[src*="player" i], video');
  const playerRect = player ? player.getBoundingClientRect() : null;

  const grids = [...document.querySelectorAll('*')]
    .filter((node) => getComputedStyle(node).display === 'grid')
    .slice(0, 20)
    .map((node) => {
      const style = getComputedStyle(node);
      return {
        columns: style.gridTemplateColumns.split(' ').filter(Boolean).length,
        gap: px(style.gap),
        children: node.children.length,
      };
    });

  return {
    documentWidth: docWidth,
    scrollHeight: round(document.documentElement.scrollHeight),
    horizontalOverflow: document.documentElement.scrollWidth > docWidth + 1,
    contentWidth,
    gutter,
    header: headerRect
      ? {
          height: round(headerRect.height),
          position: headerStyle.position,
          sticky: headerStyle.position === 'sticky' || headerStyle.position === 'fixed',
        }
      : null,
    typography,
    cardAspectRatios: Object.entries(ratios)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([ratio, count]) => ({ ratio: Number(ratio), count })),
    topLevelSections: sections,
    sectionCount: sections.length,
    grids,
    player: playerRect
      ? { width: round(playerRect.width), height: round(playerRect.height),
          aspectRatio: playerRect.height ? round(playerRect.width / playerRect.height) : null,
          tag: player.tagName.toLowerCase() }
      : null,
    linkCount: document.querySelectorAll('a[href]').length,
    imageCount: document.querySelectorAll('img').length,
    paginationLinks: document.querySelectorAll('a[href*="page" i]').length,
  };
};

(async () => {
  const result = { url, measured_at: new Date().toISOString(), viewports: {}, errors: [] };
  let browser;
  try {
    browser = await chromium.launch({ executablePath });
  } catch (error) {
    result.errors.push({ stage: 'launch', message: String(error).slice(0, 400) });
    fs.writeFileSync(path.join(outDir, 'measurements.json'), JSON.stringify(result, null, 2));
    process.exit(3);
  }

  for (const width of viewports) {
    const context = await browser.newContext({
      viewport: { width, height: width < 500 ? 844 : 1000 },
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();
    try {
      const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await page.waitForTimeout(1500);
      const measurements = await page.evaluate(measureInPage);
      measurements.httpStatus = response ? response.status() : null;
      result.viewports[width] = measurements;
      await page.screenshot({ path: path.join(outDir, `amd-online-${width}.png`), fullPage: false });
    } catch (error) {
      result.errors.push({ stage: `viewport-${width}`, message: String(error).slice(0, 400) });
    } finally {
      await context.close();
    }
  }

  await browser.close();
  fs.writeFileSync(path.join(outDir, 'measurements.json'), JSON.stringify(result, null, 2));
  const measured = Object.keys(result.viewports).length;
  console.log(JSON.stringify({ measured, errors: result.errors.length }));
  process.exit(measured > 0 ? 0 : 4);
})();

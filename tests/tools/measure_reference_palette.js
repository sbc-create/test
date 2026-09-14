/*
 * Палитра и плотность референса. Как и measure_reference.js, скрипт СЧИТАЕТ:
 * наружу отдаются только числа и цвета, без текста, разметки и изображений.
 */
const { chromium } = require('playwright');
const fs = require('fs');

const url = process.argv[2];
const out = process.argv[3];
const widths = (process.argv[4] || '1440').split(',').map(Number);

const probe = () => {
  const rgb = (v) => {
    const m = String(v).match(/-?\d+(\.\d+)?/g);
    if (!m) return null;
    return { r: +m[0], g: +m[1], b: +m[2], a: m[3] !== undefined ? +m[3] : 1 };
  };
  const area = (n) => { const r = n.getBoundingClientRect(); return r.width * r.height; };
  // Доминирующие поверхности: суммарная площадь по каждому фоновому цвету.
  const surfaces = {};
  for (const n of [...document.querySelectorAll('body *')].slice(0, 4000)) {
    const s = getComputedStyle(n);
    const bg = s.backgroundColor;
    if (!bg || bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent') continue;
    const a = area(n);
    if (a < 400) continue;
    surfaces[bg] = (surfaces[bg] || 0) + a;
  }
  // Акцент: самый частый цвет текста ссылок, отличный от основного текста.
  const linkColors = {};
  for (const a of [...document.querySelectorAll('a')].slice(0, 600)) {
    const c = getComputedStyle(a).color;
    linkColors[c] = (linkColors[c] || 0) + 1;
  }
  const bodyStyle = getComputedStyle(document.body);
  const header = document.querySelector('header') || document.querySelector('[class*="header" i]');
  return {
    body_background: bodyStyle.backgroundColor,
    body_color: bodyStyle.color,
    body_font_family: bodyStyle.fontFamily,
    html_background: getComputedStyle(document.documentElement).backgroundColor,
    header_background: header ? getComputedStyle(header).backgroundColor : null,
    header_color: header ? getComputedStyle(header).color : null,
    dominant_surfaces: Object.entries(surfaces).sort((a, b) => b[1] - a[1]).slice(0, 8)
      .map(([color, px]) => ({ color, area_px: Math.round(px), rgb: rgb(color) })),
    link_colors: Object.entries(linkColors).sort((a, b) => b[1] - a[1]).slice(0, 6)
      .map(([color, count]) => ({ color, count, rgb: rgb(color) })),
    card_like_count: document.querySelectorAll('a img').length,
    heading_count: document.querySelectorAll('h1,h2,h3').length,
    nav_link_count: document.querySelectorAll('header a, nav a').length,
  };
};

(async () => {
  const res = { url, measured_at: new Date().toISOString(), viewports: {} };
  const b = await chromium.launch();
  for (const w of widths) {
    const ctx = await b.newContext({ viewport: { width: w, height: w < 500 ? 844 : 1000 }, deviceScaleFactor: 1 });
    const p = await ctx.newPage();
    const r = await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(() => null);
    await p.waitForTimeout(2500);
    res.viewports[w] = { httpStatus: r ? r.status() : null, ...(await p.evaluate(probe)) };
    await ctx.close();
  }
  await b.close();
  fs.writeFileSync(out, JSON.stringify(res, null, 2));
  console.log(JSON.stringify({ ok: Object.keys(res.viewports).length }));
})();

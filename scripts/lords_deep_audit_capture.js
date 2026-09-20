/**
 * Deep-audit screenshot + occupancy capture (read-only).
 * Usage: node scripts/lords_deep_audit_capture.js
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const ROOT = '/home/claude/wt-lords-default-episode-01/artifacts/evidence/lords-three-distinct-deep-audit-2026-09-20';
const SHOT = path.join(ROOT, 'screenshots');
const CS = path.join(ROOT, 'CONTACT_SHEETS');
const RUN = '20260920T2148Z';
fs.mkdirSync(SHOT, { recursive: true });
fs.mkdirSync(CS, { recursive: true });
fs.mkdirSync(path.join(ROOT, '04-blocks'), { recursive: true });
fs.mkdirSync(path.join(ROOT, '05-occupancy'), { recursive: true });

const VIEWPORTS = [
  { name: '320x800', width: 320, height: 800 },
  { name: '390x844', width: 390, height: 844 },
  { name: '768x1024', width: 768, height: 1024 },
  { name: '1024x768', width: 1024, height: 768 },
  { name: '1366x768', width: 1366, height: 768 },
  { name: '1440x900', width: 1440, height: 900 },
  { name: '1920x1080', width: 1920, height: 1080 },
];

const SITES = [
  { id: 'lords-01', domain: 'lordfilm47.space', design: 'lords-cinema-v2' },
  { id: 'lords-02', domain: 'lordserial33.biz', design: 'lords-series-feed-v2' },
  { id: 'lords-03', domain: '1lordserials1.online', design: 'lords-curated-v2' },
];

function fname(parts) {
  return parts.filter(Boolean).join('__') + '.png';
}

async function gotoRetry(page, url, tries = 3) {
  let last;
  for (let i = 0; i < tries; i++) {
    try {
      return await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    } catch (e) {
      last = e;
      await page.waitForTimeout(500 * (i + 1));
    }
  }
  throw last;
}

async function shot(page, file) {
  const out = path.join(SHOT, file);
  await page.screenshot({ path: out, fullPage: false });
  return out;
}

async function shotFull(page, file) {
  const out = path.join(SHOT, file);
  await page.screenshot({ path: out, fullPage: true });
  return out;
}

async function measureHome(page) {
  return page.evaluate(() => {
    const design = document.documentElement.getAttribute('data-design') ||
      document.body.getAttribute('data-design');
    const sections = [...document.querySelectorAll('section.sec-rail, section.sec')].map((sec, idx) => {
      const h2 = sec.querySelector('h2');
      const title = h2 ? h2.innerText.trim() : `(section-${idx})`;
      const grid = sec.querySelector('.grid');
      const cards = [...sec.querySelectorAll('a.c')];
      const rect = sec.getBoundingClientRect();
      const gridRect = grid ? grid.getBoundingClientRect() : null;
      const cardRects = cards.map((c) => {
        const r = c.getBoundingClientRect();
        const img = c.querySelector('img.c__img');
        const none = c.querySelector('.c__none');
        const t = c.querySelector('.c__t');
        return {
          href: c.getAttribute('href'),
          w: Math.round(r.width),
          h: Math.round(r.height),
          top: Math.round(r.top + window.scrollY),
          left: Math.round(r.left + window.scrollX),
          hasImg: !!(img && img.getAttribute('src')),
          imgNaturalW: img ? img.naturalWidth : 0,
          imgNaturalH: img ? img.naturalHeight : 0,
          imgComplete: img ? img.complete : false,
          fallbackLetter: !!none,
          title: t ? t.innerText.trim() : '',
          titleOverflow: t ? (t.scrollHeight > t.clientHeight + 1 || t.scrollWidth > t.clientWidth + 1) : false,
        };
      });
      // geometry estimate
      let expectedCols = null, gap = null;
      if (grid && cards.length >= 2) {
        const cs = getComputedStyle(grid);
        gap = parseFloat(cs.columnGap || cs.gap || '0') || 0;
        const gw = gridRect.width;
        const cw = cardRects[0]?.w || 0;
        if (cw > 0) expectedCols = Math.max(1, Math.round((gw + gap) / (cw + gap)));
      }
      const hrefs = cardRects.map((c) => c.href);
      const dupInBlock = hrefs.length - new Set(hrefs).size;
      return {
        index: idx,
        title,
        className: sec.className,
        popularWeek: sec.getAttribute('data-popular-week'),
        popularDigest: sec.getAttribute('data-popular-digest'),
        y: Math.round(rect.top + window.scrollY),
        height: Math.round(rect.height),
        width: Math.round(rect.width),
        cardCount: cards.length,
        expectedCols,
        gap,
        gridWidth: gridRect ? Math.round(gridRect.width) : null,
        incompleteLastRow: expectedCols ? (cards.length % expectedCols !== 0) : null,
        blankSlotsEstimate: expectedCols ? ((expectedCols - (cards.length % expectedCols)) % expectedCols) : null,
        duplicateHrefsInBlock: dupInBlock,
        cards: cardRects,
      };
    });
    const allHrefs = sections.flatMap((s) => s.cards.map((c) => c.href));
    const horizOverflow = document.documentElement.scrollWidth > document.documentElement.clientWidth + 1;
    return {
      design,
      viewport: { w: window.innerWidth, h: window.innerHeight },
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      horizontalOverflow: horizOverflow,
      horizontalOverflowPx: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
      sections,
      totalCards: allHrefs.length,
      uniqueCards: new Set(allHrefs).size,
    };
  });
}

async function consoleCollector(page) {
  const errors = [];
  const failed = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('pageerror', (err) => errors.push(String(err)));
  page.on('response', (res) => {
    if (res.status() >= 400) failed.push({ url: res.url(), status: res.status() });
  });
  return { errors, failed };
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const summary = { run: RUN, sites: {}, screenshots: [], started: new Date().toISOString() };

  for (const site of SITES) {
    try {
    const base = `https://${site.domain}`;
    summary.sites[site.id] = { domain: site.domain, design: site.design, blocks: null, shots: [] };
    const context = await browser.newContext({
      userAgent: 'lords-deep-audit/1',
      locale: 'ru-RU',
    });
    const page = await context.newPage();
    const logs = await consoleCollector(page);

    // Full viewport matrix for home
    for (const vp of VIEWPORTS) {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await gotoRetry(page, base + '/');
      await page.waitForTimeout(800);
      const atf = fname([site.domain, 'home', 'atf', vp.name, 'audit', RUN]);
      const full = fname([site.domain, 'home', 'full', vp.name, 'audit', RUN]);
      await shot(page, atf);
      if (vp.name === '1440x900' || vp.name === '390x844') {
        await shotFull(page, full);
      }
      summary.screenshots.push(atf);
      summary.sites[site.id].shots.push(atf);
      if (vp.name === '1440x900') {
        const blocks = await measureHome(page);
        summary.sites[site.id].blocks = blocks;
        fs.writeFileSync(
          path.join(ROOT, '04-blocks', `${site.id}-home-blocks-1440.json`),
          JSON.stringify(blocks, null, 2)
        );
        // section screenshots
        const count = await page.locator('section.sec-rail, section.sec').count();
        for (let i = 0; i < Math.min(count, 10); i++) {
          const loc = page.locator('section.sec-rail, section.sec').nth(i);
          const sn = fname([site.domain, 'home', `block${i}`, '1440x900', 'audit', RUN]);
          try {
            await loc.screenshot({ path: path.join(SHOT, sn) });
            summary.screenshots.push(sn);
          } catch (_) {}
        }
        // footer
        const footer = page.locator('footer').first();
        if (await footer.count()) {
          const fn = fname([site.domain, 'home', 'footer', '1440x900', 'audit', RUN]);
          try { await footer.screenshot({ path: path.join(SHOT, fn) }); summary.screenshots.push(fn); } catch (_) {}
        }
        // open mobile menu only on small - skip here
      }
      if (vp.name === '390x844') {
        // open drawer if present
        const btn = page.locator('button.hd__menu, button[aria-label*="еню"], .hd__burger, [data-menu-toggle]').first();
        if (await btn.count()) {
          try {
            await btn.click({ timeout: 2000 });
            await page.waitForTimeout(400);
            const mn = fname([site.domain, 'home', 'menu-open', '390x844', 'audit', RUN]);
            await shot(page, mn);
            summary.screenshots.push(mn);
          } catch (_) {}
        }
      }
    }

    // catalog + title at 1440 and 390
    for (const route of [
      { type: 'catalog', path: '/catalog/' },
      { type: 'new', path: '/new/' },
      { type: 'search', path: '/search/?q=%D0%9D%D0%B5%D0%B4%D0%B5%D1%82%D1%81%D0%BA%D0%B8%D0%B5' },
    ]) {
      for (const vp of [VIEWPORTS.find(v => v.name === '1440x900'), VIEWPORTS.find(v => v.name === '390x844')]) {
        await page.setViewportSize({ width: vp.width, height: vp.height });
        await gotoRetry(page, base + route.path);
        await page.waitForTimeout(600);
        const sn = fname([site.domain, route.type, 'atf', vp.name, 'audit', RUN]);
        await shot(page, sn);
        summary.screenshots.push(sn);
        if (vp.name === '1440x900') {
          const fn = fname([site.domain, route.type, 'full', vp.name, 'audit', RUN]);
          await shotFull(page, fn);
          summary.screenshots.push(fn);
        }
        // open filters if any
        if (route.type === 'catalog' && vp.name === '390x844') {
          const fbtn = page.locator('button:has-text("Фильтр"), .filters__toggle, [data-filters-toggle]').first();
          if (await fbtn.count()) {
            try {
              await fbtn.click({ timeout: 2000 });
              await page.waitForTimeout(300);
              const ff = fname([site.domain, 'catalog', 'filters-open', '390x844', 'audit', RUN]);
              await shot(page, ff);
              summary.screenshots.push(ff);
            } catch (_) {}
          }
        }
      }
    }

    // pick first title from home
    await page.setViewportSize({ width: 1440, height: 900 });
    await gotoRetry(page, base + '/');
    const firstTitle = await page.locator('a.c[href^="/title/"]').first().getAttribute('href');
    if (firstTitle) {
      for (const vp of [VIEWPORTS.find(v => v.name === '1440x900'), VIEWPORTS.find(v => v.name === '390x844')]) {
        await page.setViewportSize({ width: vp.width, height: vp.height });
        await gotoRetry(page, base + firstTitle);
        await page.waitForTimeout(900);
        const sn = fname([site.domain, 'title', 'atf', vp.name, 'audit', RUN]);
        await shot(page, sn);
        summary.screenshots.push(sn);
        if (vp.name === '1440x900') {
          await shotFull(page, fname([site.domain, 'title', 'full', vp.name, 'audit', RUN]));
          // episode if link
          const ep = page.locator('a[href*="/episode-"]').first();
          if (await ep.count()) {
            const href = await ep.getAttribute('href');
            await gotoRetry(page, base + href);
            await page.waitForTimeout(900);
            await shot(page, fname([site.domain, 'episode', 'atf', '1440x900', 'audit', RUN]));
          }
        }
      }
      await page.setViewportSize({ width: 390, height: 844 });
      await gotoRetry(page, base + firstTitle);
      const ep2 = page.locator('a[href*="/episode-"]').first();
      if (await ep2.count()) {
        const href = await ep2.getAttribute('href');
        await gotoRetry(page, base + href);
        await page.waitForTimeout(700);
        await shot(page, fname([site.domain, 'episode', 'atf', '390x844', 'audit', RUN]));
      }
    }

    await page.setViewportSize({ width: 1440, height: 900 });
    await gotoRetry(page, base + '/title/this-title-does-not-exist-zzz-999999/');
    await shot(page, fname([site.domain, '404', 'atf', '1440x900', 'audit', RUN]));

    summary.sites[site.id].console_errors = logs.errors.slice(0, 50);
    summary.sites[site.id].failed_resources = logs.failed.filter(f => !f.url.includes('metrika') && !f.url.includes('mc.yandex')).slice(0, 80);
    await context.close();
    } catch (e) {
      summary.sites[site.id] = summary.sites[site.id] || { domain: site.domain };
      summary.sites[site.id].capture_error = String(e);
      console.error('SITE_FAIL', site.id, e.message || e);
    }
  }

  summary.finished = new Date().toISOString();
  summary.screenshot_count = summary.screenshots.length;
  fs.writeFileSync(path.join(ROOT, '03-screenshots', 'CAPTURE_SUMMARY.json'), JSON.stringify(summary, null, 2));
  // occupancy rollup
  const occ = {};
  for (const site of SITES) {
    occ[site.id] = summary.sites[site.id].blocks;
  }
  fs.writeFileSync(path.join(ROOT, '05-occupancy', 'HOME_OCCUPANCY.json'), JSON.stringify(occ, null, 2));
  console.log(JSON.stringify({
    screenshots: summary.screenshot_count,
    perSiteCards: Object.fromEntries(SITES.map(s => [s.id, summary.sites[s.id].blocks?.totalCards])),
    perSiteSections: Object.fromEntries(SITES.map(s => [s.id, summary.sites[s.id].blocks?.sections?.map(x => ({ t: x.title, n: x.cardCount, cols: x.expectedCols, blank: x.blankSlotsEstimate }))])),
  }, null, 2));
  await browser.close();
}

main().catch((e) => { console.error(e); process.exit(1); });

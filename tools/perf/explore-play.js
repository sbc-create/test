// Разведка нажатия Play: какие видеоэлементы появляются, в каких фреймах,
// есть ли реклама перед содержимым. node tools/perf/explore-play.js <url>
const { chromium } = require('/home/claude/node_modules/playwright-core');

const МЕДИА = `(() => { const f=[]; const w=(r,d)=>{ if(d>12||!r||!r.querySelectorAll) return;
  for(const el of r.querySelectorAll('*')){ const t=el.tagName.toLowerCase();
    if(t==='video') f.push(el); if(el.shadowRoot) w(el.shadowRoot,d+1);} };
  w(document,0); return f.map(v=>({src:(v.currentSrc||v.src||'').slice(0,60), rs:v.readyState, ct:+v.currentTime.toFixed(2), p:v.paused, w:v.videoWidth})); })()`;

(async () => {
  const url = process.argv[2];
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 } });
  const page = await ctx.newPage();
  const t0 = Date.now();
  const log = (s) => console.log(String(Date.now() - t0).padStart(6), s);
  page.on('request', (r) => { const u = r.url(); if (/okcdn|adsdk|an\.yandex|yandex\.ru\/ads|vast|strm|plapi/.test(u)) log(`> ${u.slice(0, 130)}`); });
  page.on('frameattached', (f) => log(`attach ${f.parentFrame() && f.parentFrame().url().slice(0, 50)}`));
  page.on('framenavigated', (f) => log(`frame ${f.url().slice(0, 120)}`));
  await page.goto(url, { waitUntil: 'load', timeout: 60000 });
  log('load');
  await page.waitForTimeout(6000);
  for (const f of page.frames()) log(`pre ${f.url().slice(0, 60)} ${JSON.stringify(await f.evaluate(МЕДИА).catch((e) => 'x'))}`);
  const el = await page.$('video-player');
  await el.scrollIntoViewIfNeeded();
  const b = await el.boundingBox();
  log(`click ${JSON.stringify(b)}`);
  await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2);
  for (let i = 0; i < 30; i++) {
    await page.waitForTimeout(1000);
    const st = [];
    for (const f of page.frames()) {
      const m = await f.evaluate(МЕДИА).catch(() => null);
      if (m && m.length) st.push(`${f.url().slice(8, 50)}=${JSON.stringify(m)}`);
    }
    log(st.join(' | '));
  }
  await page.screenshot({ path: process.argv[3] || 'var/perf/explore-play.png' });
  await browser.close();
})();

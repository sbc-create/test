// Разведка: последовательность запросов и событий плеера на одной странице.
// node tools/perf/explore.js <url>
const { chromium } = require('/home/claude/node_modules/playwright-core');

(async () => {
  const url = process.argv[2];
  const browser = await chromium.launch({ args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required', '--mute-audio'] });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 } });
  const page = await ctx.newPage();
  const t0 = Date.now();
  const log = (s) => console.log(String(Date.now() - t0).padStart(6), s);
  page.on('request', (r) => { if (!/\.(png|jpe?g|webp|svg|woff2?|gif)(\?|$)/.test(r.url())) log(`> ${r.resourceType().slice(0, 5)} ${r.method()} ${r.url().slice(0, 150)}`); });
  page.on('requestfinished', (r) => { const u = r.url(); if (/cdnvideohub|okcdn|m3u8|mpd|playlist|\.ts|\.m4s/.test(u)) log(`< ${u.slice(0, 120)}`); });
  page.on('console', (m) => { if (m.type() === 'error') log(`console.error ${m.text().slice(0, 160)}`); });
  page.on('framenavigated', (f) => log(`frame ${f.url().slice(0, 140)}`));
  console.log('codecs', await page.evaluate(() => ({ h264: MediaSource.isTypeSupported('video/mp4; codecs="avc1.42E01E"'), aac: MediaSource.isTypeSupported('audio/mp4; codecs="mp4a.40.2"') })).catch((e) => String(e)));
  await page.goto(url, { waitUntil: 'load', timeout: 60000 });
  log('load');
  await page.waitForTimeout(25000);
  const frames = page.frames().map((f) => f.url().slice(0, 140));
  console.log('frames', frames);
  await browser.close();
})();

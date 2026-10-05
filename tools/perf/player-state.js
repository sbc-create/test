// Что видит посетитель в рамке плеера через N секунд: состояние и текст.
// node tools/perf/player-state.js <url> <png> [сек]
const { chromium } = require('/home/claude/node_modules/playwright-core');
(async () => {
  const [url, png, сек] = process.argv.slice(2);
  const b = await chromium.launch({ args: ['--no-sandbox', '--mute-audio'] });
  const p = await (await b.newContext({ viewport: { width: 1366, height: 900 } })).newPage();
  await p.goto(url, { waitUntil: 'load', timeout: 60000 });
  await p.waitForTimeout((+сек || 10) * 1000);
  const s = await p.evaluate(() => {
    const r = document.querySelector('[data-player]');
    const t = document.querySelector('[data-player-state]');
    return { state: r && r.getAttribute('data-state'), text: t && !t.hidden ? t.textContent.trim().slice(0, 200) : null };
  });
  const el = await p.$('video-player');
  if (el) await el.scrollIntoViewIfNeeded();
  await p.screenshot({ path: png });
  console.log(JSON.stringify(s));
  await b.close();
})();

// Кто трогает <video-player> во время просмотра: атрибуты, замена узла,
// события страницы. node tools/perf/player-mutations.js <url> <секунд>
const { chromium } = require('/home/claude/node_modules/playwright-core');
(async () => {
  const [url, сек] = process.argv.slice(2);
  const b = await chromium.launch({ args: ['--no-sandbox', '--mute-audio', ...((process.argv.find((a) => a.startsWith('--resolve=')) ? [`--host-resolver-rules=MAP ${process.argv.find((a) => a.startsWith('--resolve=')).slice(10).replace('=', ' ')}`] : []))] });
  const p = await (await b.newContext({ viewport: { width: 1366, height: 900 } })).newPage();
  await p.addInitScript(() => {
    window.__mut = [];
    const t0 = performance.now();
    const лог = (s) => window.__mut.push(`${Math.round(performance.now() - t0)} ${s}`);
    const следить = () => {
      const el = document.querySelector('video-player');
      if (!el) return setTimeout(следить, 50);
      лог('video-player найден');
      new MutationObserver((ms) => ms.forEach((m) => лог(`attr ${m.attributeName}=${String(el.getAttribute(m.attributeName)).slice(0, 60)}`)))
        .observe(el, { attributes: true });
      new MutationObserver((ms) => ms.forEach((m) => {
        m.removedNodes.forEach((n) => лог(`removed <${(n.tagName || '#').toLowerCase()}> из <${m.target.tagName.toLowerCase()}>`));
        m.addedNodes.forEach((n) => лог(`added <${(n.tagName || '#').toLowerCase()}> в <${m.target.tagName.toLowerCase()}>`));
      })).observe(document.body, { childList: true, subtree: true });
      const st = document.querySelector('[data-player]');
      if (st) new MutationObserver((ms) => ms.forEach((m) => лог(`[data-player] ${m.attributeName}=${st.getAttribute(m.attributeName)}`))).observe(st, { attributes: true });
    };
    document.addEventListener('DOMContentLoaded', следить);
    window.addEventListener('message', (e) => { try { лог(`message ${e.origin} ${JSON.stringify(e.data).slice(0, 120)}`); } catch (x) { /* */ } });
  });
  await p.goto(url, { waitUntil: 'load', timeout: 60000 });
  await p.waitForTimeout(6000);
  const el = await p.$('video-player'); await el.scrollIntoViewIfNeeded();
  const box = await el.boundingBox();
  await p.evaluate(() => window.__mut.push('---- CLICK ----'));
  await p.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await p.waitForTimeout((+сек || 40) * 1000);
  for (const s of await p.evaluate(() => window.__mut)) console.log(s);
  await b.close();
})();

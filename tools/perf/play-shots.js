// Нажать Play и снять, что видит посетитель, в моменты T (с), плюс видео во
// всех фреймах. node tools/perf/play-shots.js <url> <префикс png> 3,10,30,60,90
const { chromium } = require('/home/claude/node_modules/playwright-core');
const МЕДИА = `(() => { const f=[]; const w=(r,d)=>{ if(d>12||!r||!r.querySelectorAll) return;
  for(const el of r.querySelectorAll('*')){ if(el.tagName==='VIDEO') f.push({src:(el.currentSrc||el.src||'').slice(0,50),ct:+el.currentTime.toFixed(1),p:el.paused,rs:el.readyState});
    if(el.shadowRoot) w(el.shadowRoot,d+1);} }; w(document,0); return f; })()`;
(async () => {
  const [url, префикс, моменты] = process.argv.slice(2);
  const b = await chromium.launch({ args: ['--no-sandbox', '--mute-audio', ...((process.argv.find((a) => a.startsWith('--resolve=')) ? [`--host-resolver-rules=MAP ${process.argv.find((a) => a.startsWith('--resolve=')).slice(10).replace('=', ' ')}`] : []))] });
  const p = await (await b.newContext({ viewport: { width: 1366, height: 900 } })).newPage();
  await p.goto(url, { waitUntil: 'load', timeout: 60000 });
  await p.waitForTimeout(6000);
  const el = await p.$('video-player'); await el.scrollIntoViewIfNeeded();
  const box = await el.boundingBox();
  const t0 = Date.now();
  await p.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  for (const s of (моменты || '3,10,30,60,90').split(',').map(Number)) {
    await p.waitForTimeout(Math.max(0, s * 1000 - (Date.now() - t0)));
    const кадры = [];
    for (const f of p.frames()) { const m = await f.evaluate(МЕДИА).catch(() => null); if (m && m.length) кадры.push(`${f.url().slice(8, 45)} ${JSON.stringify(m)}`); }
    await p.screenshot({ path: `${префикс}-${s}s.png`, clip: { x: box.x, y: Math.max(0, box.y - (await p.evaluate(() => scrollY)) ), width: box.width, height: box.height } }).catch(() => p.screenshot({ path: `${префикс}-${s}s.png` }));
    console.log(`${s}s frames=${p.frames().length} ${кадры.join(' | ')}`);
  }
  await b.close();
})();

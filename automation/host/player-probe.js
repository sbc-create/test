const path = require('path');
let chromium = null;
for (const где of ['/srv/site-factory/repo/node_modules/playwright',
                   '/srv/site-factory/repo/node_modules/playwright-core',
                   'playwright', 'playwright-core']) {
  try { chromium = require(где).chromium; break; } catch { }
}
if (!chromium) { console.error('playwright не найден'); process.exit(4); }
const URL = process.argv.find(a => a.startsWith('http'));
(async () => {
  const b = await chromium.launch({ args: ['--no-sandbox'] });
  const p = await b.newContext({ viewport: { width: 1280, height: 900 } }).then(c => c.newPage());
  await p.goto(URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await p.waitForTimeout(4000);
  for (const сел of ['.player-shell button', '.portal-player-chrome', '.player-shell']) {
    const э = await p.$(сел);
    if (э) { await э.click({ timeout: 3000 }).catch(() => {}); break; }
  }
  await p.waitForTimeout(8000);
  const сводка = await p.evaluate(() => {
    const кнопки = [...document.querySelectorAll('button,a,[role=button]')]
      .map(e => (e.innerText || '').trim()).filter(t => t && t.length < 40).slice(0, 25);
    return {
      iframes: [...document.querySelectorAll('iframe')].map(f => (f.src || '').slice(0, 90)),
      video: document.querySelectorAll('video').length,
      элементы: [...document.querySelectorAll('[class*=player],[id*=player],video-player')]
        .map(e => e.tagName + '.' + (e.className || '').toString().slice(0, 40)).slice(0, 8),
      кнопки,
      плеер: [...document.querySelectorAll('video-player')].map(e => {
        const о = {}; for (const a of e.attributes) о[a.name] = a.value; return о; }),
      серии: [...document.querySelectorAll('a,button')]
        .map(e => (e.innerText || '').trim())
        .filter(t => /^(Эпизод|Серия)\s*\d+$/i.test(t)).slice(0, 12),
    };
  });
  console.log(JSON.stringify(сводка, null, 1));
  for (const f of p.frames()) {
    const v = await f.evaluate(() => {
      const вид = [...document.querySelectorAll('video')];
      return вид.map(x => ({ rs: x.readyState, d: x.duration, t: x.currentTime }));
    }).catch(() => null);
    if (v && v.length) console.log('кадр', f.url().slice(0, 80), JSON.stringify(v));
  }
  await b.close();
})();

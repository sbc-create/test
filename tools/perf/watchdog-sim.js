// Проверка сторожа плеера на сценарии с рекламой без настоящей рекламы.
//
// Страницу отдаёт копия витрины, а SDK и iframe провайдера подменяются:
// поддельный фрейм шлёт родителю те же сообщения, что настоящий (снято на
// живом плеере 2026-10-05): statechange:ready → по клику requestPlay →
// adStart + rollState:start → AD_S секунд рекламы → adComplete + rollState:
// complete + adClosed → statechange:playing и timeupdate каждую секунду.
//
// node tools/perf/watchdog-sim.js <url> <домен=127.0.0.1:порт> <сек рекламы> <клик через, с> <смотреть, с>
const { chromium } = require('/home/claude/node_modules/playwright-core');

const [url, подмена, adS, кликС, смотретьС] = process.argv.slice(2);
const SDK = `
class VP extends HTMLElement {
  connectedCallback() {
    if (this.shadowRoot) return;
    const r = this.attachShadow({ mode: 'open' });
    const f = document.createElement('iframe');
    f.src = 'https://player.cdnvideohub.com/s2/fake/frame/?t=' + Date.now();
    f.style.cssText = 'width:100%;height:400px;border:0';
    r.appendChild(f);
  }
}
if (!customElements.get('video-player')) customElements.define('video-player', VP);`;
const FRAME = `<!doctype html><body style="margin:0;background:#222;color:#fff;height:400px" id=b>fake player
<script>
const ORIGIN='*';
const send=(eventType,data)=>parent.postMessage(JSON.stringify({eventType,data,key:'cvh_player_2.31.11'}),ORIGIN);
setTimeout(()=>send('statechange','ready'),400);
let started=false;
document.getElementById('b').addEventListener('click',()=>{
  if(started) return; started=true;
  send('requestPlay'); send('statechange','paused');
  if (${+adS} < 0) return;  // сломанный источник: после нажатия тишина
  setTimeout(()=>{ send('adStart','Preroll'); send('rollState',{type:'Preroll',state:'start'}); },800);
  setTimeout(()=>{ send('adComplete','Preroll'); send('rollState',{type:'Preroll',state:'complete'}); send('adClosed');
    send('statechange','playing'); let p=0; setInterval(()=>{ p+=1; send('timeupdate',{position:p,duration:5000}); },1000); }, 800+${(+adS || 40) * 1000});
});
</script></body>`;

(async () => {
  const [домен, адрес] = подмена.split('=');
  const b = await chromium.launch({ args: ['--no-sandbox', '--mute-audio', `--host-resolver-rules=MAP ${домен} ${адрес}`] });
  const ctx = await b.newContext({ viewport: { width: 1366, height: 900 } });
  await ctx.route(/player\.cdnvideohub\.com\/s2\/stable\/video-player\.umd\.js/, (r) => r.fulfill({ status: 200, contentType: 'application/javascript', body: SDK }));
  await ctx.route(/player\.cdnvideohub\.com\/s2\/fake\/frame\//, (r) => r.fulfill({ status: 200, contentType: 'text/html', body: FRAME }));
  await ctx.route(/plapi\.cdnvideohub\.com|yandex|googlesyndication|adfox|mc\.yandex/, (r) => r.abort());
  const p = await ctx.newPage();
  await p.addInitScript(() => {
    window.__log = [];
    const t0 = performance.now();
    const лог = (s) => window.__log.push(`${(performance.now() - t0) / 1000 | 0}s ${s}`);
    document.addEventListener('DOMContentLoaded', () => {
      new MutationObserver((ms) => ms.forEach((m) => {
        m.removedNodes.forEach((n) => { if (n.tagName === 'VIDEO-PLAYER') лог('ПЛЕЕР УДАЛЁН'); });
        m.addedNodes.forEach((n) => { if (n.tagName === 'VIDEO-PLAYER') лог('плеер смонтирован заново'); });
      })).observe(document.body, { childList: true, subtree: true });
      const st = document.querySelector('[data-player]');
      if (st) new MutationObserver(() => { const s = st.getAttribute('data-state'); if (window.__last !== s) { window.__last = s; лог(`state=${s}`); } })
        .observe(st, { attributes: true, attributeFilter: ['data-state'] });
    });
  });
  await p.goto(url, { waitUntil: 'load', timeout: 60000 });
  await p.waitForTimeout((+кликС || 5) * 1000);
  const fr = p.frames().find((f) => /fake\/frame/.test(f.url()));
  if (fr) await fr.click('#b'); else console.log('фрейм не найден');
  await p.evaluate(() => window.__log.push('---- CLICK ----'));
  await p.waitForTimeout((+смотретьС || 80) * 1000);
  const итог = await p.evaluate(() => {
    const st = document.querySelector('[data-player-state]');
    return { state: document.querySelector('[data-player]').getAttribute('data-state'),
             overlay: st && !st.hidden ? st.textContent.trim().slice(0, 80) : null,
             players: document.querySelectorAll('video-player').length,
             attempt: (document.querySelector('video-player') || {}).getAttribute && document.querySelector('video-player').getAttribute('data-attempt'),
             log: window.__log };
  });
  console.log(JSON.stringify(итог, null, 1));
  await b.close();
})();

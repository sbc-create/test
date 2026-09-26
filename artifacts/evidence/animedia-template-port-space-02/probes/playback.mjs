// Воспроизведение видео, а не монтирование плеера.
//
// Монтирование — это наличие <video-player> в разметке; оно ничего не говорит
// о том, пошла ли картинка. Здесь успех подтверждается тремя независимыми
// признаками, и все три обязаны сойтись:
//   1. провайдер отдал плейлист и поток (коды сети);
//   2. провайдер прислал `timeupdate`/`started` — это и есть определение
//      «картинка пошла» у самой витрины: на этих событиях СКРИПТ_СОБЫТИЯ_
//      ПРОСМОТРА шлёт маячок /event/play;
//   3. `currentTime` у <video> растёт. Элемент лежит В КАДРЕ провайдера
//      (player.cdnvideohub.com/.../frame/), поэтому обходятся кадры страницы,
//      а не document: `document.querySelector('video')` здесь всегда null, и
//      проверка, построенная на нём, объявляет отказ на работающем плеере.
//
// Издатель берётся из УЖЕ СУЩЕСТВУЮЩЕЙ разрешённой конфигурации витрины
// (LORDS_PLAYER_CONFIG в юните стенда). Значение сюда не попадает и
// умолчанием для новых доменов не становится: у витрины без своего
// player-<site>.json плеера нет вовсе.
import { chromium } from 'playwright';
const БАЗА = process.env.ANIMEDIA_PROBE_BASE || 'http://127.0.0.1:9310';
const АДРЕС = process.argv[2];
const ок = [], плохо = [];
const п = (и, у, д = '') => (у ? ок : плохо).push(и + (д ? ` — ${д}` : ''));
if (!АДРЕС) { console.error('нужен адрес серии аргументом'); process.exit(2); }

const найтиВидео = `(function(){
  function найти(к){
    var d = к.querySelector && к.querySelector('video'); if (d) return d;
    var все = к.querySelectorAll ? к.querySelectorAll('*') : [];
    for (var i=0;i<все.length;i++) if (все[i].shadowRoot){
      var в = найти(все[i].shadowRoot); if (в) return в; }
    return null;
  }
  return найти(document);
})()`;

const b = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
const c = await b.newContext({ viewport: { width: 1280, height: 800 } });
const p = await c.newPage();
const сеть = [], маячки = [], события = [];
p.on('response', r => { if (/cdnvideohub/.test(r.url())) сеть.push([r.status(), r.url()]); });
p.on('request', r => { if (r.url().includes('/event/play')) маячки.push(r.method()); });
await p.exposeFunction('__ev', e => события.push(e));
await p.addInitScript(() => {
  window.addEventListener('message', e => {
    if (!e.origin || e.origin.indexOf('cdnvideohub') < 0) return;
    let d = e.data; try { if (typeof d === 'string') d = JSON.parse(d); } catch (x) { return; }
    if (d && d.eventType) window.__ev(d.eventType);
  });
});
await p.goto(БАЗА + АДРЕС, { waitUntil: 'load' });
п('плеер смонтирован', await p.evaluate(() => !!document.querySelector('video-player')));

// Ждём появления <video> в любом кадре страницы.
let кадр = null, снимок = null;
for (let i = 0; i < 60 && !кадр; i++) {
  for (const f of p.frames()) {
    try {
      const s = await f.evaluate(`(function(){var v=${найтиВидео};return v?{readyState:v.readyState,
        duration:Math.round(v.duration||0),paused:v.paused,
        currentTime:+(v.currentTime||0).toFixed(2)}:null;})()`);
      if (s) { кадр = f; снимок = s; break; }
    } catch (e) { /* кадр ещё не готов */ }
  }
  if (!кадр) await p.waitForTimeout(1000);
}
п('элемент воспроизведения появился', !!кадр,
  кадр ? `${кадр.url().replace(/^https:\/\//, '').slice(0, 55)} ${JSON.stringify(снимок)}` : 'за 60 с не появился');

// Рост измеряется с запасом по времени: провайдер может пустить преролл, и
// основное видео всё это время стоит на 0.08 с `paused:true`. Шестисекундное
// окно попадало внутрь рекламы и объявляло отказ на работающем плеере.
let рост = null;
if (кадр) {
  рост = await кадр.evaluate(`(async function(){
    var v = ${найтиВидео};
    var t0 = v.currentTime, край = Date.now() + 90000, было = t0, шагов = 0;
    while (Date.now() < край) {
      v = ${найтиВидео} || v;
      if (v.paused) { try { await v.play(); } catch(e) {} }
      await new Promise(function(r){ setTimeout(r, 1000); });
      if (v.currentTime > было + 0.05) { шагов++; было = v.currentTime; }
      if (шагов >= 3) break;
    }
    return {t0:+t0.toFixed(2), t1:+было.toFixed(2), шагов: шагов,
            duration: Math.round(v.duration||0), paused: v.paused,
            readyState: v.readyState};
  })()`);
}
п('плейлист получен от провайдера',
  сеть.some(([s, u]) => s === 200 && u.includes('/playlist?')));
п('поток видео получен от провайдера',
  сеть.some(([s, u]) => s === 200 && /\/player\/sv\/video\//.test(u)));
п('провайдер объявил воспроизведение',
  события.includes('timeupdate') || события.includes('started'),
  события.slice(-4).join(','));
п('currentTime растёт — картинка идёт',
  !!рост && рост.шагов >= 3, JSON.stringify(рост));
if (события.some(e => /^ad/.test(e))) {
  console.log('ПРЕРОЛЛ: провайдер пустил рекламу перед контентом —',
    события.filter(e => /^ad/.test(e)).slice(0, 5).join(','));
}
п('витрина засчитала просмотр маячком /event/play', маячки.length > 0,
  `запросов ${маячки.length}`);

// Переход между сериями — и плеер на соседней серии тоже поднимается.
const след = await p.evaluate(() =>
  [...document.querySelectorAll('.zepnav a')].map(a => a.getAttribute('href'))[0] || '');
if (след) {
  const о = await p.goto(БАЗА + след, { waitUntil: 'load' });
  п('переход между сериями открывается', о.status() === 200, `код ${о.status()}`);
  п('на соседней серии плеер подключается',
    await p.evaluate(() => !!document.querySelector('video-player')));
} else {
  п('переход между сериями есть', false, 'ссылок перехода на странице нет');
}
await b.close();
console.log('СЕТЬ:', сеть.filter(([s, u]) => /playlist|\/sv\/video\//.test(u))
  .map(([s, u]) => `${s} ${u.replace(/^https:\/\//, '').slice(0, 60)}`).join(' | '));
console.log('СОБЫТИЯ:', события.join(','));
console.log(`\nОК: ${ок.length}   ПЛОХО: ${плохо.length}`);
for (const с of ок) console.log('  ·', с);
for (const с of плохо) console.log('  ✗', с);
process.exit(плохо.length ? 1 : 0);

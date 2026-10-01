/**
 * Чей publisher ID РЕАЛЬНО уходит провайдеру с живой витрины.
 *
 * Зачем отдельная проверка. Атрибут `data-publisher-id` в разметке и код 200 на
 * странице просмотра не доказывают ничего: разметку мог отдать кэш, а номер в
 * ней — не тот, с которым плеер потом идёт за плейлистом. Поэтому успехом здесь
 * считается совпадение трёх разных измерений:
 *
 *   1. в РАЗМЕТКЕ страницы стоит ожидаемый номер;
 *   2. в ФАКТИЧЕСКОМ запросе к plapi.cdnvideohub.com параметр `pub` равен ему же,
 *      и ни один запрос за весь сеанс не унёс прежний номер;
 *   3. запись ИГРАЕТ: медиа-элемент дошёл до readyState>=2 и время выросло.
 *
 * Отдельно проверяется переключение серии: плеер пересобирается, и прежний
 * номер мог бы вернуться именно здесь — из другого пути формирования запроса.
 *
 * Медиа живёт в iframe провайдера и ещё глубже — в shadow DOM, поэтому элемент
 * ищется обходом теневых корней.
 *
 * Аргументы:
 *   --url <адрес страницы просмотра>  --expect <новый pub>  --forbid <прежний pub>
 *   [--switch <адрес другой серии>] [--out <json>] [--viewport desktop|mobile]
 */
const fs = require('fs');
const path = require('path');

const КАНДИДАТЫ = [
  path.join('/srv/site-factory/repo', 'node_modules', 'playwright-core'),
  '/home/claude/node_modules/playwright-core',
];
let chromium = null;
for (const к of КАНДИДАТЫ) {
  try { chromium = require(к).chromium; break; } catch (e) { /* следующий */ }
}
if (!chromium) { console.error('playwright-core не найден'); process.exit(2); }

function arg(имя, поумолчанию = null) {
  const i = process.argv.indexOf(имя);
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : поумолчанию;
}

const МЕДИА = `(() => { const f=[]; const w=(r,d)=>{ if(d>12||!r||!r.querySelectorAll) return;
  for(const el of r.querySelectorAll('*')){ const t=el.tagName?el.tagName.toLowerCase():'';
    if(t==='video'||t==='audio') f.push(el); if(el.shadowRoot) w(el.shadowRoot,d+1);} };
  w(document,0); return f; })()`;

const ВИДЫ = {
  desktop: { viewport: { width: 1366, height: 900 }, isMobile: false },
  mobile: {
    viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true,
    deviceScaleFactor: 3,
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
  },
};

/** Вытащить pub из любого обращения к API провайдера. */
function издательЗапроса(url) {
  if (!/plapi\.cdnvideohub\.com/.test(url)) return null;
  const м = /[?&]pub=(\d+)/.exec(url);
  return м ? м[1] : null;
}

async function ждатьИгру(page, мс = 90000) {
  const предел = Date.now() + мс;
  let первое = null;
  let готово = false;
  while (Date.now() < предел) {
    for (const f of page.frames()) {
      let снимок = null;
      try {
        снимок = await f.evaluate(`(() => { const m=${МЕДИА};
          if(!m.length) return null; const e=m.find(x=>x.readyState>=2)||m[0];
          return { readyState: e.readyState, t: e.currentTime, paused: e.paused,
                   duration: e.duration || null }; })()`);
      } catch (e) { continue; }
      if (!снимок) continue;
      // Пуск: без жеста браузер не начинает сам, а без звука начинает.
      // Без этих двух строк проверка упиралась в readyState>=2 с нулевым
      // приростом времени и объявляла отказ там, где отказа нет: запись
      // просто ждала, когда её попросят играть.
      if (снимок.paused || снимок.t === 0) {
        try {
          await f.evaluate(`(()=>{const v=${МЕДИА}[0]; if(!v) return;
            v.muted=true; const p=v.play(); if(p&&p.catch)p.catch(()=>{});})()`);
        } catch (e) { /* рамка могла пересобраться */ }
      }
      if (снимок.readyState >= 2) {
        готово = true;
        if (первое === null || снимок.t < первое) первое = снимок.t;
        // Время обязано вырасти: readyState сам по себе — только готовность.
        if (снимок.t - первое >= 10) {
          return { играет: true, ...снимок, прирост: Number((снимок.t - первое).toFixed(2)) };
        }
      }
    }
    await page.waitForTimeout(500);
  }
  return { играет: false, готовность_достигнута: готово,
           прирост: первое === null ? null : 0 };
}

(async () => {
  const адрес = arg('--url');
  const ожидается = arg('--expect');
  const запрещён = arg('--forbid');
  const переключить = arg('--switch');
  const вид = ВИДЫ[arg('--viewport', 'desktop')] || ВИДЫ.desktop;
  if (!адрес || !ожидается) {
    console.error('нужны --url и --expect'); process.exit(2);
  }

  const browser = await chromium.launch({ args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'] });
  const ctx = await browser.newContext({ ...вид, locale: 'ru-RU' });
  const итог = { url: адрес, expect: ожидается, forbid: запрещён || null, viewport: arg('--viewport', 'desktop') };
  const запросы = [];
  const page = await ctx.newPage();
  page.on('request', (r) => {
    const pub = издательЗапроса(r.url());
    if (pub) запросы.push({ pub, url: r.url().slice(0, 200), phase: итог.phase || 'open' });
  });

  try {
    итог.phase = 'open';
    const о = await page.goto(адрес, { waitUntil: 'domcontentloaded', timeout: 60000 });
    итог.http = о ? о.status() : null;
    // 1. разметка
    итог.markup_pub = await page.evaluate(`(() => { const e=document.querySelector('video-player');
      return e ? e.getAttribute('data-publisher-id') : null; })()`);
    // плеер часто ждёт жеста/видимости
    try { await page.evaluate('window.scrollTo(0, 400)'); } catch (e) {}
    try { await (await page.$('video-player')).click({ timeout: 5000 }); } catch (e) {}
    const игра = await ждатьИгру(page);
    итог.playback = игра;

    // 2. переключение серии — прежний номер мог бы вернуться здесь
    if (переключить) {
      итог.phase = 'switch';
      const о2 = await page.goto(переключить, { waitUntil: 'domcontentloaded', timeout: 60000 });
      итог.switch_http = о2 ? о2.status() : null;
      итог.switch_markup_pub = await page.evaluate(`(() => { const e=document.querySelector('video-player');
        return e ? e.getAttribute('data-publisher-id') : null; })()`);
      try { await page.evaluate('window.scrollTo(0, 400)'); } catch (e) {}
      try { await (await page.$('video-player')).click({ timeout: 5000 }); } catch (e) {}
      итог.switch_playback = await ждатьИгру(page);
      итог.switch_url = переключить;
    }
  } catch (e) {
    итог.error = String(e).slice(0, 300);
  } finally {
    итог.requests = запросы;
    итог.pubs_seen = [...new Set(запросы.map((з) => з.pub))].sort();
    итог.forbidden_seen = запрещён ? итог.pubs_seen.includes(запрещён) : null;
    итог.expected_seen = итог.pubs_seen.includes(ожидается);
    итог.verdict =
      итог.expected_seen && !итог.forbidden_seen
      && итог.markup_pub === ожидается
      && итог.playback && итог.playback.играет
      && (!переключить || (итог.switch_markup_pub === ожидается
                           && итог.switch_playback && итог.switch_playback.играет))
        ? 'PASS' : 'FAIL';
    const куда = arg('--out');
    if (куда) fs.writeFileSync(куда, JSON.stringify(итог, null, 1), 'utf-8');
    console.log(JSON.stringify(итог, null, 1));
    await browser.close();
    process.exit(итог.verdict === 'PASS' ? 0 : 1);
  }
})();

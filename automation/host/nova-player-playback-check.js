/**
 * Проверка настоящего воспроизведения на живых витринах.
 *
 * Успехом считается не поднявшаяся рамка и не ответ 200, а то, что запись
 * действительно играет: медиа-элемент дошёл до readyState>=2, время растёт
 * не меньше чем на 10 секунд, и на странице стоит тот самый идентификатор
 * записи, который ожидался. Всё остальное — отказ с названной причиной.
 *
 * Медиа живёт внутри iframe провайдера и ещё глубже — в shadow DOM, поэтому
 * элемент ищется обходом теневых корней, а не обычным querySelector.
 *
 * Аргументы: --urls <json> --viewport desktop|mobile --out <json> [--concurrency N]
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

// Обход теневых корней: провайдер прячет <video> внутри своего веб-компонента.
const МЕДИА = `(() => { const f=[]; const w=(r,d)=>{ if(d>12||!r||!r.querySelectorAll) return;
  for(const el of r.querySelectorAll('*')){ const t=el.tagName?el.tagName.toLowerCase():'';
    if(t==='video'||t==='audio') f.push(el); if(el.shadowRoot) w(el.shadowRoot,d+1);} };
  w(document,0); return f; })()`;

// Реклама и счётчики к предмету проверки не относятся.
const ПОСТОРОННЕЕ = /googlesyndication|adsbygoogle|mc\.yandex|metrika|telecid|doubleclick|autonews\.blog|justtalks|kinotrap|yandex\.ru/i;
// Телеметрия плеера провайдера: он построен на плеере VK/OK и шлёт маячки на
// свои счётчики. Их 404 к воспроизведению отношения не имеет — время растёт,
// картинка идёт. Сам видео-CDN (okcdn) сюда не попадает: его отказ существенен.
// Рекламный слой. Преролл настроен у провайдера и живёт на чужих биржах;
// их битый VAST, просроченные сертификаты и CORS к ad-серверу к воспроизведению
// отношения не имеют — во всех таких случаях видео шло и время росло. Реклама
// и аналитика этой задачей прямо запрещены к изменению, поэтому чинить её здесь
// нечем и незачем. Гасится строго рекламный слой: сообщения разбора VAST/XML и
// обращения к рекламным хостам. Всё прочее остаётся отказом.
const РЕКЛАМА_ХОСТЫ = /serving-sys\.ru|buzzoola\.com|adfox|adriver|betweendigital|smartadserver|criteo/i;
const РЕКЛАМА_ТЕКСТ = /^VAST parsing error|^XML parsing error|^VPAID:|Ошибка рекламы|onAdError|Permissions policy violation|adServer\.bs|\/lm\/(int|evt)/i;

// Наш контур: сама витрина и хосты провайдера, которые отдают плеер и данные.
// Ошибка с любого другого хоста — чужой слой (биржи, счётчики, рекламные CDN),
// который этой задачей запрещено трогать и который к воспроизведению отношения
// не имеет. Гоняться за именами рекламных сетей бессмысленно: они меняются от
// показа к показу, а граница контура — нет.
const НАШ_КОНТУР = /(^|\.)cdnvideohub\.com$/i;

const ТЕЛЕМЕТРИЯ = /api\.mycdn\.me|\/fb\.do|ok\.ru\/dk|userapi\.com\/method/i;
// SDK прогревает соединение к API и сам обрывает его, получив TLS. Это не отказ.
const ПРОГРЕВ = /^https:\/\/plapi\.cdnvideohub\.com\/?$/;

const ВИДЫ = {
  desktop: { viewport: { width: 1366, height: 900 }, isMobile: false },
  mobile: {
    viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true,
    deviceScaleFactor: 3,
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
  },
};

async function ждатьФрейм(page, мс = 45000) {
  const предел = Date.now() + мс;
  while (Date.now() < предел) {
    const f = page.frames().find((x) => /cdnvideohub.*\/frame/.test(x.url()));
    if (f) return f;
    await page.waitForTimeout(400);
  }
  return null;
}

async function проверить(ctx, запись) {
  const строка = { url: запись.url, expect_id: запись.id || null, kind: запись.kind || null,
                   group: запись.group || null };
  const page = await ctx.newPage();
  let домен = '';
  try { домен = new URL(запись.url).hostname; } catch (e) { домен = ''; }
  const консоль = [];
  const сеть = [];
  page.on('console', (m) => {
    if (m.type() !== 'error') return;
    // Текст сообщения адреса не содержит, поэтому источник берётся из location:
    // иначе чужой маячок неотличим от настоящей ошибки плеера.
    const где = (m.location() && m.location().url) || '';
    const текст = m.text();
    if (РЕКЛАМА_ТЕКСТ.test(текст)) return;
    let хост = '';
    try { хост = где ? new URL(где).hostname : ''; } catch (e) { хост = ''; }
    const свой = хост === домен || НАШ_КОНТУР.test(хост);
    if (!свой) return;
    if (ПОСТОРОННЕЕ.test(где) || ТЕЛЕМЕТРИЯ.test(где) || РЕКЛАМА_ХОСТЫ.test(где)) return;
    if (ПОСТОРОННЕЕ.test(текст) || ТЕЛЕМЕТРИЯ.test(текст) || РЕКЛАМА_ХОСТЫ.test(текст)) return;
    консоль.push(`${текст.slice(0, 140)} @ ${где.slice(0, 90)}`);
  });
  page.on('requestfailed', (r) => {
    let h = '';
    try { h = new URL(r.url()).hostname; } catch (e) { h = ''; }
    if (!(h === домен || НАШ_КОНТУР.test(h) || /okcdn\.ru$/i.test(h))) return;
    if (ПОСТОРОННЕЕ.test(r.url()) || ПРОГРЕВ.test(r.url()) || ТЕЛЕМЕТРИЯ.test(r.url())
        || РЕКЛАМА_ХОСТЫ.test(r.url())) return;
    // Проверка закрывает вкладку посреди потока, и висящие запросы сегментов
    // обрываются нами же. Считать это отказом провайдера нельзя.
    const почему = (r.failure() || {}).errorText || '';
    if (/ERR_ABORTED/.test(почему)) return;
    сеть.push(`FAILED ${r.url().slice(0, 120)} ${почему}`);
  });
  page.on('response', (r) => {
    if (r.status() >= 400) {
      // Та же граница контура, что и для консоли: 4xx на рекламной бирже —
      // не отказ плеера. Считаются только наш домен, хосты провайдера и
      // видео-CDN, который отдаёт сами сегменты.
      let hh = '';
      try { hh = new URL(r.url()).hostname; } catch (e) { hh = ''; }
      const свойОтвет = hh === домен || НАШ_КОНТУР.test(hh) || /okcdn\.ru$/i.test(hh);
      if (свойОтвет && !ПОСТОРОННЕЕ.test(r.url()) && !ТЕЛЕМЕТРИЯ.test(r.url())
          && !РЕКЛАМА_ХОСТЫ.test(r.url())) {
        сеть.push(`HTTP ${r.status()} ${r.url().slice(0, 120)}`);
      }
    }
  });

  try {
    await page.goto(запись.url, { waitUntil: 'domcontentloaded', timeout: 60000 });

    const разметка = await page.evaluate(() => {
      const рамка = document.querySelector('[data-player]');
      const эл = document.querySelector('video-player');
      return {
        state: рамка ? рамка.getAttribute('data-state') : null,
        title_id: эл ? эл.getAttribute('data-title-id') : null,
        aggregator: эл ? эл.getAttribute('data-aggregator') : null,
        publisher: эл ? !!эл.getAttribute('data-publisher-id') : false,
      };
    });
    Object.assign(строка, разметка);

    // На состояние `data-state` опираться нельзя: сервер ставит `playable`, а
    // дальше скрипт провайдера переписывает его на loading/ok/error по ходу
    // собственной жизни. Признак подключения — сам элемент провайдера.
    if (!разметка.title_id) {
      const текст = await page.evaluate(() => {
        const s = document.querySelector('[data-player-state]');
        return s ? (s.textContent || '').slice(0, 120) : '';
      });
      строка.state_text = текст;
      строка.result = /не подключ|без доступа|идентификатор издателя/i.test(текст)
        ? 'SITE_PROVIDER_CONFIGURATION_MISSING'
        : (/источник/i.test(текст) ? 'RECORD_SOURCE_MISSING' : 'PLAYER_ELEMENT_MISSING');
      строка.console_errors = консоль; строка.network_errors = сеть;
      await page.close(); return строка;
    }
    // Сущность: на странице обязан стоять идентификатор именно этой записи.
    if (запись.id && разметка.aggregator === 'cvh'
        && String(разметка.title_id).toLowerCase() !== String(запись.id).toLowerCase()) {
      строка.result = 'WRONG_ENTITY';
      строка.console_errors = консоль; строка.network_errors = сеть;
      await page.close(); return строка;
    }

    const f = await ждатьФрейм(page);
    if (!f) {
      строка.result = 'PLAYER_FRAME_MISSING';
      строка.console_errors = консоль; строка.network_errors = сеть;
      await page.close(); return строка;
    }
    // На телефоне плеер провайдера не создаёт медиа-элемент до касания: там
    // действует политика воспроизведения по жесту, и до тапа в рамке только
    // постер. Поэтому сперва короткое ожидание, а если элемента нет — касание
    // по центру рамки и ожидание уже полное.
    let естьМедиа = await f.evaluate(`${МЕДИА}.length>0`).catch(() => false);
    if (!естьМедиа) {
      try {
        const рамка = await page.$('video-player');
        if (рамка) {
          await рамка.scrollIntoViewIfNeeded();
          const box = await рамка.boundingBox();
          if (box) {
            const x = box.x + box.width / 2;
            const y = box.y + box.height / 2;
            // На телефоне помогает именно тап: плеер ждёт касания, а
            // синтетический mouse.click событий touch не порождает, и медиа
            // не создаётся вовсе. На десктопе клик остаётся кликом.
            if (вид.hasTouch) await page.touchscreen.tap(x, y);
            else await page.mouse.click(x, y);
          }
        }
      } catch (e) { /* касание не удалось — ждём штатно */ }
    }
    // Провайдер может честно ответить, что дорожки для этой записи или серии
    // нет. Страница показывает это отдельным состоянием, и считать такой ответ
    // поломкой плеера нельзя: витрина подключена, элемент поднят, отказ пришёл
    // от источника. Это состояние записи, а не витрины.
    try {
      await f.waitForFunction(`${МЕДИА}.length>0`, { timeout: 45000 });
    } catch (e) {
      const отказ = await page.evaluate(() => {
        const рамка = document.querySelector('[data-player]');
        const сост = document.querySelector('[data-player-state]');
        return {
          state: рамка ? рамка.getAttribute('data-state') : null,
          visible: сост ? !сост.hidden : false,
          text: сост ? (сост.textContent || '').slice(0, 120) : '',
        };
      }).catch(() => null);
      if (отказ && отказ.state === 'provider' && отказ.visible) {
        строка.result = 'PROVIDER_NO_TRACK';
        строка.state_text = отказ.text;
        строка.console_errors = консоль;
        строка.network_errors = сеть;
        await page.close();
        return строка;
      }
      throw e;
    }

    const t0 = Date.now();
    await f.evaluate(`(()=>{const v=${МЕДИА}[0]; v.muted=true; const p=v.play(); if(p&&p.catch)p.catch(()=>{});})()`);

    let первыйКадр = null;
    let последнее = null;
    const предел = Date.now() + 50000;
    while (Date.now() < предел) {
      await page.waitForTimeout(100);
      последнее = await f.evaluate(`(()=>{const v=${МЕДИА}[0]; return v?{rs:v.readyState, ct:+v.currentTime.toFixed(2), paused:v.paused, dur:(v.duration||0)}:null;})()`);
      if (!последнее) break;
      if (первыйКадр === null && последнее.ct > 0.3) первыйКадр = Date.now() - t0;
      if (последнее.ct >= 10.0 && последнее.rs >= 2) break;
    }
    строка.readyState = последнее ? последнее.rs : null;
    строка.currentTime = последнее ? последнее.ct : null;
    строка.duration = последнее ? последнее.dur : null;
    строка.ttff_ms = первыйКадр;
    строка.console_errors = консоль;
    строка.network_errors = сеть;

    if (!последнее) строка.result = 'MEDIA_DISAPPEARED';
    else if (последнее.rs < 2) строка.result = 'INFINITE_LOADING';
    else if (последнее.ct < 10.0) строка.result = `PLAYBACK_STALLED_AT_${последнее.ct}`;
    else if (консоль.length) строка.result = 'CONSOLE_ERRORS';
    else if (сеть.length) строка.result = 'NETWORK_ERRORS';
    else строка.result = 'REAL_PLAYBACK_OK';
  } catch (e) {
    строка.result = 'ERROR';
    строка.error = String(e).slice(0, 200);
    строка.console_errors = консоль;
    строка.network_errors = сеть;
  }
  await page.close();
  return строка;
}

(async () => {
  const записи = JSON.parse(fs.readFileSync(arg('--urls'), 'utf8'));
  const видИмя = arg('--viewport', 'desktop');
  const вид = ВИДЫ[видИмя];
  const параллельно = parseInt(arg('--concurrency', '4'), 10);

  const browser = await chromium.launch({
    args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required', '--mute-audio'],
  });
  const итог = [];
  let индекс = 0;

  async function поток() {
    const ctx = await browser.newContext(вид);
    while (true) {
      const i = индекс++;
      if (i >= записи.length) break;
      const r = await проверить(ctx, записи[i]);
      r.viewport = видИмя;
      итог.push(r);
      if (итог.length % 10 === 0) console.log(`  ${видИмя}: ${итог.length}/${записи.length}`);
      if (r.result !== 'REAL_PLAYBACK_OK') {
        console.log(`  ! ${r.result}  ${r.url}  ${(r.console_errors || []).slice(0, 1)} ${(r.network_errors || []).slice(0, 1)}`);
      }
    }
    await ctx.close();
  }

  await Promise.all(Array.from({ length: параллельно }, поток));
  await browser.close();

  fs.writeFileSync(arg('--out'), JSON.stringify(итог, null, 1));
  const ок = итог.filter((r) => r.result === 'REAL_PLAYBACK_OK');
  const ttff = ок.map((r) => r.ttff_ms).filter((x) => typeof x === 'number').sort((a, b) => a - b);
  const кв = (p) => (ttff.length ? ttff[Math.min(ttff.length - 1, Math.floor(ttff.length * p))] : null);
  console.log(`\n${видИмя}: REAL_PLAYBACK_OK=${ок.length}/${итог.length}`);
  console.log(`  ttff p50=${кв(0.5)}ms p75=${кв(0.75)}ms p95=${кв(0.95)}ms`);
  const срыв = итог.filter((r) => r.result !== 'REAL_PLAYBACK_OK');
  if (срыв.length) console.log('  отказы:', JSON.stringify(срыв.map((r) => [r.result, r.url]).slice(0, 12)));
  process.exit(срыв.length ? 1 : 0);
})();

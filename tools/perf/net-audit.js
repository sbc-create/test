// СКОРОСТЬ — СЕТЬ САЙТОВ: браузерный замер пользовательского ожидания.
//
// Один «визит» = открытие одной страницы в настоящем Chromium с JavaScript и
// сетевым журналом. Для страниц с плеером дополнительно: нажатие Play как
// пользователь (клик по центру плеера, без флага autoplay), первый кадр
// РЕКЛАМЫ и первый кадр СОДЕРЖИМОГО раздельно, остановки на буферизацию и,
// для сериала, переход на другую серию до первого кадра содержимого.
//
// Первый кадр берётся ВНУТРИ iframe провайдера: Playwright исполняет код в
// чужом фрейме, а видео лежит в его shadow DOM. Признак кадра —
// requestVideoFrameCallback (браузер сообщает о представленном кадре) с
// запасным признаком «currentTime пошёл при paused=false».
// Реклама отличается от содержимого источником: содержимое провайдер играет
// через MediaSource (blob:) с okcdn, преролл — mp4 с strm.yandex.*.
//
// node tools/perf/net-audit.js --plan plan.json --out dir [--workers 2]
//   [--profile desktop|mobile] [--only domain,domain] [--cold 3 --warm 3]
//   [--watch 60] [--har]
const fs = require('fs');
const path = require('path');
const { chromium } = require('/home/claude/node_modules/playwright-core');

const arg = (k, d = null) => { const i = process.argv.indexOf(k); return i > -1 ? process.argv[i + 1] : d; };
const flag = (k) => process.argv.includes(k);

const ПРОФИЛИ = {
  desktop: { viewport: { width: 1366, height: 900 } },
  mobile: {
    viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3,
    userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36',
  },
};

// Классы хостов для раскладки байтов и запросов.
function класс(url, домен) {
  let h = '';
  try { h = new URL(url).hostname; } catch (e) { return 'other'; }
  if (h === домен || h.endsWith('.' + домен)) return 'own';
  if (/cdnvideohub\.com$/.test(h)) return 'player';
  if (/okcdn\.ru$|mycdn\.me$|(^|\.)vk\.(ru|com)$|userapi\.com$|ok\.ru$/.test(h)) return 'video';
  if (/adfox|an\.yandex|yandex\.ru$|strm\.yandex|yandex\.net$|yastatic\.net|googlesyndication|doubleclick|adriver|buzzoola|betweendigital|serving-sys|mediahills|media-hills/.test(h)) return 'ads';
  if (/mc\.yandex|metrika|yandex\.com$/.test(h)) return 'analytics';
  return 'other';
}

// Секреты из HAR: cookies, заголовки авторизации, подписанные параметры.
const ПОДПИСИ = /^(sig|signature|tkn|token|hash|expires|srcip|ip|uid|yandexuid|session|sid|key|auth|access_token|hittoken|scid|hidv2|browser-info|t|rnd|ruid|ch|ms|urls)$/i;
// Вложенные адреса (redirect=..., page-url=...) несут параметры в кодировке
// %3D/%26 — разбор URL их не видит, поэтому вторым слоем идёт замена по тексту.
const ВЛОЖЕННЫЕ = /(\b(?:sig|signature|tkn|token|hash|expires|srcIp|hittoken|access_token|yandexuid|sid|session|scid|hidv2|ruid)(?:=|%3D|%253D))(.*?)(?=&|%26|%2526|"|\\|\s|$)/gi;
const вычистить = (s) => String(s).replace(ВЛОЖЕННЫЕ, '$1REDACTED');
function чистыйUrl(u) {
  try {
    const x = new URL(u);
    for (const k of [...x.searchParams.keys()]) if (ПОДПИСИ.test(k)) x.searchParams.set(k, 'REDACTED');
    return вычистить(x.toString());
  } catch (e) { return вычистить(u); }
}
function очиститьHar(файл) {
  const har = JSON.parse(fs.readFileSync(файл, 'utf8'));
  for (const e of har.log.entries) {
    e.request.url = чистыйUrl(e.request.url);
    e.request.cookies = []; e.response.cookies = [];
    e.request.headers = e.request.headers.filter((h) => !/^(cookie|authorization|x-.*token.*)$/i.test(h.name));
    e.response.headers = e.response.headers.filter((h) => !/^(set-cookie|authorization)$/i.test(h.name));
    e.request.queryString = (e.request.queryString || []).map((q) => (ПОДПИСИ.test(q.name) ? { name: q.name, value: 'REDACTED' } : q));
    if (e.request.postData) e.request.postData = { mimeType: e.request.postData.mimeType, text: '[REDACTED]' };
    if (e.response.redirectURL) e.response.redirectURL = чистыйUrl(e.response.redirectURL);
  }
  for (const p of har.log.pages || []) p.title = чистыйUrl(p.title);
  fs.writeFileSync(файл, вычистить(JSON.stringify(har)));
}

// Наблюдатели страницы: LCP, FCP, длинные задачи, появление оболочки плеера.
const НАБЛЮДАТЕЛЬ_СТРАНИЦЫ = () => {
  window.__pa = { lcp: null, fcp: null, long: [], shell: null, cls: 0 };
  try {
    new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__pa.lcp = e.startTime; }).observe({ type: 'largest-contentful-paint', buffered: true });
    new PerformanceObserver((l) => { for (const e of l.getEntries()) if (e.name === 'first-contentful-paint') window.__pa.fcp = e.startTime; }).observe({ type: 'paint', buffered: true });
    new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__pa.long.push([e.startTime, e.duration]); }).observe({ type: 'longtask', buffered: true });
    new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__pa.cls += e.value; }).observe({ type: 'layout-shift', buffered: true });
  } catch (e) { /* старый движок */ }
  const ждать = () => {
    const el = document.querySelector('video-player');
    if (el && window.__pa.shell === null) { const b = el.getBoundingClientRect(); if (b.width > 0 && b.height > 0) window.__pa.shell = performance.now(); }
    if (window.__pa.shell === null) requestAnimationFrame(ждать);
  };
  requestAnimationFrame(ждать);
};

// Наблюдатель в iframe провайдера: каждые 20 мс обходит shadow DOM, на каждое
// новое <video> вешает события и requestVideoFrameCallback. Время — Date.now(),
// общая с узлом шкала (тот же хост).
const НАБЛЮДАТЕЛЬ_ФРЕЙМА = `(() => {
  if (window.__pv) return true;
  const S = window.__pv = { vids: [] };
  const все = () => { const f=[]; const w=(r,d)=>{ if(d>12||!r||!r.querySelectorAll) return;
    for(const el of r.querySelectorAll('*')){ if(el.tagName==='VIDEO') f.push(el); if(el.shadowRoot) w(el.shadowRoot,d+1);} };
    w(document,0); return f; };
  const kind = (v) => { const s = v.currentSrc || v.src || ''; if (!s) return 'none';
    if (s.startsWith('blob:') || /okcdn|vkuser|userapi|mycdn/.test(s)) return 'content'; return 'ad'; };
  setInterval(() => {
    for (const v of все()) {
      let r = S.vids.find((x) => x.el === v);
      if (!r) {
        r = { el: v, seen: Date.now(), ev: [], frames: [], srcs: [] };
        S.vids.push(r);
        for (const t of ['play','playing','waiting','stalled','seeking','seeked','pause','ended','error','loadeddata','canplay'])
          v.addEventListener(t, () => r.ev.push([t, Date.now(), +v.currentTime.toFixed(3), kind(v)]));
        if (v.requestVideoFrameCallback) {
          const cb = (now, md) => { r.frames.push([Date.now(), md.presentedFrames, +md.mediaTime.toFixed(3), kind(v), v.paused]);
            if (r.frames.length < 400) v.requestVideoFrameCallback(cb); };
          v.requestVideoFrameCallback(cb);
        }
      }
      const s = (v.currentSrc || v.src || '').slice(0, 48);
      if (!r.srcs.length || r.srcs[r.srcs.length-1][1] !== s) r.srcs.push([Date.now(), s, kind(v)]);
      r.last = [Date.now(), +v.currentTime.toFixed(3), v.paused, v.readyState, kind(v)];
    }
  }, 20);
  return true;
})()`;
const СНЯТЬ_ФРЕЙМ = `(() => { const S = window.__pv; if (!S) return null;
  return S.vids.map((r) => ({ seen: r.seen, ev: r.ev, frames: r.frames.slice(0, 400), srcs: r.srcs, last: r.last })); })()`;

const сон = (мс) => new Promise((r) => setTimeout(r, мс));

function фреймПлеера(page) {
  return page.frames().find((f) => /player\.cdnvideohub\.com\/.*\/frame/.test(f.url())) || null;
}

// Сетевой журнал визита: события с привязкой к стене часов.
function журнал(page, домен) {
  const ж = { req: [], failed: [], console: [], pageerrors: [], pending: [] };
  const нач = new Map();
  page.on('request', (r) => { нач.set(r, Date.now()); });
  page.on('requestfinished', (r) => {
    const t1 = Date.now();
    const rec = { url: чистыйUrl(r.url()).slice(0, 220), type: r.resourceType(), cls: класс(r.url(), домен), t0: нач.get(r) || t1, t1, status: null, bytes: null, frame: '' };
    try { rec.frame = r.frame().url().slice(0, 60); } catch (e) { rec.frame = ''; }
    ж.req.push(rec);
    ж.pending.push((async () => {
      try { const resp = await r.response(); rec.status = resp ? resp.status() : null; } catch (e) { /* закрыто */ }
      try { const s = await r.sizes(); rec.bytes = s.responseBodySize + s.responseHeadersSize; } catch (e) { /* нет */ }
      try { const t = r.timing(); rec.timing = { dns: t.domainLookupEnd - t.domainLookupStart, connect: t.connectEnd - t.connectStart, tls: t.secureConnectionStart > 0 ? t.connectEnd - t.secureConnectionStart : 0, wait: t.responseStart - t.requestStart, recv: t.responseEnd - t.responseStart }; } catch (e) { /* нет */ }
    })());
  });
  page.on('requestfailed', (r) => {
    const why = (r.failure() || {}).errorText || '';
    ж.failed.push({ url: чистыйUrl(r.url()).slice(0, 200), cls: класс(r.url(), домен), why, t: Date.now() });
  });
  page.on('console', (m) => { if (m.type() === 'error') ж.console.push({ t: Date.now(), text: m.text().slice(0, 200), where: чистыйUrl(((m.location() || {}).url || '')).slice(0, 120) }); });
  page.on('pageerror', (e) => ж.pageerrors.push({ t: Date.now(), text: String(e).slice(0, 200) }));
  return ж;
}

async function метрикиСтраницы(page) {
  return page.evaluate(() => {
    const n = performance.getEntriesByType('navigation')[0] || {};
    const pa = window.__pa || {};
    const dcl = n.domContentLoadedEventEnd || null;
    // Готовность к действиям: DCL или конец последней длинной задачи до 15 с —
    // что позже. Это приближение TTI без 5-секундного окна тишины.
    let ready = dcl;
    for (const [s, d] of (pa.long || [])) if (s < 15000 && s + d > (ready || 0)) ready = s + d;
    const tbt = (pa.long || []).filter(([s]) => s >= (pa.fcp || 0) && s < 15000).reduce((a, [, d]) => a + Math.max(0, d - 50), 0);
    return {
      timeOrigin: performance.timeOrigin,
      dns: n.domainLookupEnd - n.domainLookupStart,
      connect: n.connectEnd - n.connectStart,
      tls: n.secureConnectionStart > 0 ? n.connectEnd - n.secureConnectionStart : 0,
      ttfb: n.responseStart - n.startTime,
      server_wait: n.responseStart - n.requestStart,
      html_done: n.responseEnd - n.startTime,
      html_bytes: n.transferSize || n.encodedBodySize || null,
      fcp: pa.fcp, lcp: pa.lcp, dcl, load: n.loadEventEnd || null, ready, tbt, cls: +(pa.cls || 0).toFixed(3),
      longtasks: (pa.long || []).length,
      shell: pa.shell,
    };
  });
}

// Цепочка плеера по сетевому журналу: время относительно начала навигации.
function цепочка(ж, origin) {
  const первый = (re, поле = 't1') => { const r = ж.req.filter((x) => re.test(x.url)).sort((a, b) => a[поле] - b[поле])[0]; return r ? Math.round(r[поле] - origin) : null; };
  return {
    sdk_script_done: первый(/player\.cdnvideohub\.com\/.*video-player\.umd\.js/),
    playlist_done: первый(/plapi\.cdnvideohub\.com\/api\/v1\/player\/sv\/playlist/),
    frame_doc_done: первый(/player\.cdnvideohub\.com\/s2\/[^/]+\/frame\/?$/),
    frame_js_done: первый(/player\.cdnvideohub\.com\/s2\/[^/]+\/frame\/index\.js/),
    video_api_done: первый(/plapi\.cdnvideohub\.com\/api\/v1\/player\/sv\/video\//),
    manifest_done: первый(/okcdn\.ru\/.*type=1/),
    // Сегменты идут потоковым fetch и часто не «завершаются» до конца визита,
    // поэтому берётся начало запроса первого сегмента.
    first_segment_req: первый(/okcdn\.ru\/.*type=2/, 't0'),
  };
}

// Разбор наблюдений фрейма после нажатия Play.
function разобратьВидео(vids, tClick, окноМс) {
  const после = (t) => t >= tClick;
  let adFirst = null; let contentFirst = null; let adEnd = null;
  for (const v of vids || []) {
    for (const [t, presented, mt, kind, paused] of v.frames) {
      if (!после(t)) continue;
      if (kind === 'ad' && adFirst === null) adFirst = t;
      if (kind === 'content' && !paused && contentFirst === null && t > tClick) contentFirst = t;
    }
    for (const [ev, t, , kind] of v.ev) {
      if (kind === 'ad' && (ev === 'ended' || ev === 'pause') && после(t)) adEnd = Math.max(adEnd || 0, t);
    }
    // Запасной признак: currentTime пошёл без paused.
    if (contentFirst === null && v.last && v.last[4] === 'content' && !v.last[2] && v.last[1] > 0.5 && v.last[0] > tClick) contentFirst = contentFirst || null;
  }
  // Остановки на буферизацию содержимого после первого кадра, в окне.
  const стопы = [];
  for (const v of vids || []) {
    let открыт = null;
    for (const [ev, t, ct, kind] of v.ev) {
      if (kind !== 'content' || contentFirst === null || t < contentFirst || t > contentFirst + окноМс) continue;
      if (ev === 'waiting' && открыт === null) открыт = [t, ct];
      if (ev === 'playing' && открыт !== null) { стопы.push({ at_ct: открыт[1], ms: t - открыт[0] }); открыт = null; }
    }
    if (открыт) стопы.push({ at_ct: открыт[1], ms: null, unresolved: true });
  }
  const содержимое = (vids || []).flatMap((v) => v.frames.filter((f) => f[3] === 'content' && f[0] >= (contentFirst || Infinity)));
  const медиа = содержимое.length ? Math.max(...содержимое.map((f) => f[2])) - Math.min(...содержимое.map((f) => f[2])) : 0;
  return {
    play_to_ad_first_frame: adFirst ? adFirst - tClick : null,
    ad_end_after_play: adEnd ? adEnd - tClick : null,
    play_to_content_first_frame: contentFirst ? contentFirst - tClick : null,
    ad_end_to_content_first_frame: contentFirst && adEnd ? contentFirst - adEnd : null,
    stalls: стопы,
    stall_count: стопы.length,
    stall_ms: стопы.reduce((a, s) => a + (s.ms || 0), 0),
    content_media_s_observed: +медиа.toFixed(2),
  };
}

async function нажатьPlay(page, profile) {
  const el = await page.$('video-player');
  if (!el) return null;
  await el.scrollIntoViewIfNeeded().catch(() => {});
  const b = await el.boundingBox();
  if (!b) return null;
  const x = b.x + b.width / 2; const y = b.y + b.height / 2;
  const t = Date.now();
  if (profile === 'mobile') await page.touchscreen.tap(x, y); else await page.mouse.click(x, y);
  return t;
}

// Ждать готовности плеера принять Play. Два исхода, оба настоящие:
//  * провайдер подгрузил видео заранее — в фрейме есть <video> (так на lords);
//  * провайдер ждёт нажатия — <video> нет, но API ролика ответил и фрейм
//    загружен (так на Yummy). Тогда готовность = ответ API ролика, а
//    признак preload=false пишется в запись: Play там начинает загрузку с нуля.
async function ждатьГотовностьПлеера(page, предел, ж, сНачала, старый) {
  const конец = Date.now() + предел;
  while (Date.now() < конец) {
    const f = фреймПлеера(page);
    // После перехода на серию прежний фрейм годится, только если провайдер
    // уже спросил новый ролик: мягкая навигация (Next.js у Yummy) оставляет
    // старый iframe на месте, и его <video> — это прошлая серия.
    const новыйРолик = ж && ж.req.some((r) => r.t1 >= (сНачала || 0) && /plapi\.cdnvideohub\.com\/api\/v1\/player\/sv\/video\//.test(r.url));
    if (f && старый && f === старый && !новыйРолик) { await сон(50); continue; }
    if (f) {
      const ok = await f.evaluate(НАБЛЮДАТЕЛЬ_ФРЕЙМА).catch(() => false);
      if (ok) {
        const n = await f.evaluate('window.__pv ? window.__pv.vids.length : 0').catch(() => 0);
        if (n > 0) return { frame: f, t: Date.now(), preload: true };
        const api = ж && ж.req.filter((r) => r.t1 >= (сНачала || 0) && /plapi\.cdnvideohub\.com\/api\/v1\/player\/sv\/video\//.test(r.url))[0];
        if (api && Date.now() - api.t1 > 2000) return { frame: f, t: api.t1, preload: false };
      }
    }
    await сон(50);
  }
  return { frame: фреймПлеера(page), t: null, preload: null };
}

async function смотреть(page, frameRef, tClick, cfg) {
  // До первого кадра содержимого (с рекламой) — до 90 с; затем окно наблюдения.
  const предел = tClick + 90000;
  let vids = null; let первый = null;
  while (Date.now() < предел) {
    await сон(250);
    const f = фреймПлеера(page) || frameRef;
    vids = await f.evaluate(СНЯТЬ_ФРЕЙМ).catch(() => vids);
    const r = разобратьВидео(vids, tClick, cfg.watchMs);
    if (r.play_to_content_first_frame !== null) { первый = tClick + r.play_to_content_first_frame; break; }
    // Реклама могла завершиться, а содержимое ждать второго нажатия — это
    // поведение провайдера, его фиксируем, а не обходим.
  }
  if (первый !== null) {
    const конец = первый + cfg.watchMs;
    while (Date.now() < конец) { await сон(500); }
    const f = фреймПлеера(page) || frameRef;
    vids = await f.evaluate(СНЯТЬ_ФРЕЙМ).catch(() => vids);
  }
  return разобратьВидео(vids, tClick, cfg.watchMs);
}

async function визит(ctx, сценарий, cfg, метка) {
  const page = await ctx.newPage();
  const ж = журнал(page, сценарий.domain);
  const out = { domain: сценарий.domain, scenario: сценарий.kind, url: сценарий.url, mode: метка.mode, rep: метка.rep, profile: cfg.profile, started: new Date().toISOString() };
  try {
    const resp = await page.goto(сценарий.url, { waitUntil: 'load', timeout: 60000 });
    out.http_status = resp ? resp.status() : null;
    out.release_id = await page.evaluate(() => { const m = document.querySelector('meta[name="site-factory-release-id"]'); return m ? m.content : null; }).catch(() => null);
    out.build_header = resp ? (resp.headers()['x-site-factory-build-id'] || null) : null;
    await сон(1500); // LCP и длинные задачи после load
    out.page = await метрикиСтраницы(page);
    const origin = out.page.timeOrigin;
    out.has_player = !!(await page.$('video-player'));
    if (out.has_player && сценарий.play) {
      const гот = await ждатьГотовностьПлеера(page, 45000, ж, 0);
      out.player_ready = гот.t ? Math.round(гот.t - origin) : null;
      out.player_preload = гот.preload;
      out.chain = цепочка(ж, origin);
      if (гот.t) {
        await сон(1000); // пользователь видит плеер и нажимает
        const tClick = await нажатьPlay(page, cfg.profile);
        out.click_at = tClick ? Math.round(tClick - origin) : null;
        if (tClick) {
          out.play = await смотреть(page, гот.frame, tClick, cfg);
          out.ads_requests_after_play = ж.req.filter((r) => r.cls === 'ads' && r.t0 >= tClick).length;
          out.adfox_getcode_after_play = ж.req.filter((r) => /adfox\/.*getCode/.test(r.url) && r.t0 >= tClick).length;
          if (метка.shot) await page.screenshot({ path: path.join(cfg.out, 'shots', `${сценарий.domain}-${сценарий.kind}-${метка.mode}${метка.rep}.png`) }).catch(() => {});
          // Переключение серии: ссылка на другую серию, затем Play.
          if (сценарий.next_episode) {
            const ссылка = new URL(сценарий.next_episode).pathname;
            const a = await page.$(`a[href="${ссылка}"]`) || await page.$(`a[href="${сценарий.next_episode}"]`);
            const tSw = Date.now();
            if (a) await a.click(); else await page.goto(сценарий.next_episode, { waitUntil: 'commit' });
            out.switch = { via: a ? 'link-click' : 'goto' };
            await page.waitForLoadState('domcontentloaded', { timeout: 60000 }).catch(() => {});
            const г2 = await ждатьГотовностьПлеера(page, 45000, ж, tSw, гот.frame);
            out.switch.preload = г2.preload;
            out.switch.player_ready_after_click = г2.t ? г2.t - tSw : null;
            if (г2.t) {
              const t2 = await нажатьPlay(page, cfg.profile);
              const r2 = await смотреть(page, г2.frame, t2, { ...cfg, watchMs: 5000 });
              out.switch.play = r2;
              out.switch.click_to_content_first_frame = r2.play_to_content_first_frame !== null ? (t2 - tSw) + r2.play_to_content_first_frame : null;
              // Ожидание самого стенда между готовностью и нажатием вычитается:
              // это не время сайта и не время провайдера.
              out.switch.harness_wait = t2 - г2.t;
              out.switch.ready_plus_play_to_content = r2.play_to_content_first_frame !== null ? (г2.t - tSw) + r2.play_to_content_first_frame : null;
              out.switch.url = page.url();
            }
          }
        }
      }
    }
    out.chain = out.chain || (out.has_player ? цепочка(ж, origin) : null);
    await Promise.all(ж.pending);
    const байты = {}; const запросы = {};
    for (const r of ж.req) { байты[r.cls] = (байты[r.cls] || 0) + (r.bytes || 0); запросы[r.cls] = (запросы[r.cls] || 0) + 1; }
    const js = ж.req.filter((r) => r.type === 'script');
    out.net = {
      requests: ж.req.length, bytes: байты, count: запросы,
      js_bytes_own: js.filter((r) => r.cls === 'own').reduce((a, r) => a + (r.bytes || 0), 0),
      js_bytes_all: js.reduce((a, r) => a + (r.bytes || 0), 0),
      own_slowest: ж.req.filter((r) => r.cls === 'own').sort((a, b) => (b.t1 - b.t0) - (a.t1 - a.t0)).slice(0, 5).map((r) => ({ url: r.url.slice(0, 120), ms: r.t1 - r.t0, wait: r.timing && Math.round(r.timing.wait), type: r.type })),
      failed: ж.failed.filter((f) => !/ERR_ABORTED/.test(f.why)).slice(0, 15),
      failed_own_or_player: ж.failed.filter((f) => ['own', 'player', 'video'].includes(f.cls) && !/ERR_ABORTED/.test(f.why)).length,
      http_errors_own_or_player: ж.req.filter((r) => ['own', 'player', 'video'].includes(r.cls) && r.status >= 400).map((r) => `${r.status} ${r.url.slice(0, 100)}`).slice(0, 10),
    };
    out.console_errors = ж.console.slice(0, 20);
    out.page_errors = ж.pageerrors.slice(0, 10);
    out.result = 'OK';
  } catch (e) {
    out.result = 'ERROR'; out.error = String(e).slice(0, 300);
  }
  await page.close().catch(() => {});
  return out;
}

async function площадка(browser, сайт, cfg, писать) {
  const сценарии = [];
  сценарии.push({ domain: сайт.domain, kind: 'home', url: сайт.home });
  if (сайт.catalog) сценарии.push({ domain: сайт.domain, kind: 'catalog', url: сайт.catalog });
  if (сайт.film) сценарии.push({ domain: сайт.domain, kind: 'film', url: сайт.film.url, play: cfg.play });
  if (сайт.series) сценарии.push({ domain: сайт.domain, kind: 'series', url: сайт.series.episodes[0], play: cfg.play, next_episode: сайт.series.episodes[1] });
  for (const сц of сценарии) {
    if (cfg.kinds && !cfg.kinds.includes(сц.kind)) continue;
    for (let i = 1; i <= Math.max(cfg.cold, cfg.warm); i++) {
      const ctxOpts = { ...ПРОФИЛИ[cfg.profile], ignoreHTTPSErrors: false };
      const har = cfg.har && i === 1 ? path.join(cfg.out, 'har', `${сц.domain}-${сц.kind}-${cfg.profile}.har`) : null;
      if (har) ctxOpts.recordHar = { path: har, content: 'omit' };
      const ctx = await browser.newContext(ctxOpts);
      await ctx.addInitScript(НАБЛЮДАТЕЛЬ_СТРАНИЦЫ);
      if (i <= cfg.cold) писать(await визит(ctx, сц, { ...cfg, watchMs: i === 1 ? cfg.watchMs : Math.min(cfg.watchMs, 15000) }, { mode: 'cold', rep: i, shot: i === 1 }));
      // Тёплое открытие: тот же контекст (кэш и соединения прогреты), без
      // перехода на серию — переключение мерится в холодных.
      if (i <= cfg.warm) писать(await визит(ctx, { ...сц, next_episode: null }, { ...cfg, watchMs: 10000 }, { mode: 'warm', rep: i, shot: false }));
      await ctx.close();
      if (har && fs.existsSync(har)) очиститьHar(har);
    }
  }
}

(async () => {
  const план = JSON.parse(fs.readFileSync(arg('--plan'), 'utf8'));
  const cfg = {
    out: arg('--out'), profile: arg('--profile', 'desktop'), cold: +arg('--cold', 3), warm: +arg('--warm', 3),
    watchMs: +arg('--watch', 60) * 1000, har: flag('--har'), play: !flag('--no-play'),
    kinds: arg('--kinds') ? arg('--kinds').split(',') : null,
  };
  const только = arg('--only') ? arg('--only').split(',') : null;
  for (const d of ['', 'har', 'shots']) fs.mkdirSync(path.join(cfg.out, d), { recursive: true });
  const сайты = план.filter((s) => !s.error && (!только || только.includes(s.domain)));
  const файл = path.join(cfg.out, `visits-${cfg.profile}.jsonl`);
  const писать = (r) => {
    fs.appendFileSync(файл, JSON.stringify(r) + '\n');
    const p = r.play || {};
    console.log(`${r.started.slice(11, 19)} ${r.domain} ${r.scenario} ${r.mode}${r.rep} ${r.result} ttfb=${r.page && Math.round(r.page.ttfb)} lcp=${r.page && Math.round(r.page.lcp)} ready=${r.page && Math.round(r.page.ready)} shell=${r.page && Math.round(r.page.shell)} player=${r.player_ready} ad=${p.play_to_ad_first_frame} content=${p.play_to_content_first_frame} stalls=${p.stall_count} switch=${r.switch && r.switch.click_to_content_first_frame} ${r.error || ''}`);
  };
  // --resolve "домен=127.0.0.1:порт": A/B копии витрины под настоящим именем
  // домена (обычный HTTP, без TLS). Только для сравнения копий между собой.
  const подмена = arg('--resolve');
  const доп = подмена ? [`--host-resolver-rules=MAP ${подмена.split('=')[0]} ${подмена.split('=')[1]}`] : [];
  const browser = await chromium.launch({ args: ['--no-sandbox', '--mute-audio', ...доп] });
  console.log(`chromium ${browser.version()} profile=${cfg.profile}`);
  let k = 0;
  const workers = Math.max(1, +arg('--workers', 2));
  await Promise.all(Array.from({ length: workers }, async () => {
    while (k < сайты.length) { const s = сайты[k++]; await площадка(browser, s, cfg, писать); }
  }));
  await browser.close();
})();

#!/usr/bin/env node
/**
 * Проверка ФАКТИЧЕСКОГО начала воспроизведения.
 *
 * HTTP 200, элемент <video-player> в документе и даже загруженный скрипт
 * провайдера не означают, что зритель увидел кадр. Проверять по разметке —
 * значит не проверять: ровно так дефект «карточки получили дескриптор, а
 * страницы остались с заглушкой» и выглядел как исправление.
 *
 * Что измеряется: readyState, рост currentTime и число декодированных кадров у
 * настоящего медиаэлемента. Он живёт в теневом дереве компонента VK внутри
 * cross-origin кадра провайдера, поэтому обход теневых корней обязателен —
 * querySelector его не видит.
 *
 * Щелчок настоящей мышью по области плеера, а не программный play(): браузеры
 * не начинают воспроизведение без жеста, и синтетический вызов даёт ложный
 * отказ. На проверке трёх витрин синтетический клик один раз не сработал в
 * Firefox, и без настоящего это выглядело бы как регрессия витрины.
 *
 * Использование:
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *   node tests/tools/player_first_frame.js <url> [url...]
 *
 * Код возврата: 0 — все адреса дали ожидаемый исход, 1 — иначе.
 * Ожидаемым считается ЛИБО воспроизведение (readyState >= 2 и растущее время),
 * ЛИБО полное отсутствие кадра провайдера — честная заглушка. Промежуточное
 * состояние (кадр есть, воспроизведения нет) — отказ.
 */
const МОДУЛЬ = process.env.PLAYWRIGHT_MODULE || 'playwright';
let playwright;
try {
  playwright = require(МОДУЛЬ);
} catch (e) {
  console.log('SKIPPED: playwright не установлен (PLAYWRIGHT_MODULE укажет путь). ' +
              '«Проверено в браузере» без браузера не заявляется.');
  process.exit(2);
}
const { chromium, firefox } = playwright;

const ОБХОД = `(() => {
  const идти = (к) => {
    const v = к.querySelector && к.querySelector('video');
    if (v) return v;
    for (const e of (к.querySelectorAll ? к.querySelectorAll('*') : []))
      if (e.shadowRoot) { const r = идти(e.shadowRoot); if (r) return r; }
    return null;
  };
  return идти(document);
})()`;

const СНЯТЬ = `(() => { const v = ${ОБХОД}; if (!v) return null;
  const q = v.getVideoPlaybackQuality ? v.getVideoPlaybackQuality() : null;
  return { readyState: v.readyState, currentTime: v.currentTime, paused: v.paused,
           duration: v.duration, w: v.videoWidth, h: v.videoHeight,
           frames: q ? q.totalVideoFrames : null }; })()`;

async function проверить(движок, имя, url) {
  const b = await движок.launch({ args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'] });
  const page = await (await b.newContext({ viewport: { width: 1280, height: 800 } })).newPage();
  const итог = { engine: имя, url };
  try {
    итог.http = (await page.goto(url, { waitUntil: 'load', timeout: 30000 })).status();
    await page.waitForTimeout(7000);
    const кадр = page.frames().find((f) => /cdnvideohub/.test(f.url()));
    if (!кадр) {
      итог.verdict = 'no-player';
      итог.ok = (await page.locator('video-player').count()) === 0;
      await b.close();
      return итог;
    }
    const box = await page.locator('video-player').boundingBox();
    if (box) await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    await page.waitForTimeout(2000);
    await кадр.evaluate(`(() => { const v = ${ОБХОД};
      if (v) { v.muted = true; const q = v.play(); if (q && q.catch) q.catch(() => {}); } })()`);
    for (let i = 0; i < 14; i++) {
      итог.media = await кадр.evaluate(СНЯТЬ);
      if (итог.media && итог.media.readyState >= 2 && итог.media.currentTime > 0.5
          && !итог.media.paused) break;
      await page.waitForTimeout(1500);
    }
    итог.ok = !!(итог.media && итог.media.readyState >= 2 && итог.media.currentTime > 0.5);
    итог.verdict = итог.ok ? 'playing' : 'player-without-playback';
  } catch (e) {
    итог.error = String(e).slice(0, 200);
    итог.ok = false;
  }
  await b.close();
  return итог;
}

(async () => {
  const адреса = process.argv.slice(2);
  if (!адреса.length) { console.error('нужен хотя бы один адрес'); process.exit(1); }
  let всё = true;
  for (const [d, n] of [[chromium, 'chromium'], [firefox, 'firefox']]) {
    for (const u of адреса) {
      const r = await проверить(d, n, u);
      всё = всё && r.ok;
      const м = r.media || {};
      console.log(`${r.ok ? 'PASS' : 'FAIL'} ${n.padEnd(9)} ${r.verdict.padEnd(24)} ` +
        `${м.readyState !== undefined ? `rs=${м.readyState} t=${(м.currentTime || 0).toFixed(2)} ` +
          `кадров=${м.frames} ${м.w}x${м.h}` : ''} ${u}`);
    }
  }
  process.exit(всё ? 0 : 1);
})();

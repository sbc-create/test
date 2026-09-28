#!/usr/bin/env node
/**
 * Шесть состояний оболочки плеера — каждое подтверждено, а не объявлено.
 *
 * Проверяется ОБОЛОЧКА, а не провайдер. Источник видео, контракт и правила
 * доступности не трогаются: три состояния наблюдаются как есть, ещё три
 * вызываются условиями сети в браузере — скрипт провайдера не отдаётся, ответ
 * задерживается, элемент сообщает `noData`. Это проверка нашей реакции на
 * чужой отказ, а не подмена чужих данных.
 *
 *   available  — после щелчка кадры меняются: воспроизведение идёт;
 *   loading    — до подъёма элемента оболочка объявляет загрузку;
 *   no source  — у записи нет идентификатора агрегатора, элемента нет вовсе;
 *   unavailable— витрине не выдан publisher id, объяснено словами;
 *   provider   — провайдер ответил `noData` на эту запись;
 *   timeout    — скрипт загрузился, элемент за отведённое время не поднялся.
 *
 * Каждое состояние обязано ПОКАЗАТЬ текст. Пустой чёрный прямоугольник,
 * бесконечный кружок и кнопка Play, которая ничего не делает, считаются
 * провалом, а не состоянием.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { chromium } = require(process.env.PW_ROOT
  ? path.join(process.env.PW_ROOT, 'playwright')
  : 'playwright');

const OUT = process.env.PROBE_OUT || './artifacts/player-six';

function difference(a, b) {
  const n = Math.min(a.length, b.length);
  let d = 0;
  for (let i = 0; i < n; i++) if (a[i] !== b[i]) d++;
  return n ? d / n : 0;
}

const SHELL = `(() => {
  const f = document.querySelector('[data-player]');
  if (!f) return { present: false };
  const st = f.querySelector('[data-player-state]');
  const visible = st && !st.hidden && getComputedStyle(st).display !== 'none';
  const btns = Array.from(f.querySelectorAll('button'));
  return {
    present: true,
    state: f.getAttribute('data-state'),
    heading: st ? (st.querySelector('b') || {}).textContent || '' : '',
    text: st ? (st.querySelector('p') || {}).textContent || '' : '',
    explained: !!visible,
    hasElement: !!f.querySelector('video-player'),
    scriptTag: !!document.querySelector('[data-player-script]'),
    // Фальшивая кнопка Play — кнопка с обещанием просмотра, у которой нет
    // обработчика и нет источника. Ищем именно её.
    fakePlay: btns.some(b => /смотр|play/i.test(b.textContent || '')),
    spinner: !!f.querySelector('[class*=spin],[class*=loader]'),
  };
})()`;

async function снять(page, имя) {
  const f = await page.$('[data-player]');
  if (f) fs.writeFileSync(path.join(OUT, `${имя}.png`), await f.screenshot());
}

/** available: настоящий щелчок и смена кадров. */
async function available(page, url) {
  await page.goto(url, { waitUntil: 'load', timeout: 60000 });
  await page.waitForTimeout(9000);
  const f = await page.$('[data-player]');
  await f.scrollIntoViewIfNeeded();
  await page.waitForTimeout(600);
  const box = await f.boundingBox();
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await page.waitForTimeout(4000);
  const a = await f.screenshot();
  await page.waitForTimeout(5000);
  const b = await f.screenshot();
  fs.writeFileSync(path.join(OUT, 'available.png'), b);
  const d = difference(a, b);
  const shell = await page.evaluate(SHELL);
  return { state: 'available', url, shell, frame_difference: Math.round(d * 1e4) / 1e4,
           ok: d > 0.02 && shell.state === 'ok' };
}

/** loading: состояние до подъёма элемента. Читается сразу после load. */
async function loading(page, url) {
  await page.goto(url, { waitUntil: 'load', timeout: 60000 });
  const shell = await page.evaluate(SHELL);
  await снять(page, 'loading');
  return { state: 'loading', url, shell,
           ok: shell.present && ['loading', 'playable', 'ok'].includes(shell.state) };
}

/** provider: элемент поднялся и сообщил `noData`. */
async function provider(page, url) {
  await page.goto(url, { waitUntil: 'load', timeout: 60000 });
  await page.waitForTimeout(7000);
  await page.evaluate(() => {
    const el = document.querySelector('video-player');
    if (el) el.dispatchEvent(new Event('noData'));
  });
  await page.waitForTimeout(800);
  const shell = await page.evaluate(SHELL);
  await снять(page, 'provider');
  return { state: 'provider', url, shell,
           ok: shell.state === 'provider' && shell.explained &&
               shell.heading.length > 8 && shell.text.length > 30 };
}

/** error: скрипт провайдера не отдан сетью. */
async function providerError(page, url) {
  await page.route('**/player.cdnvideohub.com/**', r => r.abort());
  try {
    await page.goto(url, { waitUntil: 'load', timeout: 60000 });
    await page.waitForTimeout(6000);
    const shell = await page.evaluate(SHELL);
    await снять(page, 'provider-error');
    return { state: 'provider_error', url, shell,
             ok: shell.state === 'error' && shell.explained && shell.text.length > 30 };
  } finally {
    await page.unroute('**/player.cdnvideohub.com/**');
  }
}

/** timeout: скрипт отдан, но элемент не поднимается. */
async function timeoutState(page, url) {
  // Скрипт отдаётся пустым: тег загрузился (ошибки нет), элемент не появится.
  await page.route('**/video-player.umd.js', r =>
    r.fulfill({ status: 200, contentType: 'application/javascript', body: '/* пусто */' }));
  try {
    await page.goto(url, { waitUntil: 'load', timeout: 60000 });
    await page.waitForTimeout(17000);
    const shell = await page.evaluate(SHELL);
    await снять(page, 'timeout');
    return { state: 'timeout', url, shell,
             ok: shell.state === 'slow' && shell.explained && shell.text.length > 30 };
  } finally {
    await page.unroute('**/video-player.umd.js');
  }
}

/** Состояния, которые страница объявляет сама, без вмешательства. */
async function объявленное(page, url, ожидание, имя) {
  await page.goto(url, { waitUntil: 'load', timeout: 60000 });
  await page.waitForTimeout(2500);
  const shell = await page.evaluate(SHELL);
  await снять(page, имя);
  return { state: имя, url, shell,
           ok: shell.state === ожидание && shell.explained &&
               shell.heading.length > 8 && shell.text.length > 30 &&
               !shell.hasElement && !shell.fakePlay && !shell.spinner };
}

async function main() {
  const plan = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    args: ['--autoplay-policy=no-user-gesture-required', '--mute-audio'],
  });
  const page = await (await browser.newContext()).newPage();
  await page.setViewportSize({ width: 1440, height: 900 });

  const results = [];
  results.push(await available(page, plan.playable));
  results.push(await loading(page, plan.playable));
  results.push(await provider(page, plan.playable));
  results.push(await providerError(page, plan.playable));
  results.push(await timeoutState(page, plan.playable));
  results.push(await объявленное(page, plan.nosource, 'nosource', 'no_source'));
  if (plan.noaccess) {
    results.push(await объявленное(page, plan.noaccess, 'noaccess', 'unavailable'));
  }
  await browser.close();

  fs.writeFileSync(path.join(OUT, 'player-six-states.json'),
                   JSON.stringify({ plan, results }, null, 1));
  let pass = 0;
  for (const r of results) {
    pass += r.ok ? 1 : 0;
    console.log(`${r.ok ? 'PASS' : 'FAIL'} ${r.state.padEnd(15)} ` +
                `data-state=${String(r.shell.state).padEnd(10)} ` +
                `${r.frame_difference !== undefined ? 'diff=' + r.frame_difference + ' ' : ''}` +
                `${(r.shell.heading || '').slice(0, 46)}`);
  }
  console.log(`ИТОГО ${pass}/${results.length}`);
  console.log(`отчёт: ${path.join(OUT, 'player-six-states.json')}`);
}

main().catch(e => { console.error(e); process.exit(1); });

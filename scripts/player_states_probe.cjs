#!/usr/bin/env node
/**
 * Состояния плеера на кандидате: подтверждение, а не объявление.
 *
 * `playable` подтверждается ФАКТОМ воспроизведения, а не наличием элемента.
 * Плеер провайдера живёт в его собственном кадре с чужого домена, и прочитать
 * оттуда `video.currentTime` нельзя — браузер не даст. Поэтому прогресс
 * измеряется единственным доступным извне способом: два снимка области плеера
 * с интервалом в несколько секунд после пользовательского щелчка. Если
 * картинка изменилась, кадры сменились; если нет — воспроизведения не было.
 * Пиксели сравниваются попиксельно, а не по размеру файла.
 *
 * Остальные состояния подтверждаются словами на экране: страница обязана
 * объяснить, чего не хватает, а не показывать пустой чёрный прямоугольник.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { chromium } = require(process.env.PW_ROOT
  ? path.join(process.env.PW_ROOT, 'playwright')
  : 'playwright');

const OUT = process.env.PROBE_OUT || './artifacts/player-states';

/** Доля различающихся байтов двух снимков одной области. */
function difference(a, b) {
  const n = Math.min(a.length, b.length);
  let diff = 0;
  for (let i = 0; i < n; i++) if (a[i] !== b[i]) diff++;
  return { changed: diff, total: n, ratio: n ? diff / n : 0 };
}

async function playable(page, url, name) {
  await page.goto(url, { waitUntil: 'load', timeout: 60000 });
  await page.waitForTimeout(9000);
  const state = await page.evaluate(() => {
    const f = document.querySelector('[data-player]');
    return f ? f.getAttribute('data-state') : null;
  });
  const frame = await page.$('[data-player]');
  if (!frame) return { name, url, ok: false, why: 'области плеера нет' };
  // Прокрутка обязательна. На странице произведения плеер лежит ниже экрана,
  // и щелчок по координатам его середины уходил за пределы окна: браузер
  // прижимал точку к границе, попадал мимо кнопки, и проба объявляла рабочий
  // плеер неработающим. Промах оснастки выглядел ровно как дефект витрины.
  await frame.scrollIntoViewIfNeeded();
  await page.waitForTimeout(600);
  const box = await frame.boundingBox();
  // Щелчок в середину области плеера — туда, где зритель видит кнопку.
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await page.waitForTimeout(4000);
  const first = await frame.screenshot();
  await page.waitForTimeout(5000);
  const second = await frame.screenshot();
  const d = difference(first, second);
  fs.writeFileSync(path.join(OUT, `${name}-t1.png`), first);
  fs.writeFileSync(path.join(OUT, `${name}-t2.png`), second);
  return {
    name, url, state, ok: d.ratio > 0.02,
    frame_difference: Math.round(d.ratio * 10000) / 10000,
    note: d.ratio > 0.02
      ? 'кадры сменились после щелчка — воспроизведение идёт'
      : 'картинка не изменилась — воспроизведения не наблюдается',
  };
}

async function explained(page, url, name, expectState) {
  await page.goto(url, { waitUntil: 'load', timeout: 60000 });
  await page.waitForTimeout(2500);
  const r = await page.evaluate(() => {
    const f = document.querySelector('[data-player]');
    if (!f) return { state: null };
    const st = f.querySelector('[data-player-state]');
    const visible = st && !st.hidden && getComputedStyle(st).display !== 'none';
    return {
      state: f.getAttribute('data-state'),
      heading: st ? (st.querySelector('b') || {}).textContent || '' : '',
      text: st ? (st.querySelector('p') || {}).textContent || '' : '',
      visible: !!visible,
      hasElement: !!f.querySelector('video-player'),
      hasScript: !!document.querySelector('[data-player-script]'),
      // Пустой прямоугольник и бесконечный кружок — отдельные проверки:
      // именно они и выдавались раньше за «плеер на месте».
      spinner: !!f.querySelector('.spinner, [class*=spin], [class*=load]'),
      fakePlay: /смотреть|play/i.test((f.querySelector('button') || {}).textContent || ''),
    };
  });
  const frame = await page.$('[data-player]');
  if (frame) fs.writeFileSync(path.join(OUT, `${name}.png`), await frame.screenshot());
  return {
    name, url, ...r, expected: expectState,
    ok: r.state === expectState && r.visible && r.heading.length > 8 &&
        r.text.length > 30 && !r.spinner && !r.fakePlay,
  };
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
  for (const c of plan.playable) results.push(await playable(page, c.url, c.name));
  for (const c of plan.explained) results.push(await explained(page, c.url, c.name, c.state));
  await browser.close();

  fs.writeFileSync(path.join(OUT, 'player-states.json'),
                   JSON.stringify({ results }, null, 1));
  let pass = 0;
  for (const r of results) {
    pass += r.ok ? 1 : 0;
    console.log(`${r.ok ? 'PASS' : 'FAIL'} ${r.name} state=${r.state} ` +
                `${r.frame_difference !== undefined ? 'diff=' + r.frame_difference : ''} ` +
                `${r.note || r.heading || ''}`);
  }
  console.log(`ИТОГО ${pass}/${results.length}`);
  console.log(`отчёт: ${path.join(OUT, 'player-states.json')}`);
}

main().catch(e => { console.error(e); process.exit(1); });

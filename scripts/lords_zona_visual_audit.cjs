#!/usr/bin/env node
/**
 * Браузерная приёмка витрин Lords и Zona: то, что видно только в браузере.
 *
 * Проверяется именно ВЫЧИСЛЕННОЕ браузером, а не исходный CSS. Контраст,
 * переполнение по горизонтали, размеры целей касания и наличие картинки — это
 * свойства отрисованной страницы; по тексту стиля они не выводятся, потому что
 * зависят от наследования, каскада и порядка подключения. Именно на этом
 * прежняя приёмка и промахнулась: файл стилей был корректен, а страница —
 * нечитаема.
 *
 * Скрипт ничего не чинит и ничего не выкладывает. Он измеряет и складывает
 * измерения в JSON и PNG.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { chromium } = require(process.env.PW_ROOT
  ? path.join(process.env.PW_ROOT, 'playwright')
  : 'playwright');

const OUT = process.env.AUDIT_OUT || './artifacts/lords-zona-audit';

/** Обязательные окна просмотра из задания. */
const VIEWPORTS = [
  { w: 1440, h: 900 }, { w: 1366, h: 768 }, { w: 1024, h: 768 },
  { w: 768, h: 1024 }, { w: 430, h: 932 }, { w: 390, h: 844 }, { w: 360, h: 800 },
];

/**
 * Контраст считается по вычисленным цветам с подъёмом по предкам за фоном.
 *
 * Прозрачный фон — не белый: у элемента без собственного фона цвет берётся у
 * ближайшего предка, у которого он есть. Подмена прозрачного на белый даёт
 * ложное «всё хорошо» ровно там, где страница на тёмной подложке.
 */
const CONTRAST_PROBE = `(() => {
  const lum = (c) => {
    const s = c.map(v => { v /= 255; return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); });
    return 0.2126*s[0] + 0.7152*s[1] + 0.0722*s[2];
  };
  const parse = (s) => {
    const m = String(s).match(/rgba?\\(([^)]+)\\)/);
    if (!m) return null;
    const p = m[1].split(',').map(x => parseFloat(x));
    return { rgb: [p[0], p[1], p[2]], a: p.length > 3 ? p[3] : 1 };
  };
  const over = (fg, bg) => fg.rgb.map((v, i) => v * fg.a + bg[i] * (1 - fg.a));
  const bgOf = (el) => {
    let n = el, stack = [];
    while (n && n.nodeType === 1) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (c && c.a > 0) { stack.push(c); if (c.a >= 1) break; }
      n = n.parentElement;
    }
    let base = [255, 255, 255];
    for (let i = stack.length - 1; i >= 0; i--) base = over(stack[i], base);
    return base;
  };
  const out = [];
  const els = document.querySelectorAll('body *');
  for (const el of els) {
    // Только элементы с СОБСТВЕННЫМ видимым текстом: считать контраст
    // контейнера значит считать его многократно и по чужому фону.
    let text = '';
    for (const n of el.childNodes) if (n.nodeType === 3) text += n.nodeValue;
    text = text.trim();
    if (!text) continue;
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none' || parseFloat(st.opacity) === 0) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    const fg = parse(st.color); if (!fg) continue;
    const bg = bgOf(el);
    const fgc = over(fg, bg);
    const L1 = lum(fgc), L2 = lum(bg);
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const size = parseFloat(st.fontSize);
    const weight = parseInt(st.fontWeight, 10) || 400;
    const large = size >= 24 || (size >= 18.66 && weight >= 700);
    const need = large ? 3 : 4.5;
    if (ratio < need) {
      out.push({ tag: el.tagName.toLowerCase(), cls: el.className && String(el.className).slice(0, 60),
                 text: text.slice(0, 60), ratio: Math.round(ratio * 100) / 100, need,
                 size, weight, color: st.color, bg: 'rgb(' + bg.map(Math.round).join(',') + ')' });
    }
  }
  return out;
})()`;

const OVERFLOW_PROBE = `(() => {
  const d = document.documentElement;
  const over = d.scrollWidth - d.clientWidth;
  const guilty = [];
  if (over > 1) {
    for (const el of document.querySelectorAll('body *')) {
      const r = el.getBoundingClientRect();
      if (r.right > d.clientWidth + 1 && r.width > 0) {
        guilty.push({ tag: el.tagName.toLowerCase(), cls: String(el.className).slice(0, 50),
                      right: Math.round(r.right), vw: d.clientWidth });
        if (guilty.length > 5) break;
      }
    }
  }
  return { overflow: Math.max(0, over), guilty };
})()`;

/**
 * Битым считается изображение, чья загрузка ЗАВЕРШИЛАСЬ ошибкой и которое при
 * этом осталось на экране.
 *
 * Два ложных срабатывания пришлось исключить по очереди, и оба выглядели
 * убедительно.
 *
 * Первое: проба считала битым всё, что не загружено. Постеры ленивые, ниже
 * экрана они не начинают грузиться вовсе, и счётчик показывал 431. Ни одного
 * дефекта за этим не стояло.
 *
 * Второе: после прокрутки осталось 30, и они выглядели как отказ провайдера.
 * Проверка прямым запросом из того же браузера показала, что все они
 * отдаются за сотни миллисекунд: изображения просто не успели долистаться до
 * видимой области к моменту замера. `complete === false` — это «ещё не
 * начиналось», и приравнивать его к ошибке неверно.
 *
 * Остаётся единственное честное определение: `complete && naturalWidth === 0`.
 * Изображение, которое отказало И которое витрина уже прикрыла заглушкой,
 * посетителю не видно и в счётчик не идёт — заглушка и есть правильный ответ
 * на отказ чужого хранилища.
 */
const IMAGES_PROBE = `(() => {
  const bad = [], pending = [];
  for (const img of document.images) {
    // Три разных состояния, и путать их нельзя:
    //   complete && naturalWidth > 0  — загружено;
    //   complete && naturalWidth == 0 — ЗАГРУЗКА ЗАВЕРШИЛАСЬ ОШИБКОЙ;
    //   !complete                     — ленивое изображение ещё не начинало.
    // Первая версия пробы считала битым всё, что не загружено, и насчитала 30
    // «битых» постеров, каждый из которых по прямому запросу отдаётся за
    // сотни миллисекунд. Ленивая картинка ниже экрана — не дефект страницы.
    const rec = { src: String(img.currentSrc || img.src).slice(0, 120), alt: img.alt };
    if (!img.complete) { pending.push(rec); continue; }
    if (img.naturalWidth > 0) continue;
    const hidden = img.hidden || img.offsetParent === null ||
                   getComputedStyle(img).display === 'none' ||
                   getComputedStyle(img).visibility === 'hidden';
    // Ошибка, которую витрина уже прикрыла заглушкой, посетителю не видна.
    if (!hidden) bad.push(rec);
  }
  return { total: document.images.length, broken: bad, not_started: pending };
})()`;

/** Цели касания: ссылка и кнопка меньше 24 px по меньшей стороне неудобны
 *  пальцем. Порог мягкий (24, а не 44): плотная сетка эталона Lords живёт
 *  крупными постерами, и завышенный порог ловил бы подписи внутри них. */
const TOUCH_PROBE = `(() => {
  const bad = [];
  for (const el of document.querySelectorAll('a,button,input,[role="button"]')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    if (Math.min(r.width, r.height) < 24) {
      bad.push({ tag: el.tagName.toLowerCase(), cls: String(el.className).slice(0, 40),
                 w: Math.round(r.width), h: Math.round(r.height) });
      if (bad.length > 8) break;
    }
  }
  return bad;
})()`;

const FOCUS_PROBE = `(() => {
  const first = document.querySelector('main a, main button');
  if (!first) return { ok: false, why: 'нет фокусируемого элемента в main' };
  first.focus();
  const st = getComputedStyle(first);
  const w = parseFloat(st.outlineWidth) || 0;
  return { ok: w > 0 && st.outlineStyle !== 'none', outline: st.outline, width: w };
})()`;

async function measure(page, url, tag, viewport, dir) {
  const console_errors = [];
  const failed = [];
  const onMsg = (m) => { if (m.type() === 'error') console_errors.push(m.text().slice(0, 200)); };
  const onFail = (r) => failed.push({ url: r.url().slice(0, 140), err: String(r.failure() && r.failure().errorText).slice(0, 80) });
  const onResp = (r) => { if (r.status() >= 400) failed.push({ url: r.url().slice(0, 140), status: r.status() }); };
  page.on('console', onMsg); page.on('requestfailed', onFail); page.on('response', onResp);

  await page.setViewportSize({ width: viewport.w, height: viewport.h });
  const resp = await page.goto(url, { waitUntil: 'load', timeout: 45000 });
  // Постеры ленивые и приезжают из внешнего CDN. Считать битым изображение,
  // которое просто ещё не доехало, — это измерять собственное нетерпение:
  // первая версия пробы насчитала 431 «битую» картинку там, где их не было ни
  // одной. Поэтому сначала прокрутка (ленивые начинают грузиться), потом
  // ожидание завершения, и только затем подсчёт.
  await page.evaluate(async () => {
    window.scrollTo(0, document.body.scrollHeight);
    await new Promise(r => setTimeout(r, 150));
    window.scrollTo(0, 0);
  });
  await page.waitForTimeout(400);
  await page.evaluate(() => Promise.all(
    Array.from(document.images)
      .filter(i => !i.complete)
      .map(i => new Promise(res => {
        const done = () => res();
        i.addEventListener('load', done, { once: true });
        i.addEventListener('error', done, { once: true });
        setTimeout(done, 8000);
      }))
  ));
  await page.waitForTimeout(250);

  // Контраст меряется в ОБЕИХ системных темах. Прежний дефект жил ровно
  // здесь: при светлой теме системы чужой CSS красил поверхности в белый, а
  // наш — текст в почти белый. Одна тема этого не показывает.
  const contrast = [];
  for (const scheme of ['light', 'dark']) {
    await page.emulateMedia({ colorScheme: scheme });
    await page.waitForTimeout(120);
    for (const c of await page.evaluate(CONTRAST_PROBE)) contrast.push({ ...c, scheme });
  }
  await page.emulateMedia({ colorScheme: 'light' });
  const overflow = await page.evaluate(OVERFLOW_PROBE);
  const images = await page.evaluate(IMAGES_PROBE);
  const touch = await page.evaluate(TOUCH_PROBE);
  const focus = await page.evaluate(FOCUS_PROBE);

  const shot = `${tag}-${viewport.w}.png`;
  await page.screenshot({ path: path.join(dir, shot), fullPage: viewport.w >= 1024 });

  page.off('console', onMsg); page.off('requestfailed', onFail); page.off('response', onResp);
  return {
    url, tag, viewport: `${viewport.w}x${viewport.h}`, status: resp && resp.status(),
    screenshot: shot, console_errors, failed_requests: failed,
    contrast_failures: contrast, overflow: overflow.overflow, overflow_guilty: overflow.guilty,
    images_total: images.total, broken_images: images.broken,
    images_not_started: images.not_started.length,
    small_touch_targets: touch, focus_visible: focus,
  };
}

/** Настоящие клики по карточкам: не переход по собранному адресу, а щелчок
 *  мышью по тому, что видит посетитель. Перекрытая накладкой ссылка проходит
 *  проверку адресом и проваливает проверку щелчком — ради этой разницы клик
 *  здесь и делается. */
async function clickCards(page, base, picks) {
  const results = [];
  for (const pick of picks) {
    try {
      await page.goto(base + pick.from, { waitUntil: 'load', timeout: 45000 });
      const sel = `a[href="${pick.href}"]`;
      const el = await page.$(sel);
      if (!el) { results.push({ ...pick, ok: false, why: 'ссылки нет в разметке' }); continue; }
      await el.scrollIntoViewIfNeeded();
      const box = await el.boundingBox();
      if (!box || box.width < 4 || box.height < 4) {
        results.push({ ...pick, ok: false, why: 'ссылка без видимой площади' }); continue;
      }
      // Точка в середине карточки: если её перекрывает накладка, щелчок
      // достанется накладке, и это ровно тот дефект, который надо поймать.
      const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
      const top = await page.evaluate(([x, y]) => {
        const e = document.elementFromPoint(x, y);
        const a = e && e.closest('a');
        return { tag: e ? e.tagName.toLowerCase() : null, href: a ? a.getAttribute('href') : null };
      }, [cx, cy]);
      await Promise.all([
        page.waitForNavigation({ waitUntil: 'load', timeout: 45000 }).catch(() => null),
        el.click({ timeout: 10000 }),
      ]);
      const landed = new URL(page.url()).pathname;
      // URL обязан смениться: щелчок, после которого адрес тот же, — это не
      // переход, даже если страница что-то показала.
      const urlChanged = landed !== pick.from.split('?')[0];
      const info = await page.evaluate(() => ({
        h1: (document.querySelector('h1') || {}).textContent || '',
        title: document.title,
        canonical: (document.querySelector('link[rel=canonical]') || {}).href || '',
        ld: document.querySelectorAll('script[type="application/ld+json"]').length,
        crumbs: !!document.querySelector('.crumbs, .zcr'),
        player: !!document.querySelector('[data-player]'),
        poster: !!document.querySelector('.tw__ps img, .zhead__ps img, .tw__ps .c__none, .zhead__ps .zt__none'),
        bodyText: document.body.innerText.trim().length,
      }));
      // Возврат браузера: посетитель обязан вернуться туда, откуда ушёл, а не
      // на главную и не в пустую историю. Проверяется настоящей кнопкой, а не
      // переходом по собранному адресу.
      let backOk = null, backTo = null;
      try {
        await page.goBack({ waitUntil: 'load', timeout: 30000 });
        backTo = new URL(page.url()).pathname + new URL(page.url()).search;
        backOk = backTo === pick.from;
      } catch (e) { backOk = false; backTo = String(e.message).slice(0, 60); }
      results.push({
        ...pick, ok: landed === pick.href && info.bodyText > 200 && backOk === true,
        url_changed: urlChanged, back_ok: backOk, back_to: backTo,
        landed, top_element: top, h1: info.h1.slice(0, 80), title: info.title.slice(0, 90),
        canonical: info.canonical, ld_blocks: info.ld, crumbs: info.crumbs,
        player: info.player, poster: info.poster, body_chars: info.bodyText,
      });
    } catch (e) {
      results.push({ ...pick, ok: false, why: String(e.message).slice(0, 120) });
    }
  }
  return results;
}

async function main() {
  const plan = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const report = { started: new Date().toISOString(), sites: {} };

  for (const site of plan.sites) {
    const dir = path.join(OUT, site.id);
    fs.mkdirSync(dir, { recursive: true });
    const ctx = await browser.newContext({ deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    const pages = [];
    for (const arche of site.archetypes) {
      const vps = arche.viewports === 'all' ? VIEWPORTS : VIEWPORTS.filter(v => v.w === 1440);
      for (const vp of vps) {
        pages.push(await measure(page, site.base + arche.path, arche.tag, vp, dir));
      }
    }
    const clicks = await clickCards(page, site.base, site.clicks || []);
    report.sites[site.id] = { base: site.base, pages, clicks };
    await ctx.close();
  }
  await browser.close();
  report.finished = new Date().toISOString();
  fs.writeFileSync(path.join(OUT, 'audit.json'), JSON.stringify(report, null, 1));

  // Сводка на экран: она и есть то, что читает человек.
  let cErr = 0, cOver = 0, cContrast = 0, cImg = 0, cClickBad = 0, cPages = 0;
  for (const [id, s] of Object.entries(report.sites)) {
    for (const p of s.pages) {
      cPages++;
      cErr += p.console_errors.length;
      cOver += p.overflow > 1 ? 1 : 0;
      cContrast += p.contrast_failures.length;
      cImg += p.broken_images.length;
    }
    cClickBad += s.clicks.filter(c => !c.ok).length;
    console.log(`${id}: страниц ${s.pages.length}, кликов ${s.clicks.length}, ` +
                `неудачных кликов ${s.clicks.filter(c => !c.ok).length}`);
  }
  console.log(`ИТОГО страниц=${cPages} console_errors=${cErr} overflow=${cOver} ` +
              `contrast=${cContrast} broken_images=${cImg} click_failures=${cClickBad}`);
  console.log(`отчёт: ${path.join(OUT, 'audit.json')}`);
  process.exit(0);
}

main().catch(e => { console.error(e); process.exit(1); });
